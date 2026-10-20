"""Offline test for the discovered-zone graph."""

import unittest

from odin.observations.zones import observe_zone_graph, summarize_zones


class FakeRuntime:
    def __init__(self):
        root = "this.state.me.zones[0]"
        visible = f"{root}.next[0]"
        hidden = f"{root}.next[1]"
        back_to_root = f"{visible}.next[0]"
        distant = f"{visible}.next[1]"

        self.lengths = {
            "this.state.me.zones": 1,
            f"{root}.next": 2,
            f"{visible}.next": 2,
            f"{distant}.next": 1,
            f"{root}.buildings": 5,
            f"{visible}.buildings": 1,
            f"{distant}.buildings": 0,
        }
        self.values = {
            f"{root}.id": "10",
            f"{visible}.id": "20",
            f"{hidden}.id": "40",
            f"{back_to_root}.id": "10",
            f"{distant}.id": "30",
            f"{distant}.next[0].id": "20",
        }
        self.native_values = {
            f"this.state.me.hasDiscovered({root})": "true",
            f"{root}.getOwner() == this.state.me": "true",
            f"{root}.getOwner() == null": "false",
            f"this.state.me.hasDiscovered({visible})": "true",
            f"{visible}.getOwner() == this.state.me": "false",
            f"{visible}.getOwner() == null": "true",
            f"this.state.me.hasDiscovered({hidden})": "false",
            f"{hidden}.canBeScouted(this.state.me, null)": "true",
            f"this.state.me.hasDiscovered({back_to_root})": "true",
            f"this.state.me.hasDiscovered({distant})": "true",
            f"this.state.me.hasDiscovered({distant}.next[0])": "true",
            f"{distant}.getOwner() == this.state.me": "false",
            f"{distant}.getOwner() == null": "true",
            f"{root}.buildings[0].get_id()": '"Fertility"',
            f"{root}.buildings[1].get_id()": '"Grove"',
            f"{root}.buildings[2].get_id()": '"BrokenShores"',
            f"{root}.buildings[3].get_id()": '"Geyser"',
            f"{root}.buildings[4].get_id()": '"RuneStone"',
            f"{root}.hasFish()": "false",
            f"{root}.hasHostility(this.state.me, null, null, null, null)": "false",
            f"{root}.getCurrentProduction(building_key, null, null, null, null)": "3",
            f"{root}.getMaxProduction(building_key, null, null, null, null)": "5",
            f"{root}.hasCoast()": "true",
            f"{root}.getDepositResCount(stone_key)": "0.0",
            f"{root}.getDepositResCount(iron_key)": "15.5",
            f"{visible}.buildings[0].get_id()": '"DeerSpawner"',
            f"{visible}.hasFish()": "true",
            f"{visible}.hasHostility(this.state.me, null, null, null, null)": "true",
            f"{visible}.getCurrentProduction(building_key, null, null, null, null)": "0",
            f"{visible}.getMaxProduction(building_key, null, null, null, null)": "3",
            f"{visible}.hasCoast()": "false",
            f"{visible}.getDepositResCount(stone_key)": "30.0",
            f"{visible}.getDepositResCount(iron_key)": "0.0",
            f"{distant}.hasFish()": "false",
            f"{distant}.hasHostility(this.state.me, null, null, null, null)": "false",
            f"{distant}.getCurrentProduction(building_key, null, null, null, null)": "0",
            f"{distant}.getMaxProduction(building_key, null, null, null, null)": "4",
            f"{distant}.hasCoast()": "true",
            f"{distant}.getDepositResCount(stone_key)": "0.0",
            f"{distant}.getDepositResCount(iron_key)": "0.0",
        }
        self.evaluated = []

    def array_length(self, expression):
        return self.lengths[expression]

    def evaluate(self, expression):
        self.evaluated.append(expression)
        return self.values[expression]

    def call_native(self, expression):
        return self.native_values[expression]


class ZoneGraphTests(unittest.TestCase):
    def test_builds_all_discovered_zones_without_reading_hidden_zone_contents(self):
        runtime = FakeRuntime()

        report = observe_zone_graph(
            runtime,
            {"Building": "building_key", "Stone": "stone_key", "Iron": "iron_key"},
        )

        self.assertEqual(report["feature_names"], [
            "owned",
            "neutral",
            "allied_owned",
            "enemy_owned",
            "is_guarded",
            "building_slots_used",
            "building_slots_max",
            "is_coastal",
            "has_fish",
            "stone_remaining",
            "iron_remaining",
            "has_fields",
            "has_deer",
            "has_forest",
            "has_shipwreck",
            "has_geyser",
            "has_runestone",
        ])
        self.assertEqual(report["zone_ids"], [10, 20, 30])
        self.assertEqual(report["x"], [
            [1.0, 0.0, 0.0, 0.0, 0.0, 3, 5, 1.0, 0.0, 0.0, 15.5,
             1.0, 0.0, 1.0, 1.0, 1.0, 1.0],
            [0.0, 1.0, 0.0, 0.0, 1.0, 0, 3, 0.0, 1.0, 30.0, 0.0,
             0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0, 4, 1.0, 0.0, 0.0, 0.0,
             0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ])
        self.assertEqual(report["edge_index"], [[0, 1, 1, 2], [1, 0, 2, 1]])
        self.assertEqual(report["scout_target_mask"], [{
            "zone_id": 40,
            "adjacent_to": [10],
        }])
        # A hidden neighbour contributes only its opaque ID to the action mask.
        # Its owner, resources, buildings, and units are never read into the graph.
        hidden = "this.state.me.zones[0].next[1]"
        self.assertEqual(
            [expression for expression in runtime.evaluated if expression.startswith(hidden)],
            [f"{hidden}.id"],
        )

    def test_summarizes_only_present_zone_contents(self):
        summary = summarize_zones({
            "feature_names": [
                "owned", "neutral", "allied_owned", "enemy_owned",
                "is_guarded", "building_slots_used", "building_slots_max",
                "is_coastal", "has_fish", "stone_remaining", "iron_remaining",
                "has_deer", "building_town_hall", "building_house",
                "construction_house", "friendly_villager", "enemy_scout",
                "neutral_wolf", "unassigned_construction_house",
            ],
            "zone_ids": [92],
            "x": [[
                1.0, 0.0, 0.0, 0.0,
                1.0, 1, 5,
                1.0, 0.0, 0.0, 15.0,
                1.0, 1, 0,
                1, 4, 1,
                2, 1,
            ]],
            "building_ids": ["town_hall", "house"],
            "build_action_mask": [[0.0, 1.0]],
        })

        self.assertEqual(summary, {
            "92": {
                "owner": "owned",
                "flags": ["is_guarded", "is_coastal", "has_deer"],
                "building_slots": {"used": 1, "max": 5},
                "resources": {"iron": 15.0},
                "buildings": {"town_hall": 1},
                "construction": {"house": 1},
                "unassigned_construction": {"house": 1},
                "units": {
                    "friendly": {"villager": 4},
                    "enemy": {"scout": 1},
                    "neutral": {"wolf": 2},
                },
                "buildable": ["house"],
            },
        })


if __name__ == "__main__":
    unittest.main()
