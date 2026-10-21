"""Current feast state and the native cost of starting the next feast."""

import json
import math

from odin.actions.players import resolve_player


def observe_feast(runtime, *, player_id: int | None = None) -> dict:
    player = resolve_player(runtime, player_id)
    resources = f"{player}.res"
    is_feasting = runtime.call_native(f"{resources}.isFeasting()") == "true"
    remaining = runtime.call_native(f"{resources}.getRemainingFeastTime()")
    time_remaining = 0.0 if remaining == "null" else float(remaining)
    cost = f"{resources}.getFeastCost()"
    costs = []
    for index in range(runtime.array_length(cost)):
        entry = f"{cost}[{index}]"
        resource = json.loads(runtime.evaluate(f"{entry}.res"))
        quantity = int(runtime.evaluate(f"{entry}.qty"))
        if not isinstance(resource, str) or not resource or quantity < 0:
            raise RuntimeError("Invalid native feast cost.")
        costs.append({"resource": resource, "quantity": quantity})
    if not math.isfinite(time_remaining) or time_remaining < 0:
        raise RuntimeError("Invalid native remaining feast time.")
    defeated = runtime.call_native(f"{player}.isDefeated(null)") == "true"
    can_feast = runtime.call_native(f"{player}.canFeast({cost})") == "true"
    return {
        "is_feasting": is_feasting,
        "feast_time_remaining": time_remaining,
        "cost": costs,
        "can_feast": can_feast and not defeated,
    }
