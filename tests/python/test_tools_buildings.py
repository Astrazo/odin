"""Offline checks for the one-shot building-ID debugging tool."""

import unittest

from odin.tools.buildings import list_zone_buildings


class FakeRuntime:
    def array_length(self, expression):
        return {
            "this.state.me.zones": 2,
            "this.state.me.zones[1].buildings": 2,
        }[expression]

    def evaluate(self, expression):
        return {
            "this.state.me.zones[0].id": "10",
            "this.state.me.zones[1].id": "61",
            "this.state.me.zones[1].buildings[0].__uid": "1480",
            "this.state.me.zones[1].buildings[0].kind": '"TownHall"',
            "this.state.me.zones[1].buildings[1].__uid": "1512",
            "this.state.me.zones[1].buildings[1].kind": '"ScoutCamp"',
        }[expression]


class ZoneBuildingToolTests(unittest.TestCase):
    def test_lists_building_ids_and_kinds_for_the_selected_zone(self):
        result = list_zone_buildings(FakeRuntime(), 61)

        self.assertEqual(result, {
            "zone_id": 61,
            "buildings": [
                {"building_id": 1480, "kind": "TownHall"},
                {"building_id": 1512, "kind": "ScoutCamp"},
            ],
        })
