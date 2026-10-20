"""Offline tests for named native operations; no adapter or game is opened."""

from collections import deque
from pathlib import Path
import unittest
from unittest.mock import Mock
import subprocess

from odin.actions.pause import pause_game
from odin.bridge.session import NativeRuntime
from odin.observations.temporal import observe_pause


class FakeSession:
    def __init__(self, values):
        self.values = {expression: deque(results) for expression, results in values.items()}
        self.expressions = []

    def request(self, command, arguments=None, timeout=30):
        if command != "evaluate":
            raise AssertionError(f"Unexpected command: {command}")
        expression = arguments["expression"]
        self.expressions.append(expression)
        return {"result": self.values[expression].popleft()}


class FakeStepSession:
    def __init__(self):
        self.requests = []

    def request(self, command, arguments=None, timeout=30):
        self.requests.append((command, arguments))
        if command == "stackTrace":
            return {"stackFrames": [{"id": 84, "name": "Game.onUpdate"}]}
        return {}

    def wait_for_stop(self):
        return {"threadId": 8, "reason": "breakpoint"}


def runtime(values):
    bridge = NativeRuntime(
        Path("adapter.js"),
        Path("Northgard.exe"),
        6112,
    )
    bridge.session = FakeSession(values)
    bridge.frame = 42
    return bridge


class NativeRuntimeTests(unittest.TestCase):
    def test_close_waits_for_adapter_exit_after_confirmed_detach(self):
        bridge = runtime({})
        bridge.attach_attempted = True
        bridge.session = Mock()
        session = bridge.session
        bridge.process = Mock()
        bridge.process.poll.return_value = None

        bridge.close()

        session.request.assert_called_once_with(
            "disconnect", {"terminateDebuggee": False}, timeout=5,
        )
        bridge.process.stdin.close.assert_called_once_with()
        bridge.process.wait.assert_called_once_with(timeout=5)
        bridge.process.terminate.assert_not_called()

    def test_close_keeps_adapter_alive_when_disconnect_fails(self):
        bridge = runtime({})
        bridge.attach_attempted = True
        bridge.session = Mock()
        bridge.session.request.side_effect = RuntimeError("detach failed")
        bridge.process = Mock()
        bridge.process.poll.return_value = None
        bridge.process.pid = 1234

        with self.assertWarnsRegex(RuntimeWarning, "1234.*detach failed"):
            bridge.close()

        bridge.process.stdin.close.assert_not_called()
        bridge.process.terminate.assert_not_called()
        bridge.process.wait.assert_not_called()

    def test_close_can_terminate_a_detached_adapter_that_does_not_exit(self):
        bridge = runtime({})
        bridge.attach_attempted = True
        bridge.session = Mock()
        bridge.process = Mock()
        bridge.process.poll.return_value = None
        bridge.process.wait.side_effect = [subprocess.TimeoutExpired("node", 5), 0]

        bridge.close()

        bridge.process.terminate.assert_called_once_with()
        self.assertEqual(bridge.process.wait.call_count, 2)

    def test_advance_reuses_session_and_replaces_frame(self):
        bridge = runtime({})
        bridge.thread = 7
        bridge.build = {
            "update_frame": {"source": "src/Game.hx", "line": 2067, "name": "Game.onUpdate"}
        }
        bridge.session = FakeStepSession()

        bridge.advance_step(0)

        self.assertEqual(bridge.thread, 8)
        self.assertEqual(bridge.frame, 84)
        self.assertEqual(
            [command for command, arguments in bridge.session.requests],
            ["continue", "setBreakpoints", "stackTrace", "setBreakpoints"],
        )

    def test_pause_observation_uses_only_native_is_paused(self):
        bridge = runtime({"this.state.isPaused()": ["false"]})
        self.assertEqual(
            observe_pause(bridge),
            {"feature_names": ["is_paused"], "x": [0.0]},
        )
        self.assertEqual(bridge.session.expressions, ["this.state.isPaused()"])

    def test_pause_action_uses_fixed_native_sequence_once(self):
        bridge = runtime({
            "this.state.isPaused()": ["false", "true"],
            "this.state.isMulti(null)": ["false"],
            "this.state.me.ui.setPause(true, this.state.me)": ["null"],
        })
        self.assertEqual(
            pause_game(bridge),
            {"before_is_paused": False, "after_is_paused": True},
        )
        self.assertEqual(bridge.session.expressions, [
            "this.state.isPaused()",
            "this.state.isMulti(null)",
            "this.state.me.ui.setPause(true, this.state.me)",
            "this.state.isPaused()",
        ])

    def test_already_paused_aborts_before_action(self):
        bridge = runtime({"this.state.isPaused()": ["true"]})
        with self.assertRaisesRegex(RuntimeError, "already paused"):
            pause_game(bridge)
        self.assertEqual(bridge.session.expressions, ["this.state.isPaused()"])

    def test_multiplayer_aborts_before_action(self):
        bridge = runtime({
            "this.state.isPaused()": ["false"],
            "this.state.isMulti(null)": ["true"],
        })
        with self.assertRaisesRegex(RuntimeError, "offline single-player"):
            pause_game(bridge)
        self.assertNotIn(
            "this.state.me.ui.setPause(true, this.state.me)",
            bridge.session.expressions,
        )


if __name__ == "__main__":
    unittest.main()
