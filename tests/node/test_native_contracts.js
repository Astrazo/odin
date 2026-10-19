'use strict';
const assert = require('node:assert/strict');
const {contractsFor} = require('../../src/odin/native/abi_call_bridge');

const contracts = contractsFor();
assert.deepEqual([...contracts.keys()], [
    7586, 6621, 7570, 7571, 3178, 4668, 4803, 3192, 3347, 3370,
    5767, 5785, 5678, 3368, 7563, 13003, 13480, 13523, 13560,
    13449, 13505, 13471, 13474,
]);
assert.deepEqual(contracts.get(13003), {
    name: 'set_pause',
    args: ['ptr', 'bool', 'ptr'],
    kinds: [11, 7, 11],
    nullOnly: [],
    result: 'void',
});
assert.deepEqual(contracts.get(13480), {
    name: 'get_resource',
    args: ['ptr', 'ptr', 'ptr'],
    kinds: [11, 11, 14],
    nullOnly: [2],
    result: 'f64',
});

console.log('Native contracts expose only the reviewed observation and pause functions.');
