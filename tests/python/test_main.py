"""Offline tests for CLI-only observation formatting."""

import io
import json
import unittest

from odin.main import format_unmapped_buildings, write_observation


class MainTests(unittest.TestCase):
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
