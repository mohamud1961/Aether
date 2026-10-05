"""Credential-free file broker transport for selective JUDGE experiments.

A research row writes one bounded public-evidence request and waits for a matching
response. An external broker owns judge credentials and provider dispatch.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping

from ..run_cancellation import raise_if_run_cancelled
from ..run_deadline import raise_if_run_deadline_exceeded, remaining_run_s

REQUEST_SCHEMA = "aether.judge_broker_request.v1"
RESPONSE_SCHEMA = "aether.judge_broker_response.v1"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


class FileBrokerEvaluator:
    """Bounded JUDGE evaluator without provider credentials in the row process."""

    def __init__(
        self,
        *,
        broker_dir: Path,
        journal: Path,
        expected_result_model: str,
        max_calls: int,
        cap_gbp: str = "0.01",
        input_gbp_per_million: str = "0.10",
        timeout_s: float = 180.0,
        poll_s: float = 0.25,
    ) -> None:
        self.broker_dir = Path(broker_dir)
        self.broker_dir.mkdir(parents=True, exist_ok=True)
        self.journal = Path(journal)
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        self.expected_result_model = str(expected_result_model)
        self.max_calls = int(max_calls)
        self.cap = Decimal(cap_gbp)
        self.price = Decimal(input_gbp_per_million)
        if (
            not self.expected_result_model
            or self.max_calls < 1
            or self.max_calls > 64
            or not self.cap.is_finite()
            or not self.price.is_finite()
            or self.cap <= 0
            or self.price <= 0
            or timeout_s <= 0
            or poll_s <= 0
        ):
            raise ValueError("invalid JUDGE file-broker configuration")
        self.timeout_s = float(timeout_s)
        self.poll_s = float(poll_s)
        self.calls = 0
        self.reserved = Decimal(0)
        self._cancellation_event = None
        with self.journal.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "event": "broker_budget",
                "transport": "file_broker_v1",
                "max_calls": self.max_calls,
                "cap_gbp": str(self.cap),
                "input_gbp_per_million": str(self.price),
                "expected_result_model": self.expected_result_model,
            }, sort_keys=True) + "\n")

    def bind_run_cancellation(self, event: Any) -> None:
        self._cancellation_event = event

    def _record(self, row: Mapping[str, Any]) -> None:
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(row), sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        raise_if_run_cancelled(self._cancellation_event)
        raise_if_run_deadline_exceeded()
        if self.calls >= self.max_calls:
            raise RuntimeError("JUDGE broker call budget exhausted")
        encoded = _canonical_bytes(request)
        if len(encoded) > 16000:
            raise ValueError("JUDGE broker request exceeds declared bound")
        reserve = Decimal(len(encoded)) * self.price / Decimal(1_000_000)
        if self.reserved + reserve > self.cap:
            raise RuntimeError("JUDGE broker spend cap exhausted")

        self.calls += 1
        self.reserved += reserve
        call_id = self.calls
        request_sha = sha256(encoded).hexdigest()
        request_path = self.broker_dir / f"request_{call_id:03d}.json"
        response_path = self.broker_dir / f"response_{call_id:03d}.json"
        envelope = {
            "schema": REQUEST_SCHEMA,
            "call": call_id,
            "request_sha256": request_sha,
            "expected_result_model": self.expected_result_model,
            "cap_gbp": str(self.cap),
            "request": request,
        }
        tmp = request_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(request_path)
        self._record({
            "event": "broker_request",
            "call": call_id,
            "request_sha256": request_sha,
            "request_bytes": len(encoded),
            "reserved_gbp": str(reserve),
            "total_reserved_gbp": str(self.reserved),
            "request_file": request_path.name,
        })

        started = time.monotonic()
        while True:
            raise_if_run_cancelled(self._cancellation_event)
            raise_if_run_deadline_exceeded()
            elapsed = time.monotonic() - started
            remaining = remaining_run_s()
            effective_timeout = self.timeout_s if remaining is None else min(self.timeout_s, remaining)
            if elapsed >= effective_timeout:
                self._record({
                    "event": "broker_timeout",
                    "call": call_id,
                    "request_sha256": request_sha,
                    "elapsed_s": elapsed,
                })
                raise TimeoutError("JUDGE broker response timed out")
            if response_path.is_file():
                try:
                    response = json.loads(response_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    time.sleep(self.poll_s)
                    continue
                if response.get("schema") != RESPONSE_SCHEMA:
                    raise ValueError("invalid JUDGE broker response schema")
                if response.get("request_sha256") != request_sha:
                    raise ValueError("JUDGE broker response request hash mismatch")
                provider_result = response.get("provider_result")
                if not isinstance(provider_result, Mapping):
                    raise ValueError("JUDGE broker response missing provider_result")
                result = provider_result.get("result")
                if (
                    not isinstance(result, Mapping)
                    or str(result.get("model") or "") != self.expected_result_model
                ):
                    raise ValueError("JUDGE broker underlying model identity mismatch")
                self._record({
                    "event": "broker_response",
                    "call": call_id,
                    "request_sha256": request_sha,
                    "response_file": response_path.name,
                    "response_sha256": sha256(_canonical_bytes(response)).hexdigest(),
                    "elapsed_s": elapsed,
                    "gateway_request_id": response.get("gateway_request_id"),
                    "provider_model": result.get("model"),
                    "usage": result.get("usage"),
                })
                return dict(provider_result)
            time.sleep(self.poll_s)
