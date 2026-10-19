"""Controlled-clan economy tensor backed by inspected native getters."""

import json
import math
from ..bridge.session import NativeRuntime


RESOURCES = (
    ("food", "Food"),
    ("wood", "Wood"),
    ("gold", "Money"),
    ("stone", "Stone"),
    ("iron", "Iron"),
    ("lore", "Lore"),
)

FEATURE_NAMES = [
    name
    for label, _ in RESOURCES
    for name in (label, f"{label}_net_flow")
]
FEATURE_NAMES += [
    "happiness",
    "population",
    "population_cap",
    "food_cap",
    "villager_growth_active",
    "villager_progress",
    "villager_time_remaining",
]


def resolve_resource_keys(runtime) -> dict[str, str]:
    """Find the managed resource objects used as native getter arguments."""
    required = {identifier for _, identifier in RESOURCES} | {"Population"}
    keys = {}
    for index in range(runtime.array_length("Data.resource.all")):
        expression = f"Data.resource.all[{index}].id"
        identifier = json.loads(runtime.evaluate(expression))
        if identifier in required:
            keys[identifier] = expression

    missing = required - keys.keys()
    if missing:
        raise RuntimeError(f"Missing resource keys: {sorted(missing)}")
    return keys


def observe_economy(runtime: NativeRuntime, keys: dict[str, str]) -> dict:
    """Read the 19-value economy tensor from the current stopped frame."""
    resources = "this.state.me.res"
    values = []

    for _, identifier in RESOURCES:
        key = keys[identifier]
        values.append(float(runtime.call_native(f"{resources}.getResource({key}, null)")))
        values.append(float(runtime.call_native(f"{resources}.getFlux({key})")))

    values.extend([
        float(runtime.call_native(f"{resources}.getHappiness()")),
        int(runtime.call_native(f"{resources}.get_population()")),
        int(runtime.call_native(f'{resources}.getMax({keys["Population"]})')),
        int(runtime.call_native(f'{resources}.getMax({keys["Food"]})')),
    ])

    villager_time = runtime.call_native(f"{resources}.getNextVillagerTime()")
    villager_progress = float(
        runtime.call_native(f"{resources}.getNextVillagerProgress()")
    )
    time_remaining = 0.0 if villager_time == "null" else float(villager_time)
    if not 0 <= villager_progress <= 1 or time_remaining < 0:
        raise RuntimeError("Invalid villager growth observation.")
    values.extend([
        1.0 if villager_time != "null" else 0.0,
        villager_progress,
        time_remaining,
    ])

    if len(values) != len(FEATURE_NAMES) or not all(math.isfinite(value) for value in values):
        raise RuntimeError("Invalid economy observation.")
    return {"feature_names": list(FEATURE_NAMES), "x": values}
