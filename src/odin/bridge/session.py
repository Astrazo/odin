"""Connect to Northgard and expose the native calls Odin currently uses."""

import hashlib
import json
from pathlib import Path
import subprocess
import time
import warnings

from .protocol import AdapterSession


PACKAGE_DIR = Path(__file__).resolve().parents[1]
BUILD_PATH = PACKAGE_DIR / "data" / "supported_build.json"
NATIVE_DIR = PACKAGE_DIR / "native"


class NativeRuntime:
    """A paused Northgard frame that can make Odin's reviewed native calls."""

    def __init__(
        self,
        adapter: Path,
        exe: Path,
        port: int = 6112,
    ) -> None:
        self.adapter = adapter.resolve()
        self.exe = exe.resolve()
        self.port = port
        self.process = None
        self.session = None
        self.frame = None
        self.thread = None
        self.build = None
        self.boot = None
        self.attach_attempted = False

    def __enter__(self):
        try:
            self.open()
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, kind, error, traceback):
        self.close()

    def _confirm_game_version(self) -> None:
        build = json.loads(BUILD_PATH.read_text(encoding="utf-8"))
        self.build = build

        boot = self.exe.parent / "hlboot.dat"
        self.boot = boot
        boot_hash = hashlib.sha256(boot.read_bytes()).hexdigest()

        if boot_hash != build["northgard_bytecode_sha256"]:
            raise RuntimeError("Northgard changed; rediscover the native function IDs.")

    def _create_debugger_adapter(self) -> None:
        self.process = subprocess.Popen(
            ["node", str(NATIVE_DIR / "abi_adapter.js"), str(self.adapter)],
            cwd=self.adapter.parent,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.session = AdapterSession(self.process)

    def _connect_to_northgard(self) -> None:
        self.session.request("initialize", {
            "adapterID": "hl",
            "clientID": "odin",
            "linesStartAt1": True,
            "columnsStartAt1": True,
            "pathFormat": "path",
        })

        self.attach_attempted = True
        self.session.request("attach", {
            "program": str(self.boot),
            "cwd": str(self.exe.parent),
            "port": self.port,
            "classPaths": [],
        })

    def _stop_at_game_update(self, *, finish_configuration: bool = False) -> None:
        # Game.onUpdate is our known safe place to access the main Game object.
        # advance() calls this after Northgard has been running for 0.5 seconds.
        update = self.build["update_frame"]
        source = {"path": str(self.exe.parent / update["source"])}

        # Arm a breakpoint for the next time Northgard reaches Game.onUpdate.
        self.session.request("setBreakpoints", {
            "source": source,
            "breakpoints": [{"line": update["line"]}],
        })

        # This is only required for the first stop after attaching. It tells the
        # debugger that initial setup is complete and Northgard may start running.
        if finish_configuration:
            self.session.request("configurationDone")

        # Block until the adapter reports that Northgard has stopped. Because the
        # breakpoint above is armed, the expected stop is inside Game.onUpdate.
        stopped = self.session.wait_for_stop()

        # Ask which function is currently executing on the stopped thread. Its
        # frame ID gives native calls access to Game.onUpdate's `this` object.
        frames = self.session.request("stackTrace", {
            "threadId": stopped["threadId"],
            "levels": 1,
        })["stackFrames"]
        if not frames or update["name"] not in frames[0]["name"]:
            raise RuntimeError(f"Stopped in an unexpected frame: {frames}")

        self.thread = stopped["threadId"]
        self.frame = frames[0]["id"]

        # We have the stopped frame now, so disarm the one-shot breakpoint. This
        # does not resume Northgard; observe() and act() still use the frame above.
        self.session.request("setBreakpoints", {"source": source, "breakpoints": []})

    def open(self) -> None:
        """Attach and stop at Game.onUpdate, where `this` is the game instance."""
        self._confirm_game_version()
        self._create_debugger_adapter()
        self._connect_to_northgard()
        self._stop_at_game_update(finish_configuration=True)

    def advance_step(self, seconds: float = 0.5) -> None:
        """Run Northgard for a while, then capture a fresh Game.onUpdate frame."""
        if self.session is None or self.frame is None or self.thread is None:
            raise RuntimeError("The native runtime is not connected.")

        thread = self.thread
        self.frame = None
        self.thread = None
        self.session.request("continue", {"threadId": thread})
        time.sleep(seconds)
        self._stop_at_game_update()

    def call_native(self, expression: str) -> str:
        """Make an allowlisted native call using the current stopped frame."""
        if self.session is None or self.frame is None:
            raise RuntimeError("The native runtime is not connected.")
        body = self.session.request("evaluate", {
            "expression": expression,
            "frameId": self.frame,
            "context": "repl",
        })
        return body["result"]

    def evaluate(self, expression: str) -> str:
        """Resolve debugger metadata used to locate native call arguments."""
        return self.call_native(expression)

    def array_length(self, expression: str) -> int:
        """Read an array's length from debugger metadata without a game getter."""
        if self.session is None or self.frame is None:
            raise RuntimeError("The native runtime is not connected.")
        body = self.session.request("evaluate", {
            "expression": expression,
            "frameId": self.frame,
            "context": "repl",
        })
        length = body.get("indexedVariables")
        if type(length) is not int:
            raise RuntimeError(f"No array length available for {expression}.")
        return length

    def close(self) -> None:
        """Detach the adapter without closing Northgard."""
        if self.attach_attempted:
            try:
                self.session.request("disconnect", {"terminateDebuggee": False}, timeout=5)
            except Exception as error:
                warnings.warn(
                    f"Debugger adapter PID {self.process.pid} left running: {error}. "
                    "Detach is unconfirmed; terminating it could close Northgard.",
                    RuntimeWarning,
                )
                return
            self.attach_attempted = False

        if self.process is not None and self.process.poll() is None:
            # The patched adapter acknowledges only after native detach. Close
            # its input and allow normal shutdown before considering a kill.
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
        if self.process is not None:
            self.session = None
            self.frame = None
            self.thread = None
