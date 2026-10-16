"""Command-line entry point for Odin."""

from pathlib import Path
from typing import Annotated

import typer

from odin.bridge.launch import launch_game


app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def cli() -> None:
    """Launch Northgard; debugger connection comes in a later step."""


@app.command()
def launch(
    exe: Annotated[Path, typer.Option(help="Path to Northgard.exe")] = Path(
        r"C:\Program Files (x86)\Steam\steamapps\common\Northgard\Northgard.exe"
    ),
    port: Annotated[int, typer.Option(min=1, max=65535, help="Local debug port")] = 6112,
    log_dir: Annotated[Path, typer.Option(help="Directory for game output logs")] = Path("artifacts/runs"),
) -> None:
    """Start the game with debugging enabled and leave it running."""
    try:
        game, log_path = launch_game(exe, port, log_dir)
    except (OSError, ValueError) as error:
        typer.echo(f"Could not launch Northgard: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Launched process ID: {game.pid}")
    typer.echo(f"Game output: {log_path}")
    typer.echo("Load an offline match manually. Close Northgard normally when finished.")

def main() -> None:
    app()
