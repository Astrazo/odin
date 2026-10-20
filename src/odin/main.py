"""Command-line entry point for Odin."""

import json
from datetime import datetime
from pathlib import Path

import typer

from odin.actions.pause import pause_game
from odin.actions.assignments import assign_to_building, preview_assignment
from odin.actions.players import list_players, set_ai_orders
from odin.actions.colonisation import colonise_zone, list_colonisation_zones, preview_colonisation
from odin.bridge.launch import launch_game
from odin.bridge.session import NativeRuntime
from odin.environment import NorthgardEnv, OBSERVATION_TENSORS
from odin.observations.temporal import observe_pause
from odin.observations.zones import discover_zone_graph
from odin.tools.ids import list_player_ids, list_scout_ids
from odin.tools.unit_jobs import list_unit_jobs


app = typer.Typer(add_completion=False, no_args_is_help=True)
tools_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(tools_app, name="tools")
DEFAULT_EXE = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Northgard\Northgard.exe")
ADAPTER = Path(r"C:\Users\Josh\.vscode\extensions\haxefoundation.haxe-hl-2.0.0\adapter.js")
DEBUG_PORT = 6112
LOG_DIR = Path("artifacts/runs")


@app.callback()
def cli() -> None:
    """Launch Northgard and call the native functions Odin uses."""


@app.command()
def launch() -> None:
    """Start Northgard with its HashLink debug port enabled."""
    game, log_path = launch_game(DEFAULT_EXE, DEBUG_PORT, LOG_DIR)
    typer.echo(f"Northgard PID: {game.pid}")
    typer.echo(f"Game output: {log_path}")


@app.command("is-paused")
def is_paused_command() -> None:
    """Read GameState.isPaused through the native bridge."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(observe_pause(runtime)))


@app.command()
def pause() -> None:
    """Pause the current offline match through the native bridge."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(pause_game(runtime)))


@app.command()
def build(
    zone_id: int = typer.Option(..., "--zone", help="Owned zone ID."),
    building_id: str = typer.Option(..., "--building", help="Reviewed building family ID."),
) -> None:
    """Request one building through Northgard's normal placement code."""
    with NorthgardEnv(ADAPTER, DEFAULT_EXE, DEBUG_PORT, tensors=("zones",)) as env:
        typer.echo(json.dumps(env.build(zone_id, building_id)))


@app.command()
def assign(
    unit_id: int = typer.Option(..., "--unit", help="Owned unit runtime ID."),
    building_id: int = typer.Option(..., "--building", help="Owned building runtime ID."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Validate and assign one owned unit to one owned building."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(assign_to_building(runtime, unit_id, building_id, player_id=player_id)))


@app.command("ai-stop")
def ai_stop(
    player_id: int = typer.Option(..., "--player", help="Bot player UID."),
) -> None:
    """Stop one paused offline bot's stock AI decisions."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(set_ai_orders(runtime, player_id, stopped=True)))


@app.command("colonise")
def colonise(
    zone_id: int = typer.Option(..., "--zone", help="Discovered, unowned border zone ID."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Request normal colonisation, paying the game's current resource cost."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(colonise_zone(runtime, zone_id, player_id=player_id)))


@app.command("ai-resume")
def ai_resume(
    player_id: int = typer.Option(..., "--player", help="Bot player UID."),
) -> None:
    """Resume one paused offline bot's stock AI decisions."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(set_ai_orders(runtime, player_id, stopped=False)))


@app.command()
def scout(
    unit_id: int = typer.Option(..., "--unit", help="Owned Scout runtime ID."),
    zone_id: int = typer.Option(..., "--zone", help="Masked scout-target zone ID."),
) -> None:
    """Send one eligible Scout to a masked neighbouring zone."""
    with NorthgardEnv(ADAPTER, DEFAULT_EXE, DEBUG_PORT, tensors=("zones",)) as env:
        typer.echo(json.dumps(env.scout(unit_id, zone_id)))


@tools_app.command("ids")
def ids(
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Print the player's current zone and unit runtime IDs, then exit."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(list_player_ids(runtime, player_id=player_id), indent=2))


@tools_app.command("players")
def players() -> None:
    """List player UIDs, names and stock AI order state."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(list_players(runtime), indent=2))


@tools_app.command("unit-jobs")
def unit_jobs(
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Map owned unit runtime IDs to their current professions and zones."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(list_unit_jobs(runtime, player_id=player_id), indent=2))


@tools_app.command("scout-zones")
def scout_zones() -> None:
    """List eligible scout IDs and scoutable hidden zones for your local player."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        graph = discover_zone_graph(runtime)
        typer.echo(json.dumps({
            "scout_ids": list_scout_ids(runtime),
            "scoutable_zones": graph["scout_target_mask"],
        }, indent=2))


@tools_app.command("colonise-zones")
def colonise_zones(
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """List colonisable borders, native costs and blocked-zone reasons."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(list_colonisation_zones(runtime, player_id=player_id), indent=2))


@tools_app.command("colonise-preview")
def colonise_preview(
    zone_id: int = typer.Option(..., "--zone", help="Discovered, unowned border zone ID."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Preview one colonisation target without sending an order."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(preview_colonisation(runtime, zone_id, player_id=player_id), indent=2))


@tools_app.command("buildings")
def buildings(
    zone_id: int = typer.Option(..., "--zone", help="Player-owned zone runtime ID."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Print building IDs and kinds in one player-owned zone, then exit."""
    from odin.tools.buildings import list_zone_buildings

    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(list_zone_buildings(runtime, zone_id, player_id=player_id), indent=2))


@tools_app.command("assign-preview")
def assign_preview(
    unit_id: int = typer.Option(..., "--unit", help="Owned unit runtime ID."),
    building_id: int = typer.Option(..., "--building", help="Owned building runtime ID."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Show whether Northgard would accept one unit/building assignment."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(preview_assignment(runtime, unit_id, building_id, player_id=player_id), indent=2))


def format_unmapped_buildings(observation: dict) -> str | None:
    """Return a compact diagnostic report without changing tensor output."""
    zones = observation.get("zones")
    if not isinstance(zones, dict):
        return None
    entries = zones.get("unmapped_buildings")
    if not entries:
        return None

    grouped = {}
    for entry in entries:
        zone_id = entry["zone_id"]
        source = entry["source"]
        grouped.setdefault((zone_id, source), []).append(entry["engine_id"])

    lines = ["Unmapped building IDs (excluded from the policy schema):"]
    for (zone_id, source), engine_ids in sorted(grouped.items()):
        lines.append(f"  Zone {zone_id} {source}: {', '.join(sorted(engine_ids))}")
    return "\n".join(lines)


def write_observation(log_file, observation: dict, *, first: bool) -> None:
    """Append one observation to an open JSON array and make it inspectable."""
    if not first:
        log_file.write(",\n")
    json.dump(observation, log_file, indent=2)
    log_file.flush()


@app.command()
def run(
    tensor: list[str] | None = typer.Option(
        None,
        "--tensor",
        "-t",
        help=(
            "Tensor to extract: pause, economy, temporal or zones. "
            "Repeat for more than one; omit for all."
        ),
    ),
    show_unmapped: bool = typer.Option(
        False,
        "--show-unmapped",
        help="Print ignored building IDs grouped by zone to stderr.",
    ),
) -> None:
    """Keep one connection open and print an observation every 0.5 seconds."""
    selected = tuple(tensor) if tensor else None
    if selected:
        unknown = set(selected) - set(OBSERVATION_TENSORS)
        if unknown:
            choices = ", ".join(OBSERVATION_TENSORS)
            raise typer.BadParameter(
                f"unknown tensor(s) {sorted(unknown)}; choose from {choices}",
                param_hint="--tensor",
            )

    with NorthgardEnv(ADAPTER, DEFAULT_EXE, DEBUG_PORT, tensors=selected) as env:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        log_path = LOG_DIR / f"odin-observations-{timestamp}.json"
        typer.echo(f"Observation log: {log_path}", err=True)

        with log_path.open("x", encoding="utf-8") as log_file:
            log_file.write("[\n")
            first = True
            try:
                while True:
                    observation = env.observe() if first else env.step()
                    write_observation(log_file, observation, first=first)
                    first = False
                    typer.echo(json.dumps(observation))
                    report = format_unmapped_buildings(observation) if show_unmapped else None
                    if report:
                        typer.echo(report, err=True)
            finally:
                log_file.write("\n]\n")
