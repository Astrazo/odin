"""Time and pause observations sourced from inspected native getters."""

import math

from odin.observations.feast import observe_feast


PAUSE_FEATURE_NAMES = ["is_paused"]
TEMPORAL_FEATURE_NAMES = [
    "game_time",
    "time_until_winter",
    "time_until_summer",
    "is_feasting",
    "feast_time_remaining",
    "feast_resource_food",
    "feast_resource_gold",
    "feast_cost",
    "can_feast",
]


def read_is_paused(runtime) -> bool:
    result = runtime.call_native("this.state.isPaused()")
    if result not in ("true", "false"):
        raise RuntimeError(f"Expected isPaused to return a Boolean: {result!r}")
    return result == "true"


def observe_pause(runtime) -> dict:
    paused = read_is_paused(runtime)
    return {
        "feature_names": list(PAUSE_FEATURE_NAMES),
        "x": [1.0 if paused else 0.0],
    }


def observe_temporal(runtime) -> dict:
    """Read the simulation clock, season transitions and clan feast state."""
    game_time = float(runtime.call_native("this.get_time()"))
    until_winter = float(runtime.call_native("this.state.timeToNextWinter()"))
    until_summer = float(runtime.call_native("this.state.timeToWinterEnd()"))

    raw_values = [game_time, until_winter, until_summer]
    if game_time < 0 or not all(math.isfinite(value) for value in raw_values):
        raise RuntimeError("Invalid temporal observation.")

    values = [game_time, max(0.0, until_winter), max(0.0, until_summer)]
    feast = observe_feast(runtime)
    if len(feast["cost"]) != 1 or feast["cost"][0]["resource"] not in {"Food", "Money"}:
        raise RuntimeError("Unsupported feast cost for the temporal tensor.")
    cost = feast["cost"][0]
    values.extend([
        float(feast["is_feasting"]),
        feast["feast_time_remaining"],
        float(cost["resource"] == "Food"),
        float(cost["resource"] == "Money"),
        float(cost["quantity"]),
        float(feast["can_feast"]),
    ])
    return {
        "feature_names": list(TEMPORAL_FEATURE_NAMES),
        "x": values,
        "feast": feast,
    }
