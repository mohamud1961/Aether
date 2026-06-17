"""Append-only run logging and trajectory capture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runner.schemas import (
    validate_event,
    validate_event_sequence,
    validate_route_manifest,
    validate_run_header,
    validate_score_envelope,
    utc_now,
)


class RunLogger:
    """Writes Packet 01 run artifacts without mutating history."""

    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.header_path = self.run_dir / "run_header.json"
        self.events_path = self.run_dir / "run_events.jsonl"
        self.score_path = self.run_dir / "score_envelope.json"
        self.route_manifest_path = self.run_dir / "route_manifest.json"

    def start_run(self, run_header: dict[str, Any]) -> None:
        validate_run_header(run_header)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.header_path.exists():
            raise FileExistsError(f"run header already exists: {self.header_path}")
        self.header_path.write_text(
            json.dumps(run_header, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.events_path.touch(exist_ok=False)

    def append_event(
        self,
        *,
        phase: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        artifact_refs: list[str] | None = None,
        correlation_id: str | None = None,
        ts_utc: str | None = None,
    ) -> dict[str, Any]:
        if not self.header_path.exists():
            raise FileNotFoundError("start_run must be called before append_event")
        if self.score_path.exists():
            raise RuntimeError("cannot append events after score_envelope is written")
        seq = self.next_seq()
        event = {
            "seq": seq,
            "ts_utc": ts_utc or utc_now(),
            "phase": phase,
            "event_type": event_type,
            "correlation_id": correlation_id,
            "payload": payload or {"details": {}},
            "artifact_refs": artifact_refs or [],
        }
        event.setdefault("payload", {}).setdefault("details", {})
        validate_event(event)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def write_score_envelope(self, score_envelope: dict[str, Any]) -> None:
        validate_score_envelope(score_envelope)
        if not self.header_path.exists():
            raise FileNotFoundError("start_run must be called before write_score_envelope")
        if not self.events_path.exists():
            raise FileNotFoundError("run_events.jsonl must exist before write_score_envelope")
        if self.score_path.exists():
            raise FileExistsError(f"score envelope already exists: {self.score_path}")
        self.score_path.write_text(
            json.dumps(score_envelope, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def write_route_manifest(self, route_manifest: dict[str, Any]) -> None:
        validate_route_manifest(route_manifest)
        if not self.header_path.exists():
            raise FileNotFoundError("start_run must be called before write_route_manifest")
        if self.route_manifest_path.exists():
            raise FileExistsError(f"route manifest already exists: {self.route_manifest_path}")
        self.route_manifest_path.write_text(
            json.dumps(route_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def next_seq(self) -> int:
        if not self.events_path.exists():
            return 0
        return len(self.read_events())

    def read_header(self) -> dict[str, Any]:
        return validate_run_header(json.loads(self.header_path.read_text(encoding="utf-8")))

    def read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        events = [
            json.loads(line)
            for line in self.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return validate_event_sequence(events)

    def read_route_manifest(self) -> dict[str, Any]:
        return validate_route_manifest(json.loads(self.route_manifest_path.read_text(encoding="utf-8")))
