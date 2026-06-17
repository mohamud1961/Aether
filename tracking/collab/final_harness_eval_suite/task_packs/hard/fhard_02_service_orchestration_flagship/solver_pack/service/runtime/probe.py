#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from hashlib import sha256


def _probe_once(url: str, timeout: float) -> dict:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            return {
                "ok": response.status == 200,
                "http_status": response.status,
                "body_sha256": sha256(body).hexdigest(),
                "body_size": len(body),
                "body": body.decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        return {
            "ok": False,
            "http_status": exc.code,
            "body_sha256": sha256(body).hexdigest(),
            "body_size": len(body),
            "body": body.decode("utf-8", "replace"),
        }
    except Exception as exc:  # pragma: no cover - network edge cases are environment-specific
        return {"ok": False, "http_status": 0, "body_sha256": None, "body_size": 0, "body": repr(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--timeout-sec", type=float, default=2.0)
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}{args.endpoint}"
    print(json.dumps({"url": url, **_probe_once(url, args.timeout_sec)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
