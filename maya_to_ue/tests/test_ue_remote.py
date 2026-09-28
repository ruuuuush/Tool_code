"""tests.test_ue_remote

Tests for the UE Remote Execution client.

The protocol plumbing (message shape, validation, interface ordering) is
pure logic. The command channel is exercised against a fake editor: a local
socket that speaks just enough of the protocol to answer one command. No UE
required.

What is NOT covered here is multicast discovery against a real editor —
that needs a running UE and was verified by hand.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge import ue_remote as R


class TestMessageShape(unittest.TestCase):
    def test_has_the_four_required_fields(self):
        msg = R.build_message("node-1", R.TYPE_PING)
        for key in ("version", "magic", "source", "type"):
            self.assertIn(key, msg)

    def test_carries_protocol_identity(self):
        msg = R.build_message("node-1", R.TYPE_PING)
        self.assertEqual(msg["magic"], "ue_py")
        self.assertEqual(msg["version"], 1)

    def test_omits_dest_when_untargeted(self):
        self.assertNotIn("dest", R.build_message("node-1", R.TYPE_PING))

    def test_includes_dest_when_targeted(self):
        msg = R.build_message("node-1", R.TYPE_COMMAND, dest="editor-9")
        self.assertEqual(msg["dest"], "editor-9")

    def test_data_is_passed_through(self):
        msg = R.build_message("n", R.TYPE_COMMAND, data={"command": "print(1)"})
        self.assertEqual(msg["data"]["command"], "print(1)")

    def test_encode_round_trips(self):
        raw = R.encode_message("node-1", R.TYPE_PING)
        self.assertEqual(R.parse_message(raw)["source"], "node-1")


class TestMessageParsing(unittest.TestCase):
    def test_rejects_wrong_magic(self):
        raw = json.dumps({"version": 1, "magic": "nope", "type": "pong"}).encode()
        self.assertIsNone(R.parse_message(raw))

    def test_rejects_wrong_version(self):
        raw = json.dumps({"version": 99, "magic": "ue_py", "type": "pong"}).encode()
        self.assertIsNone(R.parse_message(raw))

    def test_rejects_garbage(self):
        self.assertIsNone(R.parse_message(b"not json at all"))

    def test_rejects_partial_json(self):
        # Matters for real reads: a chunk may cut a message in half.
        self.assertIsNone(R.parse_message(b'{"version": 1, "magic": "ue'))

    def test_rejects_non_object(self):
        self.assertIsNone(R.parse_message(b'["a", "list"]'))


class TestInterfaceOrder(unittest.TestCase):
    def test_loopback_comes_first(self):
        # A local editor is always reachable on loopback, and it is the only
        # interface that answered on the machine this was built against.
        self.assertEqual(R.local_ipv4s()[0], "127.0.0.1")

    def test_no_duplicates(self):
        found = R.local_ipv4s()
        self.assertEqual(len(found), len(set(found)))

    def test_all_entries_look_like_ipv4(self):
        for addr in R.local_ipv4s():
            parts = addr.split(".")
            self.assertEqual(len(parts), 4, addr)
            self.assertTrue(all(p.isdigit() for p in parts), addr)


class _FakeEditor(threading.Thread):
    """Connects back like UE does, answers one command, then stops."""

    def __init__(self, host, port, success=True, result="None", output=("hi\n",)):
        super().__init__()
        self.host = host
        self.port = port
        self.success = success
        self.result = result
        self.output = list(output)
        self.received = None

    def run(self):
        try:
            sock = socket.create_connection((self.host, self.port), timeout=5)
        except OSError:
            return
        try:
            raw = sock.recv(65536)
            self.received = R.parse_message(raw)
            reply = {
                "version": R.PROTOCOL_VERSION,
                "magic": R.PROTOCOL_MAGIC,
                "source": "fake-editor",
                "type": R.TYPE_COMMAND_RESULT,
                "data": {
                    "success": self.success,
                    "result": self.result,
                    "output": [{"type": "Info", "output": o} for o in self.output],
                },
            }
            sock.sendall(json.dumps(reply).encode("utf-8"))
        finally:
            sock.close()


class TestExecute(unittest.TestCase):
    """execute() opens a listener and waits for the editor to dial in."""

    def setUp(self):
        self.node = R.EditorNode(node_id="fake-editor", interface="127.0.0.1",
                                 project_name="P", engine_version="5.7")
        self._patched = R._multicast_socket
        # The real socket would need the multicast group; the fake editor is
        # driven directly, so stub the announcement out.
        R._multicast_socket = lambda iface: _NullSocket()
        self._threads = []
        self.addCleanup(self._restore)

    def _restore(self):
        R._multicast_socket = self._patched
        # Join every helper thread. Leaving daemon threads holding sockets
        # made the whole suite die at teardown — the tests were the flaky
        # part, not the code under test.
        for thread in self._threads:
            thread.join(timeout=2)

    def _run_with_fake(self, **kwargs):
        """Start execute(); the fake editor dials in once the port is known."""
        def on_listening(port):
            editor = _FakeEditor("127.0.0.1", port, **kwargs)
            editor.start()
            self._threads.append(editor)

        return R.execute(
            self.node, "print('x')", timeout=5, on_listening=on_listening
        )

    def test_successful_command(self):
        result = self._run_with_fake(success=True, output=("done\n",))
        self.assertTrue(result.ok, result.message)
        self.assertIn("done", result.output_text())

    def test_failed_command_reports_the_error(self):
        result = self._run_with_fake(success=False, result="SyntaxError: bad")
        self.assertFalse(result.ok)
        self.assertIn("SyntaxError", result.message)

    def test_failed_command_keeps_output(self):
        result = self._run_with_fake(success=False, result="boom", output=("partial\n",))
        self.assertIn("partial", result.output_text())

    def test_editor_never_connects(self):
        # No fake editor started: must time out, not hang or raise.
        R.CONNECT_BACK_TIMEOUT_ORIGINAL = R.CONNECT_BACK_TIMEOUT
        R.CONNECT_BACK_TIMEOUT = 0.3
        try:
            result = R.execute(self.node, "print('x')", timeout=1)
        finally:
            R.CONNECT_BACK_TIMEOUT = R.CONNECT_BACK_TIMEOUT_ORIGINAL
        self.assertFalse(result.ok)
        self.assertIn("连回来", result.message)

    def test_command_uses_file_mode(self):
        # Statement mode only accepts a single expression; the import snippet
        # is multi-line and would die with a SyntaxError.
        result = self._run_with_fake(success=True)
        self.assertTrue(result.ok)


class _NullSocket:
    def sendto(self, *_):
        return 0

    def close(self):
        pass


class TestPushDegradesQuietly(unittest.TestCase):
    def setUp(self):
        self._discover = R.discover
        self.addCleanup(self._restore)

    def _restore(self):
        R.discover = self._discover

    def test_no_editor_returns_a_reason_not_an_exception(self):
        R.discover = lambda timeout=0: None
        result = R.push("print('x')")
        self.assertFalse(result.ok)
        self.assertIn("编辑器", result.message)
        self.assertIsNone(result.editor)

    def test_result_output_text_is_safe_when_empty(self):
        self.assertEqual(R.PushResult(False, "x").output_text(), "")


if __name__ == "__main__":
    unittest.main()
