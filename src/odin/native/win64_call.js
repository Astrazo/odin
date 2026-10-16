// Pure instruction encoder. This module never opens a process or runs its bytes.
const ARGUMENT_REGISTERS = [1, 2, 8, 9]; // RCX, RDX, R8, R9
const SCRATCH_REGISTERS = [1, 2, 8, 9, 10, 11];
const SAVED_BYTES = 8 + 6 * 8 + 6 * 16; // RFLAGS, CPU scratch registers, XMM0..5
const TYPES = new Set(['i32', 'bool', 'f32', 'f64', 'ptr']);

function encodeArgument(type, value) {
    if (!TYPES.has(type)) throw new Error(`Unsupported argument type: ${type}`);
    const bits = Buffer.alloc(8);
    if (type === 'i32') {
        if (!Number.isInteger(value) || value < -2147483648 || value > 2147483647) {
            throw new Error('i32 argument out of range');
        }
        bits.writeInt32LE(value);
    } else if (type === 'bool') {
        if (typeof value !== 'boolean') throw new Error('Expected a boolean');
        bits[0] = value ? 1 : 0;
    } else if (type === 'f32' || type === 'f64') {
        if (!Number.isFinite(value)) throw new Error('Expected a finite float');
        if (type === 'f32') bits.writeFloatLE(value);
        else bits.writeDoubleLE(value);
        if (type === 'f32' && !Number.isFinite(bits.readFloatLE())) {
            throw new Error('Value overflows f32');
        }
    } else {
        // Pointer identity must already belong to the target; no literal boxing.
        if (typeof value !== 'bigint' || value < 0n || value > 0xffffffffffffffffn) {
            throw new Error('Expected an unsigned 64-bit pointer');
        }
        bits.writeBigUInt64LE(value);
    }
    return {type, bits};
}

function buildCallStub(arguments_, address, returnType) {
    if (arguments_.length > 16) throw new Error('At most 16 arguments are supported');
    if (!TYPES.has(returnType) && returnType !== 'void') throw new Error('Unsupported return type');
    for (const argument of arguments_) {
        if (!TYPES.has(argument.type) || !Buffer.isBuffer(argument.bits) || argument.bits.length !== 8) {
            throw new Error('Expected a supported type and eight encoded bytes');
        }
    }
    const target = encodeArgument('ptr', address);
    if (address < 0x10000n) throw new Error('Invalid function address');
    const stackArguments = Math.max(0, arguments_.length - 4);
    const outgoingBytes = 32 + stackArguments * 8;
    const paddingBytes = (16 - ((SAVED_BYTES + outgoingBytes) % 16)) % 16;
    const frameBytes = outgoingBytes + paddingBytes;
    const parts = [];
    function emit(...bytes) { parts.push(Buffer.from(bytes)); }
    function immediate(value) {
        const bytes = Buffer.alloc(4);
        bytes.writeUInt32LE(value);
        parts.push(bytes);
    }
    function adjustStack(subtract, amount) {
        emit(0x48, 0x81, subtract ? 0xec : 0xc4);
        immediate(amount);
    }
    function moveImmediate(register, bits) {
        emit(register >= 8 ? 0x49 : 0x48, 0xb8 + (register % 8));
        parts.push(bits);
    }

    // Entry RSP must be 16-byte aligned. Keep saved values outside shadow space.
    emit(0x9c); // pushfq, before any instruction changes flags
    for (const register of SCRATCH_REGISTERS) {
        if (register >= 8) emit(0x41);
        emit(0x50 + (register % 8));
    }
    for (let index = 0; index < 6; index++) {
        adjustStack(true, 16);
        emit(0xf3, 0x0f, 0x7f, 0x04 + index * 8, 0x24); // movdqu [rsp], xmmN
    }
    adjustStack(true, frameBytes);
    const locations = [];
    for (let index = 0; index < arguments_.length; index++) {
        const argument = arguments_[index];
        if (index >= 4) {
            const offset = 32 + (index - 4) * 8;
            moveImmediate(0, argument.bits); // use RAX only as a temporary
            emit(0x48, 0x89, 0x84, 0x24); // mov [rsp + displacement], rax
            immediate(offset);
            locations.push({index, type: argument.type, stackOffsetBeforeCall: offset});
        } else if (argument.type === 'f32' || argument.type === 'f64') {
            moveImmediate(0, argument.bits);
            emit(0x66);
            if (argument.type === 'f64') emit(0x48);
            emit(0x0f, 0x6e, 0xc0 + index * 8); // movd/movq xmmN, eax/rax
            locations.push({index, type: argument.type, register: `XMM${index}`});
        } else {
            moveImmediate(ARGUMENT_REGISTERS[index], argument.bits);
            locations.push({index, type: argument.type, register: ['RCX', 'RDX', 'R8', 'R9'][index]});
        }
    }
    moveImmediate(0, target.bits);
    emit(0xff, 0xd0); // call rax; callee sees return address at [rsp]
    if (returnType === 'f64') emit(0x66, 0x48, 0x0f, 0x7e, 0xc0);
    if (returnType === 'f32') emit(0x66, 0x0f, 0x7e, 0xc0); // return bits -> RAX
    adjustStack(false, frameBytes);
    for (let index = 5; index >= 0; index--) {
        emit(0xf3, 0x0f, 0x6f, 0x04 + index * 8, 0x24); // restore all 128 bits
        adjustStack(false, 16);
    }
    for (const register of [...SCRATCH_REGISTERS].reverse()) {
        if (register >= 8) emit(0x41);
        emit(0x58 + (register % 8));
    }
    emit(0x9d, 0xcc); // popfq; int3. Original RAX/RIP/RSP restored by dispatcher.
    return {code: Buffer.concat(parts), locations, frameBytes, paddingBytes, savedBytes: SAVED_BYTES};
}

module.exports = {encodeArgument, buildCallStub};
