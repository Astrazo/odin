"""The small persistent environment used by Odin's RL loop."""

from pathlib import Path

from odin.actions.pause import pause_game
from odin.bridge.session import NativeRuntime
from odin.observations.buildings import load_building_schema, observe_buildings
from odin.observations.economy import observe_economy, resolve_resource_keys
from odin.observations.temporal import observe_pause, observe_temporal
from odin.observations.zones import discover_zone_graph, observe_zone_graph


OBSERVATION_TENSORS = ("pause", "economy", "temporal", "zones")


class NorthgardEnv:
    """Keep one debugger connection open across repeated RL steps."""

    def __init__(
        self,
        adapter: Path,
        exe: Path,
        port: int = 6112,
        step_seconds: float = 0.5,
        tensors: tuple[str, ...] | None = None,
    ) -> None:
        self.runtime = NativeRuntime(adapter, exe, port)
        self.step_seconds = step_seconds
        selected = OBSERVATION_TENSORS if tensors is None else tensors
        unknown = set(selected) - set(OBSERVATION_TENSORS)
        if unknown:
            raise ValueError(f"Unknown observation tensors: {sorted(unknown)}")
        self.tensors = tuple(dict.fromkeys(selected))
        self.resource_keys = None
        self.building_catalogue = None

    def __enter__(self):
        try:
            self.runtime.open()
            if "economy" in self.tensors or "zones" in self.tensors:
                self.resource_keys = resolve_resource_keys(self.runtime)
            if "zones" in self.tensors:
                self.building_catalogue = load_building_schema()
            return self
        except BaseException:
            self.runtime.close()
            raise

    def __exit__(self, kind, error, traceback):
        self.runtime.close()

    def observe(self) -> dict:
        """Read every observation from the current stopped frame."""
        observation = {}
        if "pause" in self.tensors:
            observation["pause"] = observe_pause(self.runtime)
        if "economy" in self.tensors:
            observation["economy"] = observe_economy(
                self.runtime,
                self.resource_keys,
            )
        if "temporal" in self.tensors:
            observation["temporal"] = observe_temporal(self.runtime)
        graph = None
        if "zones" in self.tensors:
            graph = discover_zone_graph(self.runtime)
        if "zones" in self.tensors:
            zones = observe_zone_graph(
                self.runtime,
                self.resource_keys,
                graph,
            )
            buildings = observe_buildings(
                self.runtime,
                self.building_catalogue,
                graph,
            )
            zones["feature_names"].extend(buildings["feature_names"])
            zones["x"] = [
                zone_row + building_row
                for zone_row, building_row in zip(
                    zones["x"],
                    buildings["x"],
                    strict=True,
                )
            ]
            zones["building_ids"] = buildings["building_ids"]
            zones["building_schema_sha256"] = buildings["schema_sha256"]
            zones["build_action_mask"] = buildings["build_action_mask"]
            observation["zones"] = zones
        return observation

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
