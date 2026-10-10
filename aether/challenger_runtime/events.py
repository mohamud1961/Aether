"""Task-local CHALLENGER event log: append-only JSONL outside the task workspace."""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
from typing import Any

from ..challenger_claim_ledger_state import TaskLocalClaimLedger, TaskLocalLedgerStore

EVENT_SCHEMA = "aether.challenger.runtime_event.v1"
EVENTS_NAME = "challenger_events.jsonl"


class ChallengerEventLog:
    """One log and one ledger snapshot per run directory; nothing crosses tasks."""

    def __init__(self, directory: Path, run_id: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / EVENTS_NAME
        self.run_id = run_id
        self._seq = 0
        self._lock = threading.RLock()
        self._store = TaskLocalLedgerStore(self.directory)

    def append(self, event: str, **fields: Any) -> None:
        with self._lock:
            self._seq += 1
            row = {"schema": EVENT_SCHEMA, "seq": self._seq, "run_id": self.run_id,
                   "event": event, "unix_s": round(time.time(), 3), **fields}
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, sort_keys=True, default=str, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

    def snapshot(self, ledger: TaskLocalClaimLedger) -> None:
        self._store.save(ledger)
