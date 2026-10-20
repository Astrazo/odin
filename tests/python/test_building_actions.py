"""Offline tests for one building request."""

import json
import unittest

from odin.actions.buildings import build_building


class FakeRuntime:
    def __init__(self, available=("House",)):
        self.available = available
        self.calls = []

    def array_length(self, expression):
        if expression == "this.state.me.zones":
            return 1
        if "getAvailableBuildings" in expression:
            return len(self.available)
        raise AssertionError(expression)

    def evaluate(self, expression):
        if expression == "this.state.me.zones[0].id":
            return "92"
        for index, identifier in enumerate(self.available):
            if expression.endswith(f"[{index}].id"):
                return json.dumps(identifier)
        raise AssertionError(expression)

    def call_native(self, expression):
        self.calls.append(expression)
        if expression == "this.state.me.zones[0].getOwner() == this.state.me":
            return "true"
        if expression.startswith("Tools.buildInZone("):
            return "<ent.Building>"
        raise AssertionError(expression)


CATALOGUE = {
    "building_ids": ["house", "scout_camp"],
    "family_by_engine_id": {"House": "house", "ScoutCamp": "scout_camp"},
}


class BuildingActionTests(unittest.TestCase):
    def test_uses_current_available_definition_for_one_request(self):
        runtime = FakeRuntime()

        result = build_building(runtime, 92, "house", CATALOGUE)

        self.assertEqual(result, {
            "zone_id": 92,
            "building_id": "house",
            "engine_id": "House",
            "requested": True,
        })
        self.assertEqual(runtime.calls[-1], (
            "Tools.buildInZone(this.state.me, "
            "this.state.me.zones[0].getAvailableBuildings("
            "this.state.me, null, null, null, null)[0], "
            "this.state.me.zones[0], null)"
        ))

    def test_rejects_a_family_that_is_not_currently_available(self):
        runtime = FakeRuntime()

        with self.assertRaisesRegex(RuntimeError, "not currently buildable"):
            build_building(runtime, 92, "scout_camp", CATALOGUE)

        self.assertEqual(runtime.calls, [
            "this.state.me.zones[0].getOwner() == this.state.me",
        ])

    def test_accepts_hyphenated_building_family_names(self):
        runtime = FakeRuntime(available=("ScoutCamp",))

        result = build_building(runtime, 92, "scout-camp", CATALOGUE)

        self.assertEqual(result["building_id"], "scout_camp")
