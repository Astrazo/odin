"""Research lore and choose an ordinary military path through normal RPCs."""

import json

from odin.actions.players import require_offline_host, require_paused_bot, resolve_player
from odin.observations.progression import (
    load_progression_catalogue, native_bool, observe_progression, semantic_name,
)


def _acting_player(runtime, player_id: int | None) -> str:
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    if runtime.evaluate(f"{player} == this.state.me") != "true":
        require_paused_bot(runtime, player)
        if runtime.evaluate(f"{player}.skipAIOrder") != "true":
            raise RuntimeError("Stop the selected bot's AI orders before changing progression.")
    return player


def research_lore(runtime, tech: str, *, player_id: int | None = None) -> dict:
    """Resolve a clan tech name, pay normally, and confirm it was learned."""
    player = _acting_player(runtime, player_id)
    catalogue = load_progression_catalogue(runtime, player_id=player_id)
    label = semantic_name(tech)
    matches = [
        identifier for identifier, entry in catalogue["techs"].items()
        if label in (identifier, semantic_name(entry["name"]))
    ]
    if len(matches) != 1:
        raise ValueError(f"Unknown or ambiguous clan technology {tech!r}; list tools progression.")
    identifier = matches[0]
    observation = observe_progression(runtime, catalogue)
    choice = next(entry for entry in observation["techs"] if entry["id"] == identifier)
    if not choice["can_research"]:
        if choice["unlocked"]:
            reason = "already learned"
        elif not choice["prerequisites_met"]:
            reason = "prerequisites"
        else:
            reason = "cost"
        raise ValueError(f"Cannot research {identifier}: {reason}.")
    entry = catalogue["techs"][identifier]["expression"]
    # Public host RPC: canUnlockTech + normal payment/free-choice handling.
    # Never call Player.unlockTech or doUnlockTech, which can bypass payment.
    runtime.call_native(f"{player}.tech.unlockTech({entry}.id, null)")
    if not native_bool(runtime, f"{player}.tech.hasTech({entry}.id, null)"):
        raise RuntimeError("Lore unlock was not confirmed; inspect progression before retrying.")
    result = {**choice, "requested": True, "unlock_observed": True, "unlocked": True, "can_research": False}
    if player_id is not None:
        result["player_id"] = player_id
    return result


def choose_military_path(runtime, path: str, *, player_id: int | None = None) -> dict:
    """Select the first primary path; subsequent ordinary tiers auto-unlock."""
    player = _acting_player(runtime, player_id)
    catalogue = load_progression_catalogue(runtime, player_id=player_id)
    identifier = semantic_name(path)
    identifier = {"tactician": "leadership", "conqueror": "legions"}.get(identifier, identifier)
    if identifier not in catalogue["paths"]:
        raise ValueError(f"Unknown military path {path!r}; list tools progression.")
    observation = observe_progression(runtime, catalogue)
    choice = next(entry for entry in observation["military_paths"] if entry["id"] == identifier)
    if not choice["can_select"]:
        raise ValueError("Military path is unavailable: check XP and whether a path is already selected.")
    engine_id = catalogue["paths"][identifier][0]
    entry = catalogue["abilities"][engine_id]["expression"]
    runtime.call_native(f"{player}.tech.unlockMiliPathAbility({entry}.id, null)")
    primary = f"{player}.tech.militaryPathUnlocked.array"
    learned = [json.loads(runtime.evaluate(f"{primary}[{index}]")) for index in range(runtime.array_length(primary))]
    if engine_id not in learned:
        raise RuntimeError("Military path selection was not confirmed; inspect progression before retrying.")
    result = {"path": identifier, "first_ability": engine_id, "requested": True, "selection_observed": True}
    if player_id is not None:
        result["player_id"] = player_id
    return result
