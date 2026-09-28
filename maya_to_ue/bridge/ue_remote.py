"""bridge.ue_remote

Push Python to a running Unreal Editor via its Remote Execution protocol.

The protocol has two halves:

    1. Discovery — UDP multicast to 239.0.0.1:6766. We send ``ping``, the
       editor answers ``pong`` carrying its node id and project info.
    2. Execution — we open a TCP listener, tell the editor where it is via
       an ``open_connection`` multicast, and *the editor connects back*.
       Commands and results then travel over that socket.

Implemented here rather than reusing the engine's own ``remote_execution.py``
because that file lives under the engine install (``.../PythonScriptPlugin/
Content/Python/``), whose path differs per machine. The protocol is small;
locating the engine reliably is not. Keeping it local also means the whole
thing is testable without Maya or UE.

Everything is standard library. Nothing here imports maya or unreal.

Field notes from bringing this up against UE 5.7 — each cost a failed run:

    * Only the loopback interface receives the pong. Binding the multicast
      send to 0.0.0.0 or to the LAN address gets silence.
    * ``EvaluateStatement`` accepts a single expression only; multi-line
      code needs ``ExecuteFile`` or it dies with a SyntaxError.
    * The editor dials back to us, so the listener must exist *before*
      ``open_connection`` goes out.
"""

from __future__ import annotations

import json
import socket
import struct
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Protocol constants (must match UE's PythonScriptPlugin)
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = 1
PROTOCOL_MAGIC = "ue_py"

MULTICAST_GROUP = "239.0.0.1"
MULTICAST_PORT = 6766

TYPE_PING = "ping"
TYPE_PONG = "pong"
TYPE_OPEN_CONNECTION = "open_connection"
TYPE_CLOSE_CONNECTION = "close_connection"
TYPE_COMMAND = "command"
TYPE_COMMAND_RESULT = "command_result"

# Multi-statement code only survives in file mode.
EXEC_MODE_FILE = "ExecuteFile"

DISCOVER_TIMEOUT = 3.0
CONNECT_BACK_TIMEOUT = 5.0
COMMAND_TIMEOUT = 120.0


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class EditorNode:
    """A discovered editor and the interface we reached it on."""

    node_id: str
    interface: str
    project_name: str = ""
    engine_version: str = ""

    def describe(self) -> str:
        bits = [b for b in (self.project_name, self.engine_version) if b]
        return " · ".join(bits) or self.node_id


@dataclass
class PushResult:
    """Outcome of a push. Never raises — the UI reads these three fields.

    Network code fails in too many ways (timeout, refused, silently dropped
    by a firewall) for callers to be handed exceptions; every path lands
    here instead.
    """

    ok: bool
    message: str = ""
    output: List[str] = field(default_factory=list)
    editor: Optional[EditorNode] = None

    def output_text(self) -> str:
        return "".join(self.output).strip()


# ---------------------------------------------------------------------------
# Message plumbing
# ---------------------------------------------------------------------------

def build_message(node_id: str, msg_type: str, dest: str = "", data=None) -> dict:
    """Assemble a protocol message. `dest` is omitted when not targeting."""
    msg = {
        "version": PROTOCOL_VERSION,
        "magic": PROTOCOL_MAGIC,
        "source": node_id,
        "type": msg_type,
    }
    if dest:
        msg["dest"] = dest
    if data is not None:
        msg["data"] = data
    return msg


def encode_message(node_id: str, msg_type: str, dest: str = "", data=None) -> bytes:
    return json.dumps(build_message(node_id, msg_type, dest, data)).encode("utf-8")


def parse_message(raw: bytes) -> Optional[dict]:
    """Decode a protocol message, or None if it isn't one of ours."""
    try:
        msg = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict):
        return None
    if msg.get("magic") != PROTOCOL_MAGIC:
        return None
    if msg.get("version") != PROTOCOL_VERSION:
        return None
    return msg


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------

def local_ipv4s() -> List[str]:
    """Local IPv4 addresses, loopback first.

    Which interface works is a property of the machine, not something we can
    predict — so we try them all. Loopback leads because a local editor is
    always reachable that way, while virtual adapters and VPNs routinely
    swallow multicast and would only burn timeout.
    """
    found = []

    def add(addr):
        if addr and addr not in found:
            found.append(addr)

    add("127.0.0.1")
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    return found


def _multicast_socket(interface: str) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", MULTICAST_PORT))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    sock.setsockopt(
        socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(interface)
    )
    sock.setsockopt(
        socket.IPPROTO_IP,
        socket.IP_ADD_MEMBERSHIP,
        struct.pack("4s4s", socket.inet_aton(MULTICAST_GROUP), socket.inet_aton(interface)),
    )
    return sock


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover(timeout: float = DISCOVER_TIMEOUT) -> Optional[EditorNode]:
    """Find a running editor. Returns None if none answers in time."""
    per_interface = max(0.4, timeout / max(1, len(local_ipv4s())))
    for interface in local_ipv4s():
        node = _discover_on(interface, per_interface)
        if node is not None:
            return node
    return None


def _discover_on(interface: str, timeout: float) -> Optional[EditorNode]:
    node_id = str(uuid.uuid4())
    try:
        sock = _multicast_socket(interface)
    except OSError:
        return None

    ping = encode_message(node_id, TYPE_PING)
    sock.settimeout(0.4)
    import time

    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            try:
                sock.sendto(ping, (MULTICAST_GROUP, MULTICAST_PORT))
            except OSError:
                return None
            try:
                raw, _ = sock.recvfrom(65536)
            except socket.timeout:
                continue
            except OSError:
                return None
            msg = parse_message(raw)
            if not msg or msg.get("type") != TYPE_PONG:
                continue
            # Our own ping bounces back off the group; ignore it.
            if msg.get("source") == node_id:
                continue
            data = msg.get("data") or {}
            return EditorNode(
                node_id=msg.get("source", ""),
                interface=interface,
                project_name=data.get("project_name", ""),
                engine_version=data.get("engine_version", ""),
            )
    finally:
        sock.close()
    return None


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def execute(node: EditorNode, code: str,
            timeout: float = COMMAND_TIMEOUT,
            on_listening=None) -> PushResult:
    """Run *code* in the discovered editor and return what it reported.

    ``on_listening`` is called with the port we ended up bound to, right
    after the listener goes up. The port is chosen by the OS, so this is
    the only way anything outside can know where to dial — tests use it to
    stand in for the editor.
    """
    node_id = str(uuid.uuid4())

    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Port 0: let the OS pick. A fixed port collides the moment a second
        # Maya is open.
        listener.bind((node.interface, 0))
        listener.listen(1)
        listener.settimeout(CONNECT_BACK_TIMEOUT)
        command_port = listener.getsockname()[1]
    except OSError as exc:
        return PushResult(False, f"无法建立本地监听端口：{exc}", editor=node)

    if on_listening is not None:
        try:
            on_listening(command_port)
        except Exception:
            pass

    try:
        mc = _multicast_socket(node.interface)
    except OSError as exc:
        listener.close()
        return PushResult(False, f"无法建立多播套接字：{exc}", editor=node)

    try:
        # The editor dials us, so the listener above must already exist.
        mc.sendto(
            encode_message(
                node_id, TYPE_OPEN_CONNECTION, dest=node.node_id,
                data={"command_ip": node.interface, "command_port": command_port},
            ),
            (MULTICAST_GROUP, MULTICAST_PORT),
        )
        try:
            conn, _ = listener.accept()
        except socket.timeout:
            return PushResult(
                False, "编辑器没有连回来（可能被防火墙拦截）", editor=node
            )
        except OSError as exc:
            return PushResult(False, f"等待编辑器连接失败：{exc}", editor=node)

        try:
            conn.settimeout(timeout)
            conn.sendall(
                encode_message(
                    node_id, TYPE_COMMAND, dest=node.node_id,
                    data={
                        "command": code,
                        "unattended": True,
                        # Multi-line code needs file mode; statement mode
                        # only accepts a single expression.
                        "exec_mode": EXEC_MODE_FILE,
                    },
                )
            )
            return _read_result(conn, node)
        finally:
            try:
                mc.sendto(
                    encode_message(node_id, TYPE_CLOSE_CONNECTION, dest=node.node_id),
                    (MULTICAST_GROUP, MULTICAST_PORT),
                )
            except OSError:
                pass
            conn.close()
    finally:
        mc.close()
        listener.close()


def _read_result(conn: socket.socket, node: EditorNode) -> PushResult:
    buffer = b""
    while True:
        try:
            chunk = conn.recv(65536)
        except socket.timeout:
            return PushResult(False, "等待执行结果超时", editor=node)
        except OSError as exc:
            return PushResult(False, f"读取结果失败：{exc}", editor=node)
        if not chunk:
            return PushResult(False, "连接被编辑器关闭", editor=node)
        buffer += chunk
        msg = parse_message(buffer)
        if msg is None:
            continue      # partial JSON, keep reading
        if msg.get("type") != TYPE_COMMAND_RESULT:
            buffer = b""
            continue
        data = msg.get("data") or {}
        lines = [entry.get("output", "") for entry in data.get("output") or []]
        if data.get("success"):
            return PushResult(True, "", lines, editor=node)
        return PushResult(False, str(data.get("result") or "执行失败"), lines, editor=node)


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def push(code: str, discover_timeout: float = DISCOVER_TIMEOUT,
         command_timeout: float = COMMAND_TIMEOUT) -> PushResult:
    """Discover an editor and run *code* in it."""
    node = discover(discover_timeout)
    if node is None:
        return PushResult(False, "没有发现正在运行的 UE 编辑器")
    return execute(node, code, command_timeout)


__all__ = [
    "EditorNode",
    "PushResult",
    "build_message",
    "encode_message",
    "parse_message",
    "local_ipv4s",
    "discover",
    "execute",
    "push",
]
