"""Offline tests for sending a scout to a masked neighbouring zone."""

import unittest

from odin.actions.scouting import scout_zone


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def array_length(self, expression):
        return {
            "this.state.me.units": 1,
            "this.state.me.zones": 1,
            "this.state.me.zones[0].next": 1,
        }[expression]

    def evaluate(self, expression):
        return {
            "this.state.me.units[0].__uid": "1249",
            "this.state.me.zones[0].id": "10",
            "this.state.me.zones[0].next[0].id": "40",
        }[expression]

    def call_native(self, expression):
        self.calls.append(expression)
        if expression in {
            "this.state.me.units[0].owner == this.state.me",
            "this.state.me.units[0].get_canScout()",
            "this.state.me.hasDiscovered(this.state.me.zones[0])",
        }:
            return "true"
        if expression == "this.state.me.hasDiscovered(this.state.me.zones[0].next[0])":
            return "false"
        if expression == "this.state.me.zones[0].next[0].canBeScouted(this.state.me, null)":
            return "true"
        if expression == "this.state.me.units[0].moveToZone(this.state.me.zones[0].next[0], false, null, null)":
            return "null"
        raise AssertionError(expression)


class ScoutingTests(unittest.TestCase):
    def test_sends_an_eligible_scout_to_a_masked_target(self):
        runtime = FakeRuntime()

        result = scout_zone(runtime, 1249, 40)

        self.assertEqual(result, {"unit_id": 1249, "zone_id": 40, "scouting": True})
        self.assertEqual(runtime.calls[-1], (
            "this.state.me.units[0].moveToZone("
            "this.state.me.zones[0].next[0], false, null, null)"
        ))

    def test_missing_target_sends_no_move_order(self):
        runtime = FakeRuntime()

        with self.assertRaisesRegex(ValueError, "not a scoutable"):
            scout_zone(runtime, 1249, 99)

        self.assertFalse(any(".moveToZone(" in call for call in runtime.calls))
