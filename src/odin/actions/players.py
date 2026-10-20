"""Resolve acting players and control the stock AI's decision gate."""

import json


def _player_entries(runtime) -> dict[int, str]:
    # GameState.players is an hxbit proxy; inspect its backing Haxe array.
    players = "this.state.players.array"
    count = runtime.array_length(players)
    if not 1 <= count <= 32:
        raise RuntimeError("Unexpected player count.")
    entries = {}
    for index in range(count):
        player = f"{players}[{index}]"
        if runtime.evaluate(f"{player} == null") != "false":
            raise RuntimeError("Null player in GameState.players.")
        player_id = int(runtime.evaluate(f"{player}.__uid"))
        if player_id in entries:
            raise RuntimeError("Duplicate player UID in GameState.players.")
        entries[player_id] = player
    return entries


def resolve_player(runtime, player_id: int | None = None) -> str:
    """Resolve a current player UID, retaining the local player as the default."""
    if player_id is None:
        return "this.state.me"
    entries = _player_entries(runtime)
    if player_id not in entries:
        raise ValueError(f"Player UID {player_id} was not found; list players again.")
    return entries[player_id]


def list_players(runtime) -> dict:
    """List identities and AI gate values without changing orders."""
    players = []
    for player_id, player in _player_entries(runtime).items():
        players.append({
            "player_id": player_id,
            "name": json.loads(runtime.evaluate(f"{player}.name")),
            "is_local": runtime.evaluate(f"{player} == this.state.me") == "true",
            "has_ai_job": runtime.evaluate(f"{player}.aiJob == null") == "false",
            "ai_orders_stopped": runtime.evaluate(f"{player}.skipAIOrder") == "true",
        })
    return {"players": players}


def require_offline_host(runtime) -> None:
    """Synchronous action confirmation requires the authoritative offline host."""
    if runtime.evaluate("this.host.isAuth") != "true":
        raise RuntimeError("This action requires the authoritative host.")
    if runtime.call_native("this.state.isMulti(null)") != "false":
        raise RuntimeError("This action requires an offline single-player match.")


def require_paused_bot(runtime, player: str) -> None:
    """Require a bot with territory at a paused decision point."""
    if runtime.evaluate("this.state.play == PlayState.Pause") != "true":
        raise RuntimeError("Pause the match normally before controlling a bot.")
    if runtime.evaluate(f"{player} == this.state.me") != "false":
        raise RuntimeError("AI order control requires a non-local bot player.")
    if runtime.evaluate(f"{player}.aiJob == null") != "false":
        raise RuntimeError("The selected player does not have an AI job.")
    if runtime.array_length(f"{player}.zones") == 0:
        raise RuntimeError("The selected bot has no owned territory.")


def set_ai_orders(runtime, player_id: int, *, stopped: bool) -> dict:
    """Change one bot's native gate and verify it; leave game pause unchanged."""
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    require_paused_bot(runtime, player)
    before = runtime.evaluate(f"{player}.skipAIOrder")
    if before not in ("true", "false"):
        raise RuntimeError("Unexpected AI order gate value.")
    desired = "true" if stopped else "false"
    if before != desired:
        result = runtime.call_native(f"{player}.set_skipAIOrder({desired})")
        if result != desired:
            raise RuntimeError("AI setter result was not confirmed; inspect the bot before retrying.")
    if runtime.evaluate(f"{player}.skipAIOrder") != desired:
        raise RuntimeError("AI order gate read-back failed; inspect the bot before retrying.")
    return {
        "player_id": player_id,
        "before_orders_stopped": before == "true",
        "ai_orders_stopped": stopped,
        "setter_called": before != desired,
    }
