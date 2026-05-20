#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "service" / "config" / "service_config.json"


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _serve(port: int, endpoint: str, ready_delay_sec: float) -> None:
    started_at = time.time()
    ready_at = started_at + max(0.0, ready_delay_sec)
    state_path = ROOT / "service_runtime_state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "port": port,
                "endpoint": endpoint,
                "ready_delay_sec": ready_delay_sec,
                "started_at": started_at,
                "ready_at": ready_at,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != endpoint:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"not-found")
                return

            if time.time() < ready_at:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"booting")
                return

            body = json.dumps({"status": "ok", "service": "chain-ready"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.serve_forever(poll_interval=0.25)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--ready-delay-sec", type=float, default=None)
    args = parser.parse_args()

    config = _load_config()
    port = args.port if args.port is not None else int(config["required_port"])
    endpoint = args.endpoint if args.endpoint is not None else str(config["endpoint_path"])
    ready_delay_sec = args.ready_delay_sec if args.ready_delay_sec is not None else float(config.get("ready_delay_sec", 0.0))

    if args.serve:
        _serve(port, endpoint, ready_delay_sec)
        return 0

    log_path = ROOT / "service.log"
    pid_path = ROOT / "service.pid"
    launch_receipt_path = ROOT / "service_launch_receipt.json"

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--serve",
        "--port",
        str(port),
        "--endpoint",
        endpoint,
        "--ready-delay-sec",
        str(ready_delay_sec),
    ]

    with log_path.open("ab") as log_file:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log_file, stderr=subprocess.STDOUT)

    pid_path.write_text(f"{proc.pid}\n", encoding="utf-8")
    launch_receipt_path.write_text(
        json.dumps(
            {
                "service_name": config["service_name"],
                "required_port": port,
                "endpoint_path": endpoint,
                "expected_persistence_mode": config["expected_persistence_mode"],
                "pid": proc.pid,
                "ready_delay_sec": ready_delay_sec,
                "launch_timestamp": time.time(),
                "status": "launched",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"launched": True, "pid": proc.pid, "port": port, "endpoint": endpoint}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
