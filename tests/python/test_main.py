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

    def test_player_commands_forward_the_selected_uid(self):
        cases = [
            (["tools", "unit-jobs"], "list_unit_jobs", (), {"player_id": None}),
            (["tools", "unit-jobs", "--player", "91"], "list_unit_jobs", (), {"player_id": 91}),
            (["colonise", "--zone", "42", "--player", "91"],
             "colonise_zone", (42,), {"player_id": 91}),
            (["tools", "colonise-zones", "--player", "91"],
             "list_colonisation_zones", (), {"player_id": 91}),
            (["tools", "colonise-preview", "--zone", "42", "--player", "91"],
             "preview_colonisation", (42,), {"player_id": 91}),
            (["assign", "--unit", "1013", "--building", "1279", "--player", "91"],
             "assign_to_building", (1013, 1279), {"player_id": 91}),
            (["tools", "assign-preview", "--unit", "1013", "--building", "1279", "--player", "91"],
             "preview_assignment", (1013, 1279), {"player_id": 91}),
            (["tools", "ids", "--player", "91"], "list_player_ids", (), {"player_id": 91}),
            (["ai-stop", "--player", "91"], "set_ai_orders", (91,), {"stopped": True}),
            (["ai-resume", "--player", "91"], "set_ai_orders", (91,), {"stopped": False}),
            (["tools", "players"], "list_players", (), {}),
        ]
        for command, function, args, kwargs in cases:
            with (
                self.subTest(command=command),
                patch("odin.main.NativeRuntime") as runtime_class,
                patch(f"odin.main.{function}", return_value={}) as action,
            ):
                result = CliRunner().invoke(app, command)
                self.assertEqual(result.exit_code, 0, result.output)
                runtime = runtime_class.return_value.__enter__.return_value
                action.assert_called_once_with(runtime, *args, **kwargs)

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
