"""Offline tests for CLI-only observation formatting."""

import io
import json
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from odin.main import app, format_unmapped_buildings, write_observation


class MainTests(unittest.TestCase):

    def test_scout_zone_tool_prints_only_target_ids_and_visible_borders(self):
        with (
            patch("odin.main.NativeRuntime") as runtime_class,
            patch("odin.main.discover_zone_graph", return_value={
                "nodes": {10: {"expression": "internal zone expression"}},
                "zone_ids": [10],
                "scout_target_mask": [{"zone_id": 40, "adjacent_to": [10]}],
            }) as discover,
            patch("odin.main.list_scout_ids", return_value=[1249]) as scouts,
        ):
            result = CliRunner().invoke(app, ["tools", "scout-zones"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(json.loads(result.output), {
                "scout_ids": [1249],
                "scoutable_zones": [{"zone_id": 40, "adjacent_to": [10]}],
            })
            discover.assert_called_once_with(runtime_class.return_value.__enter__.return_value)
            scouts.assert_called_once_with(runtime_class.return_value.__enter__.return_value)


    def test_groups_unmapped_buildings_by_zone_and_source(self):
        report = format_unmapped_buildings({
            "zones": {
                "unmapped_buildings": [
                    {"zone_id": 92, "source": "available", "engine_id": "Totem"},
                    {"zone_id": 92, "source": "available", "engine_id": "Barricade"},
                    {"zone_id": 92, "source": "completed", "engine_id": "Boat"},
                ],
            },
        })

        self.assertEqual(report, "\n".join([
            "Unmapped building IDs (excluded from the policy schema):",
            "  Zone 92 available: Barricade, Totem",
            "  Zone 92 completed: Boat",
        ]))

    def test_returns_nothing_when_no_zone_diagnostics_exist(self):
        self.assertIsNone(format_unmapped_buildings({"pause": {"x": [0.0]}}))

    def test_writes_observations_as_a_json_array(self):
        log_file = io.StringIO()
        log_file.write("[\n")
        write_observation(log_file, {"pause": {"x": [0.0]}}, first=True)
        write_observation(log_file, {"pause": {"x": [1.0]}}, first=False)
        log_file.write("\n]\n")

        self.assertEqual(json.loads(log_file.getvalue()), [
            {"pause": {"x": [0.0]}},
            {"pause": {"x": [1.0]}},
        ])


if __name__ == "__main__":
    unittest.main()
