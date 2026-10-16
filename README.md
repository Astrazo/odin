# Odin

First migration milestone: launch Northgard with debugging enabled. Start Steam
and close any existing Northgard session before launching.

From this repository:

```powershell
uv run odin --help
uv run odin launch --help
uv run odin launch
```

The last command starts the game. Load an offline match manually. Odin exits and
leaves Northgard running; close the game normally when finished.

Override settings with `--exe PATH`, `--port 6112` and `--log-dir artifacts/runs`.
The log directory is relative to the current working directory. The printed PID
belongs to the process Odin started; if Steam relaunches the game, its current PID
may differ. Launch success does not prove that the debugger listener is ready.

## Follow the code

```text
odin command (pyproject.toml)
  -> main.py: main() runs the Typer app
  -> main.py: launch() parses options and reports errors/results
  -> bridge/launch.py: launch_game() starts Northgard
```

`launch_game()` validates the executable and port, checks that the local port is
available, sets the existing Steam application identity, and starts
`Northgard.exe --debug PORT` from its installation directory. Both stdout and
stderr go to a timestamped file in `artifacts/runs/` by default.

The CLI uses [Typer](https://typer.tiangolo.com/tutorial/commands/one-or-multiple/).
The callback keeps `launch` as an explicit subcommand, even while it is the only
command. Both `uv run odin` and `uv run python -m odin` use the same entry point.

## Migration scope and verification

16 October 2026: prepared from the launch-only path in
`northgard-god/northgard_bridge/cli/launch.py`. Connection probing, debugger
attach, observations and native actions are deferred. The original repository
is retained as the reference implementation.

Offline verification covers command help, argument/error handling and mocked
process creation. No game launch or debugger connection has been run here.
The first manual check is the launch command above, followed by loading a match.

The next migration step is verifying the current game PID and debugger listener,
then attaching to one known update frame.
