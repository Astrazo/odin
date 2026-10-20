// Load the reviewed HashLink adapter unchanged and replace only native calls.
const crypto = require('crypto');
const fs = require('fs');
const Module = require('module');
const path = require('path');

const adapterPath = path.resolve(process.argv[2]);

const build = require('../data/supported_build.json');
const adapterBytes = fs.readFileSync(adapterPath);
const adapterHash = crypto.createHash('sha256').update(adapterBytes).digest('hex');
if (adapterHash !== build.hashlink_adapter_sha256) {
    throw new Error('HashLink adapter build changed; review the ABI integration.');
}

const source = adapterBytes.toString('utf8');
const marker = 'HLAdapter.main();';
if (source.split(marker).length !== 2) {
    throw new Error('HashLink adapter entry point is not unique.');
}

const bridgePath = path.join(__dirname, 'abi_call_bridge.js');
const injection = `require(${JSON.stringify(bridgePath)}).install({` +
    'Eval: hld_Eval, Adapter: HLAdapter, Buffer: hld_Buffer, ' +
    'Pointer: hld_Pointer, Register: hld_Register, Value: hld_Value, Repr: hld_ValueRepr, ' +
    'DebugApi: hld_NodeDebugApiNative, Native: hld_Native' +
    '});\n';

const adapter = new Module(adapterPath, module);
adapter.filename = adapterPath;
adapter.paths = Module._nodeModulePaths(path.dirname(adapterPath));
adapter._compile(source.replace(marker, injection + marker), adapterPath);
