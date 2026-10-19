// Execute only the native functions declared for this Northgard build.
const build = require('../data/supported_build.json');
const {encodeArgument, buildCallStub} = require('./win64_call');
const {readTarget} = require('./abi_memory');

function contractsFor() {
    const contracts = new Map();
    for (const [name, declared] of Object.entries(build.native_functions)) {
        contracts.set(declared.function_index, {
            name,
            args: declared.arguments,
            kinds: declared.kinds,
            nullOnly: declared.null_only || [],
            result: declared.result,
        });
    }
    return contracts;
}

function install(classes) {
    const {Eval, Adapter, Buffer: DebugBuffer, Pointer, Register} = classes;
    const contracts = contractsFor();
    let recoveryUnconfirmed = false;

    const originalDisconnect = Adapter.prototype.disconnectRequest;
    Adapter.prototype.disconnectRequest = function(response, args) {
        if (recoveryUnconfirmed) {
            this.sendErrorResponse(
                response,
                3000,
                'RECOVERY NOT CONFIRMED: automatic resume/detach blocked. Inspect the stopped process.',
            );
            return;
        }
        return originalDisconnect.call(this, response, args);
    };

    function number(pointer) {
        if (pointer == null) throw new Error('Missing debugger pointer/register');
        return (BigInt(pointer.high >>> 0) << 32n) | BigInt(pointer.low >>> 0);
    }

    function pointer(value) {
        return Pointer.make(
            Number(value & 0xffffffffn) | 0,
            Number((value >> 32n) & 0xffffffffn) | 0,
        );
    }

    Eval.prototype.evalCall = function(vfun, values) {
        if (recoveryUnconfirmed) {
            throw new Error('RECOVERY NOT CONFIRMED: further calls blocked.');
        }
        if (!this.jit.is64 || !this.jit.isWinCall) {
            throw new Error('Native calls require Windows x64 HashLink.');
        }
        if (number(this.api.readRegister(this.currentThread, 4)) & 0x100n) {
            throw new Error('Single-step state is not supported.');
        }
        if (vfun.t._hx_index !== 10 || ![9, 10, 11].includes(vfun.v._hx_index)) {
            throw new Error('Unsupported function representation.');
        }

        const address = vfun.v._hx_index === 11
            ? vfun.v.p
            : this.readPointer(pointer(number(vfun.v.p) + 8n));
        const functionIndex = this.jit.functionFromAddr(address);
        const definition = this.module.code.functions[functionIndex];
        const contract = definition && contracts.get(definition.findex);
        if (!contract) {
            throw new Error('Function is outside this operation\'s native allowlist.');
        }

        const typeNames = new Map([
            [0, 'void'], [3, 'i32'], [5, 'f32'], [6, 'f64'],
            [7, 'bool'], [11, 'ptr'], [14, 'ptr'], [15, 'ptr'], [19, 'ptr'],
        ]);
        const signature = vfun.t.fun;
        if (
            values.length !== contract.args.length ||
            signature.args.length !== values.length ||
            typeNames.get(signature.ret._hx_index) !== contract.result
        ) {
            throw new Error(`${contract.name} signature differs from the inspected contract.`);
        }

        const arguments_ = values.map((value, index) => {
            const type = typeNames.get(value.t._hx_index);
            if (type !== contract.args[index] || typeNames.get(signature.args[index]._hx_index) !== type) {
                throw new Error(`${contract.name} argument type differs from its inspected contract.`);
            }
            if (signature.args[index]._hx_index !== contract.kinds[index]) {
                throw new Error(`${contract.name} argument kind differs from its inspected contract.`);
            }

            let actual;
            if (type === 'ptr') actual = number(this.getPtr(value));
            else if (type === 'i32' && value.v._hx_index === 3) actual = value.v.i;
            else if (type === 'bool' && value.v._hx_index === 6) actual = value.v.b;
            else if (type === 'f64' && value.v._hx_index === 5) actual = value.v.v;
            else throw new Error('Unsupported value representation.');

            if (contract.nullOnly.includes(index) && actual !== 0n) {
                throw new Error(`${contract.name} permits only null at argument ${index + 1}.`);
            }
            return encodeArgument(type, actual);
        });

        const stub = buildCallStub(arguments_, number(address), contract.result);
        const instructionPointer = number(this.api.readRegister(this.currentThread, 2));
        const stackPointer = number(this.api.readRegister(this.currentThread, 0));
        const frameFunction = this.module.code.functions[this.funIndex];
        if (!frameFunction || frameFunction.findex !== build.update_frame.function_index) {
            throw new Error('Native calls require the inspected Game.onUpdate frame.');
        }

        const functionEnd = number(this.jit.getCodePos(this.funIndex, frameFunction.debug.length >> 1));
        const functionStart = number(this.jit.getFunctionPos(this.funIndex));
        if (
            instructionPointer < functionStart ||
            instructionPointer + BigInt(stub.code.length) > functionEnd
        ) {
            throw new Error('Call stub exceeds the current function code.');
        }

        const entryStack = (stackPointer - 256n) & ~15n;
        const scratchStart = entryStack - 1024n;
        const thread = this.currentThread;
        const savedCpu = Array.from(
            {length: 16},
            (_, index) => number(this.api.readRegister(thread, Register.makeCpu(index))),
        );

        function read(api, address, length) {
            return readTarget(api, address, length, DebugBuffer, pointer);
        }

        function write(api, address, bytes) {
            const buffer = new DebugBuffer(bytes.length);
            buffer.buf = Buffer.from(bytes);
            if (
                !api.write(pointer(address), buffer, bytes.length) ||
                !read(api, address, bytes.length).equals(bytes)
            ) {
                throw new Error('Target memory write was not verified.');
            }
        }

        const originalCode = read(this.api, instructionPointer, stub.code.length);
        const originalScratch = read(this.api, scratchStart, 1024);
        let modified = false;
        let completed = false;
        process.stderr.write(JSON.stringify({
            native_call: contract.name,
            function_index: definition.findex,
            argument_locations: stub.locations,
        }) + '\n');

        try {
            modified = true;
            write(this.api, instructionPointer, stub.code);
            this.api.flush(pointer(instructionPointer), stub.code.length);
            if (
                !this.api.writeRegister(thread, 0, pointer(entryStack)) ||
                number(this.api.readRegister(thread, 0)) !== entryStack
            ) {
                throw new Error('Stack setup was not verified.');
            }

            this.resumeDebug();
            if (
                this.currentThread !== thread ||
                number(this.api.readRegister(thread, 2)) !== instructionPointer + BigInt(stub.code.length) ||
                number(this.api.readRegister(thread, 0)) !== entryStack
            ) {
                throw new Error('Native call did not return to the expected trap with a balanced stack.');
            }
            completed = true;
            const result = this.api.readRegister(thread, Register.makeCpu(0));

            for (let index = 0; index < 16; index++) {
                if (index === 0 || index === 4) continue;
                if (number(this.api.readRegister(thread, Register.makeCpu(index))) !== savedCpu[index]) {
                    throw new Error(`CPU register ${index} was not preserved.`);
                }
            }

            write(this.api, instructionPointer, originalCode);
            this.api.flush(pointer(instructionPointer), originalCode.length);
            write(this.api, scratchStart, originalScratch);
            for (const [register, value] of [
                [Register.makeCpu(0), savedCpu[0]],
                [2, instructionPointer],
                [0, stackPointer],
            ]) {
                if (
                    !this.api.writeRegister(thread, register, pointer(value)) ||
                    number(this.api.readRegister(thread, register)) !== value
                ) {
                    throw new Error('Control/register restoration was not verified.');
                }
            }
            process.stderr.write(JSON.stringify({native_restored: contract.name}) + '\n');
            return this.convertVal(result, signature.ret);
        } catch (error) {
            if (modified) {
                recoveryUnconfirmed = true;
                try {
                    write(this.api, instructionPointer, originalCode);
                    this.api.flush(pointer(instructionPointer), originalCode.length);
                } catch (restoreError) {
                    process.stderr.write(`Code restoration error: ${restoreError}\n`);
                }
                throw new Error(
                    `RECOVERY NOT CONFIRMED: ${error}; normal trap reached=${completed}`,
                );
            }
            throw error;
        }
    };
}

module.exports = {contractsFor, install};
