"""Offline player selection and stock AI gate checks."""

from collections import deque
import unittest

from odin.actions.players import list_players, resolve_player, set_ai_orders
from odin.tools.buildings import list_zone_buildings
from odin.tools.ids import list_player_ids


BOT = "this.state.players.array[1]"


class FakeRuntime:
    def __init__(self, values):
        self.values = {key: deque(items) for key, items in values.items()}
        self.expressions = []
        self.lengths = {"this.state.players.array": 2, f"{BOT}.zones": 1, f"{BOT}.units": 1,
                        f"{BOT}.zones[0].buildings": 1}

    def array_length(self, expression):
        self.expressions.append(expression)
        return self.lengths[expression]

    def evaluate(self, expression):
        self.expressions.append(expression)
        return self.values[expression].popleft()

    call_native = evaluate


class PlayerTests(unittest.TestCase):
    def values(self, *, before="false", desired="true"):
        values = {
            "this.host.isAuth": ["true"],
            "this.state.isMulti(null)": ["false"],
            "this.state.play == PlayState.Pause": ["true"],
            f"{BOT}.skipAIOrder": [before, desired],
            f"{BOT}.set_skipAIOrder({desired})": [desired],
        }
        for index, (uid, name) in enumerate([(90, '"Harald"'), (91, '"Stein"')]):
            player = f"this.state.players.array[{index}]"
            values.update({
                f"{player} == null": ["false"],
                f"{player}.__uid": [str(uid)],
                f"{player}.name": [name],
                f"{player} == this.state.me": ["true" if index == 0 else "false"],
                f"{player}.aiJob == null": ["true" if index == 0 else "false"],
            })
        values["this.state.players.array[0].skipAIOrder"] = ["false"]
        return values

    def test_listing_does_not_change_ai_orders(self):
        runtime = FakeRuntime(self.values())
        self.assertEqual(list_players(runtime), {"players": [
            {"player_id": 90, "name": "Harald", "is_local": True,
             "has_ai_job": False, "ai_orders_stopped": False},
            {"player_id": 91, "name": "Stein", "is_local": False,
             "has_ai_job": True, "ai_orders_stopped": False},
        ]})
        self.assertFalse(any("set_skipAIOrder" in expr for expr in runtime.expressions))

    def test_default_player_needs_no_global_lookup(self):
        runtime = FakeRuntime({})
        self.assertEqual(resolve_player(runtime), "this.state.me")
        self.assertEqual(runtime.expressions, [])

    def test_missing_duplicate_and_null_players_are_rejected(self):
        values = self.values()
        with self.assertRaisesRegex(ValueError, "not found"):
            resolve_player(FakeRuntime(values), 999)
        values["this.state.players.array[1].__uid"] = ["90"]
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            resolve_player(FakeRuntime(values), 90)
        values["this.state.players.array[1] == null"] = ["true"]
        with self.assertRaisesRegex(RuntimeError, "Null player"):
            resolve_player(FakeRuntime(values), 90)

    def test_stop_and_resume_target_one_bot_and_verify_readback(self):
        for stopped, before, desired in [(True, "false", "true"), (False, "true", "false")]:
            with self.subTest(stopped=stopped):
                runtime = FakeRuntime(self.values(before=before, desired=desired))
                result = set_ai_orders(runtime, 91, stopped=stopped)
                self.assertEqual(result, {"player_id": 91, "before_orders_stopped": not stopped,
                                          "ai_orders_stopped": stopped, "setter_called": True})
                setters = [expr for expr in runtime.expressions if "set_skipAIOrder" in expr]
                self.assertEqual(setters, [f"{BOT}.set_skipAIOrder({desired})"])

    def test_already_stopped_gate_is_not_changed(self):
        runtime = FakeRuntime(self.values(before="true"))
        self.assertFalse(set_ai_orders(runtime, 91, stopped=True)["setter_called"])
        self.assertFalse(any("set_skipAIOrder" in expr for expr in runtime.expressions))

    def test_gate_change_rejects_wrong_mode_or_player(self):
        invalid = [("this.host.isAuth", "false"), ("this.state.isMulti(null)", "true"),
                   ("this.state.play == PlayState.Pause", "false"),
                   (f"{BOT} == this.state.me", "true"), (f"{BOT}.aiJob == null", "true")]
        for expression, value in invalid:
            with self.subTest(expression=expression):
                values = self.values()
                values[expression] = [value]
                runtime = FakeRuntime(values)
                with self.assertRaises(RuntimeError):
                    set_ai_orders(runtime, 91, stopped=True)
                self.assertFalse(any("set_skipAIOrder" in expr for expr in runtime.expressions))

    def test_setter_failure_and_failed_readback_are_not_retried(self):
        for expression in [f"{BOT}.set_skipAIOrder(true)", f"{BOT}.skipAIOrder"]:
            with self.subTest(expression=expression):
                values = self.values()
                values[expression] = ["false", "false"]
                runtime = FakeRuntime(values)
                with self.assertRaises(RuntimeError):
                    set_ai_orders(runtime, 91, stopped=True)
                self.assertEqual(sum("set_skipAIOrder" in expr for expr in runtime.expressions), 1)

    def test_id_tools_read_selected_bot_collections(self):
        values = self.values()
        values.update({f"{BOT}.zones[0].id": ["42"], f"{BOT}.units[0].__uid": ["1013"]})
        runtime = FakeRuntime(values)
        self.assertEqual(list_player_ids(runtime, player_id=91),
                         {"player_zone_ids": [42], "player_unit_ids": [1013]})
        values = self.values()
        values.update({f"{BOT}.zones[0].id": ["42"],
                       f"{BOT}.zones[0].buildings[0].__uid": ["1279"],
                       f"{BOT}.zones[0].buildings[0].kind": ['"ScoutCamp"']})
        runtime = FakeRuntime(values)
        self.assertEqual(list_zone_buildings(runtime, 42, player_id=91),
                         {"zone_id": 42, "buildings": [{"building_id": 1279, "kind": "ScoutCamp"}]})


if __name__ == "__main__":
    unittest.main()
