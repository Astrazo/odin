"""Command-line entry point for Odin."""

import json
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path

import typer

from odin.actions.pause import pause_game
from odin.actions.feast import start_feast
from odin.observations.feast import observe_feast
from odin.actions.movement import move_units, preview_move
from odin.actions.assignments import assign_to_building, preview_assignment
from odin.actions.players import list_players, set_ai_orders
from odin.actions.progression import choose_military_path, research_lore
from odin.actions.colonisation import colonise_zone, list_colonisation_zones, preview_colonisation
from odin.actions.workers import resolve_assignment
from odin.actions.upgrades import preview_upgrade, upgrade_building
from odin.tools.debug_resources import add_resources
from odin.bridge.launch import launch_game
from odin.bridge.session import NativeRuntime
from odin.environment import NorthgardEnv, OBSERVATION_TENSORS
from odin.observations.temporal import observe_pause
from odin.observations.units import load_unit_schema
from odin.observations.progression import observe_progression
from odin.observations.zones import discover_zone_graph
from odin.tools.ids import list_player_ids, list_scout_ids
from odin.tools.unit_jobs import list_unit_jobs


app = typer.Typer(add_completion=False, no_args_is_help=True)
tools_app = typer.Typer(add_completion=False, no_args_is_help=True)
debug_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(tools_app, name="tools")
app.add_typer(debug_app, name="debug")
DEFAULT_EXE = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Northgard\Northgard.exe")
ADAPTER = Path(r"C:\Users\Josh\.vscode\extensions\haxefoundation.haxe-hl-2.0.0\adapter.js")
DEBUG_PORT = 6112
LOG_DIR = Path("artifacts/runs")


def parse_worker_job(value: str | None) -> str | None:
    """Reject unknown professions before opening a game debugger connection."""
    if value is None:
        return None
    job = value.lower().replace("-", "_")
    professions = load_unit_schema()["unit_ids"]
    if job not in professions:
        message = f"Unknown profession {value!r}."
        matches = get_close_matches(job, professions, n=1)
        if matches:
            message += f" Did you mean {matches[0]!r}?"
        raise typer.BadParameter(message)
    return job


def parse_move_who(value: str) -> str:
    """Allow a profession or the two explicit group selectors."""
    who = value.lower().replace("-", "_")
    if who in {"all", "military"}:
        return who
    return parse_worker_job(who)


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
    """Place one building; choose any worker assignment in a later action."""
    with NorthgardEnv(ADAPTER, DEFAULT_EXE, DEBUG_PORT, tensors=("zones",)) as env:
        typer.echo(json.dumps(env.build(zone_id, building_id)))


@app.command()
def assign(
    unit_id: int | None = typer.Option(None, "--unit", help="Owned unit runtime ID, or choose --from-job."),
    building_id: str = typer.Option(..., "--building", help="Building family, e.g. scout_camp; a runtime UID also works for debugging."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
    worker_job: str | None = typer.Option(None, "--from-job", callback=parse_worker_job, help="Worker profession to divert, e.g. woodcutter."),
    source_zone_id: int | None = typer.Option(None, "--from-zone", help="Source zone for --from-job; defaults to the target building's zone."),
    target_zone_id: int | None = typer.Option(None, "--zone", help="Destination zone for a building family."),
    construction: bool = typer.Option(False, "--construction", help="Target construction of this family; defaults to completed buildings."),
) -> None:
    """Validate and assign one owned unit to one owned building."""
    if worker_job is None and source_zone_id is not None:
        raise typer.BadParameter("Supply --from-job when using --from-zone.")
    if (unit_id is None) == (worker_job is None):
        raise typer.BadParameter("Choose either --unit or --from-job.")
    if not building_id.isdecimal() and target_zone_id is None:
        raise typer.BadParameter("Supply --zone with a building family.")
    if building_id.isdecimal() and (target_zone_id is not None or construction):
        raise typer.BadParameter("Use --zone/--construction with a building family, not a UID.")
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        selection = resolve_assignment(
            runtime, building_id, job=worker_job, source_zone_id=source_zone_id,
            unit_id=unit_id, target_zone_id=target_zone_id,
            construction=construction, player_id=player_id,
        )
        result = assign_to_building(runtime, selection["unit_id"], selection["building_id"], player_id=player_id)
        typer.echo(json.dumps({**selection, **result}))


@app.command("ai-stop")
def ai_stop(
    player_id: int = typer.Option(..., "--player", help="Bot player UID."),
) -> None:
    """Stop one paused offline bot's stock AI decisions."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(set_ai_orders(runtime, player_id, stopped=True)))


@app.command("lore")
def lore(
    tech: str = typer.Argument(..., help="Technology label or name from tools progression."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Research one named clan technology using normal costs and prerequisites."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(research_lore(runtime, tech, player_id=player_id)))


@app.command("move")
def move(
    from_zone: int = typer.Option(..., "--from-zone", help="Current zone of the units to select."),
    to_zone: int = typer.Option(..., "--to-zone", help="Discovered destination zone."),
    who: str = typer.Option(..., "--who", callback=parse_move_who, help="Profession, military, or all."),
    count: int | None = typer.Option(None, "--count", min=1, help="Exact number to move; omit for all eligible matches."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Move a selected group between zones, with normal fighter combat enabled."""
    if from_zone == to_zone:
        raise typer.BadParameter("Source and destination zones must differ.")
    try:
        with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
            result = move_units(runtime, from_zone, to_zone, who, count=count, player_id=player_id)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(json.dumps(result, indent=2))


@tools_app.command("move-preview")
def move_preview(
    from_zone: int = typer.Option(..., "--from-zone", help="Current zone of the units to select."),
    to_zone: int = typer.Option(..., "--to-zone", help="Discovered destination zone."),
    who: str = typer.Option(..., "--who", callback=parse_move_who, help="Profession, military, or all."),
    count: int | None = typer.Option(None, "--count", min=1, help="Exact number to move; omit for all eligible matches."),
    player_id: int | None = typer.Option(None, "--player", help="Player UID; defaults to your player."),
) -> None:
    """Resolve a move and explain blocked units without sending any orders."""
    if from_zone == to_zone:
        raise typer.BadParameter("Source and destination zones must differ.")
    try:
        with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
            result = preview_move(runtime, from_zone, to_zone, who, count=count, player_id=player_id)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(json.dumps(result, indent=2))


@app.command("military")
def military(
    path: str = typer.Argument(..., help="Military path label from tools progression."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Choose a primary military path when the native XP requirement is met."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(choose_military_path(runtime, path, player_id=player_id)))


@tools_app.command("progression")
def progression(
    player_id: int | None = typer.Option(None, "--player", help="Player UID; defaults to your player."),
) -> None:
    """Read lore and military progression, costs and legal choices without unlocking."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(observe_progression(runtime, player_id=player_id), indent=2))


@app.command("upgrade")
def upgrade(
    building: str = typer.Option(..., "--building", help="Building family, or runtime UID for debugging."),
    zone_id: int | None = typer.Option(None, "--zone", help="Owned zone; required for a building family."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Upgrade one eligible building, paying the normal native cost."""
    try:
        with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
            result = upgrade_building(runtime, building, zone_id=zone_id, player_id=player_id)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(json.dumps(result))


@tools_app.command("upgrade-preview")
def upgrade_preview(
    building: str = typer.Option(..., "--building", help="Building family, or runtime UID for debugging."),
    zone_id: int | None = typer.Option(None, "--zone", help="Owned zone; required for a building family."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Inspect the next building upgrade, native cost and blocking reason."""
    try:
        with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
            result = preview_upgrade(runtime, building, zone_id=zone_id, player_id=player_id)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(json.dumps(result, indent=2))


@debug_app.command("add-resource")
def debug_add_resource(
    resource: str = typer.Argument(..., help="food, wood, gold/krowns, stone, iron or lore."),
    amount: float = typer.Argument(..., min=0, help="Positive amount to add through native resource bookkeeping."),
    player_id: int | None = typer.Option(None, "--player", help="Player UID; defaults to your player."),
) -> None:
    """Grant resources for offline manual checks; excluded from policy actions."""
    try:
        with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
            result = add_resources(runtime, resource, amount, player_id=player_id)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(json.dumps(result))


@app.command("feast")
def feast(
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Start a feast, paying the game's current resource cost."""
    try:
        with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
            result = start_feast(runtime, player_id=player_id)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(json.dumps(result))


@tools_app.command("feast")
def feast_preview(
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
) -> None:
    """Read feast state, next cost and eligibility without starting a feast."""
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        typer.echo(json.dumps(observe_feast(runtime, player_id=player_id), indent=2))


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
    unit_id: int | None = typer.Option(None, "--unit", help="Owned unit runtime ID, or choose --from-job."),
    building_id: str = typer.Option(..., "--building", help="Building family, e.g. scout_camp; a runtime UID also works for debugging."),
    player_id: int | None = typer.Option(None, "--player", help="Acting player UID; defaults to your player."),
    worker_job: str | None = typer.Option(None, "--from-job", callback=parse_worker_job, help="Worker profession, e.g. woodcutter."),
    source_zone_id: int | None = typer.Option(None, "--from-zone", help="Source zone for --from-job; defaults to the target building's zone."),
    target_zone_id: int | None = typer.Option(None, "--zone", help="Destination zone for a building family."),
    construction: bool = typer.Option(False, "--construction", help="Target construction of this family; defaults to completed buildings."),
) -> None:
    """Show whether Northgard would accept one unit/building assignment."""
    if worker_job is None and source_zone_id is not None:
        raise typer.BadParameter("Supply --from-job when using --from-zone.")
    if (unit_id is None) == (worker_job is None):
        raise typer.BadParameter("Choose either --unit or --from-job.")
    if not building_id.isdecimal() and target_zone_id is None:
        raise typer.BadParameter("Supply --zone with a building family.")
    if building_id.isdecimal() and (target_zone_id is not None or construction):
        raise typer.BadParameter("Use --zone/--construction with a building family, not a UID.")
    with NativeRuntime(ADAPTER, DEFAULT_EXE, DEBUG_PORT) as runtime:
        if unit_id is not None and building_id.isdecimal():
            result = preview_assignment(runtime, unit_id, int(building_id), player_id=player_id)
        else:
            result = resolve_assignment(
                runtime, building_id, job=worker_job, source_zone_id=source_zone_id,
                unit_id=unit_id, target_zone_id=target_zone_id,
                construction=construction, player_id=player_id,
            )
        typer.echo(json.dumps(result, indent=2))


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
            "Tensor to extract: pause, economy, temporal, zones or progression. "
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
