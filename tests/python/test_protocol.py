"""Offline tests for the small DAP transport."""

import io
import json
import unittest
from types import SimpleNamespace

from odin.bridge.protocol import AdapterSession


def frame(message):
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


class FragmentedInput(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 2) if size >= 0 else size)


class ProtocolTests(unittest.TestCase):
    def session(self, messages):
        process = SimpleNamespace(
            stdin=io.BytesIO(),
            stdout=FragmentedInput(b"".join(frame(value) for value in messages)),
        )
        return AdapterSession(process)

    def test_fragmented_utf8_response(self):
        session = self.session([{
            "type": "response",
            "request_seq": 1,
            "success": True,
            "body": {"result": "Harald → paused", "type": "String"},
        }])
        self.assertEqual(session.request("evaluate")["result"], "Harald → paused")

    def test_stop_event_is_preserved_during_a_request(self):
        session = self.session([
            {"type": "event", "event": "stopped", "body": {"threadId": 17}},
            {"type": "response", "request_seq": 1, "success": True},
        ])
        session.request("configurationDone")
        self.assertEqual(session.wait_for_stop()["threadId"], 17)

    def test_error_response_includes_command(self):
        session = self.session([{
            "type": "response",
            "request_seq": 1,
            "success": False,
            "message": "Not a function",
        }])
        with self.assertRaisesRegex(RuntimeError, "evaluate failed: Not a function"):
            session.request("evaluate")

    def test_evaluator_error_is_rejected(self):
        session = self.session([{
            "type": "response",
            "request_seq": 1,
            "success": True,
            "body": {"result": "Exception has occurred"},
        }])
        with self.assertRaisesRegex(RuntimeError, "evaluate failed.*isPaused"):
            session.request("evaluate", {"expression": "this.state.isPaused()"})

    def test_void_native_return_is_accepted(self):
        session = self.session([{
            "type": "response",
            "request_seq": 1,
            "success": True,
            "body": {"result": "null", "type": "Void"},
        }])
        self.assertEqual(session.request("evaluate")["type"], "Void")

    def test_incomplete_message_fails(self):
        process = SimpleNamespace(
            stdin=io.BytesIO(),
            stdout=io.BytesIO(b"Content-Length: 20\r\n\r\n{}"),
        )
        session = AdapterSession(process)
        with self.assertRaisesRegex(RuntimeError, "Incomplete debugger message"):
            session.request("initialize")


if __name__ == "__main__":
    unittest.main()
