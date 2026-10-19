"""Offline tests for the fixed friendly/enemy zone-unit tensor."""

import unittest

from odin.observations.units import observe_units


class FakeRuntime:
    def __init__(self):
        self.lengths = {"zone.units": 5}
        self.native_values = {
            "zone.units[0].get_isDead()": "false",
            "zone.units[0].owner == this.state.me": "true",
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
        }
        self.values = {
            "zone.units[0].kind": '"Woodcutter"',
            "zone.units[1].kind": '"Scout"',
            "zone.units[2].kind": '"Wolf"',
            "zone.units[4].kind": '"NewUnit"',
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
        self.assertEqual(report["x"], [[0, 1, 1, 0, 1]])
        self.assertEqual(report["unmapped_units"], [
            {"zone_id": 7, "side": "friendly", "engine_id": "NewUnit"},
        ])
