#!/usr/bin/env bash
# Writes out/service_impl.py: a standard-library HTTP server that implements spec/service_contract.md.
# The server answers GET /health and POST /echo on 127.0.0.1:18923 and shuts down with exit code 0
# when it receives SIGTERM or SIGINT. The shutdown runs on a separate thread because
# HTTPServer.shutdown() blocks until serve_forever() returns, so it cannot run on the serving thread.
set -euo pipefail
mkdir -p out
cat > out/service_impl.py <<'PY'
#!/usr/bin/env python3
"""Local HTTP service: GET /health and POST /echo on 127.0.0.1:18923."""
from __future__ import annotations

import json
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 18923
HEALTH_BODY = {"status": "ok", "version": "1.0"}


class ServiceHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(HEALTH_BODY)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/echo":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            self._send_json({"echo": raw})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def main() -> int:
    server = HTTPServer((HOST, PORT), ServiceHandler)

    def _shutdown(signum: int, frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
