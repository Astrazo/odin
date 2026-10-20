"""Offline tests for the fixed friendly/enemy zone-unit tensor."""

import unittest

from odin.observations.units import observe_units


class FakeRuntime:
    def __init__(self):
        self.lengths = {"zone.units": 6}
        self.native_values = {
            "zone.units[0].get_isDead()": "false",
            "zone.units[0].owner == this.state.me": "true",
            "zone.units[0].get_canScout()": "false",
            "zone.units[1].get_isDead()": "false",
            "zone.units[1].owner == this.state.me": "false",
            "zone.units[1].owner == null": "false",
            "zone.units[1].owner.get_team() == this.state.me.get_team()": "false",
            "zone.units[2].get_isDead()": "false",
            "zone.units[2].owner == this.state.me": "false",
            "zone.units[2].owner == null": "true",
            "zone.units[3].get_isDead()": "true",
            "zone.units[4].get_isDead()": "false",
            "zone.units[4].owner == this.state.me": "true",
            "zone.units[4].get_canScout()": "false",
            "zone.units[5].get_isDead()": "false",
            "zone.units[5].owner == this.state.me": "true",
            "zone.units[5].get_canScout()": "true",
        }
        self.values = {
            "zone.units[0].kind": '"Woodcutter"',
            "zone.units[1].kind": '"Scout"',
            "zone.units[2].kind": '"Wolf"',
            "zone.units[4].kind": '"NewUnit"',
            "zone.units[5].kind": '"Scout"',
            "zone.units[5].__uid": "1249",
            "zone.units[0].__uid": "101",
            "zone.units[4].__uid": "102",
        }

    def array_length(self, expression):
        return self.lengths[expression]

    def call_native(self, expression):
        return self.native_values[expression]

    def evaluate(self, expression):
        return self.values[expression]


class UnitObservationTests(unittest.TestCase):
    def test_counts_mapped_friendly_and_enemy_units(self):
        catalogue = {
            "unit_ids": ["scout", "woodcutter"],
            "family_by_engine_id": {
                "Scout": "scout",
                "Woodcutter": "woodcutter",
            },
            "schema_sha256": "abc",
            "neutral_unit_ids": ["wolf"],
            "neutral_family_by_engine_id": {"Wolf": "wolf"},
        }
        graph = {
            "zone_ids": [7],
            "nodes": {7: {"expression": "zone"}},
        }

        report = observe_units(FakeRuntime(), catalogue, graph)

        self.assertEqual(report["feature_names"], [
            "friendly_scout",
            "friendly_woodcutter",
            "enemy_scout",
            "enemy_woodcutter",
            "neutral_wolf",
        ])
        self.assertEqual(report["x"], [[1, 1, 1, 0, 1]])
        self.assertEqual(report["unit_jobs"], {
            "101": {"job": "woodcutter", "engine_id": "Woodcutter", "zone_id": 7},
            "102": {"job": None, "engine_id": "NewUnit", "zone_id": 7},
            "1249": {"job": "scout", "engine_id": "Scout", "zone_id": 7},
        })
        self.assertEqual(report["scout_unit_mask"], [{
            "unit_id": 1249,
            "zone_id": 7,
        }])
        self.assertEqual(report["unmapped_units"], [
            {"zone_id": 7, "side": "friendly", "engine_id": "NewUnit"},
        ])

    def test_allied_units_are_counted_but_not_selectable_by_id(self):
        runtime = FakeRuntime()
        runtime.lengths["zone.units"] = 2
        runtime.native_values["zone.units[1].owner.get_team() == this.state.me.get_team()"] = "true"
        catalogue = {
            "unit_ids": ["scout", "woodcutter"],
            "family_by_engine_id": {"Scout": "scout", "Woodcutter": "woodcutter"},
            "neutral_unit_ids": [],
            "neutral_family_by_engine_id": {},
            "schema_sha256": "abc",
        }
        report = observe_units(runtime, catalogue, {
            "zone_ids": [7], "nodes": {7: {"expression": "zone"}},
        })
        self.assertEqual(report["x"], [[1, 1, 0, 0]])
        self.assertEqual(list(report["unit_jobs"]), ["101"])
