"""Offline checks for the minimal manual ID listing tool."""

import unittest

from odin.tools.ids import list_player_ids, list_scout_ids


class FakeRuntime:
    def array_length(self, expression):
        return {
            "this.state.me.zones": 2,
            "this.state.me.units": 3,
        }[expression]

    def evaluate(self, expression):
        return {
            "this.state.me.zones[0].id": "92",
            "this.state.me.zones[1].id": "10",
            "this.state.me.units[0].__uid": "1249",
            "this.state.me.units[1].__uid": "87",
            "this.state.me.units[2].__uid": "430",
        }[expression]


class PlayerIdToolTests(unittest.TestCase):
    def test_scout_ids_exclude_dead_foreign_and_ineligible_units(self):
        class ScoutRuntime:
            def array_length(self, expression):
                if expression != "this.state.me.units":
                    raise AssertionError(expression)
                return 5

            def evaluate(self, expression):
                return {
                    "this.state.me.units[0].owner == this.state.me": "true",
                    "this.state.me.units[1].owner == this.state.me": "true",
                    "this.state.me.units[2].owner == this.state.me": "true",
                    "this.state.me.units[3].owner == this.state.me": "false",
                    "this.state.me.units[4].owner == this.state.me": "true",
                    "this.state.me.units[0].__uid": "1249",
                    "this.state.me.units[4].__uid": "101",
                }[expression]

            def call_native(self, expression):
                # Missing entries also catch calls that should be skipped for
                # a dead/foreign unit, or any attempted gameplay order.
                return {
                    "this.state.me.units[0].get_isDead()": "false",
                    "this.state.me.units[0].get_canScout()": "true",
                    "this.state.me.units[1].get_isDead()": "false",
                    "this.state.me.units[1].get_canScout()": "false",
                    "this.state.me.units[2].get_isDead()": "true",
                    "this.state.me.units[4].get_isDead()": "false",
                    "this.state.me.units[4].get_canScout()": "true",
                }[expression]

        self.assertEqual(list_scout_ids(ScoutRuntime()), [101, 1249])

    def test_lists_only_ids_from_the_player_arrays(self):
        result = list_player_ids(FakeRuntime())

        self.assertEqual(result, {
            "player_zone_ids": [10, 92],
            "player_unit_ids": [87, 430, 1249],
        })
