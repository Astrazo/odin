"""Validate and send one worker-to-building assignment."""

import json

from odin.actions.players import require_offline_host, require_paused_bot, resolve_player


def _find_unit(runtime, unit_id: int, player: str) -> str:
    for index in range(runtime.array_length(f"{player}.units")):
        unit = f"{player}.units[{index}]"
        if int(runtime.evaluate(f"{unit}.__uid")) != unit_id:
            continue
        if runtime.evaluate(f"{unit}.owner == {player}") != "true":
            raise RuntimeError(f"Unit {unit_id} is no longer owned by this player.")
        return unit
    raise ValueError(f"Owned unit {unit_id} was not found.")


def _find_building(runtime, building_id: int, player: str) -> str:
    for zone_index in range(runtime.array_length(f"{player}.zones")):
        zone = f"{player}.zones[{zone_index}]"
        if runtime.call_native(f"{zone}.getOwner() == {player}") != "true":
            raise RuntimeError("Player.zones contains a zone that is no longer owned.")
        for building_index in range(runtime.array_length(f"{zone}.buildings")):
            building = f"{zone}.buildings[{building_index}]"
            if int(runtime.evaluate(f"{building}.__uid")) != building_id:
                continue
            return building
    raise ValueError(f"Owned building {building_id} was not found.")


def preview_assignment(
    runtime, unit_id: int, building_id: int, *, player_id: int | None = None,
) -> dict:
    """Check the exact pair using Northgard's own assignment validator.

    This does not change the game.  ``Building.canAssignTo`` is the check the
    game itself performs before accepting ``UnitAction.AssignTo``.
    """
    player = resolve_player(runtime, player_id)
    unit = _find_unit(runtime, unit_id, player)
    building = _find_building(runtime, building_id, player)
    unit_kind = json.loads(runtime.evaluate(f"{unit}.kind"))
    building_kind = json.loads(runtime.evaluate(f"{building}.kind"))
    allowed = runtime.call_native(
        f"{building}.canAssignTo({unit}, null, null, null, null)"
    ) == "true"

    preview = {
        "unit_id": unit_id,
        "unit_kind": unit_kind,
        "building_id": building_id,
        "building_kind": building_kind,
        "can_assign": allowed,
    }
    if player_id is not None:
        preview["player_id"] = player_id
    return preview


def assign_to_building(
    runtime, unit_id: int, building_id: int, *, player_id: int | None = None,
) -> dict:
    """Send one ScriptApi order using the selected player's units and buildings."""
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    if runtime.evaluate(f"{player} == this.state.me") != "true":
        require_paused_bot(runtime, player)
        if runtime.evaluate(f"{player}.skipAIOrder") != "true":
            raise RuntimeError("Stop the selected bot's AI orders before assigning its workers.")
    if runtime.evaluate("this.script == null") != "false":
        raise RuntimeError("Game.script is absent; no assignment was sent.")

    preview = preview_assignment(runtime, unit_id, building_id, player_id=player_id)
    if not preview["can_assign"]:
        raise RuntimeError("Northgard rejected this unit/building pair before dispatch.")

    player = resolve_player(runtime, player_id)
    unit = _find_unit(runtime, unit_id, player)
    building = _find_building(runtime, building_id, player)
    result = runtime.call_native(f"this.script.assign({unit}, {building})")
    if result != "true":
        raise RuntimeError("Northgard rejected the assignment.")

    # The authoritative engine updates this link before the script order returns.
    # A true return without this state change is not enough evidence to treat
    # the order as accepted.
    observed = runtime.evaluate(f"{unit}.assignTo == {building}") == "true"
    if not observed:
        raise RuntimeError("Northgard returned true but did not link the worker to the building.")
    return {**preview, "assigned": True, "assignment_observed": True}
