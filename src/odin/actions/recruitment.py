"""Recruit a native clan chief or companion through the normal paid RPC."""

import json

from odin.actions.assignments import find_owned_building
from odin.actions.players import require_offline_host, require_paused_bot, resolve_player
from odin.observations.recruitment import observe_recruitment
from odin.tools.unit_jobs import list_unit_jobs


def recruit_hero(
    runtime, who: str = "warchief", *, zone_id: int | None = None,
    player_id: int | None = None,
) -> dict:
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    if runtime.evaluate(f"{player} == this.state.me") != "true":
        require_paused_bot(runtime, player)
        if runtime.evaluate(f"{player}.skipAIOrder") != "true":
            raise RuntimeError("Stop the selected bot's AI orders before recruiting.")
    observation = observe_recruitment(runtime, player_id=player_id, zone_id=zone_id)
    label = who.lower().replace("-", "").replace("_", "").replace(" ", "")
    if label == "warchief":
        matches = [choice for choice in observation["choices"]
                   if choice["recruitment_type"] == "warchief"]
    elif label in {"bear", "bearcompanion", "kaija"}:
        matches = [choice for choice in observation["choices"]
                   if choice["recruitment_type"] == "bear_companion"]
    else:
        matches = [choice for choice in observation["choices"]
                   if choice["engine_id"].lower() == label]
    if len(matches) != 1:
        options = ", ".join(observation["recruit_ids"])
        raise ValueError(f"Choose one native recruit explicitly; available clan choices: {options}.")
    choice = matches[0]
    if not choice["can_recruit"]:
        raise ValueError(f"Cannot recruit {choice['id']}: {choice['reason']}.")
    location = next(location for location in choice["locations"] if location["can_recruit"])
    building = find_owned_building(runtime, location["building_id"], player)
    # Resolve the managed kind String again, rather than injecting a Python label.
    heroes = f"{player}.getAvailableHeroes()"
    hero = None
    for index in range(runtime.array_length(heroes)):
        candidate = f"{heroes}[{index}]"
        if json.loads(runtime.evaluate(candidate)) == choice["engine_id"]:
            hero = candidate
            break
    if hero is None:
        raise RuntimeError("Recruitment choices changed; inspect them again.")
    before = list_unit_jobs(runtime, player_id=player_id)["unit_jobs"]
    # Public RPC rechecks legality and pays getWarchiefCost before spawning.
    runtime.call_native(f"{player}.hireHero({building}, {hero}, null, null)")
    after = list_unit_jobs(runtime, player_id=player_id)["unit_jobs"]
    recruited = [int(uid) for uid, unit in after.items()
                 if uid not in before and unit["engine_id"] == choice["engine_id"]]
    if len(recruited) != 1:
        raise RuntimeError("Recruitment was not confirmed; inspect units before retrying.")
    return {"id": choice["id"], "engine_id": choice["engine_id"],
            "unit_id": recruited[0], "zone_id": location["zone_id"],
            "building_id": location["building_id"], "cost": choice["cost"],
            "requested": True, "recruitment_observed": True}
