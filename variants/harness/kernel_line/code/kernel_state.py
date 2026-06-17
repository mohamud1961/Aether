"""Run-local state projection for the active evidence kernel."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runner.kernel_evidence_trail import extract_evidence_trail_records_from_receipt, project_evidence_trail_state
from runner.kernel_artifacts import extract_artifact_path_refs


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _stringify_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        if isinstance(value, str) and value:
            out.append(value)
    return _dedupe(out)


def _path_hints(command: str) -> list[str]:
    return extract_artifact_path_refs(command)


def _looks_like_path_token(token: str) -> bool:
    if not token:
        return False
    if token.startswith(("/", "./", "../", "~/")):
        return True
    if "/" in token:
        return True
    suffix = Path(token).suffix.lower()
    return suffix in {
        ".csv",
        ".ini",
        ".json",
        ".jsonl",
        ".log",
        ".md",
        ".py",
        ".sh",
        ".txt",
        ".toml",
        ".xml",
        ".yaml",
        ".yml",
    }


def _is_report_like_path(path: str) -> bool:
    basename = Path(path).name.lower()
    return any(marker in basename for marker in ("report", "receipt", "manifest", "summary", "submission"))


def _normalize_path_token(path: str) -> str:
    candidate = path.strip("'\" ,;:()[]{}")
    if candidate.endswith("/."):
        candidate = candidate[:-2]
    if candidate.endswith("/.."):
        candidate = candidate[:-3]
    return candidate


def _path_tokens_match(left: str, right: str) -> bool:
    left_norm = _normalize_path_token(left)
    right_norm = _normalize_path_token(right)
    if not left_norm or not right_norm:
        return False
    return (
        left_norm == right_norm
        or left_norm.endswith(f"/{right_norm}")
        or right_norm.endswith(f"/{left_norm}")
    )


def _command_looks_like_readback(command: str) -> bool:
    lowered = command.lower()
    if lowered.startswith(("cat ", "sha256sum ", "md5sum ", "stat ", "ls ", "wc ", "jq ", "sed ", "grep ")):
        return True
    if lowered.startswith("python") or lowered.startswith("python3"):
        return any(marker in lowered for marker in ("read", "open(", "read_text", "read_bytes", "json.load", "sha256", "checksum"))
    return any(
        marker in lowered
        for marker in (
            " cat ",
            " sha256sum ",
            " md5sum ",
            " stat ",
            " ls ",
            " wc ",
            " jq ",
            " sed ",
            " grep ",
        )
    )


@dataclass
class KernelState:
    run_id: str
    task_id: str
    workspace_root: Path
    cwd: str
    task_prompt: str = ""
    receipts: list[dict[str, Any]] = field(default_factory=list)
    artifact_registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    files_read: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    artifact_candidates: list[str] = field(default_factory=list)
    selected_facts: list[str] = field(default_factory=list)
    rejected_decoys: list[str] = field(default_factory=list)
    stale_facts: list[str] = field(default_factory=list)
    cwd_lineage: dict[str, Any] = field(default_factory=dict)
    verifier_status: dict[str, Any] = field(
        default_factory=lambda: {"status": "not_run", "reason_codes": [], "output_summary": ""}
    )
    artifact_gate: dict[str, Any] = field(
        default_factory=lambda: {"status": "unknown", "required_paths": [], "missing_paths": [], "observed_hashes": {}}
    )
    first_verified_success: dict[str, Any] = field(default_factory=dict)
    verified_success_regression: dict[str, Any] = field(default_factory=dict)
    provenance_status: dict[str, Any] = field(
        default_factory=lambda: {"status": "pass", "reason_codes": [], "output_summary": "", "report_like_paths": [], "supported_report_paths": [], "missing_report_paths": []}
    )
    service_registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    process_registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    native_tool_state: dict[str, Any] = field(
        default_factory=lambda: {
            "mode": "shell_only",
            "runtime_status": "native_tool_runtime_unknown",
            "declared_tool_names": [],
            "declared_tool_schemas": {},
            "contract_status": "not_run",
            "attempted_native_tool_call": False,
            "violation_receipt_ids": [],
        }
    )
    failure_signatures: list[str] = field(default_factory=list)
    failure_signature_counts: dict[str, int] = field(default_factory=dict)
    last_failure_signature: str | None = None
    last_failure: dict[str, Any] = field(default_factory=dict)
    recovery_card: dict[str, Any] = field(default_factory=dict)
    open_obligations: dict[str, Any] = field(default_factory=dict)
    evidence_capsule: dict[str, Any] = field(
        default_factory=lambda: {"freshness": "fresh", "stale_reasons": [], "last_action_type": None}
    )
    declared_tool_names: list[str] = field(default_factory=list)
    declared_tool_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    native_tool_mode_active: bool = False
    model_call_count: int = 0
    tool_call_count: int = 0
    verifier_run_count: int = 0
    service_probe_count: int = 0
    outcome_status: str = "in_progress"
    governed_status: str = "unresolved"
    final_verdict: str = "unresolved"
    success_contract: dict[str, Any] = field(
        default_factory=lambda: {
            "status": "not_declared",
            "contract_id": "",
            "source_receipt_id": "",
            "criteria": [],
            "required_artifacts": [],
            "required_checks": [],
            "authority_hierarchy": [],
            "known_uncertainty": [],
            "suspected_decoy_classes": [],
            "done_checklist": [],
            "revision": 0,
            "visible_evidence_refs": [],
        }
    )
    success_contract_history: list[dict[str, Any]] = field(default_factory=list)
    artifact_inspection_receipts: list[str] = field(default_factory=list)
    layer2_audit_state: dict[str, Any] = field(
        default_factory=lambda: {
            "status": "not_run",
            "verdict": "unknown",
            "reason_codes": [],
            "audit_receipt_id": "",
            "mismatches": [],
        }
    )
    model_led_success_contract_active: bool = False
    anti_benchfying_mode_active: bool = False
    layer2_success_audit_active: bool = False
    model_led_evidence_substrate_active: bool = False
    file_read_history: dict[str, dict[str, Any]] = field(default_factory=dict)
    raw_receipt_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence_trail_records: list[dict[str, Any]] = field(default_factory=list)
    evidence_trail_state: dict[str, Any] = field(default_factory=dict)



    @classmethod
    def from_core_state(
        cls,
        *,
        core_state: dict[str, Any],
        working_context_pack: dict[str, Any],
        task_prompt: str,
        cwd: str,
        workspace_root: Path,
        carry_state: KernelState | None = None,
    ) -> KernelState:
        receipts = list(core_state.get("receipts", [])) if isinstance(core_state.get("receipts"), list) else []
        lineage = core_state.get("lineage", {}) if isinstance(core_state.get("lineage"), dict) else {}
        written_files = _dedupe(
            [
                *(path for path, digest in lineage.items() if isinstance(path, str) and digest != "deleted"),
                *(path for receipt in receipts for path in _stringify_list(receipt.get("changed_files"))),
            ]
        )
        read_files = _dedupe(
            [
                *(path for receipt in receipts for path in _path_hints(str(receipt.get("command") or ""))),
                *(path for receipt in receipts for path in _stringify_list(receipt.get("deleted_files"))),
            ]
        )
        artifact_candidates = _dedupe(written_files[:])
        verifier_gate = dict(core_state.get("verifier_gate", {})) if isinstance(core_state.get("verifier_gate"), dict) else {}
        artifact_gate = dict(core_state.get("artifact_gate", {})) if isinstance(core_state.get("artifact_gate"), dict) else {}
        artifact_registry = dict(core_state.get("artifact_registry", {})) if isinstance(core_state.get("artifact_registry"), dict) else {}
        if not artifact_registry and carry_state:
            artifact_registry = dict(carry_state.artifact_registry)
        first_verified_success = dict(core_state.get("first_verified_success", {})) if isinstance(core_state.get("first_verified_success"), dict) else {}
        if not first_verified_success and carry_state:
            first_verified_success = dict(carry_state.first_verified_success)
        verified_success_regression = dict(core_state.get("verified_success_regression", {})) if isinstance(core_state.get("verified_success_regression"), dict) else {}
        if not verified_success_regression and carry_state:
            verified_success_regression = dict(carry_state.verified_success_regression)
        success_contract = dict(core_state.get("success_contract", {})) if isinstance(core_state.get("success_contract"), dict) else {}
        if not success_contract and carry_state:
            success_contract = dict(carry_state.success_contract)
        success_contract_history = list(core_state.get("success_contract_history", [])) if isinstance(core_state.get("success_contract_history"), list) else []
        if not success_contract_history and carry_state:
            success_contract_history = list(carry_state.success_contract_history)
        artifact_inspection_receipts = list(core_state.get("artifact_inspection_receipts", [])) if isinstance(core_state.get("artifact_inspection_receipts"), list) else []
        if not artifact_inspection_receipts and carry_state:
            artifact_inspection_receipts = list(carry_state.artifact_inspection_receipts)
        layer2_audit_state = dict(core_state.get("layer2_audit_state", {})) if isinstance(core_state.get("layer2_audit_state"), dict) else {}
        if not layer2_audit_state and carry_state:
            layer2_audit_state = dict(carry_state.layer2_audit_state)
        model_led_success_contract_active = bool(core_state.get("model_led_success_contract_active") or (carry_state.model_led_success_contract_active if carry_state else False))
        anti_benchfying_mode_active = bool(core_state.get("anti_benchfying_mode_active") or (carry_state.anti_benchfying_mode_active if carry_state else False))
        layer2_success_audit_active = bool(core_state.get("layer2_success_audit_active") or (carry_state.layer2_success_audit_active if carry_state else False))
        model_led_evidence_substrate_active = bool(core_state.get("model_led_evidence_substrate_active") or (carry_state.model_led_evidence_substrate_active if carry_state else False))
        service_registry = dict(core_state.get("service_registry", {})) if isinstance(core_state.get("service_registry"), dict) else {}
        process_registry = dict(core_state.get("process_registry", {})) if isinstance(core_state.get("process_registry"), dict) else {}
        evidence_capsule = dict(core_state.get("evidence_capsule", {})) if isinstance(core_state.get("evidence_capsule"), dict) else {}
        evidence_trail_records = list(core_state.get("evidence_trail_records", [])) if isinstance(core_state.get("evidence_trail_records"), list) else []
        if not evidence_trail_records and carry_state:
            evidence_trail_records = list(carry_state.evidence_trail_records)
        if not evidence_trail_records:
            for receipt in receipts:
                evidence_trail_records.extend(
                    extract_evidence_trail_records_from_receipt(receipt, workspace_root=workspace_root)
                )
        evidence_trail_state = dict(core_state.get("evidence_trail_state", {})) if isinstance(core_state.get("evidence_trail_state"), dict) else {}
        if not evidence_trail_state and carry_state:
            evidence_trail_state = dict(carry_state.evidence_trail_state)
        cwd_lineage = dict(core_state.get("cwd_lineage", {})) if isinstance(core_state.get("cwd_lineage"), dict) else {}
        declared_tool_names = _stringify_list(core_state.get("declared_tool_names"))
        declared_tool_schemas = (
            dict(core_state.get("declared_tool_schemas", {}))
            if isinstance(core_state.get("declared_tool_schemas"), dict)
            else {}
        )
        open_obligations = (
            dict(working_context_pack.get("open_obligations", {}))
            if isinstance(working_context_pack.get("open_obligations"), dict)
            else {}
        )
        service_names = list(service_registry.keys())
        selected_facts = _dedupe(
            [
                *(carry_state.selected_facts if carry_state else []),
                f"cwd={cwd}",
                f"workspace_root={workspace_root}",
                *(f"tool={name}" for name in declared_tool_names[:5]),
                *(f"service={name}" for name in service_names[:5]),
                *(f"artifact={path}" for path in artifact_candidates[:5]),
            ]
        )
        rejected_decoys = _dedupe(
            [
                *(carry_state.rejected_decoys if carry_state else []),
                *(f"obligation={name}" for name in open_obligations.keys()),
            ]
        )
        state = cls(
            run_id=str(core_state.get("run_id") or (carry_state.run_id if carry_state else "")),
            task_id=str(core_state.get("task_id") or (carry_state.task_id if carry_state else "")),
            workspace_root=Path(workspace_root),
            cwd=cwd,
            task_prompt=task_prompt,
            receipts=receipts,
            artifact_registry=artifact_registry,
            files_read=read_files,
            files_written=written_files,
            artifact_candidates=artifact_candidates,
            selected_facts=selected_facts,
            rejected_decoys=rejected_decoys,
            stale_facts=list(carry_state.stale_facts if carry_state else []),
            cwd_lineage=cwd_lineage,
            verifier_status=verifier_gate or {"status": "not_run", "reason_codes": [], "output_summary": ""},
            artifact_gate=artifact_gate or {"status": "unknown", "required_paths": [], "missing_paths": [], "observed_hashes": {}},
            first_verified_success=first_verified_success,
            verified_success_regression=verified_success_regression,
            provenance_status=dict(core_state.get("provenance_status", {})) if isinstance(core_state.get("provenance_status"), dict) else {"status": "pass", "reason_codes": [], "output_summary": "", "report_like_paths": [], "supported_report_paths": [], "missing_report_paths": []},
            service_registry=service_registry,
            process_registry=process_registry,
            native_tool_state={
                "mode": "native" if bool(core_state.get("native_tool_mode_active")) else "shell_only",
                "runtime_status": "native_tool_runtime_unknown" if bool(core_state.get("native_tool_mode_active")) else "native_tool_runtime_unknown",
                "declared_tool_names": declared_tool_names,
                "declared_tool_schemas": declared_tool_schemas,
                "contract_status": "pass" if not open_obligations.get("tool_contract_violations") else "fail",
                "attempted_native_tool_call": bool(carry_state.native_tool_state.get("attempted_native_tool_call")) if carry_state else False,
                "violation_receipt_ids": list(open_obligations.get("tool_contract_violations", [])),
            },
            failure_signatures=list(carry_state.failure_signatures if carry_state else []),
            failure_signature_counts=dict(carry_state.failure_signature_counts if carry_state else {}),
            last_failure_signature=carry_state.last_failure_signature if carry_state else None,
            last_failure=dict(carry_state.last_failure if carry_state else {}),
            recovery_card=dict(carry_state.recovery_card if carry_state else {}),
            open_obligations=open_obligations,
            evidence_capsule=evidence_capsule or {"freshness": "fresh", "stale_reasons": [], "last_action_type": None},
            declared_tool_names=declared_tool_names,
            declared_tool_schemas=declared_tool_schemas,
            native_tool_mode_active=bool(core_state.get("native_tool_mode_active")),
            model_call_count=carry_state.model_call_count if carry_state else 0,
            tool_call_count=carry_state.tool_call_count if carry_state else 0,
            verifier_run_count=carry_state.verifier_run_count if carry_state else 0,
            service_probe_count=carry_state.service_probe_count if carry_state else 0,
            outcome_status=carry_state.outcome_status if carry_state else "in_progress",
            governed_status=carry_state.governed_status if carry_state else "unresolved",
            final_verdict=carry_state.final_verdict if carry_state else "unresolved",
            success_contract=success_contract or {
                "status": "not_declared",
                "contract_id": "",
                "source_receipt_id": "",
                "criteria": [],
                "required_artifacts": [],
                "required_checks": [],
                "authority_hierarchy": [],
                "known_uncertainty": [],
                "suspected_decoy_classes": [],
                "done_checklist": [],
                "revision": 0,
                "visible_evidence_refs": [],
            },
            success_contract_history=success_contract_history,
            artifact_inspection_receipts=artifact_inspection_receipts,
            layer2_audit_state=layer2_audit_state or {
                "status": "not_run",
                "verdict": "unknown",
                "reason_codes": [],
                "audit_receipt_id": "",
                "mismatches": [],
            },
            model_led_success_contract_active=model_led_success_contract_active,
            anti_benchfying_mode_active=anti_benchfying_mode_active,
            layer2_success_audit_active=layer2_success_audit_active,
            model_led_evidence_substrate_active=model_led_evidence_substrate_active,
        )
        state.file_read_history = dict(core_state.get("file_read_history", {}))
        state.raw_receipt_outputs = dict(core_state.get("raw_receipt_outputs", {}))
        state.evidence_trail_records = list(evidence_trail_records)
        state.evidence_trail_state = dict(evidence_trail_state)
        if isinstance(working_context_pack.get("autopsy_summary"), dict):
            autopsy = dict(working_context_pack["autopsy_summary"])
            if autopsy.get("triggered"):
                state.last_failure = {
                    "failure_class": "autopsy",
                    "reason_codes": list(autopsy.get("reason_codes", [])),
                    "signature_count": len(autopsy.get("failure_signatures", [])),
                }
                if state.last_failure_signature is None and autopsy.get("failure_signatures"):
                    state.last_failure_signature = str(autopsy["failure_signatures"][-1])
        state.refresh_evidence_trail()
        state.refresh_provenance_state()
        state.refresh_open_obligations()
        state.refresh_evidence_capsule()
        return state

    def register_declared_tools(self, tool_definitions: list[dict[str, Any]]) -> None:
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
                    schemas[name] = dict(schema)
        self.declared_tool_names = _dedupe(names)
        self.declared_tool_schemas = dict(schemas)
        self.native_tool_mode_active = any(name != "raw_bash" for name in self.declared_tool_names)
        self.native_tool_state["declared_tool_names"] = list(self.declared_tool_names)
        self.native_tool_state["declared_tool_schemas"] = dict(self.declared_tool_schemas)
        self.native_tool_state["mode"] = "native" if self.native_tool_mode_active else "shell_only"
        if self.native_tool_mode_active and self.native_tool_state.get("runtime_status") == "native_tool_runtime_unavailable":
            self.native_tool_state["runtime_status"] = "native_tool_runtime_unavailable"

    def note_receipt(self, receipt: dict[str, Any]) -> None:
        if not isinstance(receipt, dict):
            return
        self.receipts.append(dict(receipt))
        self.evidence_trail_records.extend(
            extract_evidence_trail_records_from_receipt(
                receipt,
                workspace_root=self.workspace_root,
            )
        )
        changed_files = _stringify_list(receipt.get("changed_files"))
        deleted_files = _stringify_list(receipt.get("deleted_files"))
        self.files_written = _dedupe([*self.files_written, *changed_files])
        self.files_read = _dedupe([*self.files_read, *(_path_hints(str(receipt.get("command") or ""))), *deleted_files])
        if changed_files or deleted_files:
            self.evidence_capsule["freshness"] = "stale"
            reasons = list(self.evidence_capsule.get("stale_reasons", []))
            reasons.append("workspace_mutation_after_action")
            self.evidence_capsule["stale_reasons"] = _dedupe(reasons)
        self.evidence_capsule["last_action_type"] = receipt.get("action_type")
        if receipt.get("action_type") == "native_tool_call":
            self.native_tool_state["attempted_native_tool_call"] = True
            tool_contract = receipt.get("tool_contract_status")
            if isinstance(tool_contract, dict):
                if tool_contract.get("status") == "fail":
                    self.native_tool_state["contract_status"] = "fail"
                    self.native_tool_state.setdefault("violation_receipt_ids", []).append(str(receipt.get("receipt_id") or ""))
        if receipt.get("action_type") in {"start_service", "probe_service"}:
            self.service_probe_count += 1
        self.refresh_evidence_trail()
        self.refresh_provenance_state()
        self.refresh_open_obligations()
        self.refresh_evidence_capsule()

    def record_failure(self, failure_signature: str, failure_info: dict[str, Any]) -> int:
        signature = failure_signature.strip()
        if not signature:
            return 0
        previous = int(self.failure_signature_counts.get(signature, 0))
        updated = previous + 1
        self.failure_signature_counts[signature] = updated
        self.failure_signatures.append(signature)
        self.last_failure_signature = signature
        self.last_failure = dict(failure_info)
        stale_reasons = list(self.evidence_capsule.get("stale_reasons", []))
        stale_reasons.extend([str(failure_info.get("failure_class") or "failure"), str(failure_info.get("reason_code") or "")])
        self.evidence_capsule["freshness"] = "stale"
        self.evidence_capsule["stale_reasons"] = _dedupe([reason for reason in stale_reasons if reason])
        self.refresh_evidence_capsule()
        return updated

    def refresh_open_obligations(self) -> dict[str, Any]:
        evidence_trail_state = self.refresh_evidence_trail()
        self.refresh_provenance_state()
        obligations: dict[str, Any] = {}
        verifier_status = str(self.verifier_status.get("status") or "")
        if verifier_status not in {"", "pass", "not_run", "unknown"}:
            obligations["verifier_gate_status"] = verifier_status
        missing_paths = _stringify_list(self.artifact_gate.get("missing_paths"))
        if missing_paths:
            obligations["artifact_gate_missing_paths"] = missing_paths
        empty_paths = _stringify_list(self.artifact_gate.get("empty_paths"))
        if empty_paths:
            obligations["artifact_gate_empty_paths"] = empty_paths
        missing_report_paths = _stringify_list(self.provenance_status.get("missing_report_paths"))
        if missing_report_paths:
            obligations["report_provenance_missing"] = missing_report_paths
        service_not_ready = sorted(
            name for name, value in self.service_registry.items() if isinstance(value, dict) and value.get("status") not in {"ready", "running", "starting"}
        )
        if service_not_ready:
            obligations["service_not_ready"] = service_not_ready
        process_not_running = sorted(
            name for name, value in self.process_registry.items() if isinstance(value, dict) and value.get("status") not in {"running", "starting", "ready"}
        )
        if process_not_running:
            obligations["process_not_running"] = process_not_running
        if self.native_tool_state.get("contract_status") == "fail":
            obligations["tool_contract_violations"] = list(self.native_tool_state.get("violation_receipt_ids", []))
        if (
            self.native_tool_state.get("runtime_status") == "native_tool_runtime_unavailable"
            and self.native_tool_state.get("attempted_native_tool_call")
        ):
            obligations["native_tool_runtime_unavailable"] = True
        if self.last_failure_signature and int(self.failure_signature_counts.get(self.last_failure_signature, 0)) >= 3:
            obligations["same_signature_recovery_exhausted"] = self.last_failure_signature
        evidence_requirements = dict(evidence_trail_state.get("requirements", {}))
        if evidence_requirements.get("status") == "fail":
            obligations["evidence_trail_missing"] = _dedupe(
                [
                    *(_stringify_list(evidence_requirements.get("missing_evidence_ids"))),
                    *(_stringify_list(evidence_requirements.get("missing_claim_requirements"))),
                    *(_stringify_list(evidence_requirements.get("reason_codes"))),
                ]
            ) or ["evidence_trail_missing"]
        first_verified_success = dict(self.first_verified_success) if isinstance(self.first_verified_success, dict) else {}
        if first_verified_success:
            regression_reasons: list[str] = []
            if verifier_status not in {"", "pass", "not_run", "unknown"}:
                regression_reasons.extend(_stringify_list(self.verifier_status.get("reason_codes")))
                regression_reasons.append("verifier_gate_failed")
            if str(self.artifact_gate.get("status") or "") == "fail":
                regression_reasons.extend(_stringify_list(self.artifact_gate.get("reason_codes")))
                regression_reasons.append("artifact_gate_failed")
            if regression_reasons:
                obligations["verified_success_overwritten"] = _dedupe([reason for reason in regression_reasons if reason])
                self.verified_success_regression = {
                    "status": "fail",
                    "reason_codes": _dedupe(["verified_success_overwritten", *regression_reasons]),
                    "first_verified_success": first_verified_success,
                    "current_verifier_status": dict(self.verifier_status),
                    "current_artifact_gate": dict(self.artifact_gate),
                }
            else:
                self.verified_success_regression = {}
        if getattr(self, "model_led_success_contract_active", False):
            curr_status = self.success_contract.get("status", "not_declared") if self.success_contract else "not_declared"
            if curr_status == "not_declared":
                obligations["success_contract_missing"] = ["declare_success_contract"]
        self.open_obligations = obligations
        return obligations

    def refresh_provenance_state(self) -> dict[str, Any]:
        report_like_paths = _dedupe(
            [path for path in self.files_written if _is_report_like_path(path)]
        )
        supported_report_paths: list[str] = []
        missing_report_paths: list[str] = []
        for report_path in report_like_paths:
            if self._has_solver_visible_support(report_path):
                supported_report_paths.append(report_path)
            else:
                missing_report_paths.append(report_path)
        if missing_report_paths:
            self.provenance_status = {
                "status": "fail",
                "reason_codes": ["report_provenance_missing"],
                "output_summary": f"missing_report_provenance_count={len(missing_report_paths)}",
                "report_like_paths": list(report_like_paths),
                "supported_report_paths": list(supported_report_paths),
                "missing_report_paths": list(missing_report_paths),
            }
        else:
            summary = "no_report_like_artifacts" if not report_like_paths else f"grounded_report_paths={len(supported_report_paths)}"
            self.provenance_status = {
                "status": "pass",
                "reason_codes": [],
                "output_summary": summary,
                "report_like_paths": list(report_like_paths),
                "supported_report_paths": list(supported_report_paths),
                "missing_report_paths": [],
            }
        return self.provenance_status

    def refresh_evidence_trail(self) -> dict[str, Any]:
        self.evidence_trail_state = project_evidence_trail_state(
            list(self.evidence_trail_records),
            success_contract=dict(self.success_contract) if isinstance(self.success_contract, dict) else {},
        )
        return self.evidence_trail_state

    def _has_solver_visible_support(self, report_path: str) -> bool:
        report_path = _normalize_path_token(report_path)
        if not report_path:
            return False
        for receipt in self.receipts:
            if not isinstance(receipt, dict):
                continue
            command = str(receipt.get("command") or "")
            if not command:
                continue
            if not any(_path_tokens_match(hint, report_path) for hint in _path_hints(command)):
                continue
            if not _command_looks_like_readback(command):
                continue
            stdout_excerpt = str(receipt.get("stdout_excerpt") or "")
            stderr_excerpt = str(receipt.get("stderr_excerpt") or "")
            if stdout_excerpt or stderr_excerpt:
                return True
        return False

    def refresh_evidence_capsule(self) -> None:
        stale_reasons = list(self.evidence_capsule.get("stale_reasons", []))
        if self.verifier_status.get("status") == "fail":
            stale_reasons.append("verifier_gate_failed")
        if self.artifact_gate.get("status") == "fail":
            stale_reasons.append("artifact_gate_failed")
        if self.provenance_status.get("status") == "fail":
            stale_reasons.append("report_provenance_missing")
        if self.open_obligations.get("evidence_trail_missing"):
            stale_reasons.append("evidence_trail_missing")
        if self.open_obligations.get("service_not_ready"):
            stale_reasons.append("service_not_ready")
        if self.open_obligations.get("tool_contract_violations"):
            stale_reasons.append("tool_contract_violation")
        if self.open_obligations.get("native_tool_runtime_unavailable"):
            stale_reasons.append("native_tool_runtime_unavailable")
        if self.open_obligations.get("same_signature_recovery_exhausted"):
            stale_reasons.append("recovery_replan_required")
        if self.verified_success_regression.get("status") == "fail":
            stale_reasons.append("verified_success_overwritten")
        self.evidence_capsule["stale_reasons"] = _dedupe([reason for reason in stale_reasons if reason])
        self.evidence_capsule["freshness"] = "stale" if self.evidence_capsule["stale_reasons"] else "fresh"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "cwd": self.cwd,
            "workspace_root": str(self.workspace_root),
            "task_prompt": self.task_prompt,
            "receipts": list(self.receipts),
            "files_read": list(self.files_read),
            "files_written": list(self.files_written),
            "artifact_candidates": list(self.artifact_candidates),
            "selected_facts": list(self.selected_facts),
            "rejected_decoys": list(self.rejected_decoys),
            "stale_facts": list(self.stale_facts),
            "cwd_lineage": dict(self.cwd_lineage),
            "verifier_status": dict(self.verifier_status),
            "artifact_gate": dict(self.artifact_gate),
            "first_verified_success": dict(self.first_verified_success),
            "verified_success_regression": dict(self.verified_success_regression),
            "artifact_registry": dict(self.artifact_registry),
            "provenance_status": dict(self.provenance_status),
            "service_registry": dict(self.service_registry),
            "process_registry": dict(self.process_registry),
            "native_tool_state": dict(self.native_tool_state),
            "evidence_trail_records": list(self.evidence_trail_records),
            "evidence_trail_state": dict(self.evidence_trail_state),
            "failure_signatures": list(self.failure_signatures),
            "failure_signature_counts": dict(self.failure_signature_counts),
            "last_failure_signature": self.last_failure_signature,
            "last_failure": dict(self.last_failure),
            "recovery_card": dict(self.recovery_card),
            "open_obligations": dict(self.open_obligations),
            "evidence_capsule": dict(self.evidence_capsule),
            "declared_tool_names": list(self.declared_tool_names),
            "declared_tool_schemas": dict(self.declared_tool_schemas),
            "native_tool_mode_active": self.native_tool_mode_active,
            "model_call_count": self.model_call_count,
            "tool_call_count": self.tool_call_count,
            "verifier_run_count": self.verifier_run_count,
            "service_probe_count": self.service_probe_count,
            "outcome_status": self.outcome_status,
            "governed_status": self.governed_status,
            "final_verdict": self.final_verdict,
            "success_contract": dict(self.success_contract),
            "success_contract_history": list(self.success_contract_history),
            "artifact_inspection_receipts": list(self.artifact_inspection_receipts),
            "layer2_audit_state": dict(self.layer2_audit_state),
            "model_led_success_contract_active": self.model_led_success_contract_active,
            "anti_benchfying_mode_active": self.anti_benchfying_mode_active,
            "layer2_success_audit_active": self.layer2_success_audit_active,
            "model_led_evidence_substrate_active": self.model_led_evidence_substrate_active,
            "file_read_history": dict(self.file_read_history),
            "raw_receipt_outputs": dict(self.raw_receipt_outputs),
        }
