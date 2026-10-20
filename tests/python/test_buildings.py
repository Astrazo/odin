"""Offline tests for building observations and action masks."""

import json
import unittest

from odin.observations.buildings import load_building_schema, observe_buildings


class FakeRuntime:
    def __init__(self):
        self.lengths = {
            "zone_10.buildings": 3,
            "zone_20.buildings": 1,
            "this.state.me.units": 0,
            (
                "zone_10.getAvailableBuildings("
                "this.state.me, null, null, null, null)"
            ): 1,
        }
        self.values = {
            "zone_10.buildings[1].__uid": "500",
            "zone_10.buildings[0].baseKind": json.dumps("House"),
            "zone_10.buildings[2].baseKind": json.dumps("UnknownWorkshop"),
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
            "zone_10.buildings[2].get_id()": json.dumps("UnknownWorkshop"),
            "zone_10.buildings[2].get_realKind()": json.dumps("UnknownWorkshop"),
            "zone_10.buildings[2].isPlayerBuilt()": "true",
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
    def test_incoming_worker_counts_as_assigned_and_completion_drops_old_site_id(self):
        runtime = FakeRuntime()
        runtime.lengths["this.state.me.units"] = 3
        runtime.lengths["zone_10.buildings"] = 4
        runtime.values.update({
            "zone_10.buildings[3].__uid": "501",
            "this.state.me.units[0].owner == this.state.me": "true",
            "this.state.me.units[0].assignTo == null": "false",
            "this.state.me.units[0].assignTo.__uid": "500",
            "this.state.me.units[0].__uid": "101",
            "this.state.me.units[1].owner == this.state.me": "true",
            "this.state.me.units[2].owner == this.state.me": "false",
        })
        runtime.native_values.update({
            "zone_10.buildings[3].get_id()": json.dumps("Construction"),
            "zone_10.buildings[3].get_realKind()": json.dumps("GuardTower"),
            "this.state.me.units[0].get_isDead()": "false",
            "this.state.me.units[1].get_isDead()": "true",
        })
        # There is intentionally no worker zone value: assignments in another
        # zone still staff the site, while dead and allied units are excluded.
        catalogue = load_building_schema()
        graph = {
            "zone_ids": [10],
            "nodes": {10: {"expression": "zone_10", "owner": {"owned": True}}},
        }
        report = observe_buildings(runtime, catalogue, graph)
        values = dict(zip(report["feature_names"], report["x"][0], strict=True))
        self.assertEqual(values["construction_tower"], 2)
        self.assertEqual(values["unassigned_construction_tower"], 1)
        self.assertEqual(report["construction_sites"][0]["assigned_unit_ids"], [101])
        self.assertTrue(report["construction_sites"][0]["has_assigned_worker"])

        runtime.values["this.state.me.units[0].assignTo == null"] = "true"
        report = observe_buildings(runtime, catalogue, graph)
        values = dict(zip(report["feature_names"], report["x"][0], strict=True))
        self.assertEqual(values["unassigned_construction_tower"], 2)

        # Completion creates a different object; fresh reads must not keep 500
        # or report that the vanished construction still needs staffing.
        runtime.values["zone_10.buildings[1].__uid"] = "600"
        runtime.values["zone_10.buildings[1].baseKind"] = json.dumps("GuardTower")
        runtime.native_values["zone_10.buildings[1].get_id()"] = json.dumps("GuardTower")
        runtime.native_values["zone_10.buildings[1].isPlayerBuilt()"] = "true"
        report = observe_buildings(runtime, catalogue, graph)
        self.assertEqual([site["building_id"] for site in report["construction_sites"]], [501])
        values = dict(zip(report["feature_names"], report["x"][0], strict=True))
        self.assertEqual(values["construction_tower"], 1)
        self.assertEqual(values["building_tower"], 1)

    def test_non_owned_construction_is_not_a_staffing_target(self):
        runtime = FakeRuntime()
        runtime.native_values["zone_20.buildings[0].get_id()"] = json.dumps("Construction")
        runtime.native_values["zone_20.buildings[0].get_realKind()"] = json.dumps("House")
        # No unit collection or construction UID is readable in this fixture.
        report = observe_buildings(runtime, load_building_schema(), {
            "zone_ids": [20],
            "nodes": {20: {"expression": "zone_20", "owner": {"owned": False}}},
        })
        self.assertEqual(report["construction_sites"], [])
        values = dict(zip(report["feature_names"], report["x"][0], strict=True))
        self.assertEqual(values["construction_house"], 1)
        self.assertEqual(values["unassigned_construction_house"], 0)

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
            "unassigned_construction_house",
            "unassigned_construction_tower",
        ])
        self.assertEqual(report["x"], [[1, 0, 0, 1, 0, 1], [0, 0, 0, 0, 0, 0]])
        self.assertEqual(report["construction_sites"], [{
            "building_id": 500, "zone_id": 10,
            "building_family": "tower", "engine_id": "GuardTower",
            "assigned_unit_ids": [], "has_assigned_worker": False,
        }])
        self.assertEqual(
            report["build_action_mask"],
            [[1.0, 0.0], [0.0, 0.0]],
        )
        self.assertEqual(report["unmapped_buildings"], [{
            "zone_id": 10,
            "source": "completed",
            "engine_id": "UnknownWorkshop",
        }])


if __name__ == "__main__":
    unittest.main()
