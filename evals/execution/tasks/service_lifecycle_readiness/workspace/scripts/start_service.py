#!/usr/bin/env python3
"""Scaffold: a minimal HTTP service skeleton. Routes are not implemented yet."""
from __future__ import annotations

import signal
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 18923
HOST = "127.0.0.1"


class ServiceHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        # TODO: implement GET /health
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        # TODO: implement POST /echo
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def main() -> int:
    server = HTTPServer((HOST, PORT), ServiceHandler)
    signal.signal(signal.SIGTERM, lambda *_: (server.shutdown(),))
    signal.signal(signal.SIGINT, lambda *_: (server.shutdown(),))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
