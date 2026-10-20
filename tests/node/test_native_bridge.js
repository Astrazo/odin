// Offline bridge preflight checks; no debugger or game is opened.
const assert = require('node:assert/strict');
const {install} = require('../../src/odin/native/abi_call_bridge');

class Eval {}
const disconnectEvents = [];
class Adapter {
    disconnectRequest(response) {
        // Reproduce the installed adapter's premature acknowledgement.
        this.sendResponse(response);
        this.api.stop();
        disconnectEvents.push('detached');
    }
    sendResponse() { disconnectEvents.push('response'); }
    shutdown() { disconnectEvents.push('shutdown'); }
}
class DebugApi {
    stop() { Native.debugStop(this.pid); }
}
let detachSucceeded = true;
const Native = {debugStop() {
    disconnectEvents.push('native-stop');
    return detachSucceeded;
}};
const Register = {EFlags: 3};
install({Eval, Adapter, Register, DebugApi, Native});

const adapter = new Adapter();
adapter.api = new DebugApi();
adapter.disconnectRequest({}, {terminateDebuggee: false});
assert.deepEqual(disconnectEvents, ['native-stop', 'detached', 'response']);
disconnectEvents.length = 0;
detachSucceeded = false;
assert.throws(() => adapter.disconnectRequest({}, {}), /detach failed/);
assert.deepEqual(disconnectEvents, ['native-stop']);
disconnectEvents.length = 0;
adapter.dbg = {api: adapter.api};
adapter.shutdown();
assert.deepEqual(disconnectEvents, []);
adapter.dbg = null;
adapter.shutdown();
assert.deepEqual(disconnectEvents, ['shutdown']);

const evaluator = new Eval();
evaluator.jit = {is64: true, isWinCall: true};
evaluator.currentThread = 42;
const reads = [];
let flags = 0x100;
let dr0 = 0;
evaluator.api = {
    readRegister(thread, register) {
        reads.push(register);
        assert.equal(thread, 42);
        // Register 4 is DR0, whose bits say nothing about single stepping.
        return {high: 0, low: register === Register.EFlags ? flags : dr0};
    },
};

assert.throws(() => evaluator.evalCall({}, []), /Single-step state is not supported/);
assert.deepEqual(reads, [Register.EFlags]);

flags = 0;
dr0 = 0x100;
reads.length = 0;
assert.throws(
    () => evaluator.evalCall({t: {_hx_index: 0}}, []),
    /Unsupported function representation/,
);
assert.deepEqual(reads, [Register.EFlags]);
console.log('Native bridge rejects the trap flag using EFLAGS before inspecting or modifying a call.');
