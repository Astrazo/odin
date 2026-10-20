"""Read the minimum runtime IDs needed for manual debugging."""

from odin.actions.players import resolve_player


def list_scout_ids(runtime) -> list[int]:
    """Return living local units that the engine currently allows to scout."""
    scout_ids = []
    for index in range(runtime.array_length("this.state.me.units")):
        unit = f"this.state.me.units[{index}]"
        if runtime.evaluate(f"{unit}.owner == this.state.me") != "true":
            continue
        if runtime.call_native(f"{unit}.get_isDead()") != "false":
            continue
        if runtime.call_native(f"{unit}.get_canScout()") == "true":
            scout_ids.append(int(runtime.evaluate(f"{unit}.__uid")))
    return sorted(scout_ids)


def list_player_ids(runtime, *, player_id: int | None = None) -> dict:
    """Return the player's current zone and unit IDs without native calls."""
    player = resolve_player(runtime, player_id)
    zone_ids = [
        int(runtime.evaluate(f"{player}.zones[{index}].id"))
        for index in range(runtime.array_length(f"{player}.zones"))
    ]
    unit_ids = [
        int(runtime.evaluate(f"{player}.units[{index}].__uid"))
        for index in range(runtime.array_length(f"{player}.units"))
    ]
    return {
        "player_zone_ids": sorted(zone_ids),
        "player_unit_ids": sorted(unit_ids),
    }
