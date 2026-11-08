"""Native messaging host. Thunderbird starts it and it serves a private Unix socket.

Thunderbird side: 4-byte length + JSON on stdin and stdout.
Client side: one JSON object per line.
"""

import json
import os
import socket
import struct
import sys
import threading
from pathlib import Path

from .client import socket_path
from .protected import redact

# Everything the add-on offers. There is no send method, and the add-on has no send permission.
ALLOWED_METHODS = frozenset({
    "status", "accounts", "unread", "career", "search", "read", "draft", "saveDraft",
    "folders", "createFolder", "renameFolder", "moveFolder", "deleteFolder", "markFolderRead",
    "moveMessages", "copyMessages", "archiveMessages", "trashMessages", "updateMessages",
    "tags", "createTag", "updateTag", "contacts", "addressBooks", "createContact",
    "identities", "setSignature",
})
MAX_REQUEST_BYTES = 256 * 1024
MAX_NATIVE_BYTES = 64 * 1024 * 1024
PING_SECONDS = 15


def read_native(stream) -> dict | None:
    header = stream.read(4)
    if len(header) < 4:
        return None
    length = struct.unpack("=I", header)[0]
    if length > MAX_NATIVE_BYTES:
        raise ValueError("native message too large")
    payload = stream.read(length)
    if len(payload) < length:
        return None
    return json.loads(payload)


def write_native(stream, message: dict) -> None:
    payload = json.dumps(message).encode()
    stream.write(struct.pack("=I", len(payload)) + payload)
    stream.flush()


class Client:
    def __init__(self, conn: socket.socket):
        self.conn = conn
        self.lock = threading.Lock()

    def send(self, message: dict) -> bool:
        try:
            with self.lock:
                self.conn.sendall(json.dumps(message).encode() + b"\n")
            return True
        except OSError:
            return False


class Host:
    def __init__(self, native_in, native_out, path: Path):
        self.native_in = native_in
        self.native_out = native_out
        self.path = path
        self.write_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.pending: dict[int, tuple[Client, object, str]] = {}
        self.subscribers: set[Client] = set()
        self.next_id = 0
        self.stopped = threading.Event()
        self.listener: socket.socket | None = None

    def to_extension(self, message: dict) -> None:
        with self.write_lock:
            write_native(self.native_out, message)

    def bind(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self.path.unlink(missing_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.path))
        os.chmod(self.path, 0o600)
        listener.listen(16)
        self.listener = listener

    def accept_loop(self) -> None:
        while not self.stopped.is_set():
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self.serve_client, args=(conn,), daemon=True).start()

    def serve_client(self, conn: socket.socket) -> None:
        client = Client(conn)
        try:
            with conn, conn.makefile("rb") as stream:
                while True:
                    line = stream.readline(MAX_REQUEST_BYTES + 1)
                    if not line:
                        return
                    if len(line) > MAX_REQUEST_BYTES:
                        client.send({"ok": False, "error": "request too large"})
                        return
                    self.handle_request(client, line)
        except OSError:
            pass
        finally:
            with self.state_lock:
                self.subscribers.discard(client)
                for key in [k for k, (c, _, _) in self.pending.items() if c is client]:
                    del self.pending[key]

    def handle_request(self, client: Client, line: bytes) -> None:
        try:
            request = json.loads(line)
            method = request["method"]
            request_id = request.get("id")
        except (ValueError, KeyError, TypeError):
            client.send({"ok": False, "error": "invalid request"})
            return
        if method == "subscribe":
            with self.state_lock:
                self.subscribers.add(client)
            client.send({"id": request_id, "ok": True})
            return
        if method not in ALLOWED_METHODS:
            client.send({"id": request_id, "ok": False, "error": f"method not allowed: {method}"})
            return
        with self.state_lock:
            self.next_id += 1
            native_id = self.next_id
            self.pending[native_id] = (client, request_id, method)
        self.to_extension({"id": native_id, "method": method, "params": request.get("params") or {}})

    def handle_native(self, message: dict) -> None:
        if "event" in message:
            with self.state_lock:
                subscribers = list(self.subscribers)
            for client in subscribers:
                client.send(message)
            return
        with self.state_lock:
            entry = self.pending.pop(message.get("id"), None)
        if entry:
            client, request_id, method = entry
            if message.get("ok"):
                message = {**message, "result": redact(method, message.get("result"))}
            client.send({**message, "id": request_id})

    def ping_loop(self) -> None:
        while not self.stopped.wait(PING_SECONDS):
            try:
                self.to_extension({"type": "ping"})
            except (OSError, ValueError):
                return

    def run(self) -> None:
        self.bind()
        threading.Thread(target=self.accept_loop, daemon=True).start()
        threading.Thread(target=self.ping_loop, daemon=True).start()
        try:
            while (message := read_native(self.native_in)) is not None:
                self.handle_native(message)
        finally:
            self.stopped.set()
            self.listener.close()
            self.path.unlink(missing_ok=True)


def main() -> None:
    Host(sys.stdin.buffer, sys.stdout.buffer, socket_path()).run()
