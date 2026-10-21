"""Read owned unit professions and locations for assignment decisions."""

import json

from odin.actions.players import resolve_player
from odin.observations.units import load_unit_schema


def list_unit_jobs(runtime, *, player_id: int | None = None) -> dict:
    """Map living unit UIDs to professions, without sending any orders."""
    player = resolve_player(runtime, player_id)
    catalogue = load_unit_schema()
    unit_jobs = {}
    for index in range(runtime.array_length(f"{player}.units")):
        unit = f"{player}.units[{index}]"
        if runtime.evaluate(f"{unit}.owner == {player}") != "true":
            continue
        if runtime.call_native(f"{unit}.get_isDead()") != "false":
            continue
        unit_id = str(int(runtime.evaluate(f"{unit}.__uid")))
        engine_id = json.loads(runtime.evaluate(f"{unit}.kind"))
        if not isinstance(engine_id, str) or not engine_id:
            raise RuntimeError(f"Expected a unit ID from {unit}.kind")
        zone_id = None
        if runtime.evaluate(f"{unit}.zone == null") == "false":
            zone_id = int(runtime.evaluate(f"{unit}.zone.id"))
        job = catalogue["family_by_engine_id"].get(engine_id)
        if job is None and runtime.call_native(f"{unit}.get_isWarchief()") == "true":
            job = "warchief"
        unit_jobs[unit_id] = {
            "job": job,
            "engine_id": engine_id,
            "zone_id": zone_id,
        }
    return {
        "unit_jobs": dict(sorted(unit_jobs.items(), key=lambda entry: int(entry[0]))),
    }
