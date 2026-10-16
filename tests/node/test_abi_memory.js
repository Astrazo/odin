// Offline transport mocks only; no adapter or process is opened.
const assert = require('node:assert/strict');
const {readTarget} = require('../../src/odin/native/abi_memory');
class DebugBuffer {
    constructor(length) { this.buf = Buffer.alloc(length); }
}
function read(requested, returned, success = true) {
    const api = {read(address, buffer, length) {
        assert.equal(address, 0x12345n);
        assert.equal(length, requested);
        buffer.buf = Buffer.alloc(returned, 0x7b);
        return success;
    }};
    return readTarget(api, 0x12345n, requested, DebugBuffer, value => value);
}
assert.equal(read(203, 204).length, 203);
assert.equal(read(203, 203).length, 203);
assert.equal(read(1024, 1024).length, 1024);
assert.throws(() => read(203, 202), /requested 203 bytes, received 202/);
assert.throws(() => read(203, 205));
assert.throws(() => read(1024, 1025));
assert.throws(() => read(203, 204, false));
console.log('ABI memory transport tests passed: exact reads and one odd-length padding byte accepted; partial/error reads rejected.');
