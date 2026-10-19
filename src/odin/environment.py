"""The small persistent environment used by Odin's RL loop."""

from pathlib import Path

from odin.actions.pause import pause_game
from odin.bridge.session import NativeRuntime
from odin.observations.economy import observe_economy, resolve_resource_keys
from odin.observations.temporal import observe_pause


class NorthgardEnv:
    """Keep one debugger connection open across repeated RL steps."""

    def __init__(
        self,
        adapter: Path,
        exe: Path,
        port: int = 6112,
        step_seconds: float = 0.5,
    ) -> None:
        self.runtime = NativeRuntime(adapter, exe, port)
        self.step_seconds = step_seconds
        self.resource_keys = None

    def __enter__(self):
        try:
            self.runtime.open()
            self.resource_keys = resolve_resource_keys(self.runtime)
            return self
        except BaseException:
            self.runtime.close()
            raise

    def __exit__(self, kind, error, traceback):
        self.runtime.close()

    def observe(self) -> dict:
        """Read every observation from the current stopped frame."""
        return {
            "pause": observe_pause(self.runtime),
            "economy": observe_economy(self.runtime, self.resource_keys),
        }

    def advance_step(self) -> None:
        """Let the game run, then replace the current frame with a fresh one."""
        self.runtime.advance_step(self.step_seconds)

    def step(self) -> dict:
        """Advance one step and return the next observation."""
        self.advance_step()
        return self.observe()

    def act(self, action, *args, **kwargs):
        """Apply an action to the clan using the current stopped frame."""
        return action(self.runtime, *args, **kwargs)

    def pause(self) -> dict:
        """Apply the currently available test action to the stopped frame."""
        return self.act(pause_game)
