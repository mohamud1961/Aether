"""Provider failures, and which exceptions are transport faults or carry a Retry-After.

Split from provider.py (module-size cap, 2026-10-26) with the code unchanged.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


class ProviderError(RuntimeError):
    """The provider could not produce a response (after retries) or rejected the request."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        context_overflow: bool = False,
        deadline: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.context_overflow = context_overflow
        self.deadline = deadline  # the run's time ran out; not a provider fault


class IncompleteStream(ProviderError):
    """The stream stopped before a finish_reason. Nothing from it was dispatched, so the call is safe to retry
    (B1 dna-assembly: one cut stream at 256 s ended the whole run at 636 s of 1800 s)."""


def _is_transport(exc: Exception) -> bool:
    name = type(exc).__name__
    return name in {
        "APIConnectionError",
        "APITimeoutError",
        "RemoteProtocolError",
        "ReadTimeout",
        "ConnectError",
        "ReadError",
        "ConnectionResetError",
    }


def _retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    for key in ("retry-after-ms", "retry-after"):
        value = headers.get(key) if hasattr(headers, "get") else None
        if value:
            try:
                seconds = float(value) / (1000.0 if key.endswith("ms") else 1.0)
            except ValueError:
                if key.endswith("ms"):
                    continue
                try:
                    deadline = parsedate_to_datetime(value)
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    seconds = (deadline - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    continue
            if math.isfinite(seconds):
                return max(seconds, 0.5)
    return None


def _in_band_rate_limit(text: str) -> bool:
    """A rate limit the provider reported inside a 200 stream (an SSE ``error`` event): the SDK raises it with no
    status code. M1 b0 (2026-10-28): "exceeded token rate limit" ended runs at step 5 with no retry."""
    lowered = text.lower()
    return "rate limit" in lowered or "rate_limit" in lowered or "too many requests" in lowered


def _in_band_transient(text: str) -> bool:
    """A server fault the provider reported inside a 200 stream (no status code). Mission ho5 (2026-10-28):
    "The server is overloaded or not ready yet. Please try again later." ended a run at once as provider_error."""
    lowered = text.lower()
    # G14 (2026-11-17): the gateway's proxy reset the upstream connection mid-request ("upstream connect error or
    # disconnect/reset before headers. reset reason: connection termination"); nothing was produced, the row died.
    return any(k in lowered for k in ("overloaded", "not ready yet", "try again later", "server_error",
                                      "service unavailable", "internal server error", "upstream connect error",
                                      "reset before headers", "connection termination"))


def _retry_after_text(text: str) -> float | None:
    match = re.search(r"retry after (\d+(?:\.\d+)?) seconds?", text, re.IGNORECASE)
    return max(float(match.group(1)), 0.5) if match else None
