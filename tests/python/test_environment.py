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
                return_value={"feature_names": ["owned"], "zone_ids": [], "x": []},
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
            patch(
                "odin.environment.observe_units",
                return_value={
                    "feature_names": [],
                    "x": [],
                    "unit_ids": [],
                    "neutral_unit_ids": [],
                    "neutral_family_by_engine_id": {},
                    "schema_sha256": "def",
                    "unmapped_units": [],
                },
            ) as observe_units,
        ):
            observation = env.observe()

        self.assertEqual(observation, {
            "pause": {"x": [0.0]},
            "zones": {
                "feature_names": ["owned"],
                "zone_ids": [],
                "x": [],
                "building_ids": [],
                "building_schema_sha256": "abc",
                "build_action_mask": [],
                "unmapped_buildings": [],
                "unit_ids": [],
                "neutral_unit_ids": [],
                "unit_schema_sha256": "def",
                "unmapped_units": [],
                "summary": {},
            },
        })
        discover_zones.assert_called_once_with(env.runtime)
        observe_zones.assert_called_once_with(
            env.runtime,
            env.resource_keys,
            {"nodes": {}, "zone_ids": [], "edge_index": [[], []]},
            env.zone_feature_catalogue,
        )
        observe_buildings.assert_called_once_with(
            env.runtime,
            env.building_catalogue,
            {"nodes": {}, "zone_ids": [], "edge_index": [[], []]},
        )
        observe_units.assert_called_once_with(
            env.runtime,
            env.unit_catalogue,
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
