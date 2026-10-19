"""Building counts and legal build actions aligned with the zone graph."""

import hashlib
import json
from pathlib import Path


BUILDING_SCHEMA_PATH = Path(__file__).parents[1] / "data" / "building_schema.json"


def _call_bool(runtime, expression: str) -> bool:
    result = runtime.call_native(expression)
    if result not in ("true", "false"):
        raise RuntimeError(f"Expected a Boolean from {expression}: {result!r}")
    return result == "true"


def _call_string(runtime, expression: str) -> str | None:
    result = runtime.call_native(expression)
    if result == "null":
        return None
    value = json.loads(result)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Expected a building ID from {expression}: {result!r}")
    return value


def load_building_schema() -> dict:
    """Load the small, reviewed building vocabulary for the current rollout."""
    encoded = BUILDING_SCHEMA_PATH.read_bytes()
    schema = json.loads(encoded)
    families = schema.get("families")
    if not isinstance(families, list) or not families:
        raise ValueError("Building schema must contain at least one family.")

    building_ids = []
    family_by_engine_id = {}
    for family in families:
        identifier = family.get("id")
        engine_ids = family.get("engine_ids")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("Building family has an invalid ID.")
        if not isinstance(engine_ids, list) or not engine_ids:
            raise ValueError(f"Building family {identifier!r} has no engine IDs.")
        if identifier in building_ids:
            raise ValueError(f"Building schema has duplicate family {identifier!r}.")
        building_ids.append(identifier)

        for engine_id in engine_ids:
            if not isinstance(engine_id, str) or not engine_id:
                raise ValueError(f"Building family {identifier!r} has an invalid engine ID.")
            if engine_id in family_by_engine_id:
                raise ValueError(f"Engine building {engine_id!r} is mapped twice.")
            family_by_engine_id[engine_id] = identifier

    return {
        "building_ids": building_ids,
        "family_by_engine_id": family_by_engine_id,
        "schema_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _available_buildings(runtime, zone: str) -> set[str]:
    expression = (
        f"{zone}.getAvailableBuildings("
        "this.state.me, null, null, null, null)"
    )
    available = set()
    for index in range(runtime.array_length(expression)):
        identifier = json.loads(runtime.evaluate(f"{expression}[{index}].id"))
        if not isinstance(identifier, str) or not identifier:
            raise RuntimeError("Native building availability returned an invalid ID.")
        available.add(identifier)
    return available


def observe_buildings(runtime, catalogue: dict, graph: dict) -> dict:
    """Return zone-node building features and legal build actions."""
    building_ids = catalogue["building_ids"]
    column_by_id = {
        identifier: column
        for column, identifier in enumerate(building_ids)
    }
    completed_rows = []
    construction_rows = []
    action_rows = []

    for zone_id in graph["zone_ids"]:
        node = graph["nodes"][zone_id]
        zone = node["expression"]
        completed = [0] * len(building_ids)
        construction = [0] * len(building_ids)

        for index in range(runtime.array_length(f"{zone}.buildings")):
            building = f"{zone}.buildings[{index}]"
            current_id = _call_string(runtime, f"{building}.get_id()")
            real_id = _call_string(runtime, f"{building}.get_realKind()")

            if current_id == "Construction":
                family = catalogue["family_by_engine_id"].get(real_id)
                column = column_by_id.get(family)
                if column is not None:
                    construction[column] += 1
            else:
                player_built = _call_bool(runtime, f"{building}.isPlayerBuilt()")
                base_kind = json.loads(runtime.evaluate(f"{building}.baseKind"))
                if player_built or base_kind == "TownHall":
                    family = catalogue["family_by_engine_id"].get(current_id)
                    column = column_by_id.get(family)
                    if column is not None:
                        completed[column] += 1

        available = set()
        if node["owner"]["owned"]:
            available = _available_buildings(runtime, zone)

        completed_rows.append(completed)
        construction_rows.append(construction)
        action_rows.append([
            1.0 if any(
                engine_id in available
                for engine_id, family in catalogue["family_by_engine_id"].items()
                if family == identifier
            ) else 0.0
            for identifier in building_ids
        ])

    return {
        "feature_names": [
            f"building_{identifier}"
            for identifier in building_ids
        ] + [
            f"construction_{identifier}"
            for identifier in building_ids
        ],
        "x": [
            completed + construction
            for completed, construction in zip(
                completed_rows,
                construction_rows,
                strict=True,
            )
        ],
        "building_ids": building_ids,
        "schema_sha256": catalogue["schema_sha256"],
        "zone_ids": graph["zone_ids"],
        "build_action_mask": action_rows,
    }
