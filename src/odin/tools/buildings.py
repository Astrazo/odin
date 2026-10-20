"""List building runtime IDs for one player-owned zone."""

import json

from odin.actions.players import resolve_player


def list_zone_buildings(runtime, zone_id: int, *, player_id: int | None = None) -> dict:
    """Return the current building IDs and kinds in one player zone."""
    player = resolve_player(runtime, player_id)
    zone = None
    for index in range(runtime.array_length(f"{player}.zones")):
        candidate = f"{player}.zones[{index}]"
        if int(runtime.evaluate(f"{candidate}.id")) == zone_id:
            zone = candidate
            break
    if zone is None:
        raise ValueError(f"Zone {zone_id} was not found in the selected player's zones.")

    buildings = []
    for index in range(runtime.array_length(f"{zone}.buildings")):
        building = f"{zone}.buildings[{index}]"
        buildings.append({
            "building_id": int(runtime.evaluate(f"{building}.__uid")),
            "kind": json.loads(runtime.evaluate(f"{building}.kind")),
        })

    return {"zone_id": zone_id, "buildings": sorted(buildings, key=lambda item: item["building_id"])}
