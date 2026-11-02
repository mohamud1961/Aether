"""The Core loop's result and append-only trace records."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import time
from typing import Any


@dataclass
class RunResult:
    status: str  # finished | timeout | provider_error | context_error | no_tool_loop
    steps: int = 0
    usage: dict[str, int | None] = field(default_factory=dict)
    sub_usage: dict[str, int] = field(default_factory=dict)  # llm() and checkpoint calls
    calls: int = 0
    failed_attempts: int = 0
    request_chars: list[int] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    # Harness facts and model summary delivered to the caller, never to the model.
    final_account: str = ""


class Trace:
    def __init__(self, path: Path) -> None:
        self._path = self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._t0 = time.monotonic()

    def __call__(self, event: str, **data: Any) -> None:
        row = {"t": round(time.monotonic() - self._t0, 3), "event": event, **data}
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def durable(self, event: str, **data: Any) -> None:
        row = {"t": round(time.monotonic() - self._t0, 3), "event": event, **data}
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
