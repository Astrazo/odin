"""Offline test for the discovered-zone graph."""

import unittest

from odin.observations.zones import observe_zone_graph


class FakeRuntime:
    def __init__(self):
        root = "this.state.me.zones[0]"
        visible = f"{root}.next[0]"
        hidden = f"{root}.next[1]"
        back_to_root = f"{visible}.next[0]"

        self.lengths = {
            "this.state.me.zones": 1,
            f"{root}.next": 2,
            f"{visible}.next": 1,
        }
        self.values = {
            f"{root}.id": "10",
            f"{visible}.id": "20",
            f"{back_to_root}.id": "10",
        }
        self.native_values = {
            f"this.state.me.hasDiscovered({root})": "true",
            f"{root}.getOwner() == this.state.me": "true",
            f"{root}.getOwner() == null": "false",
            f"this.state.me.hasDiscovered({visible})": "true",
            f"{visible}.getOwner() == this.state.me": "false",
            f"{visible}.getOwner() == null": "true",
            f"this.state.me.hasDiscovered({hidden})": "false",
            f"this.state.me.hasDiscovered({back_to_root})": "true",
            f"{root}.hasNaturalFoodSource()": "true",
            f"{root}.hasFish()": "false",
            f"{root}.getDepositResCount(stone_key)": "0.0",
            f"{root}.getDepositResCount(iron_key)": "15.5",
            f"{visible}.hasNaturalFoodSource()": "false",
            f"{visible}.hasFish()": "true",
            f"{visible}.getDepositResCount(stone_key)": "30.0",
            f"{visible}.getDepositResCount(iron_key)": "0.0",
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
    def test_builds_one_hop_graph_without_reading_hidden_zone_contents(self):
        runtime = FakeRuntime()

        report = observe_zone_graph(
            runtime,
            {"Stone": "stone_key", "Iron": "iron_key"},
        )

        self.assertEqual(report["feature_names"], [
            "owned",
            "neutral",
            "allied_owned",
            "enemy_owned",
            "natural_food_available",
            "has_fish",
            "stone_remaining",
            "iron_remaining",
        ])
        self.assertEqual(report["zone_ids"], [10, 20])
        self.assertEqual(report["x"], [
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 15.5],
            [0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 30.0, 0.0],
        ])
        self.assertEqual(report["edge_index"], [[0, 1], [1, 0]])
        self.assertNotIn("this.state.me.zones[0].next[1].id", runtime.evaluated)


if __name__ == "__main__":
    unittest.main()
