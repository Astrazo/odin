'use strict';
const assert = require('node:assert/strict');
const {contractsFor} = require('../../src/odin/native/abi_call_bridge');

const contracts = contractsFor();
assert.deepEqual([...contracts.keys()], [
    7586, 6621, 7570, 7571, 3178, 4668, 4803, 4248, 3206, 3192,
    3334, 26048, 11737, 5216, 5804, 3414, 14622, 14618, 14688, 4240, 4415, 3347, 3370, 3377,
    3378, 5767, 5785, 5678, 3368, 7563, 13003, 13480, 13523, 13560,
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
assert.deepEqual(contracts.get(5804), {
    name: 'building_can_assign_to',
    args: ['ptr', 'ptr', 'ptr', 'ptr', 'ptr', 'ptr'],
    kinds: [11, 11, 19, 19, 19, 19],
    nullOnly: [2, 3, 4, 5],
    result: 'bool',
});
assert.equal(contracts.has(12262), false);
assert.deepEqual(contracts.get(11737), {
    name: 'script_assign',
    args: ['ptr', 'ptr', 'ptr'],
    kinds: [11, 11, 11],
    nullOnly: [],
    result: 'bool',
});
assert.deepEqual(contracts.get(5216), {
    name: 'set_skip_ai_order',
    args: ['ptr', 'bool'],
    kinds: [11, 7],
    nullOnly: [],
    result: 'bool',
});
assert.equal(contracts.has(11674), false); // ScriptApi.colonize is a debug takeover.
assert.equal(contracts.has(19499), false);
assert.deepEqual(contracts.get(14622), {
    name: 'colonisation_reason', args: ['ptr', 'ptr', 'ptr'],
    kinds: [11, 11, 18], nullOnly: [], result: 'ptr',
});
assert.deepEqual(contracts.get(14618), {
    name: 'colonisation_cost', args: ['ptr', 'ptr', 'ptr', 'ptr', 'ptr', 'ptr'],
    kinds: [11, 11, 11, 14, 14, 19], nullOnly: [2, 3, 4, 5], result: 'ptr',
});
assert.deepEqual(contracts.get(14688), {
    name: 'start_colonisation', args: ['ptr', 'ptr', 'ptr'],
    kinds: [11, 11, 10], nullOnly: [2], result: 'void',
});

console.log('Native contracts expose only reviewed observation and action functions.');
