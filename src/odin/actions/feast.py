"""Start a feast through the game's normal paid request."""

from odin.actions.players import require_offline_host, require_paused_bot, resolve_player
from odin.observations.feast import observe_feast


def start_feast(runtime, *, player_id: int | None = None) -> dict:
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    if runtime.evaluate(f"{player} == this.state.me") != "true":
        require_paused_bot(runtime, player)
        if runtime.evaluate(f"{player}.skipAIOrder") != "true":
            raise RuntimeError("Stop the selected bot's AI orders before starting a feast.")
    before = observe_feast(runtime, player_id=player_id)
    if not before["can_feast"]:
        if before["is_feasting"]:
            raise ValueError("A feast is already active.")
        raise ValueError("The clan cannot start a feast: check resources and defeat state.")
    # The public RPC rechecks affordability and pays the current native cost.
    # Do not pass startFeast options, which include payment/active-feast bypasses.
    runtime.call_native(f"{player}.res.netStartFeast(null)")
    after = observe_feast(runtime, player_id=player_id)
    if not after["is_feasting"]:
        raise RuntimeError("Feast start was not confirmed; inspect state before retrying.")
    result = {**after, "requested": True, "cost_paid": before["cost"]}
    if player_id is not None:
        result["player_id"] = player_id
    return result
