"""Offline tests for selecting observation tensors."""

from pathlib import Path
import unittest
from unittest.mock import patch

from odin.environment import NorthgardEnv


class EnvironmentTests(unittest.TestCase):
    def test_observe_only_extracts_selected_tensors(self):
        env = NorthgardEnv(
            Path("adapter.js"),
            Path("Northgard.exe"),
            tensors=("pause", "zones"),
        )
        env.resource_keys = {"Stone": "stone_key", "Iron": "iron_key"}

        with (
            patch("odin.environment.observe_pause", return_value={"x": [0.0]}),
            patch(
                "odin.environment.discover_zone_graph",
                return_value={"nodes": {}, "zone_ids": [], "edge_index": [[], []]},
            ) as discover_zones,
            patch(
                "odin.environment.observe_zone_graph",
                return_value={"feature_names": ["owned"], "x": []},
            ) as observe_zones,
            patch(
                "odin.environment.observe_buildings",
                return_value={
                    "feature_names": [],
                    "x": [],
                    "building_ids": [],
                    "schema_sha256": "abc",
                    "build_action_mask": [],
                    "unmapped_buildings": [],
                },
            ) as observe_buildings,
        ):
            observation = env.observe()

        self.assertEqual(observation, {
            "pause": {"x": [0.0]},
            "zones": {
                "feature_names": ["owned"],
                "x": [],
                "building_ids": [],
                "building_schema_sha256": "abc",
                "build_action_mask": [],
                "unmapped_buildings": [],
            },
        })
        discover_zones.assert_called_once_with(env.runtime)
        observe_zones.assert_called_once_with(
            env.runtime,
            env.resource_keys,
            {"nodes": {}, "zone_ids": [], "edge_index": [[], []]},
        )
        observe_buildings.assert_called_once_with(
            env.runtime,
            env.building_catalogue,
            {"nodes": {}, "zone_ids": [], "edge_index": [[], []]},
        )

    def test_rejects_unknown_tensor(self):
        with self.assertRaisesRegex(ValueError, "Unknown observation tensors"):
            NorthgardEnv(
                Path("adapter.js"),
                Path("Northgard.exe"),
                tensors=("weather",),
            )


if __name__ == "__main__":
    unittest.main()
