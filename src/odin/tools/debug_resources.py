"""Explicit offline resource grants for manual game validation."""

import json
import math

from odin.actions.players import require_offline_host, resolve_player
from odin.observations.economy import RESOURCES


def add_resources(runtime, resource: str, amount: float, *, player_id: int | None = None) -> dict:
    """Grant one basic resource; report the actual change after native limits."""
    resources = dict(RESOURCES)
    resources.update({"krowns": "Money", "money": "Money"})
    resource = resource.lower()
    if resource not in resources:
        raise ValueError(f"Unknown debug resource {resource!r}; use {', '.join(resources)}.")
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Resource amount must be a finite positive number.")
    require_offline_host(runtime)
    player = resolve_player(runtime, player_id)
    key = None
    for index in range(runtime.array_length("Data.resource.all")):
        candidate = f"Data.resource.all[{index}].id"
        if json.loads(runtime.evaluate(candidate)) == resources[resource]:
            key = candidate
            break
    if key is None:
        raise RuntimeError("Native resource key was not found.")
    before = float(runtime.call_native(f"{player}.res.getResource({key}, null)"))
    # Native addition updates resource bookkeeping and retains normal caps/rules.
    # This helper is deliberately absent from NorthgardEnv's policy actions.
    accepted = runtime.call_native(f"{player}.res.addResource({key}, {float(amount)!r}, null)")
    after = float(runtime.call_native(f"{player}.res.getResource({key}, null)"))
    return {"debug": True, "resource": resources[resource], "amount_requested": amount,
            "accepted": accepted == "true", "before": before, "after": after,
            "amount_added": after - before, "player_id": int(runtime.evaluate(f"{player}.__uid"))}
