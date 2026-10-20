"""Build one reviewed building family in an owned Northgard zone."""

import json


def _owned_zone(runtime, zone_id: int) -> str:
    """Return the current expression for one of the controlled player's zones."""
    for index in range(runtime.array_length("this.state.me.zones")):
        zone = f"this.state.me.zones[{index}]"
        if int(runtime.evaluate(f"{zone}.id")) != zone_id:
            continue
        if runtime.call_native(f"{zone}.getOwner() == this.state.me") != "true":
            raise RuntimeError(f"Zone {zone_id} is no longer owned by this player.")
        return zone
    raise ValueError(f"Zone {zone_id} is not owned by this player.")


def build_building(
    runtime, zone_id: int, building_id: str, catalogue: dict,
) -> dict:
    """Place one building; worker assignment is a separate policy action."""
    building_id = building_id.replace("-", "_")
    if building_id not in catalogue["building_ids"]:
        raise ValueError(f"Unknown building family: {building_id!r}")

    zone = _owned_zone(runtime, zone_id)
    available = (
        f"{zone}.getAvailableBuildings("
        "this.state.me, null, null, null, null)"
    )
    selected_index = None
    selected_engine_id = None
    for index in range(runtime.array_length(available)):
        engine_id = json.loads(runtime.evaluate(f"{available}[{index}].id"))
        if catalogue["family_by_engine_id"].get(engine_id) == building_id:
            selected_index = index
            selected_engine_id = engine_id
            break

    if selected_index is None:
        raise RuntimeError(
            f"{building_id!r} is not currently buildable in owned zone {zone_id}."
        )

    previous_ids = {
        int(runtime.evaluate(f"{zone}.buildings[{index}].__uid"))
        for index in range(runtime.array_length(f"{zone}.buildings"))
    }

    # Use the definition returned by Northgard, never a Python-created string or
    # virtual object. The game performs its normal placement and cost checks.
    result = runtime.call_native(
        f"Tools.buildInZone(this.state.me, {available}[{selected_index}], {zone}, null)"
    )
    if result == "null":
        raise RuntimeError(
            "Northgard could not find a placement for the selected building."
        )
    response = {
        "zone_id": zone_id,
        "building_id": building_id,
        "engine_id": selected_engine_id,
        "requested": True,
        "placed": True,
        "construction_id": None,
    }

    # The debugger remains stopped throughout. Match a new UID and exact kind;
    # never re-evaluate the placement expression just to inspect its result.
    try:
        candidates = []
        for index in range(runtime.array_length(f"{zone}.buildings")):
            building = f"{zone}.buildings[{index}]"
            native_id = int(runtime.evaluate(f"{building}.__uid"))
            if native_id in previous_ids:
                continue
            if json.loads(runtime.call_native(f"{building}.get_id()")) != "Construction":
                continue
            if json.loads(runtime.call_native(f"{building}.get_realKind()")) == selected_engine_id:
                candidates.append(native_id)
        if len(candidates) != 1:
            raise RuntimeError("Could not uniquely identify the new construction site.")
        response["construction_id"] = candidates[0]
    except (RuntimeError, ValueError, OSError, TimeoutError) as error:
        response["construction_error"] = str(error)
    return response
