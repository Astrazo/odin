"""Command-line entry point for Odin."""

import json
from pathlib import Path

import typer

from odin.actions.pause import pause_game
from odin.bridge.launch import launch_game
from odin.bridge.session import NativeRuntime
from odin.environment import NorthgardEnv, OBSERVATION_TENSORS
from odin.observations.temporal import observe_pause


app = typer.Typer(add_completion=False, no_args_is_help=True)
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
        typer.echo(json.dumps(env.observe()))
        while True:
            typer.echo(json.dumps(env.step()))
