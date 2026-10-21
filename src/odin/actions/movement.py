"""Move semantic groups of owned units between discovered zones."""

from odin.actions.assignments import find_owned_unit
from odin.actions.players import require_offline_host, require_paused_bot, resolve_player
from odin.observations.units import load_unit_schema
from odin.tools.unit_jobs import list_unit_jobs


def _native_bool(runtime, expression: str) -> bool:
    result = runtime.call_native(expression)
    if result not in ("true", "false"):
        raise RuntimeError(f"Expected a Boolean from {expression}: {result!r}")
    return result == "true"


def _find_destination(runtime, player: str, source: str, zone_id: int) -> str:
    """Resolve visible destinations from owned territory and the unit's zone."""
    queue = [
        f"{player}.zones[{index}]"
        for index in range(runtime.array_length(f"{player}.zones"))
    ]
    # A scout can physically occupy a zone that is not fully revealed yet.
    # Owned roots still let it move home without inspecting that hidden zone.
    queue.append(source)
    seen = set()
    index = 0
    while index < len(queue):
        zone = queue[index]
        index += 1
        if not _native_bool(runtime, f"{player}.hasDiscovered({zone})"):
            continue
        current_id = int(runtime.evaluate(f"{zone}.id"))
        if current_id in seen:
            continue
        seen.add(current_id)
        if current_id == zone_id:
            return zone
        for neighbour in range(runtime.array_length(f"{zone}.next")):
            queue.append(f"{zone}.next[{neighbour}]")
    raise ValueError(f"Destination zone {zone_id} was not found in the discovered map.")


def _prepare_move(
    runtime, from_zone: int, to_zone: int, who: str,
    count: int | None, player_id: int | None,
) -> dict:
    if from_zone == to_zone:
        raise ValueError("Source and destination zones must differ.")
    if count is not None and (type(count) is not int or count < 1):
        raise ValueError("Movement count must be a positive integer.")
    who = who.lower().replace("-", "_")
    if who not in {"all", "military"} and who not in load_unit_schema()["unit_ids"]:
        raise ValueError(f"Unknown movement selector: {who!r}.")
    player = resolve_player(runtime, player_id)
    jobs = list_unit_jobs(runtime, player_id=player_id)["unit_jobs"]
    candidates = sorted(
        int(unit_id) for unit_id, unit in jobs.items()
        if unit["zone_id"] == from_zone
        and (who in {"all", "military"} or unit["job"] == who)
    )
    if not candidates:
        raise ValueError(f"No living owned {who} units in source zone {from_zone}.")
    source_unit = find_owned_unit(runtime, candidates[0], player)
    destination = _find_destination(runtime, player, f"{source_unit}.zone", to_zone)
    eligible = []
    fighters = {}
    excluded = []
    already_ordered = []
    for unit_id in candidates:
        unit = find_owned_unit(runtime, unit_id, player)
        fighter = _native_bool(runtime, f"{unit}.get_isFighter()")
        if who == "military" and not fighter:
            continue
        if not _native_bool(runtime, f"{unit}.isControlable(null)"):
            excluded.append({"unit_id": unit_id, "reason": "not_controllable"})
            continue
        if not _native_bool(runtime, f"{unit}.canGoTo({destination}, null)"):
            excluded.append({"unit_id": unit_id, "reason": "cannot_reach_destination"})
            continue
        eligible.append(unit_id)
        fighters[unit_id] = fighter
        if runtime.evaluate(f"{unit}.goingTo == {destination}") == "true":
            if not fighter or runtime.evaluate(f"{unit}.canAttack") == "true":
                already_ordered.append(unit_id)
    selected = eligible if count is None else eligible[:count]
    reason = None
    if not selected:
        reason = f"No eligible {who} units can move from zone {from_zone} to zone {to_zone}."
        if not excluded:
            reason = f"No living owned {who} units in source zone {from_zone}."
        for rejection in excluded:
            unit_id = rejection["unit_id"]
            job = jobs[str(unit_id)]["job"]
            if rejection["reason"] == "cannot_reach_destination":
                reason += f" The game route check rejected {job} {unit_id}."
            else:
                reason += f" {job.capitalize()} {unit_id} is not controllable."
    elif count is not None and len(selected) < count:
        reason = f"Requested {count} units but only {len(eligible)} are eligible."
    report = {
        "from_zone": from_zone, "to_zone": to_zone, "who": who,
        "count_requested": count, "eligible_count": len(eligible),
        "unit_ids": selected, "already_ordered_unit_ids": [uid for uid in selected if uid in already_ordered],
        "excluded_units": excluded, "can_move": reason is None, "reason": reason,
    }
    if player_id is not None:
        report["player_id"] = player_id
    return {"report": report, "player": player, "destination": destination, "fighters": fighters}


def preview_move(
    runtime, from_zone: int, to_zone: int, who: str, *, count: int | None = None,
    player_id: int | None = None,
) -> dict:
    """Resolve selection and native movement eligibility without giving orders."""
    return _prepare_move(runtime, from_zone, to_zone, who, count, player_id)["report"]


def move_units(
    runtime, from_zone: int, to_zone: int, who: str, *, count: int | None = None,
    player_id: int | None = None,
) -> dict:
    """Send normal move orders once, reporting any partially dispatched group."""
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    if runtime.evaluate(f"{player} == this.state.me") != "true":
        require_paused_bot(runtime, player)
        if runtime.evaluate(f"{player}.skipAIOrder") != "true":
            raise RuntimeError("Stop the selected bot's AI orders before moving its units.")
    context = _prepare_move(runtime, from_zone, to_zone, who, count, player_id)
    report = context["report"]
    if not report["can_move"]:
        raise ValueError(report["reason"])
    destination = context["destination"]
    orders = []
    attempted = 0
    for unit_id in report["unit_ids"]:
        if unit_id in report["already_ordered_unit_ids"]:
            orders.append({"unit_id": unit_id, "status": "already_ordered"})
            continue
        try:
            unit = find_owned_unit(runtime, unit_id, player)
            can_attack = "true" if context["fighters"][unit_id] else "false"
            # This is the normal MoveTo action/RPC, not the strategic clan AI.
            # Fighters retain autonomous combat; civilian moves clear work links.
            attempted += 1
            runtime.call_native(f"{unit}.moveToZone({destination}, {can_attack}, null, null)")
            heading = runtime.evaluate(f"{unit}.goingTo == {destination}") == "true"
            arrived = runtime.evaluate(f"{unit}.zone == {destination}") == "true"
            if not heading and not arrived:
                raise RuntimeError("Movement order was not confirmed; inspect state before retrying.")
            orders.append({"unit_id": unit_id, "status": "ordered"})
        except (RuntimeError, ValueError, OSError, TimeoutError) as error:
            # Earlier orders may have succeeded. Do not retry, roll them back,
            # or send the remaining cohort when native state is uncertain.
            orders.append({"unit_id": unit_id, "status": "unconfirmed", "error": str(error)})
            break
    confirmed = len(orders) == len(report["unit_ids"]) and all(
        order["status"] in {"ordered", "already_ordered"} for order in orders
    )
    return {
        **report, "orders": orders, "orders_attempted": attempted,
        "orders_confirmed": confirmed,
        "not_attempted_unit_ids": report["unit_ids"][len(orders):],
    }
