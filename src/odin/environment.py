"""The small persistent environment used by Odin's RL loop."""

from pathlib import Path

from odin.actions.pause import pause_game
from odin.bridge.session import NativeRuntime
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
        self.runtime = NativeRuntime(adapter, exe, port, allow_pause=True)
        self.step_seconds = step_seconds

    def __enter__(self):
        try:
            self.runtime.open()
            return self
        except BaseException:
            self.runtime.close()
            raise

    def __exit__(self, kind, error, traceback):
        self.runtime.close()

    def observe(self) -> dict:
        """Read every observation from the current stopped frame."""
        return observe_pause(self.runtime)

    def advance(self) -> None:
        """Let the game run, then replace the current frame with a fresh one."""
        self.runtime.advance(self.step_seconds)

    def step(self) -> dict:
        """Advance once and return the next observation."""
        self.advance()
        return self.observe()

    def act(self, action, *args, **kwargs):
        """Apply an action to the clan using the current stopped frame."""
        return action(self.runtime, *args, **kwargs)

    def pause(self) -> dict:
        """Apply the currently available test action to the stopped frame."""
        return self.act(pause_game)
