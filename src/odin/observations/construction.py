"""Read construction staffing links, including workers in other zones."""


def read_builder_assignments(runtime, *, player: str = "this.state.me") -> dict[int, list[int]]:
    """Group living owned workers by their assigned building's current UID.

    An assignment is an order, not proof that the worker has arrived or is
    making progress. Read the whole player collection so travel is included.
    """
    assignments = {}
    for index in range(runtime.array_length(f"{player}.units")):
        unit = f"{player}.units[{index}]"
        if runtime.evaluate(f"{unit}.owner == {player}") != "true":
            continue
        if runtime.call_native(f"{unit}.get_isDead()") != "false":
            continue
        if runtime.evaluate(f"{unit}.assignTo == null") == "true":
            continue
        building_id = int(runtime.evaluate(f"{unit}.assignTo.__uid"))
        unit_id = int(runtime.evaluate(f"{unit}.__uid"))
        assignments.setdefault(building_id, []).append(unit_id)
    return {
        building_id: sorted(unit_ids)
        for building_id, unit_ids in assignments.items()
    }


def describe_construction_site(
    runtime, building: str, zone_id: int, engine_id: str | None,
    catalogue: dict, assignments: dict[int, list[int]],
) -> dict:
    """Use a fresh native UID; completion replaces the construction object."""
    building_id = int(runtime.evaluate(f"{building}.__uid"))
    worker_ids = assignments.get(building_id, [])
    return {
        "building_id": building_id,
        "zone_id": zone_id,
        "building_family": catalogue["family_by_engine_id"].get(engine_id),
        "engine_id": engine_id,
        "assigned_unit_ids": worker_ids,
        "has_assigned_worker": bool(worker_ids),
    }
