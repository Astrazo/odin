"""Resolve a building family and request its next normal paid upgrade."""

import json

from odin.actions.assignments import find_owned_building
from odin.actions.players import require_offline_host, require_paused_bot, resolve_player
from odin.actions.workers import resolve_building_candidates


def preview_upgrade(
    runtime, building: int | str, *, zone_id: int | None = None,
    player_id: int | None = None,
) -> dict:
    """Prefer an eligible member of the requested family, then lowest UID."""
    player = resolve_player(runtime, player_id)
    candidates, zone_id = resolve_building_candidates(runtime, building, zone_id, False, player_id)
    previews = []
    for uid in candidates:
        target = find_owned_building(runtime, uid, player)
        kind = json.loads(runtime.call_native(f"{target}.get_id()"))
        if kind == "Construction":
            raise ValueError("Finish construction before upgrading a building.")
        reason = runtime.call_native(f"{target}.getNoUpgradeReason()")
        cost = f"{target}.getUpgradeCost(null)"
        costs = []
        if runtime.call_native(cost) != "null":
            for index in range(runtime.array_length(cost)):
                entry = f"{cost}[{index}]"
                resource = json.loads(runtime.evaluate(f"{entry}.res"))
                quantity = int(runtime.evaluate(f"{entry}.qty"))
                if not isinstance(resource, str) or not resource or quantity < 0:
                    raise RuntimeError("Invalid native building upgrade cost.")
                costs.append({"resource": resource, "quantity": quantity})
        preview = {
            "building_id": uid, "engine_id": kind, "zone_id": zone_id,
            "upgrade_level": int(runtime.evaluate(f"{target}.upgraded")),
            "can_upgrade": reason == "null",
            "reason": None if reason == "null" else reason,
            "cost": costs,
            "free_upgrade": runtime.call_native(
                f"{player}.upgrades.hasFreeBuildingUpgrades({target}, null)"
            ) == "true",
        }
        if player_id is not None:
            preview["player_id"] = player_id
        if preview["can_upgrade"]:
            return preview
        previews.append(preview)
    # A blocked preview still explains what prevents the family's next upgrade.
    return previews[0]


def upgrade_building(
    runtime, building: int | str, *, zone_id: int | None = None,
    player_id: int | None = None,
) -> dict:
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    if runtime.evaluate(f"{player} == this.state.me") != "true":
        require_paused_bot(runtime, player)
        if runtime.evaluate(f"{player}.skipAIOrder") != "true":
            raise RuntimeError("Stop the selected bot's AI orders before upgrading buildings.")
    preview = preview_upgrade(runtime, building, zone_id=zone_id, player_id=player_id)
    if not preview["can_upgrade"]:
        raise ValueError(f"Cannot upgrade building {preview['building_id']}: {preview['reason']}.")
    target = find_owned_building(runtime, preview["building_id"], player)
    # Null chooses the next ordinary level, rather than a transformation branch.
    # The public RPC uses normal payment/free-upgrade handling.
    runtime.call_native(f"{target}.doUpgrade(null, null)")
    target = find_owned_building(runtime, preview["building_id"], player)
    level = int(runtime.evaluate(f"{target}.upgraded"))
    if level <= preview["upgrade_level"]:
        raise RuntimeError("Upgrade was not confirmed; inspect the building before retrying.")
    return {**preview, "requested": True, "upgrade_observed": True,
            "previous_upgrade_level": preview["upgrade_level"], "upgrade_level": level}
