"""Client for the bridge's Unix socket."""

import json
import os
import socket
from pathlib import Path

TIMEOUT_SECONDS = 60


class BridgeError(RuntimeError):
    pass


def socket_path() -> Path:
    override = os.environ.get("EMAIL_TUI_SOCKET")
    if override:
        return Path(override)
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/email-tui-{os.getuid()}"
    return Path(runtime) / "email-tui" / "bridge.sock"


def _connect(timeout: float | None) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(socket_path()))
    except OSError as error:
        sock.close()
        raise BridgeError(
            "bridge not reachable. Is Thunderbird running with the Email TUI Bridge add-on?"
        ) from error
    return sock


def call(method: str, **params) -> object:
    """Send one request and return its result."""
    with _connect(TIMEOUT_SECONDS) as sock:
        sock.sendall(json.dumps({"id": 1, "method": method, "params": params}).encode() + b"\n")
        with sock.makefile("rb") as stream:
            try:
                line = stream.readline()
            except TimeoutError as error:
                raise BridgeError(f"timed out waiting for {method}") from error
    if not line:
        raise BridgeError("bridge closed the connection")
    reply = json.loads(line)
    if not reply.get("ok"):
        raise BridgeError(reply.get("error", "unknown bridge error"))
    return reply.get("result")


def events():
    """Yield events such as new mail until the bridge closes."""
    with _connect(None) as sock:
        sock.sendall(json.dumps({"id": 1, "method": "subscribe"}).encode() + b"\n")
        with sock.makefile("rb") as stream:
            for line in stream:
                message = json.loads(line)
                if "event" in message:
                    yield message
