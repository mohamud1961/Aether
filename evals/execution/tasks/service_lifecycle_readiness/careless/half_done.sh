#!/usr/bin/env bash
# expect: echo_status_mismatch
# Implements GET /health with the contract body, but leaves POST /echo unimplemented, so it answers 404.
set -euo pipefail
mkdir -p out
cat > out/service_impl.py <<'PY'
import json
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"status": "ok", "version": "1.0"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # read the body first: closing a socket with unread data resets the connection, which the
        # grader would see as a failed probe instead of the 404 this agent is meant to show
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer(("127.0.0.1", 18923), Handler)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, f: threading.Thread(target=server.shutdown, daemon=True).start())
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
