"""Offline assignment checks, including selected bot ownership and dispatch."""

from collections import deque
import unittest

from odin.actions.assignments import assign_to_building, preview_assignment


BOT = "this.state.players.array[1]"


class FakeRuntime:
    def __init__(self, values):
        self.values = {expression: deque(results) for expression, results in values.items()}
        self.expressions = []

    def array_length(self, expression):
        self.expressions.append(expression)
        return 2 if expression == "this.state.players.array" else 1

    def evaluate(self, expression):
        self.expressions.append(expression)
        return self.values[expression].popleft()

    call_native = evaluate


class AssignmentTests(unittest.TestCase):
    def values(self, *, allowed="true", dispatched=None, player="this.state.me"):
        unit = f"{player}.units[0]"
        zone = f"{player}.zones[0]"
        building = f"{zone}.buildings[0]"
        result = {
            "this.host.isAuth": ["true"],
            "this.state.isMulti(null)": ["false"],
            "this.script == null": ["false"],
            f"{player} == this.state.me": ["true" if player == "this.state.me" else "false"],
            f"{unit}.__uid": ["1013"],
            f"{unit}.owner == {player}": ["true"],
            f"{zone}.getOwner() == {player}": ["true"],
            f"{building}.__uid": ["1279"],
            f"{unit}.kind": ['"Villager"'],
            f"{building}.kind": ['"ScoutCamp"'],
            f"{building}.canAssignTo({unit}, null, null, null, null)": [allowed],
        }
        if player != "this.state.me":
            result.update({
                "this.state.play == PlayState.Pause": ["true"],
                f"{player} == this.state.me": ["false", "false"],
                f"{player}.aiJob == null": ["false"],
                f"{player}.skipAIOrder": ["true"],
            })
            for index, uid in enumerate((90, 91)):
                # Resolve the player before validation, during preview and again
                # before dispatch. Never retain an array index across commands.
                entry = f"this.state.players.array[{index}]"
                result[f"{entry} == null"] = ["false"] * 3
                result[f"{entry}.__uid"] = [str(uid)] * 3
        if dispatched is not None:
            result[f"{unit}.__uid"].append("1013")
            result[f"{unit}.owner == {player}"].append("true")
            result[f"{zone}.getOwner() == {player}"].append("true")
            result[f"{building}.__uid"].append("1279")
            result[f"this.script.assign({unit}, {building})"] = [dispatched]
            result[f"{unit}.assignTo == {building}"] = ["true"]
        return result

    def assert_no_order(self, runtime):
        self.assertFalse(any(".assign(" in expr for expr in runtime.expressions))

    def test_preview_uses_engine_validator_without_dispatch(self):
        runtime = FakeRuntime(self.values())
        self.assertEqual(preview_assignment(runtime, 1013, 1279), {
            "unit_id": 1013, "unit_kind": "Villager",
            "building_id": 1279, "building_kind": "ScoutCamp", "can_assign": True,
        })
        self.assert_no_order(runtime)

    def test_assignment_does_not_dispatch_when_game_rejects_pair(self):
        runtime = FakeRuntime(self.values(allowed="false"))
        with self.assertRaisesRegex(RuntimeError, "before dispatch"):
            assign_to_building(runtime, 1013, 1279)
        self.assert_no_order(runtime)

    def test_assignment_uses_script_route_once_and_confirms_link(self):
        runtime = FakeRuntime(self.values(dispatched="true"))
        result = assign_to_building(runtime, 1013, 1279)
        self.assertTrue(result["assigned"])
        self.assertTrue(result["assignment_observed"])
        orders = [expr for expr in runtime.expressions if ".assign(" in expr]
        self.assertEqual(orders, [
            "this.script.assign(this.state.me.units[0], this.state.me.zones[0].buildings[0])",
        ])
        self.assertEqual(runtime.expressions[-1],
                         "this.state.me.units[0].assignTo == this.state.me.zones[0].buildings[0]")

    def test_bot_assignment_uses_only_selected_player_objects(self):
        runtime = FakeRuntime(self.values(player=BOT, dispatched="true"))
        result = assign_to_building(runtime, 1013, 1279, player_id=91)
        self.assertEqual(result["player_id"], 91)
        self.assertTrue(result["assigned"])
        self.assertIn(f"this.script.assign({BOT}.units[0], {BOT}.zones[0].buildings[0])",
                      runtime.expressions)
        self.assertFalse(any("this.state.me.units" in expr or "this.state.me.zones" in expr
                             for expr in runtime.expressions))
        self.assertFalse(any("set_skipAIOrder" in expr for expr in runtime.expressions))

    def test_bot_preview_is_read_only_even_with_stock_ai_running(self):
        values = self.values(player=BOT)
        values[f"{BOT}.skipAIOrder"] = ["false"]
        runtime = FakeRuntime(values)
        self.assertTrue(preview_assignment(runtime, 1013, 1279, player_id=91)["can_assign"])
        self.assert_no_order(runtime)

    def test_bot_with_running_ai_is_rejected(self):
        values = self.values(player=BOT, dispatched="true")
        values[f"{BOT}.skipAIOrder"] = ["false"]
        runtime = FakeRuntime(values)
        with self.assertRaisesRegex(RuntimeError, "Stop the selected bot"):
            assign_to_building(runtime, 1013, 1279, player_id=91)
        self.assert_no_order(runtime)

    def test_foreign_unit_is_rejected(self):
        values = self.values(player=BOT, dispatched="true")
        values[f"{BOT}.units[0].owner == {BOT}"] = ["false"]
        runtime = FakeRuntime(values)
        with self.assertRaisesRegex(RuntimeError, "no longer owned"):
            assign_to_building(runtime, 1013, 1279, player_id=91)
        self.assert_no_order(runtime)

    def test_foreign_zone_is_rejected(self):
        values = self.values(player=BOT, dispatched="true")
        values[f"{BOT}.zones[0].getOwner() == {BOT}"] = ["false"]
        runtime = FakeRuntime(values)
        with self.assertRaisesRegex(RuntimeError, "no longer owned"):
            assign_to_building(runtime, 1013, 1279, player_id=91)
        self.assert_no_order(runtime)

    def test_missing_script_is_rejected(self):
        values = self.values()
        values["this.script == null"] = ["true"]
        runtime = FakeRuntime(values)
        with self.assertRaisesRegex(RuntimeError, "Game.script is absent"):
            assign_to_building(runtime, 1013, 1279)
        self.assert_no_order(runtime)

    def test_multiplayer_or_non_host_is_rejected(self):
        for expression, value in [("this.host.isAuth", "false"),
                                  ("this.state.isMulti(null)", "true")]:
            with self.subTest(expression=expression):
                values = self.values()
                values[expression] = [value]
                runtime = FakeRuntime(values)
                with self.assertRaises(RuntimeError):
                    assign_to_building(runtime, 1013, 1279)
                self.assert_no_order(runtime)

    def test_native_rejection_is_not_retried(self):
        runtime = FakeRuntime(self.values(dispatched="false"))
        with self.assertRaisesRegex(RuntimeError, "rejected the assignment"):
            assign_to_building(runtime, 1013, 1279)
        self.assertEqual(sum(".assign(" in expr for expr in runtime.expressions), 1)

    def test_true_result_without_link_is_not_accepted(self):
        values = self.values(dispatched="true")
        values["this.state.me.units[0].assignTo == this.state.me.zones[0].buildings[0]"] = ["false"]
        runtime = FakeRuntime(values)
        with self.assertRaisesRegex(RuntimeError, "did not link"):
            assign_to_building(runtime, 1013, 1279)
        self.assertEqual(sum(".assign(" in expr for expr in runtime.expressions), 1)


if __name__ == "__main__":
    unittest.main()
