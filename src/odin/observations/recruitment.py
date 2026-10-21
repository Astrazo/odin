"""Clan hero choices and recruitment buildings resolved by the native game."""

import json
import math
import re

from odin.actions.players import resolve_player


SUPPORTED_CLANS = {"Wolf", "Bear", "Stag", "Goat", "Raven", "Boar", "Snake", "Horse"}
RECRUIT_IDS = ("warchief", "bear_companion")
RECRUIT_COST_RESOURCES = (("food", "Food"), ("gold", "Money"), ("iron", "Iron"))
RECRUIT_FEATURE_NAMES = tuple(
    f"recruit_{identifier}_{suffix}"
    for identifier in RECRUIT_IDS
    for suffix in ("available", "can_recruit", "cost_food", "cost_gold", "cost_iron")
)


def encode_recruitment(observation: dict) -> dict:
    """Encode fixed policy choices; cosmetic native IDs never become features."""
    values = []
    mask = []
    for identifier in RECRUIT_IDS:
        matches = [choice for choice in observation["choices"]
                   if choice["recruitment_type"] == identifier]
        # Multiple chiefs need an explicit choice (e.g. Horse). Do not silently
        # buy one through the single-chief action used by the seven-clan rollout.
        choice = matches[0] if len(matches) == 1 else None
        can_recruit = choice is not None and choice["can_recruit"]
        costs = {resource: 0.0 for _, resource in RECRUIT_COST_RESOURCES}
        if choice is not None:
            for cost in choice["cost"]:
                if cost["resource"] not in costs:
                    raise RuntimeError(f"Unsupported recruitment cost resource: {cost['resource']}.")
                costs[cost["resource"]] += cost["quantity"]
        values.extend([float(choice is not None), float(can_recruit)])
        values.extend(costs[resource] for _, resource in RECRUIT_COST_RESOURCES)
        mask.append(int(can_recruit))
    if len(values) != len(RECRUIT_FEATURE_NAMES) or any(
        not math.isfinite(value) or value < 0 for value in values
    ):
        raise RuntimeError("Invalid numeric recruitment observation.")
    return {"feature_names": list(RECRUIT_FEATURE_NAMES), "x": values,
            "recruit_ids": list(RECRUIT_IDS), "recruit_action_mask": mask}


def observe_recruitment(runtime, *, player_id: int | None = None, zone_id: int | None = None) -> dict:
    """List each native hero option, cost and eligibility at owned buildings."""
    player = resolve_player(runtime, player_id)
    clan = json.loads(runtime.evaluate(f"{player}.clan"))
    if clan not in SUPPORTED_CLANS:
        raise ValueError(f"Recruitment is not reviewed for clan {clan!r}.")
    heroes = f"{player}.getAvailableHeroes()"
    chiefs = f"{player}.getAvailableWarchiefs()"
    chief_kinds = {
        json.loads(runtime.evaluate(f"{chiefs}[{index}]"))
        for index in range(runtime.array_length(chiefs))
    }
    buildings = []
    for index in range(runtime.array_length(f"{player}.zones")):
        zone = f"{player}.zones[{index}]"
        current_zone = int(runtime.evaluate(f"{zone}.id"))
        if zone_id is not None and current_zone != zone_id:
            continue
        if runtime.call_native(f"{zone}.getOwner() == {player}") != "true":
            raise RuntimeError("Recruitment zone is no longer owned.")
        for building_index in range(runtime.array_length(f"{zone}.buildings")):
            building = f"{zone}.buildings[{building_index}]"
            if runtime.call_native(f"{building}.canHireHero({player})") != "true":
                continue
            buildings.append({"expression": building, "zone_id": current_zone,
                              "building_id": int(runtime.evaluate(f"{building}.__uid")),
                              "building_kind": json.loads(runtime.evaluate(f"{building}.kind"))})
    buildings.sort(key=lambda building: building["building_id"])
    choices = []
    for index in range(runtime.array_length(heroes)):
        hero = f"{heroes}[{index}]"
        engine_id = json.loads(runtime.evaluate(hero))
        if not isinstance(engine_id, str) or not engine_id:
            raise RuntimeError("Invalid native hero identifier.")
        identifier = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", engine_id).lower()
        recruitment_type = None
        if engine_id in chief_kinds:
            recruitment_type = "warchief"
        elif engine_id == "BearMaiden":
            recruitment_type = "bear_companion"
        cost = f"{player}.getWarchiefCost({hero})"
        costs = []
        for cost_index in range(runtime.array_length(cost)):
            entry = f"{cost}[{cost_index}]"
            resource = json.loads(runtime.evaluate(f"{entry}.res"))
            quantity = int(runtime.evaluate(f"{entry}.qty"))
            if not isinstance(resource, str) or not resource or quantity < 0:
                raise RuntimeError("Invalid native hero recruitment cost.")
            costs.append({"resource": resource, "quantity": quantity})
        locations = []
        for building in buildings:
            reason = runtime.call_native(
                f"{player}.getNoHireHeroReason({building['expression']}, {hero}, null)"
            )
            locations.append({
                "building_id": building["building_id"], "building_kind": building["building_kind"],
                "zone_id": building["zone_id"], "can_recruit": reason == "null",
                "reason": None if reason == "null" else reason,
            })
        reason = runtime.call_native(f"{player}.getNoHireHeroReason(null, {hero}, null)")
        eligible = any(location["can_recruit"] for location in locations)
        blocked_reason = None
        if not eligible:
            blocked_reason = locations[0]["reason"] if locations else "NoRecruitmentBuilding"
        choices.append({
            "id": identifier, "engine_id": engine_id,
            "is_warchief": engine_id in chief_kinds,
            "recruitment_type": recruitment_type,
            "can_recruit": eligible, "cost": costs, "locations": locations,
            "reason": blocked_reason,
            "unit_reason": None if reason == "null" else reason,
        })
    choices.sort(key=lambda choice: choice["id"])
    return {"clan": clan, "zone_id": zone_id, "choices": choices,
            "recruit_ids": [choice["id"] for choice in choices],
            "recruit_action_mask": [int(choice["can_recruit"]) for choice in choices]}
