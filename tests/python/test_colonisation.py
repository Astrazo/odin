"""Offline colonisation checks using the native reason, cost and public RPC."""

import unittest

from odin.actions.colonisation import colonise_zone, list_colonisation_zones, preview_colonisation


class FakeRuntime:
    def __init__(self, *, player="this.state.me", reason="null"):
        self.player = player
        self.calls = []
        self.started = True
        self.owned = False
        root = f"{player}.zones[0]"
        target = f"{root}.next[0]"
        hidden = f"{root}.next[1]"
        other_owner = f"{root}.next[2]"
        cost = f"{player}.world.colonizeCost({target}, null, null, null, null)"
        self.target = target
        self.values = {
            "this.host.isAuth": "true",
            "this.state.isMulti(null)": "false",
            "this.state.play == PlayState.Pause": "true",
            f"{player} == this.state.me": "true" if player == "this.state.me" else "false",
            f"{player}.aiJob == null": "false",
            f"{player}.skipAIOrder": "true",
            f"{root}.getOwner() == {player}": "true",
            f"{root}.id": "10",
            f"{player}.hasDiscovered({target})": "true",
            f"{target}.getOwner() == null": "true",
            f"{target}.id": "20",
            f"{player}.hasDiscovered({hidden})": "false",
            f"{player}.hasDiscovered({other_owner})": "true",
            f"{other_owner}.getOwner() == null": "false",
            f"{player}.world.getNoColonizeReason({target}, ColonizeTestType.CurrentRes)": reason,
            f"{cost}.res": '"Food"',
            f"{cost}.qty": "120",
        }
        self.lengths = {f"{player}.zones": 1, f"{root}.next": 3, "this.state.players.array": 2}
        if player != "this.state.me":
            for index, uid in enumerate((90, 91)):
                entry = f"this.state.players.array[{index}]"
                self.values[f"{entry} == null"] = "false"
                self.values[f"{entry}.__uid"] = str(uid)

    def array_length(self, expression):
        self.calls.append(expression)
        return self.lengths[expression]

    def evaluate(self, expression):
        self.calls.append(expression)
        if expression == f"{self.target}.colonizeBy == {self.player}":
            return "true" if self.started else "false"
        return self.values[expression]

    def call_native(self, expression):
        self.calls.append(expression)
        if expression == f"{self.player}.world.startColonize({self.target}, null)":
            return "null"
        if expression == f"{self.target}.getOwner() == {self.player}":
            return "true" if self.owned else "false"
        return self.values[expression]

    def orders(self):
        return [call for call in self.calls if ".startColonize(" in call]


class ColonisationTests(unittest.TestCase):
    def test_listing_shows_native_cost_without_hidden_contents_or_orders(self):
        runtime = FakeRuntime()
        result = list_colonisation_zones(runtime)
        self.assertEqual(result, {"colonisable_zones": [{
            "zone_id": 20, "adjacent_to": [10], "can_colonise": True,
            "reason": None, "cost": {"resource": "Food", "quantity": 120},
        }], "blocked_zones": []})
        self.assertEqual(runtime.orders(), [])
        self.assertFalse(any(call.startswith("this.state.me.zones[0].next[1].")
                             for call in runtime.calls))

    def test_blocking_reasons_prevent_dispatch(self):
        for reason in ["Occupied", "MissingResources", "LonelyZone", "NearbyAttack", "NotAllowed"]:
            with self.subTest(reason=reason):
                runtime = FakeRuntime(reason=reason)
                report = list_colonisation_zones(runtime)
                self.assertEqual(report["colonisable_zones"], [])
                self.assertEqual(report["blocked_zones"][0]["reason"], reason)
                with self.assertRaisesRegex(RuntimeError, reason):
                    colonise_zone(runtime, 20)
                self.assertEqual(runtime.orders(), [])

    def test_hidden_owned_and_non_border_ids_are_rejected(self):
        for zone_id in [30, 40, 999]:
            with self.subTest(zone_id=zone_id):
                runtime = FakeRuntime()
                with self.assertRaisesRegex(ValueError, "discovered, unowned neighbour"):
                    preview_colonisation(runtime, zone_id)
                with self.assertRaises(ValueError):
                    colonise_zone(runtime, zone_id)
                self.assertEqual(runtime.orders(), [])

    def test_dispatches_public_rpc_once_and_confirms_start(self):
        runtime = FakeRuntime()
        result = colonise_zone(runtime, 20)
        self.assertEqual(runtime.orders(), [
            "this.state.me.world.startColonize(this.state.me.zones[0].next[0], null)",
        ])
        self.assertTrue(result["requested"])
        self.assertTrue(result["colonisation_observed"])
        self.assertFalse(result["owned"])
        self.assertFalse(any("script.colonize" in call or "__impl" in call for call in runtime.calls))

    def test_immediate_ownership_also_confirms_colonisation(self):
        runtime = FakeRuntime()
        runtime.started = False
        runtime.owned = True
        self.assertTrue(colonise_zone(runtime, 20)["owned"])

    def test_unconfirmed_start_is_not_retried(self):
        runtime = FakeRuntime()
        runtime.started = False
        with self.assertRaisesRegex(RuntimeError, "not confirmed"):
            colonise_zone(runtime, 20)
        self.assertEqual(len(runtime.orders()), 1)

    def test_bot_selection_reaches_its_own_world_component(self):
        player = "this.state.players.array[1]"
        runtime = FakeRuntime(player=player)
        result = colonise_zone(runtime, 20, player_id=91)
        self.assertEqual(result["player_id"], 91)
        self.assertEqual(runtime.orders(), [f"{player}.world.startColonize({player}.zones[0].next[0], null)"])
        self.assertFalse(any("this.state.me.zones" in call for call in runtime.calls))

    def test_bot_with_running_ai_or_unpaused_match_is_rejected(self):
        player = "this.state.players.array[1]"
        for expression in [f"{player}.skipAIOrder", "this.state.play == PlayState.Pause"]:
            with self.subTest(expression=expression):
                runtime = FakeRuntime(player=player)
                runtime.values[expression] = "false"
                with self.assertRaises(RuntimeError):
                    colonise_zone(runtime, 20, player_id=91)
                self.assertEqual(runtime.orders(), [])

    def test_non_host_and_multiplayer_requests_are_rejected(self):
        for expression, value in [("this.host.isAuth", "false"), ("this.state.isMulti(null)", "true")]:
            runtime = FakeRuntime()
            runtime.values[expression] = value
            with self.assertRaises(RuntimeError):
                colonise_zone(runtime, 20)
            self.assertEqual(runtime.orders(), [])

    def test_repeated_border_is_deduplicated(self):
        runtime = FakeRuntime()
        runtime.lengths["this.state.me.zones"] = 2
        runtime.lengths["this.state.me.zones[1].next"] = 1
        runtime.values.update({
            "this.state.me.zones[1].getOwner() == this.state.me": "true",
            "this.state.me.zones[1].id": "11",
            "this.state.me.hasDiscovered(this.state.me.zones[1].next[0])": "true",
            "this.state.me.zones[1].next[0].getOwner() == null": "true",
            "this.state.me.zones[1].next[0].id": "20",
        })
        self.assertEqual(list_colonisation_zones(runtime)["colonisable_zones"][0]["adjacent_to"], [10, 11])


if __name__ == "__main__":
    unittest.main()
