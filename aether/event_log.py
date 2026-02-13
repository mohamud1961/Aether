from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .enum_registry import EnumRegistry, load_enum_registry
from .hash_chain import NULL_EVENT_HASH, compute_event_id, verify_event_chain
from .hashing import canonical_json_bytes, sha256_hex

REQUIRED_FIELDS = [
    "run_id",
    "event_type",
    "step_id",
    "timestamp",
    "cwd",
    "tool_name",
    "tool_args",
    "exit_code",
    "files_read",
    "files_written",
    "artifact_refs",
    "truncation",
    "verifier_run",
    "verifier_result",
    "triggers_fired",
    "trigger_explanation",
    "workspace_fingerprint_hash",
    "dirty_since_last_verify",
    "context_pack_hash",
    "manifest_hash",
    "completion_signals",
    "termination_reason",
    "checkpoint_ref",
    "retry_after_fix",
    "recovery_candidate",
]

DEFAULT_FIELDS: Dict[str, Any] = {
    "tool_name": None,
    "tool_args": None,
    "exit_code": None,
    "files_read": [],
    "files_written": [],
    "artifact_refs": [],
    "truncation": {"stdout": None, "stderr": None},
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
    "context_pack_ref": None,
    "manifest_ref": None,
    "context_slice_ref": None,
    "context_slice_hash": None,
    "model_request_ref": None,
    "model_request_hash": None,
    "completion_evidence_bundle_id": None,
    "completion_evidence_bundle_ref": None,
    "preimage_mismatch": None,
    "expected_preimage_hash": None,
    "observed_preimage_hash": None,
    "re_read_required": None,
    "reanchor_summary_artifact_id": None,
    "policy_profile_id": None,
    "valid": None,
    "missing_components": [],
}


class EventLog:
    def __init__(
        self,
        path: Path,
        *,
        enum_registry: Optional[EnumRegistry] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: List[Dict[str, Any]] = []
        self._last_step_id: int = 0
        self._enum_registry = enum_registry or load_enum_registry()
        self.enum_registry_hash = self._enum_registry.registry_hash
        default_run_id = sha256_hex(self.path.resolve().as_posix().encode("utf-8"))[:16]
        self._run_id = run_id or default_run_id
        self._enum_violation_seen = False
        self._unknown_enum_violation_emitted = False
        self._enum_violation_details: List[Dict[str, str]] = []

    @property
    def events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    @property
    def run_id(self) -> str:
        return self._run_id

    def set_run_id(self, run_id: str) -> None:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id must be a non-empty string")
        self._run_id = run_id

    def set_last_step_id(self, step_id: int) -> None:
        self._last_step_id = step_id

    def hydrate(self, events: List[Dict[str, Any]]) -> None:
        self._events = [dict(event) for event in events]
        if self._events:
            last_step = self._events[-1].get("step_id")
            self._last_step_id = int(last_step) if isinstance(last_step, int) else 0
            last_run_id = self._events[-1].get("run_id")
            if isinstance(last_run_id, str) and last_run_id:
                self._run_id = last_run_id
        else:
            self._last_step_id = 0

        self._enum_violation_seen = False
        self._unknown_enum_violation_emitted = False
        self._enum_violation_details = []
        for event in self._events:
            canonical = self._enum_registry.canonicalize_event_type(event.get("event_type"))
            if canonical != "POLICY_VIOLATION":
                continue
            if event.get("violation_code") == "UNKNOWN_ENUM":
                self._enum_violation_seen = True
                self._unknown_enum_violation_emitted = True

    def append_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        full_event = self._apply_defaults(event)
        canonical_event_type = self._canonical_event_type(full_event.get("event_type"))

        if canonical_event_type == "STEP_COMMIT":
            full_event = self._normalize_step_commit(full_event)

        enum_violations = self._collect_enum_violations(full_event)
        if enum_violations:
            self._enum_violation_seen = True
            for violation in enum_violations:
                detail = {
                    "enum_name": violation["enum_name"],
                    "value": violation["value"],
                }
                if detail not in self._enum_violation_details:
                    self._enum_violation_details.append(detail)

        if canonical_event_type == "POLICY_VIOLATION" and full_event.get("violation_code") == "UNKNOWN_ENUM":
            self._enum_violation_seen = True
            self._unknown_enum_violation_emitted = True

        # Unknown enum values are fail-closed and cannot end as SUCCESS.
        if canonical_event_type == "run_END" and self._enum_violation_seen:
            self._emit_unknown_enum_policy_violation(
                timestamp=full_event["timestamp"],
                cwd=full_event["cwd"],
            )
            if isinstance(full_event.get("terminal_outcome"), str) and full_event["terminal_outcome"].upper() == "SUCCESS":
                full_event["terminal_outcome"] = "FAIL_POLICY"
                if not full_event.get("summary_reason_code"):
                    full_event["summary_reason_code"] = "unknown_enum_value"
                full_event["termination_reason"] = full_event.get("summary_reason_code") or "unknown_enum_value"
            if "step_id" not in event or event.get("step_id") is None:
                full_event["step_id"] = self._last_step_id + 1

        return self._append_prepared_event(full_event)

    def append_hash_chain_report(
        self,
        artifact_store,
        *,
        timestamp: str,
        cwd: str,
    ) -> Dict[str, Any]:
        report = verify_event_chain(self._events)
        report_bytes = canonical_json_bytes(report)
        artifact = artifact_store.put_bytes(report_bytes, content_type="application/json")
        event = self.append_event(
            {
                "event_type": "LOG_INTEGRITY_CHECK",
                "timestamp": timestamp,
                "cwd": cwd,
                "pass": bool(report.get("ok")),
                "first_bad_event_id": report.get("failure_event_id"),
                "artifact_refs": [artifact.artifact_id],
            }
        )
        return {"report": report, "artifact_id": artifact.artifact_id, "event": event}

    @staticmethod
    def load_events(path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def _apply_defaults(self, event: Dict[str, Any]) -> Dict[str, Any]:
        for required in ("event_type", "timestamp", "cwd"):
            if required not in event:
                raise ValueError(f"Missing required field: {required}")

        full_event = dict(event)
        if "step_id" not in full_event or full_event.get("step_id") is None:
            full_event["step_id"] = self._last_step_id + 1
        if "run_id" not in full_event:
            full_event["run_id"] = self._run_id

        for key, value in DEFAULT_FIELDS.items():
            if key not in full_event:
                if isinstance(value, (list, dict)):
                    full_event[key] = copy.deepcopy(value)
                else:
                    full_event[key] = value

        for field in REQUIRED_FIELDS:
            if field not in full_event:
                raise ValueError(f"Missing required field after defaults: {field}")

        return full_event

    def _canonical_event_type(self, raw_value: object) -> str:
        canonical = self._enum_registry.canonicalize_event_type(raw_value)
        if canonical is None:
            raise ValueError(f"Unknown event_type: {raw_value}")
        return canonical

    def _collect_enum_violations(self, event: Dict[str, Any]) -> List[Dict[str, str]]:
        checks: List[tuple[str, str, object]] = []

        checks.append(("event_type", "event_type", event.get("event_type")))
        checks.extend(
            [
                ("summary_reason_code", "summary_reason_code", event.get("summary_reason_code")),
                ("deny_reason_code", "deny_reason_code", event.get("deny_reason_code")),
                ("violation_code", "violation_code", event.get("violation_code")),
                ("approval_type", "approval_type", event.get("approval_type")),
                ("approval_reason_code", "approval_reason_code", event.get("approval_reason_code")),
                ("risk_class", "risk_class", event.get("risk_class")),
                ("tool_category", "tool_category", event.get("tool_category")),
                ("truncation_flags", "truncation_flags", event.get("truncation_flags")),
                ("side_effect_scope", "side_effect_scope", event.get("side_effect_scope")),
                ("reversibility", "reversibility", event.get("reversibility")),
                ("verifier_stage", "verifier_stage", event.get("verifier_stage")),
                ("reanchor_trigger_code", "trigger_code", event.get("trigger_code")),
                ("plan_update_reason_code", "update_reason_code", event.get("update_reason_code")),
                ("phase_reason_code", "phase_reason_code", event.get("phase_reason_code")),
                ("plan_status", "status", event.get("status")),
                ("plan_status", "from_status", event.get("from_status")),
                ("plan_status", "to_status", event.get("to_status")),
            ]
        )

        violations: List[Dict[str, str]] = []

        for enum_name, field_name, value in checks:
            if value in (None, ""):
                continue
            if self._enum_registry.validate_enum(enum_name, value):
                continue
            violations.append(
                {
                    "enum_name": enum_name,
                    "field": field_name,
                    "value": str(value),
                }
            )

        slice_list = event.get("slice_list")
        if isinstance(slice_list, list):
            for item in slice_list:
                if not isinstance(item, dict):
                    continue
                trust_level = item.get("trust_level")
                if trust_level not in (None, "") and not self._enum_registry.validate_enum("trust_level", trust_level):
                    violations.append(
                        {
                            "enum_name": "trust_level",
                            "field": "slice_list.trust_level",
                            "value": str(trust_level),
                        }
                    )
                truncation_flags = item.get("truncation_flags")
                if truncation_flags not in (None, "") and not self._enum_registry.validate_enum("truncation_flags", truncation_flags):
                    violations.append(
                        {
                            "enum_name": "truncation_flags",
                            "field": "slice_list.truncation_flags",
                            "value": str(truncation_flags),
                        }
                    )

        return violations

    def _normalize_step_commit(self, event: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(event)
        provided_missing = normalized.get("missing_components")
        if isinstance(provided_missing, list):
            missing = {str(item) for item in provided_missing if str(item)}
        else:
            missing = set()

        has_manifest = self._has_component(
            normalized,
            "required_manifest_ids",
            "manifest_id",
            "manifest_ref",
            "manifest_hash",
        )
        has_context_pack = self._has_component(
            normalized,
            "context_pack_ref",
            "context_pack_hash",
        )
        has_workspace_hash = self._has_component(
            normalized,
            "workspace_hash",
            "workspace_fingerprint_hash",
        )

        if not (has_manifest or has_context_pack):
            missing.add("manifest_or_context_pack")
        if not has_workspace_hash:
            missing.add("workspace_hash")

        if missing:
            normalized["valid"] = False
            normalized["missing_components"] = sorted(missing)
            normalized["commit_status"] = "missing_components"
            return normalized

        valid = normalized.get("valid")
        if valid is None:
            valid = True
        normalized["valid"] = bool(valid)

        if normalized["valid"]:
            normalized["missing_components"] = []
            normalized["commit_status"] = "valid"
        else:
            # Keep explicit invalid marker deterministic even if caller omitted details.
            if not missing:
                missing = {"unspecified"}
            normalized["missing_components"] = sorted(missing)
            normalized["commit_status"] = "missing_components"

        return normalized

    @staticmethod
    def _has_component(event: Dict[str, Any], *keys: str) -> bool:
        for key in keys:
            value = event.get(key)
            if isinstance(value, str) and value:
                return True
            if isinstance(value, list) and bool(value):
                return True
        return False

    def _emit_unknown_enum_policy_violation(self, *, timestamp: str, cwd: str) -> None:
        if self._unknown_enum_violation_emitted:
            return
        self.append_event(
            {
                "event_type": "POLICY_VIOLATION",
                "timestamp": timestamp,
                "cwd": cwd,
                "violation_code": "UNKNOWN_ENUM",
                "enum_violations": copy.deepcopy(self._enum_violation_details),
            }
        )

    def _append_prepared_event(self, full_event: Dict[str, Any]) -> Dict[str, Any]:
        step_id = full_event.get("step_id")
        if not isinstance(step_id, int):
            raise ValueError("step_id must be an int")

        if self._last_step_id != 0 and step_id <= self._last_step_id:
            raise ValueError(f"Non-monotonic step_id: {step_id} <= {self._last_step_id}")

        prev_hash = self._events[-1]["event_id"] if self._events else NULL_EVENT_HASH
        full_event["prev_event_hash"] = prev_hash
        full_event["event_id"] = compute_event_id(full_event)

        self._write_event(full_event)
        self._events.append(full_event)
        self._last_step_id = step_id
        return full_event

    def _write_event(self, event: Dict[str, Any]) -> None:
        payload = canonical_json_bytes(event)
        with self.path.open("ab") as handle:
            handle.write(payload)
            handle.write(b"\n")
