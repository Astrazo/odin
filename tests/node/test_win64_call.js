// Offline byte interpreter: no process access, addon import or CPU execution.
const assert = require('node:assert/strict');
const {encodeArgument, buildCallStub} = require('../../src/odin/native/win64_call');

function verifyStub(arguments_, returnType, returnValue) {
    const target = 0x12345678n;
    const stub = buildCallStub(arguments_, target, returnType);
    const code = stub.code;
    const cpu = Array.from({length: 16}, (_, index) => BigInt(0x100 + index));
    const initialCpu = [...cpu];
    const xmm = Array.from({length: 6}, (_, index) => Buffer.alloc(16, 0xa0 + index));
    const initialXmm = xmm.map(value => Buffer.from(value));
    const memory = new Map();
    let rsp = 0x100000;
    let flags = 0x202n;
    let pc = 0;
    let calls = 0;
    function store(address, bytes) {
        for (let index = 0; index < bytes.length; index++) memory.set(address + index, bytes[index]);
    }
    function load(address, length) {
        return Buffer.from(Array.from({length}, (_, index) => {
            assert(memory.has(address + index), `Uninitialized read at ${address + index}`);
            return memory.get(address + index);
        }));
    }
    function bits(value) {
        const bytes = Buffer.alloc(8);
        bytes.writeBigUInt64LE(value);
        return bytes;
    }
    function push(value) { rsp -= 8; store(rsp, bits(value)); }
    function pop() { const value = load(rsp, 8).readBigUInt64LE(); rsp += 8; return value; }

    while (pc < code.length) {
        const op = code[pc];
        if (op === 0x9c) { push(flags); pc++; }
        else if (op === 0x9d) { flags = pop(); pc++; }
        else if (op === 0x41 || (op >= 0x50 && op <= 0x5f)) {
            const high = op === 0x41 ? 8 : 0;
            if (high) pc++;
            const instruction = code[pc++];
            if (instruction >= 0x50 && instruction <= 0x57) push(cpu[high + instruction - 0x50]);
            else if (instruction >= 0x58 && instruction <= 0x5f) cpu[high + instruction - 0x58] = pop();
            else assert.fail('Invalid push/pop');
        } else if ((op === 0x48 || op === 0x49) && code[pc + 1] >= 0xb8 && code[pc + 1] <= 0xbf) {
            const register = (op === 0x49 ? 8 : 0) + code[pc + 1] - 0xb8;
            cpu[register] = code.readBigUInt64LE(pc + 2);
            pc += 10;
        } else if (op === 0x48 && code[pc + 1] === 0x81) {
            const amount = code.readUInt32LE(pc + 3);
            if (code[pc + 2] === 0xec) rsp -= amount;
            else if (code[pc + 2] === 0xc4) rsp += amount;
            else assert.fail('Invalid stack adjustment');
            flags = 0n;
            pc += 7;
        } else if (op === 0xf3 && code[pc + 1] === 0x0f) {
            const index = (code[pc + 3] - 4) / 8;
            assert.equal(code[pc + 4], 0x24);
            if (code[pc + 2] === 0x7f) store(rsp, xmm[index]);
            else if (code[pc + 2] === 0x6f) xmm[index] = load(rsp, 16);
            else assert.fail('Invalid XMM save/restore');
            pc += 5;
        } else if (op === 0x48 && code[pc + 1] === 0x89) {
            assert.equal(code[pc + 2], 0x84);
            assert.equal(code[pc + 3], 0x24);
            store(rsp + code.readUInt32LE(pc + 4), bits(cpu[0]));
            pc += 8;
        } else if (op === 0x66) {
            const width = code[pc + 1] === 0x48 ? 8 : 4;
            const prefix = width === 8 ? 2 : 1;
            assert.equal(code[pc + prefix], 0x0f);
            const instruction = code[pc + prefix + 1];
            const index = (code[pc + prefix + 2] - 0xc0) / 8;
            if (instruction === 0x6e) {
                xmm[index].fill(0);
                bits(cpu[0]).copy(xmm[index], 0, 0, width);
            } else if (instruction === 0x7e) {
                assert.equal(index, 0);
                cpu[0] = width === 8 ? xmm[0].readBigUInt64LE() : BigInt(xmm[0].readUInt32LE());
            } else assert.fail('Invalid float transfer');
            pc += prefix + 3;
        } else if (op === 0xff && code[pc + 1] === 0xd0) {
            calls++;
            assert.equal(cpu[0], target);
            assert.equal(rsp % 16, 0, 'Caller RSP must be aligned');
            const calleeRsp = rsp - 8; // CALL pushes a return address.
            for (let index = 0; index < arguments_.length; index++) {
                const argument = arguments_[index];
                let actual;
                if (index >= 4) actual = load(calleeRsp + 40 + (index - 4) * 8, 8);
                else if (argument.type.startsWith('f')) actual = xmm[index].subarray(0, 8);
                else actual = bits(cpu[[1, 2, 8, 9][index]]);
                assert.deepEqual(actual, argument.bits, `Argument ${index + 1} differs`);
            }
            // A conforming callee may write the shadow area and clobber volatile registers.
            store(rsp, Buffer.alloc(32, 0xee));
            for (const register of [1, 2, 8, 9, 10, 11]) cpu[register] = 0xbadn;
            for (const value of xmm) value.fill(0xdd);
            flags = 0n;
            if (returnType !== 'void') {
                const result = encodeArgument(returnType, returnValue).bits;
                if (returnType.startsWith('f')) result.copy(xmm[0], 0);
                else cpu[0] = result.readBigUInt64LE();
            }
            pc += 2;
        } else if (op === 0xcc) {
            assert.equal(pc, code.length - 1);
            pc++;
        } else assert.fail(`Unknown opcode ${op.toString(16)} at ${pc}`);
    }
    assert.equal(calls, 1);
    assert.equal(rsp, 0x100000, 'Stub stack must balance');
    assert.equal(flags, 0x202n);
    for (const register of [1, 2, 8, 9, 10, 11]) assert.equal(cpu[register], initialCpu[register]);
    assert.deepEqual(xmm, initialXmm, 'Restore all 128 bits of each saved XMM register');
    if (returnType !== 'void') assert.equal(cpu[0], encodeArgument(returnType, returnValue).bits.readBigUInt64LE());
}

const types = ['i32', 'f64', 'ptr', 'bool', 'f32', 'i32'];
const values = [-123, 1.25, 0x123456789abcdef0n, true, -2.5, 987];
for (let count = 0; count <= 16; count++) {
    const arguments_ = Array.from({length: count}, (_, index) => encodeArgument(types[index % 6], values[index % 6]));
    for (const [type, value] of [['void', null], ['i32', -37], ['bool', false], ['f32', 3.25], ['f64', -8.125], ['ptr', 0x123456780n]]) {
        verifyStub(arguments_, type, value);
    }
}
assert.throws(() => encodeArgument('i32', 2147483648));
assert.throws(() => encodeArgument('bool', 1));
assert.throws(() => encodeArgument('f64', NaN));
assert.throws(() => encodeArgument('f32', 1e100));
assert.throws(() => encodeArgument('ptr', -1n));
assert.throws(() => buildCallStub(Array(17).fill(encodeArgument('i32', 1)), 0x12345678n, 'i32'));
console.log('Offline byte-interpreter checks passed: 0–16 mixed arguments, shadow space, stack balance, register restoration and returns.');
