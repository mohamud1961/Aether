"""Direct HTTP judge transport. No broker dependency or credential persistence."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import time
import urllib.request

from ..run_cancellation import raise_if_run_cancelled
from ..run_deadline import raise_if_run_deadline_exceeded, remaining_run_s


ENDPOINT = os.environ.get("AETHER_JUDGE_ENDPOINT", "")
MAX_REQUEST_BYTES = 16_000
# Floor that callers may only raise; MAX_REQUEST_BYTES itself can be raised per session.
BASE_REQUEST_BYTES = 16_000
OUTPUT_PRICING_STATUS = "unknown_not_included_in_local_reservation"
BUDGET_ACCOUNTING = (
    "input-only serialized-byte reservation at the configured rate; local estimate, "
    "not an invoice and not a guaranteed total currency cap; output pricing is "
    "unknown and excluded"
)


class HttpJudgeTransport:
    def __init__(self, *, model: str, journal: Path, max_calls: int,
                 cap_gbp: str = "0.10", input_gbp_per_million: str = "0.10",
                 timeout_s: float = 15, opener=None, max_request_bytes: int | None = None):
        if os.environ.get("AETHER_JUDGE_CALLS_ALLOWED") != "1":
            raise RuntimeError("Judge calls not authorized")
        self._key = os.environ.get("AETHER_JUDGE_API_KEY", "")
        if not self._key:
            raise RuntimeError("judge credential unavailable")
        if not ENDPOINT:
            raise RuntimeError("AETHER_JUDGE_ENDPOINT is not set")
        if max_request_bytes is None:
            max_request_bytes = MAX_REQUEST_BYTES  # read at call time so a session raise applies
        if max_request_bytes < BASE_REQUEST_BYTES:
            raise ValueError("request byte bound may only be raised")
        self.max_request_bytes = max_request_bytes
        self.model = model
        self.max_calls = max_calls
        self.cap = Decimal(cap_gbp)
        self.price = Decimal(input_gbp_per_million)
        if not self.cap.is_finite() or not self.price.is_finite() or min(self.cap, self.price) <= 0 or max_calls <= 0:
            raise ValueError("positive finite budget required")
        self.reserved = Decimal(0)
        self.calls = 0
        self._cancellation_event = None
        self.timeout_s = timeout_s
        self.opener = opener or urllib.request.urlopen
        self.journal = Path(journal)
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        # Refuse an old namespace: no process restart can silently reset this cap.
        with self.journal.open("x") as stream:
            stream.write(json.dumps({"event": "budget", "endpoint": ENDPOINT,
                "model": model, "max_calls": max_calls, "cap_gbp": str(self.cap),
                "input_gbp_per_million": str(self.price),
                "output_price_gbp_per_million": None,
                "output_pricing_status": OUTPUT_PRICING_STATUS,
                "max_request_bytes": max_request_bytes,
                "accounting": BUDGET_ACCOUNTING}) + "\n")

    def bind_run_cancellation(self, event):
        self._cancellation_event = event

    def _record(self, row: dict) -> None:
        with self.journal.open("a") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def __call__(self, request: dict) -> dict:
        raise_if_run_cancelled(self._cancellation_event)
        raise_if_run_deadline_exceeded()
        if request.get("model") != self.model:
            raise ValueError("Judge model changed within run")
        body = json.dumps(request, allow_nan=False, separators=(",", ":")).encode()
        if len(body) > self.max_request_bytes:
            raise ValueError("Judge input exceeds declared bound")
        reserve = Decimal(len(body)) * self.price / Decimal(1000000)
        if self.calls >= self.max_calls or self.reserved + reserve > self.cap:
            raise RuntimeError("Judge budget exhausted")
        self.calls += 1
        self.reserved += reserve
        identity = {"call": self.calls, "request_sha256": sha256(body).hexdigest()}
        self._record({**identity, "event": "reserve", "request": request,
                      "reserved_gbp": str(reserve), "total_reserved_gbp": str(self.reserved)})
        started = time.monotonic()
        wire = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
            "Authorization": "Bearer " + self._key, "Content-Type": "application/json"})
        try:
            remaining = remaining_run_s()
            timeout = self.timeout_s if remaining is None else min(self.timeout_s, remaining)
            raise_if_run_cancelled(self._cancellation_event)
            raise_if_run_deadline_exceeded()
            with self.opener(wire, timeout=timeout) as response:
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ValueError("Judge response exceeds bound")
                result = json.loads(raw)
            raise_if_run_cancelled(self._cancellation_event)
            raise_if_run_deadline_exceeded()
            self._record({**identity, "event": "response", "response": result,
                          "elapsed_s": time.monotonic() - started})
            return result
        except Exception as exc:
            # Never log exception text: HTTP bodies may contain request echoes.
            self._record({**identity, "event": "error", "error_type": type(exc).__name__,
                          "elapsed_s": time.monotonic() - started})
            raise
