"""Small Debug Adapter Protocol client used by the HashLink bridge."""

import json
import queue
import threading
import time


class AdapterTimeout(RuntimeError):
    pass


class AdapterSession:
    def __init__(self, process):
        self.process = process
        self.sequence = 0
        self.incoming = queue.Queue()
        self.events = []
        self.responses = {}
        threading.Thread(target=self.read_messages, daemon=True).start()

    def read_messages(self):
        try:
            while True:
                headers = {}
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        raise RuntimeError("Debugger adapter closed its output.")
                    if line == b"\r\n":
                        break
                    key, value = line.decode("ascii").split(":", 1)
                    headers[key.lower()] = value.strip()

                length = int(headers["content-length"])
                body = bytearray()
                while len(body) < length:
                    chunk = self.process.stdout.read(length - len(body))
                    if not chunk:
                        raise RuntimeError("Incomplete debugger message.")
                    body.extend(chunk)
                self.incoming.put(json.loads(body))
        except Exception as error:
            self.incoming.put(error)

    def next_message(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AdapterTimeout("Debugger request timed out.")
        try:
            message = self.incoming.get(timeout=remaining)
        except queue.Empty:
            raise AdapterTimeout("Debugger request timed out.") from None
        if isinstance(message, Exception):
            raise RuntimeError(str(message))
        return message

    def request(self, command, arguments=None, timeout=30):
        self.sequence += 1
        sequence = self.sequence
        message = {
            "seq": sequence,
            "type": "request",
            "command": command,
            "arguments": arguments or {},
        }
        body = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self.process.stdin.write(header + body)
        self.process.stdin.flush()

        deadline = time.monotonic() + timeout
        while sequence not in self.responses:
            reply = self.next_message(deadline)
            if reply["type"] == "event":
                self.events.append(reply)
            elif reply["type"] == "response":
                self.responses[reply["request_seq"]] = reply

        reply = self.responses.pop(sequence)
        if not reply.get("success"):
            raise RuntimeError(f"{command} failed: {reply.get('message', reply.get('body'))}")

        body = reply.get("body") or {}
        if command == "evaluate":
            valid = isinstance(body.get("type"), str) and isinstance(body.get("result"), str)
            if not valid:
                expression = (arguments or {}).get("expression", "<missing expression>")
                raise RuntimeError(f"evaluate failed for {expression!r}: {body.get('result', body)}")
        return body

    def wait_for_stop(self, timeout=20):
        """Wait for the adapter's asynchronous `stopped` event and return its body."""
        deadline = time.monotonic() + timeout
        while True:
            # A stopped event may have arrived while we were waiting for an
            # earlier request, so check the events already collected first.
            for index, event in enumerate(self.events):
                if event["event"] == "stopped":
                    return self.events.pop(index)["body"]

            # Otherwise wait for the next debugger message. Responses are saved
            # for request(), while events are saved for this loop to inspect.
            message = self.next_message(deadline)
            if message["type"] == "event":
                self.events.append(message)
            elif message["type"] == "response":
                self.responses[message["request_seq"]] = message
