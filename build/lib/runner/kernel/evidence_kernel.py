"""Integrated evidence-kernel primitives for terminal-first harness runs."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from runner.action_bus import infer_action_type

ACTION_TYPES = {
    "command",
    "script",
    "native_tool_call",
    "start_service",
    "probe_service",
    "verify",
    "finalize",
}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_json_value(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class EvidenceKernel:
    run_id: str
    task_id: str
    workspace_root: Path
    max_snapshot_files: int = 200
    session_state: dict[str, Any] = field(default_factory=dict)
    service_registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    process_registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    autopsy_state: dict[str, Any] = field(
        default_factory=lambda: {
            "triggered": False,
            "replan_required": False,
            "trigger_count": 0,
            "reason_codes": [],
            "failure_signatures": [],
            "last_step_count": 0,
        }
    )
    verifier_gate: dict[str, Any] = field(default_factory=lambda: {"status": "not_run", "reason_codes": []})
    artifact_gate: dict[str, Any] = field(default_factory=lambda: {"status": "unknown", "required_paths": [], "missing_paths": []})
    receipts: list[dict[str, Any]] = field(default_factory=list)
    lineage: dict[str, str] = field(default_factory=dict)
    evidence_capsule: dict[str, Any] = field(
        default_factory=lambda: {"freshness": "fresh", "stale_reasons": [], "last_action_type": None}
    )
    _last_snapshot: dict[str, str] = field(default_factory=dict)
    cwd_history: list[str] = field(default_factory=list)
    cwd_outside_workspace_count: int = 0
    _last_cwd: str | None = None
    declared_tool_names: list[str] = field(default_factory=list)
    declared_tool_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    native_tool_mode_active: bool = False
    _service_port_index: dict[str, str] = field(default_factory=dict)

    def bind_session(self, session_state: dict[str, Any]) -> None:
        self.session_state = dict(session_state)
        session_cwd = session_state.get("cwd")
        if isinstance(session_cwd, str) and session_cwd:
            if not self.cwd_history or self.cwd_history[-1] != session_cwd:
                self.cwd_history.append(session_cwd)
            self._last_cwd = session_cwd
            if not self._cwd_within_workspace_root(session_cwd):
                self.cwd_outside_workspace_count += 1

    def set_declared_tools(self, tool_definitions: list[dict[str, Any]]) -> None:
        names: list[str] = []
        schemas: dict[str, dict[str, Any]] = {}
        for entry in tool_definitions:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if isinstance(name, str) and name:
                names.append(name)
                schema = entry.get("input_schema")
                if isinstance(schema, dict):
                    schemas[name] = schema
        self.declared_tool_names = sorted(dict.fromkeys(names))
        self.declared_tool_schemas = dict(schemas)
        self.native_tool_mode_active = any(name != "raw_bash" for name in self.declared_tool_names)

    def record_action(
        self,
        *,
        action_type: str | None,
        action_payload: dict[str, Any],
        result_payload: dict[str, Any],
        cwd: str,
    ) -> dict[str, Any]:
        command = _safe_text(action_payload.get("command"))
        tool_name = _safe_text(action_payload.get("tool_name"))
        arguments = self._normalized_arguments(action_payload.get("arguments"), command=command)
        resolved_action_type = action_type or infer_action_type(tool_name=tool_name, command=command)
        if resolved_action_type not in ACTION_TYPES:
            raise ValueError(f"unsupported action_type: {resolved_action_type}")
        snapshot = self._workspace_snapshot()
        changed = sorted(path for path, digest in snapshot.items() if self._last_snapshot.get(path) != digest)
        deleted = sorted(path for path in self._last_snapshot if path not in snapshot)
        for path in changed:
            self.lineage[path] = snapshot[path]
        for path in deleted:
            self.lineage[path] = "deleted"

        if changed or deleted:
            self.evidence_capsule["freshness"] = "stale"
            self.evidence_capsule["stale_reasons"] = ["workspace_mutation_after_action"]
        else:
            self.evidence_capsule["freshness"] = "fresh"
            self.evidence_capsule["stale_reasons"] = []
        self.evidence_capsule["last_action_type"] = resolved_action_type
        self._last_snapshot = snapshot

        stdout = _safe_text(result_payload.get("stdout"))
        stderr = _safe_text(result_payload.get("stderr"))
        contract_status = self._validate_tool_contract(tool_name=tool_name, arguments=arguments)
        cwd_value = _safe_text(cwd)
        prior_cwd = self._last_cwd
        cwd_changed = bool(prior_cwd is not None and prior_cwd != cwd_value)
        if not self.cwd_history or self.cwd_history[-1] != cwd_value:
            self.cwd_history.append(cwd_value)
        self._last_cwd = cwd_value
        cwd_within_workspace_root = self._cwd_within_workspace_root(cwd_value)
        if not cwd_within_workspace_root:
            self.cwd_outside_workspace_count += 1
        receipt = {
            "receipt_id": f"r{len(self.receipts) + 1:04d}",
            "action_id": _safe_text(action_payload.get("action_id")),
            "phase": _safe_text(action_payload.get("phase")),
            "step": action_payload.get("step"),
            "tool_index": action_payload.get("tool_index"),
            "action_type": resolved_action_type,
            "cwd": cwd,
            "tool_name": tool_name or "raw_bash",
            "command": command,
            "exit_code": int(result_payload.get("exit_code", 1)),
            "pid": result_payload.get("pid"),
            "timed_out": bool(result_payload.get("timed_out", False)),
            "reason_code": _safe_text(result_payload.get("reason_code")),
            "stdout_sha256": _hash_text(stdout),
            "stderr_sha256": _hash_text(stderr),
            "tool_contract_status": contract_status,
            "cwd_changed_from_previous": cwd_changed,
            "cwd_within_workspace_root": cwd_within_workspace_root,
            "changed_files": changed,
            "deleted_files": deleted,
            "mutation_observed": bool(changed or deleted),
        }
        self.receipts.append(receipt)
        if resolved_action_type in {"start_service", "probe_service"}:
            service_name = self._resolve_service_name(
                command=command,
                tool_name=tool_name,
                action_type=resolved_action_type,
            )
            self._record_service_lifecycle(
                service_name=service_name,
                action_type=resolved_action_type,
                receipt=receipt,
            )
        return receipt

    def update_service(self, service_name: str, *, status: str, pid: int | None = None, probe: dict[str, Any] | None = None) -> None:
        entry = {"status": status, "pid": pid, "probe": probe or {}}
        self.service_registry[service_name] = entry
        if pid is not None:
            process_entry = self.process_registry.get(service_name, {})
            if not isinstance(process_entry, dict):
                process_entry = {}
            self.process_registry[service_name] = {
                **process_entry,
                "pid": pid,
                "status": status,
            }

    def apply_autopsy(self, *, autopsy: dict[str, Any], step_count: int) -> None:
        if not isinstance(autopsy, dict):
            return
        if not bool(autopsy.get("triggered")):
            return
        prior_count = int(self.autopsy_state.get("trigger_count", 0) or 0)
        reason_codes = [
            reason
            for reason in autopsy.get("reason_codes", [])
            if isinstance(reason, str) and reason
        ]
        failure_signatures = [
            signature
            for signature in autopsy.get("repeated_failure_signatures", [])
            if isinstance(signature, str) and signature
        ]
        self.autopsy_state = {
            "triggered": True,
            "replan_required": bool(autopsy.get("replan_required")),
            "trigger_count": prior_count + 1,
            "reason_codes": reason_codes,
            "failure_signatures": failure_signatures[:10],
            "last_step_count": step_count if isinstance(step_count, int) and step_count >= 0 else 0,
        }

    def set_verifier_gate(self, *, passed: bool, reason_codes: list[str] | None = None) -> None:
        self.verifier_gate = {
            "status": "pass" if passed else "fail",
            "reason_codes": list(reason_codes or []),
        }

    def set_artifact_gate(self, *, required_paths: list[str], workspace_root: Path | None = None) -> None:
        root = workspace_root or self.workspace_root
        missing = [path for path in required_paths if not (root / path).exists()]
        observed_hashes: dict[str, str] = {}
        for rel_path in required_paths:
            target = root / rel_path
            if not target.exists():
                continue
            if target.is_file():
                observed_hashes[rel_path] = _file_hash(target)
            elif target.is_dir():
                observed_hashes[rel_path] = "dir"
        self.artifact_gate = {
            "status": "pass" if not missing else "fail",
            "required_paths": list(required_paths),
            "missing_paths": missing,
            "hash_algorithm": "sha256",
            "observed_hashes": observed_hashes,
        }

    def export_state(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "session_state": dict(self.session_state),
            "service_registry": dict(self.service_registry),
            "process_registry": dict(self.process_registry),
            "autopsy_state": dict(self.autopsy_state),
            "cwd_lineage": self._cwd_lineage_summary(),
            "declared_tool_names": list(self.declared_tool_names),
            "declared_tool_schemas": dict(self.declared_tool_schemas),
            "native_tool_mode_active": self.native_tool_mode_active,
            "verifier_gate": dict(self.verifier_gate),
            "artifact_gate": dict(self.artifact_gate),
            "evidence_capsule": self._effective_evidence_capsule(),
            "receipt_count": len(self.receipts),
            "receipts": list(self.receipts),
            "lineage": dict(self.lineage),
        }

    def build_working_context_pack(self, *, max_recent_receipts: int = 5) -> dict[str, Any]:
        recent = self.receipts[-max_recent_receipts:] if max_recent_receipts > 0 else []
        omitted = self.receipts[: len(self.receipts) - len(recent)] if recent else list(self.receipts)
        omitted_ids = [
            receipt.get("receipt_id")
            for receipt in omitted
            if isinstance(receipt, dict) and isinstance(receipt.get("receipt_id"), str)
        ]
        deleted_paths = [path for path, digest in self.lineage.items() if digest == "deleted"]
        lineage_pairs = [[path, digest] for path, digest in sorted(self.lineage.items())]
        compression = {
            "max_recent_receipts_applied": max_recent_receipts if max_recent_receipts > 0 else 0,
            "total_receipt_count": len(self.receipts),
            "recent_receipt_count": len(recent),
            "omitted_receipt_count": len(omitted),
            "omitted_receipt_digest": _hash_json_value(omitted) if omitted else "",
            "omitted_receipt_id_range": [omitted_ids[0], omitted_ids[-1]] if omitted_ids else [],
        }
        service_summary = {
            name: {
                "status": (value.get("status") if isinstance(value, dict) else None),
                "last_action_type": (value.get("last_action_type") if isinstance(value, dict) else None),
                "event_count": len(value.get("events", [])) if isinstance(value, dict) else 0,
            }
            for name, value in self.service_registry.items()
        }
        process_summary = {
            name: {
                "status": (value.get("status") if isinstance(value, dict) else None),
                "pid": (value.get("pid") if isinstance(value, dict) else None),
                "start_receipt_id": (value.get("start_receipt_id") if isinstance(value, dict) else None),
                "last_probe_receipt_id": (value.get("last_probe_receipt_id") if isinstance(value, dict) else None),
            }
            for name, value in self.process_registry.items()
        }
        return {
            "task_contract": {
                "task_id": self.task_id,
                "run_id": self.run_id,
            },
            "environment": {
                "session_state": dict(self.session_state),
                "declared_tool_names": list(self.declared_tool_names),
                "native_tool_mode_active": self.native_tool_mode_active,
            },
            "native_tool_contract": self._tool_contract_summary(recent_receipts=recent),
            "evidence_capsule": self._effective_evidence_capsule(),
            "open_obligations": {
                "artifact_gate_missing_paths": list(self.artifact_gate.get("missing_paths", [])),
                "artifact_gate_hashes_recorded": sorted(
                    key
                    for key, value in self.artifact_gate.get("observed_hashes", {}).items()
                    if isinstance(key, str) and isinstance(value, str) and value
                ),
                "verifier_gate_status": self.verifier_gate.get("status"),
                "cwd_outside_workspace_root_observed": self.cwd_outside_workspace_count > 0,
                "service_not_ready": sorted(
                    key for key, value in self.service_registry.items()
                    if isinstance(value, dict) and value.get("status") != "ready"
                ),
                "process_not_running": sorted(
                    key for key, value in self.process_registry.items()
                    if isinstance(value, dict) and value.get("status") not in {"starting", "ready", "running"}
                ),
                "tool_contract_violations": self._tool_contract_violation_receipt_ids(),
                "autopsy_replan_required": bool(self.autopsy_state.get("replan_required")),
            },
            "service_summary": service_summary,
            "process_summary": process_summary,
            "recent_receipts": list(recent),
            "compression": compression,
            "lineage_digest": {
                "tracked_paths": len(self.lineage),
                "deleted_paths": len(deleted_paths),
                "sample_paths": sorted(self.lineage.keys())[:10],
                "lineage_fingerprint": _hash_json_value(lineage_pairs),
            },
            "cwd_contract": self._cwd_lineage_summary(),
            "artifact_contract": {
                "status": self.artifact_gate.get("status"),
                "required_path_count": len(self.artifact_gate.get("required_paths", [])),
                "missing_path_count": len(self.artifact_gate.get("missing_paths", [])),
                "hashed_path_count": len(self.artifact_gate.get("observed_hashes", {})),
            },
            "allowed_action_types": sorted(ACTION_TYPES),
            "autopsy_summary": dict(self.autopsy_state),
        }

    def _effective_evidence_capsule(self) -> dict[str, Any]:
        capsule = dict(self.evidence_capsule)
        stale_reasons = [
            reason
            for reason in capsule.get("stale_reasons", [])
            if isinstance(reason, str) and reason
        ]
        if self.verifier_gate.get("status") == "fail":
            stale_reasons.append("verifier_gate_failed")
        if self.artifact_gate.get("status") == "fail":
            stale_reasons.append("artifact_gate_failed")
        service_not_ready = [
            name
            for name, entry in self.service_registry.items()
            if isinstance(entry, dict) and entry.get("status") != "ready"
        ]
        if service_not_ready:
            stale_reasons.append("service_not_ready")
        if self._tool_contract_violation_receipt_ids():
            stale_reasons.append("tool_contract_violation")
        if bool(self.autopsy_state.get("replan_required")):
            stale_reasons.append("autopsy_replan_required")
        process_not_running = [
            key
            for key, value in self.process_registry.items()
            if isinstance(value, dict) and value.get("status") not in {"starting", "ready", "running"}
        ]
        if process_not_running:
            stale_reasons.append("process_not_running")
        if self.cwd_outside_workspace_count > 0:
            stale_reasons.append("cwd_outside_workspace_root")
        deduped: list[str] = []
        for reason in stale_reasons:
            if reason in deduped:
                continue
            deduped.append(reason)
        capsule["stale_reasons"] = deduped
        capsule["freshness"] = "stale" if deduped else "fresh"
        return capsule

    def _cwd_within_workspace_root(self, cwd: str) -> bool:
        if not cwd:
            return False
        try:
            cwd_path = Path(cwd).resolve()
            root = self.workspace_root.resolve()
        except Exception:
            return False
        return cwd_path == root or root in cwd_path.parents

    def _cwd_lineage_summary(self) -> dict[str, Any]:
        history = [cwd for cwd in self.cwd_history if isinstance(cwd, str) and cwd]
        unique = []
        for item in history:
            if item in unique:
                continue
            unique.append(item)
        transitions = 0
        for index in range(1, len(history)):
            if history[index] != history[index - 1]:
                transitions += 1
        return {
            "current_cwd": self._last_cwd,
            "initial_cwd": history[0] if history else None,
            "cwd_history_count": len(history),
            "unique_cwd_count": len(unique),
            "cwd_transition_count": transitions,
            "cwd_outside_workspace_count": self.cwd_outside_workspace_count,
        }

    def _normalized_arguments(self, raw_arguments: Any, *, command: str) -> dict[str, Any]:
        if isinstance(raw_arguments, dict):
            return dict(raw_arguments)
        if isinstance(raw_arguments, str):
            text = raw_arguments.strip()
            if not text:
                return {"command": command} if command else {}
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {"command": text}
            if isinstance(parsed, dict):
                return parsed
            return {"command": text}
        if command:
            return {"command": command}
        return {}

    def _validate_tool_contract(self, *, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        schema = self.declared_tool_schemas.get(tool_name)
        if not isinstance(schema, dict):
            return {
                "status": "schema_unavailable",
                "tool_name": tool_name or "unknown",
                "schema_present": False,
                "missing_required": [],
                "unexpected_keys": [],
                "type_violations": [],
            }
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required")
        required_keys = [item for item in required if isinstance(item, str)] if isinstance(required, list) else []
        missing_required = [key for key in required_keys if key not in arguments]
        unexpected_keys = [key for key in arguments if key not in properties] if properties else []
        type_violations: list[dict[str, str]] = []
        for key, value in arguments.items():
            prop = properties.get(key)
            if not isinstance(prop, dict):
                continue
            expected_type = prop.get("type")
            if not isinstance(expected_type, str):
                continue
            if self._value_matches_type(value, expected_type):
                continue
            type_violations.append({"key": key, "expected_type": expected_type, "observed_type": type(value).__name__})
        status = "pass"
        if missing_required or type_violations:
            status = "fail"
        elif unexpected_keys:
            status = "warn"
        return {
            "status": status,
            "tool_name": tool_name or "unknown",
            "schema_present": True,
            "missing_required": missing_required,
            "unexpected_keys": unexpected_keys,
            "type_violations": type_violations,
        }

    def _value_matches_type(self, value: Any, expected_type: str) -> bool:
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        return True

    def _tool_contract_violation_receipt_ids(self) -> list[str]:
        receipt_ids: list[str] = []
        for receipt in self.receipts:
            if not isinstance(receipt, dict):
                continue
            contract = receipt.get("tool_contract_status")
            if not isinstance(contract, dict):
                continue
            if contract.get("status") != "fail":
                continue
            receipt_id = receipt.get("receipt_id")
            if isinstance(receipt_id, str) and receipt_id:
                receipt_ids.append(receipt_id)
        return receipt_ids

    def _tool_contract_summary(self, *, recent_receipts: list[dict[str, Any]]) -> dict[str, Any]:
        recent_violations = [
            receipt.get("receipt_id")
            for receipt in recent_receipts
            if isinstance(receipt, dict)
            and isinstance(receipt.get("tool_contract_status"), dict)
            and receipt["tool_contract_status"].get("status") == "fail"
            and isinstance(receipt.get("receipt_id"), str)
        ]
        schema_tool_names = sorted(self.declared_tool_schemas.keys())
        return {
            "tool_schema_count": len(schema_tool_names),
            "tool_names_with_schema": schema_tool_names,
            "violation_receipt_ids": self._tool_contract_violation_receipt_ids(),
            "recent_violation_receipt_ids": recent_violations,
        }

    def _workspace_snapshot(self) -> dict[str, str]:
        root = self.workspace_root
        if not root.exists():
            return {}
        files = [path for path in root.rglob("*") if path.is_file()]
        files.sort()
        if len(files) > self.max_snapshot_files:
            files = files[: self.max_snapshot_files]
        snapshot: dict[str, str] = {}
        for path in files:
            rel = path.relative_to(root).as_posix()
            snapshot[rel] = _file_hash(path)
        return snapshot

    def _guess_service_name(self, *, command: str, tool_name: str) -> str:
        if "launch_service.py" in command:
            return "managed_service"
        if "http.server" in command:
            return "http_server"
        port_match = re.search(r"--port\s+(\d+)", command)
        if port_match:
            return f"service_port_{port_match.group(1)}"
        if tool_name and tool_name != "raw_bash":
            return tool_name
        return "service_unknown"

    def _record_service_lifecycle(
        self,
        *,
        service_name: str,
        action_type: str,
        receipt: dict[str, Any],
    ) -> None:
        prior = self.service_registry.get(service_name, {})
        if not isinstance(prior, dict):
            prior = {}
        events = prior.get("events", [])
        if not isinstance(events, list):
            events = []
        event = {
            "action_id": receipt.get("action_id"),
            "action_type": action_type,
            "exit_code": receipt.get("exit_code"),
            "reason_code": receipt.get("reason_code"),
            "command": receipt.get("command"),
        }
        events = [*events, event][-20:]
        raw_exit_code = receipt.get("exit_code", 1)
        if isinstance(raw_exit_code, bool):
            exit_code = int(raw_exit_code)
        elif isinstance(raw_exit_code, int):
            exit_code = raw_exit_code
        else:
            try:
                exit_code = int(str(raw_exit_code).strip())
            except Exception:
                exit_code = 1
        if action_type == "start_service":
            status = "starting" if exit_code == 0 else "start_failed"
        else:
            status = "ready" if exit_code == 0 else "not_ready"
        process_prior = self.process_registry.get(service_name, {})
        if not isinstance(process_prior, dict):
            process_prior = {}
        raw_pid = receipt.get("pid")
        pid: int | None
        if isinstance(raw_pid, int):
            pid = raw_pid
        elif isinstance(raw_pid, str):
            try:
                pid = int(raw_pid.strip())
            except Exception:
                pid = None
        else:
            pid = None
        if action_type == "start_service":
            process_status = "starting" if exit_code == 0 else "start_failed"
            process_entry = {
                **process_prior,
                "pid": pid if pid is not None else process_prior.get("pid"),
                "status": process_status,
                "command": receipt.get("command"),
                "start_receipt_id": receipt.get("receipt_id"),
                "last_probe_receipt_id": process_prior.get("last_probe_receipt_id"),
                "last_exit_code": exit_code,
            }
        else:
            process_status = "running" if exit_code == 0 else "not_running"
            process_entry = {
                **process_prior,
                "status": process_status,
                "last_probe_receipt_id": receipt.get("receipt_id"),
                "last_exit_code": exit_code,
            }
        self.process_registry[service_name] = process_entry
        self.service_registry[service_name] = {
            **prior,
            "status": status,
            "last_action_type": action_type,
            "probe": {
                "action_type": action_type,
                "exit_code": exit_code,
                "reason_code": receipt.get("reason_code"),
            },
            "events": events,
        }

    def _resolve_service_name(self, *, command: str, tool_name: str, action_type: str) -> str:
        port = _extract_service_port(command)
        if action_type == "probe_service" and port and port in self._service_port_index:
            return self._service_port_index[port]
        name = self._guess_service_name(command=command, tool_name=tool_name)
        if action_type == "start_service" and port:
            self._service_port_index[port] = name
        return name


def _extract_service_port(command: str) -> str | None:
    launch_match = re.search(r"--port\s+(\d+)", command)
    if launch_match:
        return launch_match.group(1)
    url_match = re.search(r"127\.0\.0\.1:(\d+)", command)
    if url_match:
        return url_match.group(1)
    return None
