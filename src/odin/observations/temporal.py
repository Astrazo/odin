FEATURE_NAMES = ["game_time"]


def observe_temporal(evaluate) -> dict:
    game_time = float(evaluate("this.state.time"))

    return {
        "feature_names": FEATURE_NAMES,
        "x": [game_time],
    }