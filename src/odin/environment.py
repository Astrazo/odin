"""The small persistent environment used by Odin's RL loop."""

from pathlib import Path

from odin.actions.assignments import assign_to_building
from odin.actions.buildings import build_building
from odin.actions.colonisation import colonise_zone
from odin.actions.pause import pause_game
from odin.actions.feast import start_feast
from odin.actions.upgrades import upgrade_building
from odin.actions.recruitment import recruit_hero
from odin.actions.movement import move_units
from odin.actions.progression import choose_military_path, research_lore
from odin.actions.scouting import scout_zone
from odin.actions.workers import assign_worker_to_building
from odin.bridge.session import NativeRuntime
from odin.observations.buildings import load_building_schema, observe_buildings
from odin.observations.economy import observe_economy, resolve_resource_keys
from odin.observations.temporal import observe_pause, observe_temporal
from odin.observations.progression import load_progression_catalogue, observe_progression
from odin.observations.units import load_unit_schema, observe_units
from odin.observations.zones import (
    discover_zone_graph,
    load_zone_feature_schema,
    observe_zone_graph,
    summarize_zones,
)


OBSERVATION_TENSORS = ("pause", "economy", "temporal", "zones", "progression")


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
        self.unit_catalogue = None
        self.zone_feature_catalogue = None
        self.progression_catalogue = None

    def __enter__(self):
        try:
            self.runtime.open()
            if "economy" in self.tensors or "zones" in self.tensors:
                self.resource_keys = resolve_resource_keys(self.runtime)
            if "zones" in self.tensors:
                self.building_catalogue = load_building_schema()
                self.unit_catalogue = load_unit_schema()
                self.zone_feature_catalogue = load_zone_feature_schema()
            if "progression" in self.tensors:
                self.progression_catalogue = load_progression_catalogue(self.runtime)
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
        if "progression" in self.tensors:
            observation["progression"] = observe_progression(self.runtime, self.progression_catalogue)
        graph = None
        if "zones" in self.tensors:
            graph = discover_zone_graph(self.runtime)
        if "zones" in self.tensors:
            zones = observe_zone_graph(
                self.runtime,
                self.resource_keys,
                graph,
                self.zone_feature_catalogue,
            )
            buildings = observe_buildings(
                self.runtime,
                self.building_catalogue,
                graph,
            )
            units = observe_units(
                self.runtime,
                self.unit_catalogue,
                graph,
            )
            zones["feature_names"].extend(buildings["feature_names"])
            zones["feature_names"].extend(units["feature_names"])
            zones["x"] = [
                zone_row + building_row + unit_row
                for zone_row, building_row, unit_row in zip(
                    zones["x"],
                    buildings["x"],
                    units["x"],
                    strict=True,
                )
            ]
            zones["building_ids"] = buildings["building_ids"]
            zones["building_schema_sha256"] = buildings["schema_sha256"]
            zones["build_action_mask"] = buildings["build_action_mask"]
            zones["upgrade_action_mask"] = buildings["upgrade_action_mask"]
            zones["unmapped_buildings"] = buildings["unmapped_buildings"]
            zones["construction_sites"] = buildings["construction_sites"]
            zones["unit_ids"] = units["unit_ids"]
            zones["neutral_unit_ids"] = units["neutral_unit_ids"]
            zones["unit_schema_sha256"] = units["schema_sha256"]
            zones["scout_unit_mask"] = units["scout_unit_mask"]
            zones["unit_jobs"] = units["unit_jobs"]
            zones["unmapped_units"] = units["unmapped_units"]
            zones["summary"] = summarize_zones(zones)
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

    def build(self, zone_id: int, building_id: str) -> dict:
        """Place a building; observe staffing after advancing the simulation."""
        return self.act(
            build_building,
            zone_id,
            building_id,
            self.building_catalogue,
        )

    def assign(self, unit_id: int, building_id: int, *, player_id: int | None = None) -> dict:
        """Assign one owned unit to one owned building."""
        return self.act(assign_to_building, unit_id, building_id, player_id=player_id)

    def scout(self, unit_id: int, zone_id: int) -> dict:
        """Send one eligible scout to an undiscovered neighbouring zone."""
        return self.act(scout_zone, unit_id, zone_id)

    def move(
        self, from_zone: int, to_zone: int, who: str, *, count: int | None = None,
        player_id: int | None = None,
    ) -> dict:
        """Move an eligible semantic unit group without exposing runtime IDs."""
        return self.act(move_units, from_zone, to_zone, who, count=count, player_id=player_id)

    def assign_worker(
        self, job: str, source_zone_id: int | None = None, building_id: int | str | None = None,
        *, target_zone_id: int | None = None, construction: bool = False,
        player_id: int | None = None,
    ) -> dict:
        """Assign by profession/source zone and building family/destination zone."""
        return self.act(
            assign_worker_to_building, job, source_zone_id, building_id,
            target_zone_id=target_zone_id, construction=construction,
            player_id=player_id,
        )

    def colonise(self, zone_id: int, *, player_id: int | None = None) -> dict:
        """Request normal colonisation for the selected player."""
        return self.act(colonise_zone, zone_id, player_id=player_id)

    def lore(self, tech: str, *, player_id: int | None = None) -> dict:
        """Learn a currently legal named clan technology."""
        return self.act(research_lore, tech, player_id=player_id)

    def military(self, path: str, *, player_id: int | None = None) -> dict:
        """Choose a currently legal primary military path."""
        return self.act(choose_military_path, path, player_id=player_id)

    def feast(self, *, player_id: int | None = None) -> dict:
        """Start one currently affordable feast, paying the game's cost."""
        return self.act(start_feast, player_id=player_id)

    def upgrade(
        self, building: int | str, *, zone_id: int | None = None,
        player_id: int | None = None,
    ) -> dict:
        """Upgrade one eligible building of this family in the chosen zone."""
        return self.act(upgrade_building, building, zone_id=zone_id, player_id=player_id)

    def recruit(
        self, who: str = "warchief", *, zone_id: int | None = None,
        player_id: int | None = None,
    ) -> dict:
        """Recruit one named chief/companion at an eligible native building."""
        return self.act(recruit_hero, who, zone_id=zone_id, player_id=player_id)
