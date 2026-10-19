"""Time and pause observations sourced from inspected native getters."""

import math


PAUSE_FEATURE_NAMES = ["is_paused"]
TEMPORAL_FEATURE_NAMES = [
    "game_time",
    "time_until_winter",
    "time_until_summer",
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
    """Read the simulation clock and the next two season transitions."""
    game_time = float(runtime.call_native("this.get_time()"))
    until_winter = float(runtime.call_native("this.state.timeToNextWinter()"))
    until_summer = float(runtime.call_native("this.state.timeToWinterEnd()"))

    raw_values = [game_time, until_winter, until_summer]
    if game_time < 0 or not all(math.isfinite(value) for value in raw_values):
        raise RuntimeError("Invalid temporal observation.")

    values = [game_time, max(0.0, until_winter), max(0.0, until_summer)]
    return {
        "feature_names": list(TEMPORAL_FEATURE_NAMES),
        "x": values,
    }
