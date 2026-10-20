"""Unit job maps retain identities without treating allies as owned workers."""

import json
import unittest
from unittest.mock import patch

from odin.tools.unit_jobs import list_unit_jobs


class FakeRuntime:
    def __init__(self):
        self.units = [
            {"id": 20, "kind": "Woodcutter", "zone": 7, "owned": True, "dead": False},
            {"id": 3, "kind": "VillagerWoman", "zone": 8, "owned": True, "dead": False},
            {"id": 4, "kind": "Scout", "zone": 7, "owned": True, "dead": True},
            {"id": 5, "kind": "Farmer", "zone": 7, "owned": False, "dead": False},
            {"id": 6, "kind": "NewUnit", "zone": None, "owned": True, "dead": False},
        ]
        self.player = "this.state.me"

    def array_length(self, expression):
        assert expression == f"{self.player}.units"
        return len(self.units)

    def evaluate(self, expression):
        prefix, field = expression.split("].", 1)
        assert prefix.startswith(f"{self.player}.units[")
        unit = self.units[int(prefix.rsplit("[", 1)[1])]
        return {
            f"owner == {self.player}": str(unit["owned"]).lower(),
            "get_isDead()": str(unit["dead"]).lower(),
            "__uid": str(unit["id"]),
            "kind": json.dumps(unit["kind"]),
            "zone == null": str(unit["zone"] is None).lower(),
            "zone.id": str(unit["zone"]),
        }[field]

    def call_native(self, expression):
        return self.evaluate(expression)


class UnitJobToolTests(unittest.TestCase):
    def test_owned_living_units_keep_roles_and_locations(self):
        runtime = FakeRuntime()
        report = list_unit_jobs(runtime)
        self.assertEqual(report, {"unit_jobs": {
            "3": {"job": "villager", "engine_id": "VillagerWoman", "zone_id": 8},
            "6": {"job": None, "engine_id": "NewUnit", "zone_id": None},
            "20": {"job": "woodcutter", "engine_id": "Woodcutter", "zone_id": 7},
        }})
        self.assertEqual(list(report["unit_jobs"]), ["3", "6", "20"])
        runtime.units[0]["kind"] = "Farmer"
        self.assertEqual(list_unit_jobs(runtime)["unit_jobs"]["20"]["job"], "farmer")

    def test_selected_bot_uses_its_own_units(self):
        runtime = FakeRuntime()
        runtime.player = "bot"
        with patch("odin.tools.unit_jobs.resolve_player", return_value="bot") as resolve:
            report = list_unit_jobs(runtime, player_id=91)
        resolve.assert_called_once_with(runtime, 91)
        self.assertIn("20", report["unit_jobs"])
