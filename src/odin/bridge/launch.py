"""Start Northgard without opening a debugger connection."""

from datetime import datetime
import os
from pathlib import Path
import subprocess


def launch_game(exe: Path, port: int, log_dir: Path) -> tuple[subprocess.Popen, Path]:
    """Return the launched process and log path"""
    # Make log dir
    log_dir = log_dir.resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    log_path = log_dir / f"northgard-debug-{timestamp}.log"

    # Allow steam to attach itself to this process
    environment = os.environ.copy()
    environment["SteamAppId"] = "466560"
    environment["SteamGameId"] = "466560"

    # Open the game as a subprocess
    game_path = exe.resolve()
    with log_path.open("xb") as log_file:
        game = subprocess.Popen(
            [str(game_path), "--debug", str(port)],
            cwd=str(game_path.parent),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=environment,
        )

    # Return game object and the log_path
    return game, log_path
