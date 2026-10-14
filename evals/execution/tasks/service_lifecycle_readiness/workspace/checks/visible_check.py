#!/usr/bin/env python3
"""Readiness gate for the solver-visible service contract."""
from __future__ import annotations

import json
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PORT = 18923


def _port_is_free() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((HOST, PORT)) != 0


def _http_get(url: str, timeout: float = 2.0) -> dict:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {
                "ok": True,
                "status": resp.status,
                "content_type": resp.headers.get_content_type(),
                "body": resp.read().decode("utf-8"),
            }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _http_post(url: str, body: str, timeout: float = 2.0) -> dict:
    try:
        req = urllib.request.Request(
            url,
            data=body.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {
                "ok": True,
                "status": resp.status,
                "content_type": resp.headers.get_content_type(),
                "body": resp.read().decode("utf-8"),
            }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _wait_for_bind() -> bool:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        result = _http_get(f"http://{HOST}:{PORT}/health", timeout=1.0)
        if result.get("ok"):
            return True
        time.sleep(0.2)
    return False


def _check_service(workspace: Path) -> list[str]:
    reasons: list[str] = []
    if not _port_is_free():
        return ["port_already_in_use"]

    proc = subprocess.Popen(
        [sys.executable, str(workspace / "out" / "service_impl.py")],
        cwd=str(workspace),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_for_bind():
            return ["service_did_not_bind"]

        health = _http_get(f"http://{HOST}:{PORT}/health")
        if not health.get("ok"):
            reasons.append("health_probe_failed")
        else:
            try:
                health_body = json.loads(health.get("body", ""))
            except json.JSONDecodeError:
                health_body = {}
                reasons.append("health_response_not_json")
            if health.get("status") != 200 or health_body != {"status": "ok", "version": "1.0"}:
                reasons.append("health_response_mismatch")

        echo = _http_post(f"http://{HOST}:{PORT}/echo", "visible-probe")
        if not echo.get("ok"):
            reasons.append("echo_probe_failed")
        else:
            try:
                echo_body = json.loads(echo.get("body", ""))
            except json.JSONDecodeError:
                echo_body = {}
                reasons.append("echo_response_not_json")
            if echo.get("status") != 200 or echo_body != {"echo": "visible-probe"}:
                reasons.append("echo_response_mismatch")

        time.sleep(1.0)
        if proc.poll() is not None:
            reasons.append("service_crashed_before_second_observation")
        else:
            second = _http_get(f"http://{HOST}:{PORT}/health")
            if not second.get("ok"):
                reasons.append("second_health_probe_failed")

        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                exit_code = proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                reasons.append("shutdown_timeout")
                proc.kill()
                proc.wait(timeout=3.0)
            else:
                if exit_code != 0:
                    reasons.append("unclean_shutdown")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3.0)
    return reasons


def main() -> int:
    workspace = Path(__file__).resolve().parents[1]
    impl_path = workspace / "out" / "service_impl.py"

    reasons = []
    if not impl_path.exists():
        reasons.append("missing_service_impl")
    elif impl_path.stat().st_size == 0:
        reasons.append("empty_service_impl")
    else:
        reasons.extend(_check_service(workspace))

    result = {"passed": not reasons, "reason_codes": reasons}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
