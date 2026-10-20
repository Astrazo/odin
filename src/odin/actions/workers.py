"""Resolve semantic worker and building choices to current owned identities."""

import json

from odin.actions.assignments import assign_to_building, find_owned_building, preview_assignment
from odin.actions.players import resolve_player
from odin.observations.buildings import load_building_schema
from odin.observations.construction import read_builder_assignments
from odin.observations.units import load_unit_schema
from odin.tools.unit_jobs import list_unit_jobs


def _worker_candidates(runtime, job: str, source_zone_id: int, player_id: int | None) -> list[int]:
    """Read living owned candidates from the current profession/zone map."""
    job = job.lower().replace("-", "_")
    if job not in load_unit_schema()["unit_ids"]:
        raise ValueError(f"Unknown worker profession: {job!r}")
    jobs = list_unit_jobs(runtime, player_id=player_id)["unit_jobs"]
    candidates = sorted(
        int(unit_id)
        for unit_id, worker in jobs.items()
        if worker["job"] == job and worker["zone_id"] == source_zone_id
    )
    if not candidates:
        raise ValueError(f"No living owned {job} in zone {source_zone_id}.")
    return candidates


def resolve_worker(
    runtime, job: str, source_zone_id: int,
    *, building_id: int | None = None, player_id: int | None = None,
) -> int:
    """Choose the lowest matching UID, checking target eligibility if supplied."""
    candidates = _worker_candidates(runtime, job, source_zone_id, player_id)
    for unit_id in candidates:
        if building_id is None:
            return unit_id
        preview = preview_assignment(runtime, unit_id, building_id, player_id=player_id)
        if preview["can_assign"]:
            return unit_id
    target = "" if building_id is None else f" eligible for building {building_id}"
    raise ValueError(f"No living owned {job} in zone {source_zone_id}{target}.")


def _building_candidates(
    runtime, building: int | str, target_zone_id: int | None,
    construction: bool, player_id: int | None,
) -> tuple[list[int], int]:
    """Resolve current targets by zone, semantic family and construction state."""
    if isinstance(building, int) or building.isdecimal():
        if target_zone_id is not None or construction:
            raise ValueError("Use destination zone/construction state with a building family, not a UID.")
        player = resolve_player(runtime, player_id)
        expression = find_owned_building(runtime, int(building), player)
        zone_id = int(runtime.evaluate(f"{expression}.zone.id"))
        return [int(building)], zone_id

    family = building.lower().replace("-", "_")
    catalogue = load_building_schema()
    if family not in catalogue["building_ids"]:
        raise ValueError(f"Unknown building family: {family!r}")
    if target_zone_id is None:
        raise ValueError("Supply a destination zone when selecting a building family.")
    player = resolve_player(runtime, player_id)
    candidates = []
    for index in range(runtime.array_length(f"{player}.zones")):
        zone = f"{player}.zones[{index}]"
        if int(runtime.evaluate(f"{zone}.id")) != target_zone_id:
            continue
        if runtime.call_native(f"{zone}.getOwner() == {player}") != "true":
            raise ValueError(f"Destination zone {target_zone_id} is no longer owned.")
        for building_index in range(runtime.array_length(f"{zone}.buildings")):
            candidate = f"{zone}.buildings[{building_index}]"
            kind = json.loads(runtime.call_native(f"{candidate}.get_id()"))
            if (kind == "Construction") != construction:
                continue
            if construction:
                kind = json.loads(runtime.call_native(f"{candidate}.get_realKind()"))
            if catalogue["family_by_engine_id"].get(kind) == family:
                candidates.append(int(runtime.evaluate(f"{candidate}.__uid")))
        break
    if not candidates:
        state = "construction site" if construction else "completed building"
        raise ValueError(f"No owned {family} {state} in zone {target_zone_id}.")
    if construction:
        assignments = read_builder_assignments(runtime, player=player)
        # The zone feature reports unstaffed sites. Prefer those over sites
        # already assigned a worker, including a worker travelling from afar.
        return sorted(candidates, key=lambda uid: (bool(assignments.get(uid)), uid)), target_zone_id
    return sorted(candidates), target_zone_id


def resolve_assignment(
    runtime, building: int | str, *, job: str | None = None,
    source_zone_id: int | None = None, unit_id: int | None = None,
    target_zone_id: int | None = None, construction: bool = False,
    player_id: int | None = None,
) -> dict:
    """Resolve both ends of a semantic assignment without sending an order.

    Workers and buildings are interchangeable within the selected groups.
    Prefer unstaffed construction, then building UID and worker UID order.
    Completion is handled by fresh state; construction never falls back to a
    completed building (or vice versa).
    """
    if job is None and source_zone_id is not None:
        raise ValueError("Supply a profession when selecting a source zone.")
    if (unit_id is None) == (job is None):
        raise ValueError("Choose a worker UID or profession/source zone.")
    building_ids, building_zone_id = _building_candidates(runtime, building, target_zone_id, construction, player_id)
    if source_zone_id is None:
        source_zone_id = building_zone_id
    unit_ids = [unit_id] if unit_id is not None else _worker_candidates(runtime, job, source_zone_id, player_id)
    for building_id in building_ids:
        for candidate_id in unit_ids:
            preview = preview_assignment(runtime, candidate_id, building_id, player_id=player_id)
            if not preview["can_assign"]:
                continue
            if job is not None:
                preview["worker_job"] = job.lower().replace("-", "_")
                preview["source_zone_id"] = source_zone_id
            if target_zone_id is not None:
                preview["building_family"] = str(building).lower().replace("-", "_")
                preview["target_zone_id"] = target_zone_id
                preview["construction"] = construction
            return preview
    raise ValueError("No eligible worker/building pair in the requested groups.")


def assign_worker_to_building(
    runtime, job: str, source_zone_id: int | None = None, building_id: int | str | None = None,
    *, target_zone_id: int | None = None, construction: bool = False,
    player_id: int | None = None,
) -> dict:
    """Resolve a profession/zone choice, then dispatch one normal assignment."""
    if building_id is None:
        raise ValueError("Supply a building UID or family for assignment.")
    selection = resolve_assignment(
        runtime, building_id, job=job, source_zone_id=source_zone_id,
        target_zone_id=target_zone_id, construction=construction, player_id=player_id,
    )
    result = assign_to_building(runtime, selection["unit_id"], selection["building_id"], player_id=player_id)
    return {**selection, **result}
