from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

from ..utils.hashes import canonical_json_dumps, sha256_bytes, sha256_text, stable_hash


NULL_EVENT_HASH = "0" * 64


DEFAULT_TrunCATION = {
    "stdout": {
        "truncated": False,
        "size_bytes": 0,
        "captured_bytes": 0,
        "unknown": False,
    },
    "stderr": {
        "truncated": False,
        "size_bytes": 0,
        "captured_bytes": 0,
        "unknown": False,
    },
}


DEFAULT_EVENT_FIELDS: Dict[str, Any] = {
    "tool_name": None,
    "tool_args": None,
    "exit_code": None,
    "files_read": [],
    "files_written": [],
    "artifact_refs": [],
    "truncation": DEFAULT_TrunCATION,
    "verifier_run": False,
    "verifier_result": None,
    "triggers_fired": [],
    "trigger_explanation": None,
    "workspace_fingerprint_hash": None,
    "dirty_since_last_verify": None,
    "context_pack_hash": None,
    "manifest_hash": None,
    "completion_signals": [],
    "termination_reason": None,
    "checkpoint_ref": None,
    "retry_after_fix": None,
    "recovery_candidate": None,
    "policy_hash": None,
}


@dataclass
class FixtureBuilder:
    root: Path
    fixture_name: str

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.cas_dir = self.root / "cas"
        self.cas_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir = self.root / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        self.events: List[Dict[str, Any]] = []
        self._step = 0

        policy_payload = {
            "policy_name": "v1_1_default",
            "policy_version": "1.1",
            "fixture": self.fixture_name,
        }
        self.policy_hash = self.put_json(policy_payload)

    def reset_output(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.__post_init__()

    def put_bytes(self, data: bytes) -> str:
        content_hash = sha256_bytes(data)
        path = self.cas_dir / content_hash
        if not path.exists():
            path.write_bytes(data)
        return content_hash

    def put_text(self, text: str) -> str:
        return self.put_bytes(text.encode("utf-8"))

    def put_json(self, payload: Mapping[str, Any]) -> str:
        serialized = canonical_json_dumps(payload)
        content_hash = sha256_text(serialized)
        path = self.cas_dir / content_hash
        if not path.exists():
            path.write_text(serialized, encoding="utf-8")
        return content_hash

    def write_artifact_file(self, relative_path: str, content: str) -> Path:
        path = self.artifacts_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def append_event(
        self,
        event_type: str,
        *,
        tamper_after_hash: Optional[Dict[str, Any]] = None,
        **fields: Any,
    ) -> Dict[str, Any]:
        self._step += 1
        step = self._step

        event: Dict[str, Any] = {
            "event_type": event_type,
            "step_id": step,
            "timestamp": fields.pop("timestamp", _timestamp_for_step(step)),
            "cwd": fields.pop("cwd", "/workspace"),
        }

        for key, value in DEFAULT_EVENT_FIELDS.items():
            if isinstance(value, list):
                event[key] = list(value)
            elif isinstance(value, dict):
                event[key] = dict(value)
            else:
                event[key] = value

        event.update(fields)
        if event.get("policy_hash") is None:
            event["policy_hash"] = self.policy_hash

        prev_hash = self.events[-1]["event_id"] if self.events else NULL_EVENT_HASH
        event["prev_event_hash"] = prev_hash
        event["event_id"] = stable_hash(
            {
                key: value
                for key, value in event.items()
                if key not in {"event_id", "prev_event_hash"}
            }
        )

        if tamper_after_hash:
            event.update(tamper_after_hash)

        self.events.append(event)
        return event

    def finalize(self, enum_registry: Mapping[str, List[str]]) -> Path:
        events_path = self.root / "events.jsonl"
        lines = [canonical_json_dumps(event) for event in self.events]
        events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        enum_path = self.root / "enum_registry.json"
        enum_payload = {"enums": {key: sorted(set(values)) for key, values in sorted(enum_registry.items())}}
        enum_path.write_text(canonical_json_dumps(enum_payload) + "\n", encoding="utf-8")

        return self.root


def _timestamp_for_step(step_id: int) -> str:
    minutes = step_id // 60
    seconds = step_id % 60
    return f"2026-02-08T00:{minutes:02d}:{seconds:02d}Z"
