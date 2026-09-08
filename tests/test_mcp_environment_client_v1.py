from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import queue
import sys
import tempfile
import threading
from typing import Any

from aether.mcp_environment_client import run


class _Server:
    def __init__(self, handler: type[BaseHTTPRequestHandler]) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


class _StreamableHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    observed_headers: list[dict[str, str]] = []

    def log_message(self, _format: str, *args: Any) -> None:
        del args

    def do_POST(self) -> None:  # noqa: N802
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        type(self).observed_headers.append({k: v for k, v in self.headers.items()})
        method = payload.get("method")
        if method == "notifications/initialized":
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if method == "initialize":
            result = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test", "version": "1"},
            }
        elif method == "tools/list":
            result = {
                "tools": [{
                    "name": "echo",
                    "description": "echo input",
                    "inputSchema": {"type": "object"},
                }]
            }
        elif method == "tools/call":
            result = {
                "content": [{"type": "text", "text": json.dumps(payload["params"]["arguments"], sort_keys=True)}],
                "isError": False,
            }
        else:
            self.send_error(400)
            return
        body = json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": result}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "test-session")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _LegacySSEHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    lock = threading.Lock()
    next_session = 0
    sessions: dict[str, queue.Queue[str]] = {}

    def log_message(self, _format: str, *args: Any) -> None:
        del args

    @classmethod
    def reset(cls) -> None:
        with cls.lock:
            cls.next_session = 0
            cls.sessions = {}

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/sse":
            self.send_error(404)
            return
        with type(self).lock:
            type(self).next_session += 1
            session = str(type(self).next_session)
            events: queue.Queue[str] = queue.Queue()
            type(self).sessions[session] = events
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(f"event: endpoint\ndata: /messages?session={session}\n\n".encode("utf-8"))
        self.wfile.flush()
        while True:
            try:
                data = events.get(timeout=0.1)
            except queue.Empty:
                continue
            if data == "__close__":
                return
            try:
                self.wfile.write(("event: message\ndata: " + data + "\n\n").encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/messages?session="):
            self.send_error(404)
            return
        session = self.path.split("session=", 1)[1]
        with type(self).lock:
            events = type(self).sessions.get(session)
        if events is None:
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        method = payload.get("method")
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "legacy", "version": "1"},
            }
        elif method == "tools/list":
            result = {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]}
        elif method == "tools/call":
            result = {
                "content": [{"type": "text", "text": "legacy:" + str(payload["params"]["arguments"].get("value"))}],
                "isError": False,
            }
        else:
            result = None
        if "id" in payload:
            events.put(json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": result}, separators=(",", ":")))
        self.send_response(202)
        self.send_header("Content-Length", "0")
        self.end_headers()


def test_streamable_http_tools_list_and_call_with_session_and_routing_headers() -> None:
    _StreamableHandler.observed_headers = []
    server = _Server(_StreamableHandler)
    try:
        config = {"name": "api", "transport": "streamable-http", "url": server.base + "/mcp"}
        listed = run(config, "tools_list", "", {}, 5)
        assert listed["result"]["tools"][0]["name"] == "echo"
        called = run(config, "tools_call", "echo", {"x": 1}, 5)
        assert called["result"]["isError"] is False
        headers = _StreamableHandler.observed_headers
        assert any(row.get("Mcp-Method") == "tools/call" and row.get("Mcp-Name") == "echo" for row in headers)
        assert any(row.get("Mcp-Session-Id") == "test-session" for row in headers if row.get("Mcp-Method") != "initialize")
    finally:
        server.close()


def test_legacy_sse_tools_list_and_call_use_endpoint_event_and_message_stream() -> None:
    _LegacySSEHandler.reset()
    server = _Server(_LegacySSEHandler)
    try:
        config = {"name": "legacy", "transport": "sse", "url": server.base + "/sse"}
        listed = run(config, "tools_list", "", {}, 5)
        assert listed["result"]["tools"][0]["name"] == "echo"
        called = run(config, "tools_call", "echo", {"value": 7}, 5)
        assert called["result"]["content"][0]["text"] == "legacy:7"
    finally:
        with _LegacySSEHandler.lock:
            for events in _LegacySSEHandler.sessions.values():
                events.put("__close__")
        server.close()


def test_stdio_tools_list_and_call_are_newline_delimited_json_rpc() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "stdio_server.py"
        script.write_text(
            '''import json,sys\nfor line in sys.stdin:\n p=json.loads(line); m=p.get("method")\n if "id" not in p: continue\n if m=="initialize": r={"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"stdio","version":"1"}}\n elif m=="tools/list": r={"tools":[{"name":"echo","inputSchema":{"type":"object"}}]}\n elif m=="tools/call": r={"content":[{"type":"text","text":"stdio:"+str(p["params"]["arguments"].get("value"))}],"isError":False}\n else: r={}\n print(json.dumps({"jsonrpc":"2.0","id":p["id"],"result":r}),flush=True)\n''',
            encoding="utf-8",
        )
        config = {
            "name": "local",
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(script)],
        }
        listed = run(config, "tools_list", "", {}, 5)
        assert listed["result"]["tools"][0]["name"] == "echo"
        called = run(config, "tools_call", "echo", {"value": 9}, 5)
        assert called["result"]["content"][0]["text"] == "stdio:9"
