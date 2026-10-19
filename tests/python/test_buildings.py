"""Offline tests for building observations and action masks."""

import json
import unittest

from odin.observations.buildings import load_building_schema, observe_buildings


class FakeRuntime:
    def __init__(self):
        self.lengths = {
            "zone_10.buildings": 2,
            "zone_20.buildings": 1,
            (
                "zone_10.getAvailableBuildings("
                "this.state.me, null, null, null, null)"
            ): 1,
        }
        self.values = {
            "zone_10.buildings[0].baseKind": json.dumps("House"),
            (
                "zone_10.getAvailableBuildings("
                "this.state.me, null, null, null, null)[0].id"
            ): json.dumps("House"),
        }
        self.native_values = {
            "zone_10.buildings[0].get_id()": json.dumps("House"),
            "zone_10.buildings[0].get_realKind()": json.dumps("House"),
            "zone_10.buildings[0].isPlayerBuilt()": "true",
            "zone_10.buildings[1].get_id()": json.dumps("Construction"),
            "zone_10.buildings[1].get_realKind()": json.dumps("GuardTower"),
            "zone_20.buildings[0].get_id()": json.dumps("WolfCamp"),
            "zone_20.buildings[0].get_realKind()": json.dumps("WolfCamp"),
            "zone_20.buildings[0].isPlayerBuilt()": "false",
        }
        self.values["zone_20.buildings[0].baseKind"] = json.dumps("WolfCamp")

    def array_length(self, expression):
        return self.lengths[expression]

    def evaluate(self, expression):
        return self.values[expression]

    def call_native(self, expression):
        return self.native_values[expression]


class BuildingTests(unittest.TestCase):
    def test_uses_authored_families_and_masks_actions_by_owned_zone(self):
        runtime = FakeRuntime()
        catalogue = {
            "building_ids": ["house", "tower"],
            "family_by_engine_id": {"House": "house", "GuardTower": "tower"},
            "schema_sha256": "test",
        }
        graph = {
            "zone_ids": [10, 20],
            "nodes": {
                10: {"expression": "zone_10", "owner": {"owned": True}},
                20: {"expression": "zone_20", "owner": {"owned": False}},
            },
        }

        report = observe_buildings(runtime, catalogue, graph)

        self.assertEqual(
            report["building_ids"],
            ["house", "tower"],
        )
        self.assertEqual(report["zone_ids"], [10, 20])
        self.assertEqual(report["feature_names"], [
            "building_house",
            "building_tower",
            "construction_house",
            "construction_tower",
        ])
        self.assertEqual(report["x"], [[1, 0, 0, 1], [0, 0, 0, 0]])
        self.assertEqual(
            report["build_action_mask"],
            [[1.0, 0.0], [0.0, 0.0]],
        )

    def test_schema_maps_both_tower_engine_ids_to_one_family(self):
        schema = load_building_schema()

        self.assertEqual(schema["family_by_engine_id"]["GuardTower"], "tower")
        self.assertEqual(schema["family_by_engine_id"]["WatchTower"], "tower")


if __name__ == "__main__":
    unittest.main()
