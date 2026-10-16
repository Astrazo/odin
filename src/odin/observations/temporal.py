"""Small first observation sourced entirely from an inspected native getter."""

FEATURE_NAMES = ["is_paused"]


def read_is_paused(runtime) -> bool:
    result = runtime.call_native("this.state.isPaused()")
    if result not in ("true", "false"):
        raise RuntimeError(f"Expected isPaused to return a Boolean: {result!r}")
    return result == "true"


def observe_pause(runtime) -> dict:
    paused = read_is_paused(runtime)
    return {
        "feature_names": list(FEATURE_NAMES),
        "x": [1.0 if paused else 0.0],
    }
