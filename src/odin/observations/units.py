"""Zone unit counts and owned unit identities with current professions."""

import hashlib
import json
from pathlib import Path


UNIT_SCHEMA_PATH = Path(__file__).parents[1] / "data" / "unit_schema.json"


def load_unit_schema() -> dict:
    """Load the reviewed, fixed unit vocabulary for the current clan rollout."""
    encoded = UNIT_SCHEMA_PATH.read_bytes()
    schema = json.loads(encoded)
    families = schema.get("families")
    neutral_families = schema.get("neutral_families")
    if not isinstance(families, list) or not families:
        raise ValueError("Unit schema must contain at least one family.")
    if not isinstance(neutral_families, list) or not neutral_families:
        raise ValueError("Unit schema must contain neutral unit families.")

    def read_families(families, description: str) -> tuple[list[str], dict[str, str]]:
        identifiers = []
        family_by_engine_id = {}
        for family in families:
            identifier = family.get("id")
            engine_ids = family.get("engine_ids")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"{description} unit family has an invalid ID.")
            if not isinstance(engine_ids, list) or not engine_ids:
                raise ValueError(f"Unit family {identifier!r} has no engine IDs.")
            if identifier in identifiers:
                raise ValueError(f"Unit schema has duplicate family {identifier!r}.")
            identifiers.append(identifier)

            for engine_id in engine_ids:
                if not isinstance(engine_id, str) or not engine_id:
                    raise ValueError(f"Unit family {identifier!r} has an invalid engine ID.")
                if engine_id in family_by_engine_id:
                    raise ValueError(f"Engine unit {engine_id!r} is mapped twice.")
                family_by_engine_id[engine_id] = identifier
        return identifiers, family_by_engine_id

    unit_ids, family_by_engine_id = read_families(families, "Player")
    neutral_unit_ids, neutral_family_by_engine_id = read_families(
        neutral_families,
        "Neutral",
    )

    return {
        "unit_ids": unit_ids,
        "family_by_engine_id": family_by_engine_id,
        "neutral_unit_ids": neutral_unit_ids,
        "neutral_family_by_engine_id": neutral_family_by_engine_id,
        "schema_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _call_bool(runtime, expression: str) -> bool:
    result = runtime.call_native(expression)
    if result not in ("true", "false"):
        raise RuntimeError(f"Expected a Boolean from {expression}: {result!r}")
    return result == "true"


def _unit_side(runtime, unit: str) -> str:
    """Classify a live unit by the controlled player's team."""
    if _call_bool(runtime, f"{unit}.owner == this.state.me"):
        return "friendly"
    if _call_bool(runtime, f"{unit}.owner == null"):
        return "neutral"
    if _call_bool(runtime, f"{unit}.owner.get_team() == this.state.me.get_team()"):
        return "friendly"
    return "enemy"


def observe_units(runtime, catalogue: dict, graph: dict) -> dict:
    """Return zone counts and owned unit professions from the same stopped frame."""
    unit_ids = catalogue["unit_ids"]
    neutral_unit_ids = catalogue["neutral_unit_ids"]
    column_by_id = {
        identifier: column
        for column, identifier in enumerate(unit_ids)
    }
    neutral_column_by_id = {
        identifier: column
        for column, identifier in enumerate(neutral_unit_ids)
    }
    rows = []
    unmapped = set()
    scout_unit_mask = []
    unit_jobs = {}

    for zone_id in graph["zone_ids"]:
        zone = graph["nodes"][zone_id]["expression"]
        friendly = [0] * len(unit_ids)
        enemy = [0] * len(unit_ids)
        neutral = [0] * len(neutral_unit_ids)

        for index in range(runtime.array_length(f"{zone}.units")):
            unit = f"{zone}.units[{index}]"
            if _call_bool(runtime, f"{unit}.get_isDead()"):
                continue

            side = _unit_side(runtime, unit)
            owned = side == "friendly" and _call_bool(runtime, f"{unit}.owner == this.state.me")
            if owned:
                if _call_bool(runtime, f"{unit}.get_canScout()"):
                    scout_unit_mask.append({
                        "unit_id": int(runtime.evaluate(f"{unit}.__uid")),
                        "zone_id": zone_id,
                    })
            engine_id = json.loads(runtime.evaluate(f"{unit}.kind"))
            if not isinstance(engine_id, str) or not engine_id:
                raise RuntimeError(f"Expected a unit ID from {unit}.kind")
            families = catalogue["family_by_engine_id"]
            columns = column_by_id
            if side == "neutral":
                families = catalogue["neutral_family_by_engine_id"]
                columns = neutral_column_by_id
            family = families.get(engine_id)
            # Cosmetic chief kinds can be absent from the ordinary unit list.
            if family is None and side != "neutral":
                if _call_bool(runtime, f"{unit}.get_isWarchief()"):
                    family = "warchief"
            if owned:
                unit_id = str(int(runtime.evaluate(f"{unit}.__uid")))
                unit_jobs[unit_id] = {
                    "job": family,
                    "engine_id": engine_id,
                    "zone_id": zone_id,
                }
            column = columns.get(family)
            if column is None:
                unmapped.add((zone_id, side, engine_id))
                continue
            if side == "friendly":
                friendly[column] += 1
            elif side == "enemy":
                enemy[column] += 1
            else:
                neutral[column] += 1

        rows.append(friendly + enemy + neutral)

    return {
        "feature_names": [
            f"friendly_{identifier}"
            for identifier in unit_ids
        ] + [
            f"enemy_{identifier}"
            for identifier in unit_ids
        ] + [
            f"neutral_{identifier}"
            for identifier in neutral_unit_ids
        ],
        "x": rows,
        "unit_ids": unit_ids,
        "neutral_unit_ids": neutral_unit_ids,
        "schema_sha256": catalogue["schema_sha256"],
        "unit_jobs": dict(sorted(unit_jobs.items(), key=lambda entry: int(entry[0]))),
        "scout_unit_mask": sorted(scout_unit_mask, key=lambda unit: unit["unit_id"]),
        "unmapped_units": [
            {"zone_id": zone_id, "side": side, "engine_id": engine_id}
            for zone_id, side, engine_id in sorted(unmapped)
        ],
    }
