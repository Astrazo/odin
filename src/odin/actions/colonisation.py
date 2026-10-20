"""Preview and request normal, paid colonisation of a discovered border zone."""

import json

from odin.actions.players import require_offline_host, require_paused_bot, resolve_player


def _border_zones(runtime, player: str) -> dict[int, dict]:
    """Resolve discovered, unowned neighbours without inspecting hidden contents."""
    targets = {}
    for index in range(runtime.array_length(f"{player}.zones")):
        root = f"{player}.zones[{index}]"
        if runtime.call_native(f"{root}.getOwner() == {player}") != "true":
            raise RuntimeError("Player.zones contains a zone no longer owned by that player.")
        root_id = int(runtime.evaluate(f"{root}.id"))
        for neighbour_index in range(runtime.array_length(f"{root}.next")):
            zone = f"{root}.next[{neighbour_index}]"
            if runtime.call_native(f"{player}.hasDiscovered({zone})") != "true":
                continue
            if runtime.call_native(f"{zone}.getOwner() == null") != "true":
                continue
            zone_id = int(runtime.evaluate(f"{zone}.id"))
            if zone_id not in targets:
                targets[zone_id] = {"expression": zone, "adjacent_to": []}
            targets[zone_id]["adjacent_to"].append(root_id)
    return targets


def _preview_zone(runtime, player: str, zone_id: int, target: dict) -> dict:
    zone = target["expression"]
    # CurrentRes expands to Res(the native cost's resource), enabling the full
    # affordability/cooldown checks. Passing null here skips those checks.
    reason = runtime.call_native(
        f"{player}.world.getNoColonizeReason({zone}, ColonizeTestType.CurrentRes)"
    )
    cost = f"{player}.world.colonizeCost({zone}, null, null, null, null)"
    resource = json.loads(runtime.evaluate(f"{cost}.res"))
    quantity = int(runtime.evaluate(f"{cost}.qty"))
    if not isinstance(resource, str) or not resource or quantity < 0:
        raise RuntimeError("Invalid native colonisation cost.")
    return {
        "zone_id": zone_id,
        "adjacent_to": sorted(set(target["adjacent_to"])),
        "can_colonise": reason == "null",
        "reason": None if reason == "null" else reason,
        "cost": {"resource": resource, "quantity": quantity},
    }


def list_colonisation_zones(runtime, *, player_id: int | None = None) -> dict:
    """List legal targets and blocked borders, including native costs/reasons."""
    player = resolve_player(runtime, player_id)
    available = []
    blocked = []
    for zone_id, target in sorted(_border_zones(runtime, player).items()):
        preview = _preview_zone(runtime, player, zone_id, target)
        if preview["can_colonise"]:
            available.append(preview)
        else:
            blocked.append(preview)
    return {"colonisable_zones": available, "blocked_zones": blocked}


def preview_colonisation(runtime, zone_id: int, *, player_id: int | None = None) -> dict:
    """Inspect one discovered border zone without sending a request."""
    player = resolve_player(runtime, player_id)
    targets = _border_zones(runtime, player)
    if zone_id not in targets:
        raise ValueError(f"Zone {zone_id} is not a discovered, unowned neighbour of this player.")
    return _preview_zone(runtime, player, zone_id, targets[zone_id])


def colonise_zone(runtime, zone_id: int, *, player_id: int | None = None) -> dict:
    """Send one normal world-component RPC and confirm the immediate start."""
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    if runtime.evaluate(f"{player} == this.state.me") != "true":
        require_paused_bot(runtime, player)
        if runtime.evaluate(f"{player}.skipAIOrder") != "true":
            raise RuntimeError("Stop the selected bot's AI orders before colonising.")
    targets = _border_zones(runtime, player)
    if zone_id not in targets:
        raise ValueError(f"Zone {zone_id} is not a discovered, unowned neighbour of this player.")
    target = targets[zone_id]
    preview = _preview_zone(runtime, player, zone_id, target)
    if not preview["can_colonise"]:
        raise RuntimeError(f"Northgard rejected colonisation: {preview['reason']}.")
    zone = target["expression"]
    # Use the public RPC, which revalidates and pays the native cost. The
    # similarly named ScriptApi.colonize is a debug takeover and bypasses this.
    runtime.call_native(f"{player}.world.startColonize({zone}, null)")
    started = runtime.evaluate(f"{zone}.colonizeBy == {player}") == "true"
    owned = runtime.call_native(f"{zone}.getOwner() == {player}") == "true"
    if not started and not owned:
        raise RuntimeError("Colonisation was not confirmed; inspect the zone before retrying.")
    result = {**preview, "requested": True, "colonisation_observed": True, "owned": owned}
    if player_id is not None:
        result["player_id"] = player_id
    return result
