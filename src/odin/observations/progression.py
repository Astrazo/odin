"""Clan-wide lore choices and ordinary military path progression."""

import hashlib
import json
import math
import re

from odin.actions.players import resolve_player
from odin.observations.recruitment import (
    RECRUIT_IDS, RECRUIT_FEATURE_NAMES, observe_recruitment, encode_recruitment,
)


# Reviewed ordinary Viking trees. Exceptional clan research/boards need their
# own selection rules rather than inheriting a misleading legality mask.
SUPPORTED_CLANS = {"Wolf", "Bear", "Stag", "Goat", "Raven", "Boar", "Snake", "Horse"}
MILITARY_PATHS = {"leadership": 0, "guardian": 1, "legions": 2}


def semantic_name(identifier: str) -> str:
    """Turn named catalogue entries into stable, readable action labels."""
    label = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", identifier)
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def native_bool(runtime, expression: str) -> bool:
    result = runtime.call_native(expression)
    if result not in ("true", "false"):
        raise RuntimeError(f"Expected a Boolean from {expression}: {result!r}")
    return result == "true"


def load_progression_catalogue(runtime, *, player_id: int | None = None) -> dict:
    """Keep the entire clan tree in a stable order, including learned techs."""
    player = resolve_player(runtime, player_id)
    clan = json.loads(runtime.evaluate(f"{player}.clan"))
    if clan not in SUPPORTED_CLANS:
        raise ValueError(f"Progression selection is not reviewed for clan {clan!r}.")
    component = f"{player}.tech"
    if runtime.evaluate(f"{component} == null") != "false":
        raise RuntimeError("Player tech component is not initialized.")
    count = runtime.array_length(f"{component}.getAvailableTechs()")
    if not 1 <= count <= 256:
        raise RuntimeError("Unexpected clan tech catalogue size.")
    techs = {}
    for index in range(count):
        entry = f"{component}.availableTechs[{index}]"
        engine_id = json.loads(runtime.evaluate(f"{entry}.id"))
        name = json.loads(runtime.evaluate(f"{entry}.name"))
        if not isinstance(engine_id, str) or not engine_id or not isinstance(name, str):
            raise RuntimeError("Invalid native technology entry.")
        identifier = semantic_name(engine_id)
        if identifier in techs:
            raise RuntimeError("Duplicate semantic technology label.")
        techs[identifier] = {"engine_id": engine_id, "name": name, "expression": entry}

    count = runtime.array_length("Data.militaryPath.all")
    if not 1 <= count <= 256:
        raise RuntimeError("Unexpected military catalogue size.")
    abilities = {}
    for index in range(count):
        entry = f"Data.militaryPath.all[{index}]"
        group = int(runtime.evaluate(f"{entry}.group"))
        if group not in MILITARY_PATHS.values():
            continue
        engine_id = json.loads(runtime.evaluate(f"{entry}.id"))
        if not isinstance(engine_id, str) or not engine_id or engine_id in abilities:
            raise RuntimeError("Invalid military ability entry.")
        abilities[engine_id] = {
            "expression": entry, "group": group,
            "index": int(runtime.evaluate(f"{entry}.index")),
        }
    paths = {}
    for name, group in MILITARY_PATHS.items():
        entries = sorted(
            (identifier for identifier, ability in abilities.items() if ability["group"] == group),
            key=lambda identifier: (abilities[identifier]["index"], identifier),
        )
        # Native index is the full catalogue position, not a tier starting at
        # zero in each group (Guardian follows the Leadership rows).
        if not entries:
            raise RuntimeError(f"Missing first military ability for {name}.")
        paths[name] = entries

    xp_key = None
    for index in range(runtime.array_length("Data.resource.all")):
        entry = f"Data.resource.all[{index}].id"
        if json.loads(runtime.evaluate(entry)) == "MilitaryXP":
            xp_key = entry
            break
    if xp_key is None:
        raise RuntimeError("MilitaryXP resource was not found.")
    identity = {
        "clan": clan, "techs": {key: value["engine_id"] for key, value in sorted(techs.items())},
        "paths": paths, "recruit_ids": RECRUIT_IDS, "recruit_features": RECRUIT_FEATURE_NAMES,
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return {
        "player": player, "clan": clan, "techs": dict(sorted(techs.items())),
        "player_id": player_id,
        "abilities": abilities, "paths": paths, "xp_key": xp_key,
        "schema_sha256": digest,
    }


def observe_progression(runtime, catalogue: dict | None = None, *, player_id: int | None = None) -> dict:
    """Expose learned state and complete action masks without repeating lore stock."""
    if catalogue is None:
        catalogue = load_progression_catalogue(runtime, player_id=player_id)
    player = catalogue["player"]
    if json.loads(runtime.evaluate(f"{player}.clan")) != catalogue["clan"]:
        raise RuntimeError("Clan changed; reopen the environment to rebuild progression features.")
    component = f"{player}.tech"
    primary_array = f"{component}.militaryPathUnlocked.array"
    count = runtime.array_length(primary_array)
    if not 0 <= count <= 64:
        raise RuntimeError("Unexpected military unlock count.")
    primary = [json.loads(runtime.evaluate(f"{primary_array}[{index}]")) for index in range(count)]
    if len(set(primary)) != len(primary) or any(identifier not in catalogue["abilities"] for identifier in primary):
        raise RuntimeError("Primary military unlocks are outside the reviewed ordinary board.")
    groups = {catalogue["abilities"][identifier]["group"] for identifier in primary}
    if len(groups) > 1:
        raise RuntimeError("Primary unlocks span multiple military paths.")
    levels = int(runtime.call_native(f"{player}.getMilitaryXPLevelsCount()"))
    if not 1 <= levels <= 64:
        raise RuntimeError("Unexpected military XP threshold count.")
    threshold = int(runtime.call_native(f"{player}.getMilitaryXPLevel({count})")) if count < levels else 0
    xp = float(runtime.call_native(f'{player}.res.getResource({catalogue["xp_key"]}, null)'))
    values = {
        "next_lore_cost": int(runtime.call_native(f"{component}.getNextTechCost(null)")),
        "free_lore_choices": int(runtime.evaluate(f"{component}.freeTechPending")),
        "military_xp": xp,
        "military_path_unselected": not primary,
        "military_has_next_threshold": count < levels,
        "military_next_xp_threshold": threshold,
        "military_auto_unlock_next": native_bool(runtime, f"{component}.canAutoUnlockNextMilitaryPathAbility()"),
    }
    tech_choices = []
    for identifier, tech in catalogue["techs"].items():
        entry = tech["expression"]
        learned = native_bool(runtime, f"{component}.hasTech({entry}.id, null)")
        eligible = not learned and native_bool(runtime, f"{component}.canUnlockTech({entry}.id)")
        affordable = native_bool(runtime, f"{component}.canPayTech({entry})") if eligible else False
        can_research = eligible and affordable
        values[f"tech_{identifier}_unlocked"] = learned
        values[f"tech_{identifier}_can_research"] = can_research
        cost = int(runtime.call_native(f"{component}.getNextTechCost({entry})"))
        resource = json.loads(runtime.call_native(f"{component}.getTechPayRes({entry})"))
        tech_choices.append({
            "id": identifier, "engine_id": tech["engine_id"], "name": tech["name"],
            "unlocked": learned, "can_research": can_research,
            "prerequisites_met": eligible, "can_pay": affordable,
            "cost": {"resource": resource, "quantity": cost},
        })
    military_choices = []
    for name, identifiers in catalogue["paths"].items():
        first = catalogue["abilities"][identifiers[0]]["expression"]
        selected = MILITARY_PATHS[name] in groups
        # Only choose the first primary path. Subsequent ordinary unlocks belong
        # to the native auto-unlock loop; cross-path/free-path rules are separate.
        can_select = not primary and native_bool(runtime, f"{component}.canUnlockMiliPathAbility({first}.id)")
        values[f"military_path_{name}_selected"] = selected
        values[f"military_path_{name}_can_select"] = can_select
        military_choices.append({"id": name, "selected": selected, "can_select": can_select})
        for engine_id in identifiers:
            entry = catalogue["abilities"][engine_id]["expression"]
            values[f"military_{semantic_name(engine_id)}_unlocked"] = native_bool(
                runtime, f"{component}.hasMiliPathAbility({entry}.id, null)",
            )
    recruitment = observe_recruitment(runtime, player_id=catalogue["player_id"])
    encoded_recruitment = encode_recruitment(recruitment)
    values.update(zip(encoded_recruitment["feature_names"], encoded_recruitment["x"], strict=True))
    if any(not math.isfinite(value) or value < 0 for value in values.values()):
        raise RuntimeError("Invalid progression feature value.")
    return {
        "feature_names": list(values), "x": list(values.values()),
        "schema_sha256": catalogue["schema_sha256"], "clan": catalogue["clan"],
        "tech_ids": list(catalogue["techs"]), "military_path_ids": list(catalogue["paths"]),
        "lore_action_mask": [int(tech["can_research"]) for tech in tech_choices],
        "military_action_mask": [int(path["can_select"]) for path in military_choices],
        "recruit_ids": encoded_recruitment["recruit_ids"],
        "recruit_action_mask": encoded_recruitment["recruit_action_mask"],
        "recruitment": recruitment,
        "techs": tech_choices, "military_paths": military_choices,
    }
