'use strict';
const assert = require('node:assert/strict');
const {contractsFor} = require('../../src/odin/native/abi_call_bridge');

const readContracts = contractsFor({allowPause: false});
assert.deepEqual([...readContracts.keys()], [7586]);
assert.equal(readContracts.get(7586).name, 'is_paused');

const actionContracts = contractsFor({allowPause: true});
assert.deepEqual([...actionContracts.keys()], [7586, 7563, 13003]);
assert.deepEqual(actionContracts.get(13003), {
    name: 'set_pause',
    args: ['ptr', 'bool', 'ptr'],
    kinds: [11, 7, 11],
    nullOnly: [],
    result: 'void',
});

console.log('Native operation profiles expose only pause read or bounded pause action contracts.');
