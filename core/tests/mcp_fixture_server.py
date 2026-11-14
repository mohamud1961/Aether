"""A small real MCP server for tests: SSE, streamable HTTP or stdio, with per-session state.

Tools: ``count`` (per-session counter, proves the session persists), ``shot`` (returns a PNG image item),
``fail`` (returns isError). Run as ``python mcp_fixture_server.py sse|http PORT`` or ``... stdio``.
"""

import base64
import json
import queue
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")).decode()
TOOLS = [{"name": "count", "description": "Increment this session's counter.", "inputSchema": {"type": "object"}},
         {"name": "shot", "description": "Return an image.", "inputSchema": {"type": "object"}},
         {"name": "fail", "description": "Always fails.", "inputSchema": {"type": "object"}}]


def handle(message, state):
    method, ident = message.get("method"), message.get("id")
    if ident is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fixture", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        name = message["params"]["name"]
        if name == "count":
            state["n"] = state.get("n", 0) + 1
            result = {"content": [{"type": "text", "text": f"count={state['n']}"}]}
        elif name == "shot":
            result = {"content": [{"type": "text", "text": "here"}, {"type": "image", "data": PNG,
                                                                      "mimeType": "image/png"}]}
        elif name == "fail":
            result = {"content": [{"type": "text", "text": "it broke"}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": f"unknown tool {name}"}}
    else:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


SESSIONS = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):  # SSE stream
        sid = uuid.uuid4().hex
        SESSIONS[sid] = ({}, queue.Queue())
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(f"event: endpoint\ndata: /messages?sessionId={sid}\n\n".encode())
        self.wfile.flush()
        state, out = SESSIONS[sid]
        while True:
            reply = out.get()
            self.wfile.write(f"event: message\ndata: {json.dumps(reply)}\n\n".encode())
            self.wfile.flush()

    def do_POST(self):
        message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.startswith("/messages"):
            state, out = SESSIONS[self.path.split("sessionId=")[1]]
            reply = handle(message, state)
            self.send_response(202)
            self.end_headers()
            if reply:
                out.put(reply)
            return
        sid = self.headers.get("Mcp-Session-Id") or uuid.uuid4().hex  # streamable HTTP
        state = SESSIONS.setdefault(sid, ({}, None))[0]
        reply = handle(message, state)
        if reply is None:
            self.send_response(202)
            self.send_header("Mcp-Session-Id", sid)
            self.end_headers()
            return
        body = f"event: message\ndata: {json.dumps(reply)}\n\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Mcp-Session-Id", sid)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    if sys.argv[1] == "stdio":
        state = {}
        for line in sys.stdin:
            reply = handle(json.loads(line), state)
            if reply:
                sys.stdout.write(json.dumps(reply) + "\n")
                sys.stdout.flush()
        return
    server = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[2])), Handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
