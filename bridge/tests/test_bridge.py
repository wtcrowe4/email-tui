"""Tests with a fake extension. They use invented data and never touch Thunderbird."""

import io
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "bin"))

from email_tui_bridge import client, mcp_server
from email_tui_bridge.host import ALLOWED_METHODS, Host, read_native, write_native


class Framing(unittest.TestCase):
    def test_round_trip(self):
        stream = io.BytesIO()
        write_native(stream, {"id": 1, "text": "héllo"})
        stream.seek(0)
        self.assertEqual(read_native(stream), {"id": 1, "text": "héllo"})

    def test_end_of_stream(self):
        self.assertIsNone(read_native(io.BytesIO()))

    def test_rejects_oversized_message(self):
        with self.assertRaises(ValueError):
            read_native(io.BytesIO((2**32 - 1).to_bytes(4, sys.byteorder)))


class HostOverSocket(unittest.TestCase):
    """Runs a real host. A thread plays Thunderbird on the native pipes."""

    def setUp(self):
        # Unix socket paths have a short length limit, so use a short directory.
        self.directory = Path(tempfile.mkdtemp(prefix="etb", dir="/tmp"))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.path = self.directory / "run" / "bridge.sock"
        patcher = mock.patch.dict(os.environ, {"EMAIL_TUI_SOCKET": str(self.path)})
        patcher.start()
        self.addCleanup(patcher.stop)

        to_host_r, to_host_w = os.pipe()
        from_host_r, from_host_w = os.pipe()
        self.ext_out = os.fdopen(to_host_w, "wb")
        self.ext_in = os.fdopen(from_host_r, "rb")
        self.host = Host(os.fdopen(to_host_r, "rb"), os.fdopen(from_host_w, "wb"), self.path)
        self.host.bind()
        threading.Thread(target=self.host.accept_loop, daemon=True).start()
        self.runner = threading.Thread(target=self.run_host, daemon=True)
        self.runner.start()
        self.addCleanup(self.ext_in.close)
        self.addCleanup(self.stop_host)
        self.seen = []
        threading.Thread(target=self.fake_extension, daemon=True).start()

    def run_host(self):
        while (message := read_native(self.host.native_in)) is not None:
            self.host.handle_native(message)

    def stop_host(self):
        self.ext_out.close()
        self.runner.join(2)
        # Gives the fake extension end of file, so closing ext_in cannot block.
        self.host.native_out.close()
        self.host.listener.close()

    def fake_extension(self):
        try:
            while (message := read_native(self.ext_in)) is not None:
                self.seen.append(message)
                if message["method"] == "search":
                    reply = {"id": message["id"], "ok": False, "error": "fake failure"}
                else:
                    reply = {"id": message["id"], "ok": True, "result": message.get("params")}
                write_native(self.ext_out, reply)
        except (OSError, ValueError):
            pass

    def test_socket_is_private(self):
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)

    def test_request_reaches_extension_and_returns(self):
        self.assertEqual(client.call("read", id=7), {"id": 7})

    def test_extension_error_becomes_bridge_error(self):
        with self.assertRaisesRegex(client.BridgeError, "fake failure"):
            client.call("search", text="x")

    def test_blocked_methods_never_reach_extension(self):
        for method in ("send", "delete", "move", "messages.delete", "__proto__"):
            with self.assertRaisesRegex(client.BridgeError, "not allowed"):
                client.call(method)
        self.assertEqual(self.seen, [])

    def test_invalid_json_is_rejected(self):
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(5)
            sock.connect(str(self.path))
            sock.sendall(b"not json\n")
            reply = json.loads(sock.makefile().readline())
        self.assertFalse(reply["ok"])

    def test_events_reach_subscribers(self):
        stream = client.events()
        received = []
        ready = threading.Event()

        def consume():
            ready.set()
            received.append(next(stream))

        thread = threading.Thread(target=consume, daemon=True)
        thread.start()
        ready.wait(2)
        for _ in range(100):
            if self.host.subscribers:
                break
            threading.Event().wait(0.02)
        self.host.handle_native({"event": "new_mail", "account": "a1", "count": 2})
        thread.join(5)
        self.assertEqual(received, [{"event": "new_mail", "account": "a1", "count": 2}])

    def test_missing_bridge_has_helpful_error(self):
        with mock.patch.dict(os.environ, {"EMAIL_TUI_SOCKET": str(self.directory / "none.sock")}):
            with self.assertRaisesRegex(client.BridgeError, "Thunderbird"):
                client.call("status")


class SafetyBoundary(unittest.TestCase):
    def test_extension_has_no_dangerous_permission(self):
        manifest = json.loads((ROOT / "bridge/extension/manifest.json").read_text())
        self.assertEqual(
            set(manifest["permissions"]),
            {"accountsRead", "messagesRead", "compose", "nativeMessaging", "alarms"},
        )
        self.assertNotIn("experiment_apis", manifest)
        self.assertNotIn("host_permissions", manifest)

    def test_extension_calls_no_dangerous_api(self):
        source = (ROOT / "bridge/extension/background.js").read_text()
        for name in ("sendMessage", "saveMessage", "messages.delete", "messages.move",
                     "messages.update", "messages.import", "fetch(", "getRaw"):
            self.assertNotIn(name, source)

    def test_host_allowlist(self):
        self.assertEqual(ALLOWED_METHODS, {"status", "accounts", "unread", "search", "read", "draft"})

    def test_mcp_tools_only_use_allowed_methods(self):
        for tool in mcp_server.TOOLS.values():
            self.assertIn(tool["method"], ALLOWED_METHODS)


class McpServer(unittest.TestCase):
    def rpc(self, method, params=None, request_id=1):
        return mcp_server.handle({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})

    def test_initialize_echoes_version(self):
        result = self.rpc("initialize", {"protocolVersion": "2025-03-26"})["result"]
        self.assertEqual(result["protocolVersion"], "2025-03-26")
        self.assertIn("untrusted", result["instructions"])

    def test_notifications_get_no_reply(self):
        self.assertIsNone(mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tool_list(self):
        tools = {t["name"]: t for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertEqual(
            set(tools),
            {"list_accounts", "unread_counts", "search_messages", "read_message", "open_draft"},
        )
        self.assertFalse(tools["open_draft"]["annotations"]["readOnlyHint"])
        self.assertTrue(tools["read_message"]["annotations"]["readOnlyHint"])

    def test_unknown_tool_is_rpc_error(self):
        self.assertEqual(self.rpc("tools/call", {"name": "send_message"})["error"]["code"], -32602)

    def test_unknown_argument_is_refused(self):
        with mock.patch.object(mcp_server, "call") as call:
            result = self.rpc("tools/call", {"name": "open_draft", "arguments": {"attachments": ["/etc/passwd"]}})["result"]
        self.assertTrue(result["isError"])
        call.assert_not_called()

    def test_tool_call_returns_json_text(self):
        with mock.patch.object(mcp_server, "call", return_value=[{"unread": 3}]) as call:
            result = self.rpc("tools/call", {"name": "unread_counts"})["result"]
        call.assert_called_once_with("unread")
        self.assertEqual(json.loads(result["content"][0]["text"]), [{"unread": 3}])

    def test_bridge_failure_is_tool_error(self):
        with mock.patch.object(mcp_server, "call", side_effect=client.BridgeError("down")):
            result = self.rpc("tools/call", {"name": "list_accounts"})["result"]
        self.assertTrue(result["isError"])


if __name__ == "__main__":
    unittest.main()
