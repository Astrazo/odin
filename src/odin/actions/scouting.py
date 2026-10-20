"""Send an owned scout to an adjacent, undiscovered zone."""


def _call_bool(runtime, expression: str) -> bool:
    result = runtime.call_native(expression)
    if result not in ("true", "false"):
        raise RuntimeError(f"Expected a Boolean from {expression}: {result!r}")
    return result == "true"


def _find_scout(runtime, unit_id: int) -> str:
    for index in range(runtime.array_length("this.state.me.units")):
        unit = f"this.state.me.units[{index}]"
        if int(runtime.evaluate(f"{unit}.__uid")) != unit_id:
            continue
        if not _call_bool(runtime, f"{unit}.owner == this.state.me"):
            raise RuntimeError(f"Unit {unit_id} is no longer owned by this player.")
        if not _call_bool(runtime, f"{unit}.get_canScout()"):
            raise ValueError(f"Unit {unit_id} cannot scout right now.")
        return unit
    raise ValueError(f"Owned unit {unit_id} was not found.")


def _find_scout_target(runtime, target_id: int) -> str:
    """Find a currently legal hidden neighbour without reading its contents."""
    queue = []
    seen = set()

    for index in range(runtime.array_length("this.state.me.zones")):
        zone = f"this.state.me.zones[{index}]"
        if not _call_bool(runtime, f"this.state.me.hasDiscovered({zone})"):
            raise RuntimeError("An owned zone is not discovered.")
        queue.append(zone)

    while queue:
        zone = queue.pop(0)
        zone_id = int(runtime.evaluate(f"{zone}.id"))
        if zone_id in seen:
            continue
        seen.add(zone_id)

        for index in range(runtime.array_length(f"{zone}.next")):
            neighbour = f"{zone}.next[{index}]"
            if not _call_bool(runtime, f"this.state.me.hasDiscovered({neighbour})"):
                if int(runtime.evaluate(f"{neighbour}.id")) != target_id:
                    continue
                if not _call_bool(runtime, f"{neighbour}.canBeScouted(this.state.me, null)"):
                    raise ValueError(f"Zone {target_id} cannot be scouted right now.")
                return neighbour
            queue.append(neighbour)

    raise ValueError(f"Zone {target_id} is not a scoutable hidden neighbour.")


def scout_zone(runtime, unit_id: int, zone_id: int) -> dict:
    """Send one currently eligible owned scout through Northgard's move order."""
    unit = _find_scout(runtime, unit_id)
    target = _find_scout_target(runtime, zone_id)
    runtime.call_native(f"{unit}.moveToZone({target}, false, null, null)")
    return {"unit_id": unit_id, "zone_id": zone_id, "scouting": True}
