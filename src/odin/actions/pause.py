"""The first native action exposed to the RL environment."""

from odin.observations.temporal import read_is_paused


def pause_game(runtime) -> dict:
    """Call the normal pause function once and confirm that it worked."""
    before = read_is_paused(runtime)
    if before:
        raise RuntimeError("The game is already paused, waiting, or ended; no action sent.")

    is_multi = runtime.call_native("this.state.isMulti(null)")
    if is_multi != "false":
        raise RuntimeError("The pause test requires an offline single-player match.")

    runtime.call_native("this.state.me.ui.setPause(true, this.state.me)")
    after = read_is_paused(runtime)
    if not after:
        raise RuntimeError("Pause returned without changing the pause state.")
    return {"before_is_paused": before, "after_is_paused": after}
