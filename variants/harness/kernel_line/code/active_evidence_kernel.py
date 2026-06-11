"""Active evidence-kernel runtime with modular generic adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from runner.action_bus import infer_action_type
from runner.kernel_compaction import (
    build_compaction_prompt,
    create_compaction_boundary,
    extract_compaction_summary,
    rehydrate_after_compaction,
    render_compaction_summary,
    should_compact,
    validate_compaction_summary,
)
from runner.kernel_control_plane import (
    apply_model_state_update,
    extract_model_state_update,
    initialize_control_plane,
    refresh_from_kernel_state,
    render_model_contract,
    validate_pinned_invariants,
)
from runner.kernel_context_pack import build_context_pack
from runner.kernel_artifacts import build_first_verified_success_record, extract_artifact_path_refs
from runner.kernel_gates import check as run_verifier_gate_check, finalize as finalize_governed_gate
from runner.kernel_native_tools import discover_native_tool_definitions
from runner.kernel_receipts import build_receipt, summarize_receipt
from runner.kernel_recovery import build_recovery_card, classify_tool_result, handle_error
from runner.kernel_services import update_service_state
from runner.kernel_interrupts import build_interrupt_packet, detect_interrupt, finish_claim_requires_gate
from runner.kernel_working_window import build_working_window, estimate_window_size, render_working_window
from runner.kernel_state import KernelState
from runner.model_client import ModelClientError


@dataclass
class ActiveEvidenceKernel:
    """Run-local active kernel facade that owns receipts, gates, recovery, and context."""

    state: KernelState
    route_manifest: dict[str, Any] = field(default_factory=dict)
    max_steps: int = 0
    control_plane_state: dict[str, Any] = field(default_factory=dict)
    control_plane_events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def feature_flags(self) -> dict[str, Any]:
        return self.route_manifest.get("feature_flags", {})

    def _control_plane_enabled(self) -> bool:
        return _is_control_plane_route(self.route_manifest)

    def _ensure_control_plane_state(self) -> None:
        if self.control_plane_state:
            return
        self.control_plane_state = initialize_control_plane(
            self.state,
            self.state.task_prompt,
            {
                "cwd": self.state.cwd,
                "workspace_root": str(self.state.workspace_root),
                "required_artifact_paths": list(self.state.artifact_gate.get("required_paths", [])),
            },
            self.route_manifest,
        )
        self._record_control_plane_event(
            phase="context",
            event_type="control_plane_state_initialized",
            details={
                "route_variant_id": self.control_plane_state.get("route_variant_id"),
                "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
                "task_prompt": self.control_plane_state.get("task_contract", {}).get("task_prompt", ""),
            },
        )

    def _record_control_plane_event(self, *, phase: str, event_type: str, details: dict[str, Any]) -> None:
        self.control_plane_events.append(
            {
                "phase": phase,
                "event_type": event_type,
                "payload": {"details": dict(details)},
            }
        )

    def drain_control_plane_events(self) -> list[dict[str, Any]]:
        events = list(self.control_plane_events)
        self.control_plane_events.clear()
        return events

    def _store_model_compaction_summary(
        self,
        summary_record: dict[str, Any],
        *,
        source: str,
        status: str,
    ) -> None:
        self.control_plane_state["last_model_compaction_summary"] = dict(summary_record)
        self.control_plane_state["last_model_compaction_summary_status"] = status
        self.control_plane_state["last_model_compaction_summary_source"] = source
        semantic_state = dict(self.control_plane_state.get("semantic_state", {}))
        semantic_state["compaction_summary"] = dict(summary_record)
        semantic_state["compaction_summary_status"] = status
        semantic_state["compaction_summary_source"] = source
        self.control_plane_state["semantic_state"] = semantic_state

    def _maybe_apply_model_compaction_summary(
        self,
        model: Any,
    ) -> dict[str, Any] | None:
        compact_check = dict(self.control_plane_state.get("pending_compaction_check", {}))
        if not compact_check.get("triggered"):
            return None
        compact_boundary = dict(self.control_plane_state.get("last_compaction_boundary", {}))
        receipt_range = compact_boundary.get("preserved_receipt_id_range") if isinstance(compact_boundary, dict) else []
        prompt = build_compaction_prompt(self.control_plane_state, self.state, receipt_range)
        try:
            self.state.model_call_count += 1
            completion = model.complete(prompt, tools=[])
        except Exception as error:
            fallback = _build_model_compaction_fallback(self.state, compact_check, compact_boundary, reason_codes=[type(error).__name__, "compaction_model_call_failed"])
            self._store_model_compaction_summary(fallback, source="deterministic_fallback", status="fallback")
            self.control_plane_state.pop("pending_compaction_check", None)
            self.control_plane_state.pop("pending_compaction_summary", None)
            self._record_control_plane_event(
                phase="context",
                event_type="kernel_compaction_failed",
                details={
                    "reason_codes": list(fallback.get("reason_codes", [])),
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
                    "compact_id": compact_boundary.get("compact_id", ""),
                },
            )
            return {"summary_message": render_compaction_summary(fallback), "summary_record": fallback, "status": "fallback"}
        proposed = extract_compaction_summary(completion)
        validation = validate_compaction_summary(proposed, self.control_plane_state, self.state, compact_check)
        if validation["status"] == "accepted":
            summary_record = dict(validation)
            summary_record["compact_id"] = str(compact_boundary.get("compact_id") or "")
            summary_record["receipt_range"] = list(receipt_range or [])
            self._store_model_compaction_summary(summary_record, source=str(summary_record.get("source") or "model"), status="accepted")
            self.control_plane_state.pop("pending_compaction_check", None)
            self.control_plane_state.pop("pending_compaction_summary", None)
            self._record_control_plane_event(
                phase="context",
                event_type="control_plane_state_updated",
                details={
                    "reason_code": "model_compaction_summary_applied",
                    "compact_id": compact_boundary.get("compact_id", ""),
                    "receipt_ids": list(summary_record.get("receipt_ids", [])),
                    "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
                },
            )
            return {"summary_message": render_compaction_summary(summary_record), "summary_record": summary_record, "status": "accepted"}
        fallback = _build_model_compaction_fallback(
            self.state,
            compact_check,
            compact_boundary,
            reason_codes=list(validation.get("reason_codes", [])),
        )
        self._store_model_compaction_summary(fallback, source="deterministic_fallback", status="fallback")
        self.control_plane_state.pop("pending_compaction_check", None)
        self.control_plane_state.pop("pending_compaction_summary", None)
        self._record_control_plane_event(
            phase="context",
            event_type="kernel_compaction_failed",
            details={
                "reason_codes": list(validation.get("reason_codes", [])),
                "compact_id": compact_boundary.get("compact_id", ""),
                "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
            },
        )
        return {"summary_message": render_compaction_summary(fallback), "summary_record": fallback, "status": "fallback"}

    def before_model_call(
        self,
        *,
        max_recent_receipts: int = 5,
        history: list[dict[str, Any]] | None = None,
        working_window_budget: int = 6000,
    ) -> dict[str, Any]:
        self.state.model_call_count += 1
        self.state.refresh_open_obligations()
        self.state.refresh_evidence_capsule()
        if self._control_plane_enabled():
            self._ensure_control_plane_state()
            compact_check = should_compact(
                self.control_plane_state,
                self.state,
                history,
                budget=working_window_budget,
            )
            if compact_check["triggered"]:
                try:
                    boundary = create_compaction_boundary(
                        self.control_plane_state,
                        self.state,
                        _deterministic_compaction_summary(self.state, compact_check),
                        compact_check["trigger"],
                    )
                    rehydrated = rehydrate_after_compaction(self.control_plane_state, self.state, boundary)
                    self.control_plane_state = rehydrated["control_plane"]
                    self.control_plane_state["pending_compaction_check"] = dict(compact_check)
                    self.control_plane_state["pending_compaction_summary"] = {
                        "compact_id": boundary.get("compact_id", ""),
                        "receipt_range": list(boundary.get("preserved_receipt_id_range", [])),
                        "receipt_ids": list(boundary.get("preserved_receipt_ids", [])),
                        "trigger": compact_check["trigger"],
                    }
                    self._record_control_plane_event(
                        phase="context",
                        event_type="kernel_compaction_boundary",
                        details=boundary,
                    )
                except Exception as error:
                    self._record_control_plane_event(
                        phase="context",
                        event_type="kernel_compaction_failed",
                        details={
                            "error_type": type(error).__name__,
                            "error": str(error),
                            "trigger": compact_check["trigger"],
                        },
                    )
                    raise
            self.control_plane_state = refresh_from_kernel_state(self.control_plane_state, self.state, {})
            window = build_working_window(self.control_plane_state, self.state, budget=working_window_budget)
            self.control_plane_state["last_working_window"] = dict(window)
            self.control_plane_state["last_working_window_rendered"] = render_working_window(window)
            if compact_check["triggered"]:
                window["control_plane_compaction_request"] = dict(self.control_plane_state.get("pending_compaction_summary", {}))
                window["control_plane_compaction_boundary"] = dict(self.control_plane_state.get("last_compaction_boundary", {}))
            validation = validate_pinned_invariants(self.control_plane_state)
            if validation["status"] != "pass":
                self._record_control_plane_event(
                    phase="context",
                    event_type="kernel_compaction_failed",
                    details={"missing_keys": validation["missing_keys"], "pinned_invariant_hash": validation["pinned_invariant_hash"]},
                )
                raise ValueError(f"missing pinned invariants: {validation['missing_keys']}")
            self._record_control_plane_event(
                phase="context",
                event_type="control_plane_working_window",
                details={
                    "working_window_version": window.get("working_window_version"),
                    "estimated_window_size": window.get("estimated_window_size"),
                    "budget_chars": window.get("budget_chars"),
                    "recent_receipt_count": window.get("compression", {}).get("recent_receipt_count"),
                    "omitted_receipt_count": window.get("compression", {}).get("omitted_receipt_count"),
                    "model_contract_version": window.get("model_contract", {}).get("model_contract_version"),
                    "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
                },
            )
            return window
        return build_context_pack(self.state, max_recent_receipts=max_recent_receipts)

    def after_tool_result(
        self,
        *,
        tool_call: dict[str, Any] | None,
        tool_result: dict[str, Any],
        cwd: str,
        step: int | None = None,
        tool_index: int | None = None,
        phase: str = "execute",
        action_id: str | None = None,
    ) -> dict[str, Any]:
        tool_name = _tool_name(tool_call, tool_result)
        command = _tool_command(tool_call, tool_result)
        action_type = infer_action_type(tool_name=tool_name, command=command)
        self.state.tool_call_count += 1
        receipt = build_receipt(
            receipt_id=f"r{len(self.state.receipts) + 1:04d}",
            action_id=action_id or f"{self.state.run_id}-a{len(self.state.receipts) + 1:04d}",
            action_type=action_type,
            tool_name=tool_name,
            command=command,
            cwd=cwd,
            exit_code=_exit_code(tool_result.get("exit_code")),
            reason_code=str(tool_result.get("reason_code") or "tool_result_recorded"),
            stdout=str(tool_result.get("stdout") or ""),
            stderr=str(tool_result.get("stderr") or ""),
            changed_files=_as_string_list(tool_result.get("changed_files")),
            deleted_files=_as_string_list(tool_result.get("deleted_files")),
            mutation_observed=bool(tool_result.get("mutation_observed", False)),
            service_name=tool_result.get("service_name") if isinstance(tool_result.get("service_name"), str) else None,
            service_status=tool_result.get("service_status") if isinstance(tool_result.get("service_status"), str) else None,
            native_tool_status=tool_result.get("native_tool_status") if isinstance(tool_result.get("native_tool_status"), str) else None,
            verifier_status=tool_result.get("verifier_status") if isinstance(tool_result.get("verifier_status"), str) else None,
            tool_contract_status=tool_result.get("tool_contract_status") if isinstance(tool_result.get("tool_contract_status"), dict) else None,
            pid=tool_result.get("pid") if isinstance(tool_result.get("pid"), int) else None,
            timed_out=bool(tool_result.get("timed_out", False)),
        )
        self.state.note_receipt(receipt)

        from runner.kernel_artifacts import (
            refresh_artifact_registry,
            classify_artifact_command,
            build_artifact_inspection_receipt_payload,
        )
        candidate_paths = (
            _as_string_list(tool_result.get("changed_files"))
            + _as_string_list(tool_result.get("deleted_files"))
            + extract_artifact_path_refs(command)
        )
        self.state.artifact_registry = refresh_artifact_registry(
            workspace_root=self.state.workspace_root,
            existing=self.state.artifact_registry,
            candidate_paths=candidate_paths,
            receipt_id=receipt["receipt_id"],
        )
        classification = classify_artifact_command(command)
        if classification["kind"] != "artifact_other":
            inspection_payload = build_artifact_inspection_receipt_payload(
                command=command,
                receipt=receipt,
                registry=self.state.artifact_registry,
            )
            receipt["artifact_inspection"] = inspection_payload
            if not hasattr(self.state, "artifact_inspection_receipts") or self.state.artifact_inspection_receipts is None:
                self.state.artifact_inspection_receipts = []
            self.state.artifact_inspection_receipts.append(inspection_payload)
        service_name, service_entry = update_service_state(
            service_registry=self.state.service_registry,
            process_registry=self.state.process_registry,
            receipt=receipt,
        )
        if service_name and service_entry is not None:
            self.state.refresh_open_obligations()
        if tool_name != "raw_bash":
            self.state.native_tool_state["mode"] = "native"
        if bool(tool_result.get("native_tool_runtime_active", True)) is False and tool_name != "raw_bash":
            self.state.native_tool_state["runtime_status"] = "native_tool_runtime_unavailable"
        elif tool_name != "raw_bash":
            self.state.native_tool_state["runtime_status"] = "native_tool_runtime_available"

        if self.feature_flags.get("tool_contract_substrate"):
            from runner.kernel_native_tools import project_native_tool_state
            declared_tool_names = [tool["name"] for tool in self.state.native_tool_definitions] if hasattr(self.state, "native_tool_definitions") and self.state.native_tool_definitions else []
            declared_tool_schemas = {tool["name"]: tool.get("input_schema", {}) for tool in self.state.native_tool_definitions} if hasattr(self.state, "native_tool_definitions") and self.state.native_tool_definitions else {}
            violations = []
            for r in self.state.receipts:
                tc_status = r.get("tool_contract_status")
                if isinstance(tc_status, dict) and tc_status.get("status") == "fail":
                    violations.append(r.get("receipt_id"))
            contract_status = "fail" if violations else "pass"
            projected = project_native_tool_state(
                declared_tool_names=declared_tool_names,
                declared_tool_schemas=declared_tool_schemas,
                receipts=self.state.receipts,
                runtime_status=self.state.native_tool_state.get("runtime_status", "native_tool_runtime_available"),
                attempted_native_tool_call=bool(declared_tool_names),
                contract_status=contract_status,
            )
            self.state.native_tool_state.update(projected)

        failure_signal: dict[str, Any] | None = None
        if _result_failed(tool_result):
            failure_signal = classify_tool_result(tool_call=tool_call, tool_result=tool_result, state=self.state)
            repeated_count = int(self.state.failure_signature_counts.get(failure_signal["failure_signature"], 0) or 0)
            self.state.recovery_card = build_recovery_card(
                failure_info=failure_signal,
                repeated_count=repeated_count,
                state=self.state,
            )
            self.state.refresh_open_obligations()
            self.state.refresh_evidence_capsule()
        if self._control_plane_enabled():
            self._ensure_control_plane_state()
            self.control_plane_state = refresh_from_kernel_state(self.control_plane_state, self.state, {})
            self._record_control_plane_event(
                phase=phase,
                event_type="control_plane_state_updated",
                details={
                    "receipt_id": receipt.get("receipt_id"),
                    "reason_code": receipt.get("reason_code"),
                    "updated_sections": [
                        "receipts",
                        "service_state",
                        "verifier_state",
                        "artifact_state",
                        "provenance_state",
                        "open_obligations",
                        "latest_recovery_card",
                    ],
                    "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
                    "open_obligations_count": len(self.state.open_obligations),
                },
            )

        if self.state.model_led_evidence_substrate_active:
            import hashlib
            if "stdout" in tool_result and isinstance(tool_result["stdout"], str):
                tool_result["stdout"] = _truncate_output(tool_result["stdout"])
            if "stderr" in tool_result and isinstance(tool_result["stderr"], str):
                tool_result["stderr"] = _truncate_output(tool_result["stderr"])
            
            read_info = _detect_file_read(tool_name, command, tool_call, tool_result)
            if read_info:
                file_path, content, line_count = read_info
                curr_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:7]
                if not hasattr(self.state, "file_read_history") or self.state.file_read_history is None:
                    self.state.file_read_history = {}
                if file_path in self.state.file_read_history:
                    prev = self.state.file_read_history[file_path]
                    prev_hash = prev.get("hash")
                    prev_step = prev.get("step")
                    prev_receipt_id = prev.get("receipt_id")
                    
                    if curr_hash == prev_hash:
                        nudge = (
                            f"\nObservation: You already read {file_path} at step {prev_step}, "
                            f"receipt {prev_receipt_id}, hash unchanged.\n"
                            f"Use that prior content if sufficient, or reread if you want a fresh view."
                        )
                    else:
                        nudge = (
                            f"\nObservation: {file_path} changed since your last read at step {prev_step}.\n"
                            f"Last read hash: {prev_hash}. Current hash: {curr_hash}."
                        )
                    
                    orig_stderr = tool_result.get("stderr") or ""
                    if orig_stderr:
                        tool_result["stderr"] = orig_stderr + "\n" + nudge
                    else:
                        tool_result["stderr"] = nudge
                
                self.state.file_read_history[file_path] = {
                    "hash": curr_hash,
                    "step": step or len(self.state.receipts),
                    "receipt_id": receipt["receipt_id"],
                    "line_count": line_count,
                }

        # Store full, raw output in state.raw_receipt_outputs
        if not hasattr(self.state, "raw_receipt_outputs") or self.state.raw_receipt_outputs is None:
            self.state.raw_receipt_outputs = {}
        self.state.raw_receipt_outputs[receipt["receipt_id"]] = {
            "stdout": str(tool_result.get("stdout") or ""),
            "stderr": str(tool_result.get("stderr") or ""),
        }

        return {
            "receipt": receipt,
            "service_update": {"service_name": service_name, "service_entry": service_entry} if service_name else {},
            "failure_signal": failure_signal,
            "recovery_signal": dict(self.state.recovery_card) if self.state.recovery_card else {},
            "evidence_capsule": dict(self.state.evidence_capsule),
            "evidence_trail_state": dict(self.state.evidence_trail_state),
            "control_plane_state": dict(self.control_plane_state) if self.control_plane_state else {},
        }

    def after_model_no_tool_calls(
        self,
        *,
        step: int,
        completion: dict[str, Any] | None = None,
        workspace_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.state.refresh_open_obligations()
        self.state.refresh_evidence_capsule()
        completion = dict(completion or {})
        if self._control_plane_enabled():
            self._ensure_control_plane_state()
            self.control_plane_state = refresh_from_kernel_state(self.control_plane_state, self.state, workspace_state or {})
            proposal = extract_model_state_update(completion)
            if isinstance(proposal, dict):
                applied = apply_model_state_update(self.control_plane_state, proposal, receipt_id=f"{self.state.run_id}-step{step:04d}")
                if applied["status"] == "accepted":
                    self.control_plane_state = applied["control_plane"]
                    self._record_control_plane_event(
                        phase="execute",
                        event_type="control_plane_state_updated",
                        details={
                            "step": step,
                            "reason_code": "model_state_update_applied",
                            "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
                        },
                    )
                else:
                    self._record_control_plane_event(
                        phase="execute",
                        event_type="control_plane_update_rejected",
                        details={
                            "step": step,
                            "reason_codes": list(applied.get("reason_codes", [])),
                            "update_version": "control_plane_update_rejected",
                            "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
                        },
                    )
            interrupt = detect_interrupt(
                self.control_plane_state,
                self.state,
                {
                    "step": step,
                    "completion": completion,
                    "working_window_size": estimate_window_size(self.control_plane_state.get("last_working_window", {}))
                    if isinstance(self.control_plane_state.get("last_working_window"), dict)
                    else 0,
                },
            )
            packet = build_interrupt_packet(interrupt, self.control_plane_state, self.state)
            self._record_control_plane_event(
                phase="execute",
                event_type="kernel_interrupt_packet",
                details={"step": step, **packet},
            )
            finish_claim = bool(packet.get("finish_claim"))
            if finish_claim:
                self._record_control_plane_event(
                    phase="execute",
                    event_type="kernel_finish_claim",
                    details={
                        "step": step,
                        "finish_gate_required": True,
                        "finish_claim": True,
                        "open_obligations_count": len(self.state.open_obligations),
                    },
                )
            if packet["interrupt_reason"] == "same_failure_repeated":
                action = "stop"
                reason = "same_signature_recovery_exhausted"
            elif finish_claim:
                action = "finalize" if not self.state.open_obligations else "replan"
                reason = "explicit_finish_claim" if action == "finalize" else "finish_claim_requires_open_obligations_clear"
            elif packet["interrupt_reason"] in {"model_replan_requested", "model_blocked"}:
                action = "replan"
                reason = packet["interrupt_reason"]
            elif packet["interrupt_reason"] in {"completion_claimed", "model_no_progress"}:
                action = "replan"
                reason = "explicit_finish_claim_required" if packet["interrupt_reason"] == "model_no_progress" else "completion_claim_requires_gate"
            else:
                action = "replan"
                reason = packet["interrupt_reason"]
            governed_status = "governed_pass" if action == "finalize" and self.state.verifier_status.get("status") == "pass" and not self.state.open_obligations else "ungoverned_model_claim"
            if action == "stop":
                governed_status = "budget_exhausted_open_obligations"
            return {
                "action": action,
                "reason": reason,
                "governed_status": governed_status,
                "recovery_card": dict(self.state.recovery_card),
                "step": step,
                "completion": completion,
                "interrupt_packet": packet,
                "finish_claim": finish_claim,
            }
        if not self.state.open_obligations:
            return {
                "action": "finalize",
                "reason": "no_open_obligations",
                "governed_status": "governed_pass" if self.state.verifier_status.get("status") == "pass" else "ungoverned_model_claim",
                "recovery_card": {},
                "step": step,
                "completion": dict(completion or {}),
            }
        failure_info = {
            "failure_class": "repeated_no_progress",
            "reason_code": "no_tool_calls_with_open_obligations",
            "failure_signature": f"no_tool_calls_with_open_obligations|{step}|{sorted(self.state.open_obligations.keys())}",
            "repair_hint": "Use the open obligations to decide the next deterministic repair action.",
            "required_next_obligation": "address_open_obligations",
            "stale_facts": list(self.state.stale_facts),
        }
        repeated_count = self.state.record_failure(failure_info["failure_signature"], failure_info)
        self.state.recovery_card = build_recovery_card(
            failure_info=failure_info,
            repeated_count=repeated_count,
            state=self.state,
        )
        self.state.refresh_open_obligations()
        self.state.refresh_evidence_capsule()
        action = "replan" if repeated_count < 3 else "stop"
        return {
            "action": action,
            "reason": "open_obligations_after_no_tool_calls",
            "governed_status": "budget_exhausted_open_obligations" if action == "stop" else "ungoverned_model_claim",
            "recovery_card": dict(self.state.recovery_card),
            "step": step,
            "completion": completion,
        }

    def run_verifier_gate(self, task_prompt: str, workspace_state: dict[str, Any]) -> bool:
        self.state.verifier_run_count += 1
        verified = run_verifier_gate_check(task_prompt, workspace_state)
        self.state.verifier_status = {
            "status": "pass" if verified else "fail",
            "reason_codes": _as_string_list(workspace_state.get("verification_reason_codes")),
            "output_summary": str(workspace_state.get("verification_output_summary") or ""),
        }
        if verified and self.state.artifact_gate.get("status") == "pass" and not self.state.first_verified_success:
            self.state.first_verified_success = build_first_verified_success_record(
                artifact_registry=self.state.artifact_registry,
                artifact_gate=self.state.artifact_gate,
                verifier_status=self.state.verifier_status,
                receipt_id=self.state.receipts[-1].get("receipt_id") if self.state.receipts else None,
            )
            import shutil
            backup_dir = self.state.workspace_root / ".backup_success"
            backup_dir.mkdir(parents=True, exist_ok=True)
            for file_path in self.state.artifact_registry.keys():
                src = self.state.workspace_root / str(file_path)
                if src.is_file():
                    dst = backup_dir / str(file_path)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
        self.state.refresh_open_obligations()
        self.state.refresh_evidence_capsule()
        if self._control_plane_enabled():
            self._ensure_control_plane_state()
            self.control_plane_state = refresh_from_kernel_state(self.control_plane_state, self.state, workspace_state)
            self._record_control_plane_event(
                phase="verify",
                event_type="control_plane_state_updated",
                details={
                    "reason_code": "verifier_gate_checked",
                    "verified": bool(verified),
                    "pinned_invariant_hash": self.control_plane_state.get("pinned_invariant_hash"),
                },
            )
        return verified

    def finalize(
        self,
        *,
        execution_result: dict[str, Any],
        recovery_action: dict[str, Any] | None = None,
        workspace_state: dict[str, Any] | None = None,
        verified: bool | None = None,
    ) -> dict[str, Any]:
        workspace_state = workspace_state or execution_result.get("workspace_state")
        if not isinstance(workspace_state, dict):
            workspace_state = {}
        workspace_state = dict(workspace_state)
        workspace_state.setdefault("active_kernel_state", self.state.to_dict())
        if self.control_plane_state:
            workspace_state.setdefault("control_plane_state", dict(self.control_plane_state))
            if isinstance(self.control_plane_state.get("last_working_window"), dict):
                workspace_state.setdefault("control_plane_working_window", dict(self.control_plane_state["last_working_window"]))
        finalization = finalize_governed_gate(
            execution_result=execution_result,
            recovery_action=recovery_action,
            workspace_state=workspace_state,
            verified=verified,
        )

        if finalization["status"] != "governed_pass" and self.state.first_verified_success:
            backup_dir = self.state.workspace_root / ".backup_success"
            if backup_dir.exists() and backup_dir.is_dir():
                import shutil
                for src in backup_dir.rglob("*"):
                    if src.is_file():
                        rel = src.relative_to(backup_dir)
                        dst = self.state.workspace_root / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                
                self.state.verifier_status = dict(self.state.first_verified_success.get("verifier_status", {}))
                self.state.artifact_gate = dict(self.state.first_verified_success.get("artifact_gate", {}))
                self.state.artifact_registry = dict(self.state.first_verified_success.get("artifact_registry", {}))
                self.state.open_obligations = {}
                
                workspace_state["active_kernel_state"] = self.state.to_dict()
                finalization = finalize_governed_gate(
                    execution_result=execution_result,
                    recovery_action=recovery_action,
                    workspace_state=workspace_state,
                    verified=True,
                )

        if self.feature_flags.get("layer2_success_audit"):
            from runner.kernel_layer2_audit import normalize_layer2_audit_state
            from runner.kernel_success_contract import audit_success_contract_consistency
            final_state = dict(workspace_state)
            final_state.update(self.state.to_dict())
            if "artifact_state" not in final_state:
                registry_keys = list(self.state.artifact_registry.keys()) if isinstance(self.state.artifact_registry, dict) else []
                registry_hashes = {k: v.get("sha256", "") for k, v in self.state.artifact_registry.items() if isinstance(v, dict)} if isinstance(self.state.artifact_registry, dict) else {}
                final_state["artifact_state"] = {
                    "artifact_refs": registry_keys,
                    "captured_paths": registry_keys,
                    "observed_paths": registry_keys,
                    "observed_hashes": registry_hashes,
                }
            final_state["success_contract"] = self.state.success_contract
            audit_result = audit_success_contract_consistency(
                task_prompt=self.state.task_prompt,
                success_contract=self.state.success_contract,
                final_state=final_state,
            )
            normalized_audit = normalize_layer2_audit_state(audit_result)
            self.state.layer2_audit_state = normalized_audit
            finalization["layer2_audit_state"] = dict(normalized_audit)
            workspace_state["layer2_audit_state"] = dict(normalized_audit)
            if normalized_audit.get("status") in {"fail", "unclear"} or normalized_audit.get("verdict") in {"FAIL", "UNCLEAR"}:
                workspace_state["active_kernel_state"] = self.state.to_dict()
                workspace_state["route_manifest"] = dict(self.route_manifest)
                finalization = finalize_governed_gate(
                    execution_result=execution_result,
                    recovery_action=recovery_action,
                    workspace_state=workspace_state,
                    verified=verified,
                )
                finalization["layer2_audit_state"] = dict(normalized_audit)

        if self.feature_flags.get("anti_benchfying_mode"):
            from runner.kernel_success_contract import FORBIDDEN_MARKERS
            forbidden_found = False
            for marker in FORBIDDEN_MARKERS:
                if self.state.success_contract:
                    contract_str = json.dumps(self.state.success_contract).lower()
                    if marker in contract_str:
                        forbidden_found = True
                        break
            if not forbidden_found and hasattr(self.state, "artifact_registry") and self.state.artifact_registry:
                captured_paths = list(self.state.artifact_registry.keys())
                for path_str in captured_paths:
                    try:
                        p = Path(self.state.workspace_root) / path_str
                        if p.is_file():
                            content = p.read_text(encoding="utf-8", errors="ignore").lower()
                            for marker in FORBIDDEN_MARKERS:
                                if marker in content:
                                    forbidden_found = True
                                    break
                    except Exception:
                        pass
                    if forbidden_found:
                        break
            if forbidden_found:
                finalization["governed_status"] = "artifact_gate_failed"
                finalization["final_verdict"] = "fail"
                if "reason_codes" not in finalization:
                    finalization["reason_codes"] = []
                if "forbidden_marker_detected" not in finalization["reason_codes"]:
                    finalization["reason_codes"].append("forbidden_marker_detected")

        self.state.governed_status = finalization["governed_status"]
        self.state.final_verdict = finalization["final_verdict"]
        self.state.outcome_status = finalization["status"]
        self.state.open_obligations = dict(finalization["open_obligations"])
        self.state.refresh_open_obligations()
        self.state.refresh_evidence_capsule()
        return finalization


def orient(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    env_info = dict(env_info or {})
    variant_id = str(env_info.get("variant_id") or "active_evidence_kernel_v1")
    messages = [
        {
            "role": "system",
            "content": (
                "You are operating inside the active evidence kernel. "
                "Use the real tools truthfully, keep receipts, and respond to recovery cards. "
                "Visible verifier success is necessary but not sufficient; claimed report and receipt fields must be grounded in solver-visible evidence. "
                "The harness will enforce verifier, provenance, artifact, service, and finalization gates."
            ),
        },
        {
            "role": "system",
            "content": f"Task prompt:\n{task_prompt}\n\nEnvironment:\n{json.dumps(_project_env_info(env_info), sort_keys=True)}",
        },
    ]
    if variant_id == "active_evidence_kernel_control_plane_context_v1":
        messages.append(
            {
                "role": "system",
                "content": (
                    "Control-plane contract:\n"
                    "Emit structured `control_plane_update` or `semantic_state_update` JSON when you have semantic progress to share. "
                    "Use `plan_state` for the immediate step sequence and `semantic_state` for hypotheses, evidence_targets, candidate_next_checks, subtasks, discoveries, open_questions, evidence_notes, blocked_reason, confidence, proposed_success_criteria, finish_claim, model_claimed_done, interrupt_reason, and replan_requested. "
                    "The working window includes a compact `semantic_sideband` projection for quick orientation. "
                    "Do not mutate pinned truth or finalization authority.\n"
                    + render_model_contract(
                        task_prompt,
                        {
                            "variant_id": variant_id,
                        },
                    )
                ),
            }
        )
    return {
        "messages": messages,
        "active_kernel_bootstrap": {
            "task_prompt": task_prompt,
            "env_info": _project_env_info(env_info),
            "route": variant_id,
        },
    }


def start_run(
    *,
    core_state: dict[str, Any],
    working_context_pack: dict[str, Any],
    carry_state: KernelState | None = None,
    tool_definitions: list[dict[str, Any]] | None = None,
    route_manifest: dict[str, Any] | None = None,
) -> ActiveEvidenceKernel:
    env_info = dict(core_state.get("env_info", {}))
    workspace_root = Path(str(core_state.get("workspace_root") or env_info.get("workspace_root") or env_info.get("cwd") or ".")).resolve()
    cwd = str(core_state.get("cwd") or env_info.get("cwd") or workspace_root)
    task_prompt = str(core_state.get("task_prompt") or env_info.get("task_prompt") or "")
    run_id = str(core_state.get("run_id") or env_info.get("run_id") or "")
    task_id = str(core_state.get("task_id") or env_info.get("task_id") or "")
    declared_tool_definitions = list(tool_definitions or discover_native_tool_definitions(
        cwd=cwd,
        workspace_state=core_state.get("workspace_state") if isinstance(core_state.get("workspace_state"), dict) else None,
        route_manifest=route_manifest,
        task_prompt=task_prompt,
    ))
    state = KernelState.from_core_state(
        core_state={
            "run_id": run_id,
            "task_id": task_id,
            "native_tool_mode_active": any(_tool_name_from_definition(entry) != "raw_bash" for entry in declared_tool_definitions),
            "declared_tool_names": [name for name in (_tool_name_from_definition(entry) for entry in declared_tool_definitions) if name],
            "declared_tool_schemas": {
                str(entry["name"]): dict(entry.get("input_schema", {}))
                for entry in declared_tool_definitions
                if isinstance(entry, dict) and isinstance(entry.get("name"), str) and isinstance(entry.get("input_schema"), dict)
            },
            "workspace_state": core_state.get("workspace_state", {}) if isinstance(core_state.get("workspace_state"), dict) else {},
        },
        working_context_pack=working_context_pack,
        task_prompt=task_prompt,
        cwd=cwd,
        workspace_root=workspace_root,
        carry_state=carry_state,
    )
    state.register_declared_tools(declared_tool_definitions)
    if route_manifest and route_manifest.get("variant_id"):
        state.selected_facts = [
            *state.selected_facts,
            f"route_variant={route_manifest['variant_id']}",
        ]
    state.model_led_success_contract_active = bool((route_manifest or {}).get("feature_flags", {}).get("model_led_success_contract"))
    state.anti_benchfying_mode_active = bool((route_manifest or {}).get("feature_flags", {}).get("anti_benchfying_mode"))
    state.layer2_success_audit_active = bool((route_manifest or {}).get("feature_flags", {}).get("layer2_success_audit"))
    state.model_led_evidence_substrate_active = ((route_manifest or {}).get("variant_id") == "model_led_evidence_substrate_v1")
    kernel = ActiveEvidenceKernel(state=state, route_manifest=dict(route_manifest or {}))
    if _is_control_plane_route(kernel.route_manifest):
        kernel._ensure_control_plane_state()
    return kernel


def before_model_call(
    kernel: ActiveEvidenceKernel,
    *,
    max_recent_receipts: int = 5,
    history: list[dict[str, Any]] | None = None,
    working_window_budget: int = 6000,
) -> dict[str, Any]:
    return kernel.before_model_call(
        max_recent_receipts=max_recent_receipts,
        history=history,
        working_window_budget=working_window_budget,
    )


def after_tool_result(
    kernel: ActiveEvidenceKernel,
    *,
    tool_call: dict[str, Any] | None,
    tool_result: dict[str, Any],
    cwd: str,
    step: int | None = None,
    tool_index: int | None = None,
    phase: str = "execute",
    action_id: str | None = None,
) -> dict[str, Any]:
    return kernel.after_tool_result(
        tool_call=tool_call,
        tool_result=tool_result,
        cwd=cwd,
        step=step,
        tool_index=tool_index,
        phase=phase,
        action_id=action_id,
    )


def after_model_no_tool_calls(
    kernel: ActiveEvidenceKernel,
    *,
    step: int,
    completion: dict[str, Any] | None = None,
    workspace_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return kernel.after_model_no_tool_calls(step=step, completion=completion, workspace_state=workspace_state)


def run_verifier_gate(task: str, workspace_state: dict[str, Any]) -> bool:
    return run_verifier_gate_check(task, workspace_state)


def finalize(
    *,
    execution_result: dict[str, Any],
    recovery_action: dict[str, Any] | None = None,
    workspace_state: dict[str, Any] | None = None,
    verified: bool | None = None,
) -> dict[str, Any]:
    return finalize_governed_gate(
        execution_result=execution_result,
        recovery_action=recovery_action,
        workspace_state=workspace_state
        if isinstance(workspace_state, dict)
        else (execution_result.get("workspace_state") if isinstance(execution_result.get("workspace_state"), dict) else None),
        verified=verified,
    )


def run_loop(
    model: Any,
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    context: dict[str, Any],
    max_steps: int,
    tool_definitions: list[dict[str, Any]] | None = None,
    route_manifest: dict[str, Any] | None = None,
    workspace_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if max_steps <= 0:
        raise ValueError("max_steps must be >= 1")
    history = list(context.get("history", []))
    manage_history = context["manage_history"]
    env_info = dict(context.get("env_info", {}))
    if route_manifest is None and isinstance(context.get("route_manifest"), dict):
        route_manifest = dict(context["route_manifest"])
    if workspace_state is None and isinstance(context.get("workspace_state"), dict):
        workspace_state = dict(context["workspace_state"])
    working_context_pack = dict(context.get("working_context_pack", {}))
    task_prompt = str(env_info.get("task_prompt") or context.get("task_prompt") or "")
    model_led_active = (route_manifest or {}).get("variant_id") == "model_led_evidence_substrate_v1"
    if model_led_active:
        if tool_definitions is None:
            tool_definitions = []
        if not any(d.get("name") == "view_receipt" for d in tool_definitions):
            tool_definitions = list(tool_definitions)
            tool_definitions.append({
                "name": "view_receipt",
                "description": "Examine the full raw stdout and stderr of a past action/step by specifying its receipt_id (e.g. 'r0002'). Use this if previous tool outputs were truncated.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "receipt_id": {
                            "type": "string",
                            "description": "The receipt ID of the past step (e.g. 'r0001', 'r0002') whose full raw output you want to retrieve."
                        }
                    },
                    "required": ["receipt_id"]
                }
            })
    kernel = start_run(
        core_state={
            "run_id": env_info.get("run_id") or "",
            "task_id": env_info.get("task_id") or "",
            "task_prompt": task_prompt,
            "cwd": env_info.get("cwd") or "",
            "workspace_root": env_info.get("workspace_root") or env_info.get("cwd") or "",
            "env_info": env_info,
            "workspace_state": workspace_state or {},
        },
        working_context_pack=working_context_pack or {"open_obligations": {}},
        carry_state=_coerce_kernel_state(context.get("active_kernel_carry_state")),
        tool_definitions=tool_definitions,
        route_manifest=route_manifest,
    )
    kernel.max_steps = max_steps
    if model_led_active:
        tools = dict(tools)
        def view_receipt_tool(tool_call: dict[str, Any]) -> dict[str, Any]:
            args = tool_call.get("arguments") or {}
            receipt_id = str(args.get("receipt_id") or "").strip()
            if not receipt_id:
                return {
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "Error: receipt_id is required.",
                    "reason_code": "view_receipt_missing_id"
                }
            raw_outputs = getattr(kernel.state, "raw_receipt_outputs", {}) or {}
            if receipt_id in raw_outputs:
                out = raw_outputs[receipt_id]
                return {
                    "exit_code": 0,
                    "stdout": out.get("stdout") or "",
                    "stderr": out.get("stderr") or "",
                    "reason_code": "view_receipt_success"
                }
            for r in getattr(kernel.state, "receipts", []):
                if r.get("receipt_id") == receipt_id:
                    return {
                        "exit_code": r.get("exit_code") or 0,
                        "stdout": r.get("stdout_excerpt") or "",
                        "stderr": r.get("stderr_excerpt") or "",
                        "reason_code": "view_receipt_excerpt_only"
                    }
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Error: receipt_id '{receipt_id}' not found.",
                "reason_code": "view_receipt_not_found"
            }
        tools["view_receipt"] = view_receipt_tool
    if tool_definitions:
        kernel.state.register_declared_tools(tool_definitions)
    steps: list[dict[str, Any]] = []
    control_plane_events: list[dict[str, Any]] = []
    status = "max_steps_exhausted"
    finish_claim_observed = False
    last_completion: dict[str, Any] = {}
    last_model_client_error: dict[str, Any] | None = None
    active_recovery_prompt = ""
    active_workspace_state = dict(workspace_state or {})
    active_workspace_state.setdefault("route_manifest", route_manifest or {})
    active_workspace_state.setdefault("task_prompt", env_info.get("task_prompt") or context.get("task_prompt") or "")
    active_workspace_state.setdefault("cwd", env_info.get("cwd") or "")
    active_workspace_state.setdefault("workspace_root", env_info.get("workspace_root") or env_info.get("cwd") or "")
    active_workspace_state.setdefault("active_kernel_state", kernel.state.to_dict())
    active_workspace_state.setdefault("workspace_state", dict(active_workspace_state))
    required_artifact_paths = _ensure_required_artifact_paths(active_workspace_state, route_manifest)
    active_workspace_state["required_artifact_paths"] = list(required_artifact_paths)
    if kernel.control_plane_state:
        active_workspace_state["control_plane_state"] = dict(kernel.control_plane_state)
    artifact_root = Path(
        str(
            active_workspace_state.get("workspace_root")
            or env_info.get("workspace_root")
            or active_workspace_state.get("cwd")
            or env_info.get("cwd")
            or "."
        )
    )
    sync_status = _sync_execution_artifact_gate_state(kernel.state, artifact_root, required_artifact_paths)
    active_workspace_state["verifier_artifact_present"] = sync_status["status"] == "pass"
    active_workspace_state["artifact_status"] = dict(sync_status)

    def _inject_compaction_summary_if_needed(context_pack: dict[str, Any]) -> None:
        nonlocal history
        if not kernel._control_plane_enabled():
            return
        if not isinstance(context_pack, dict) or not context_pack.get("control_plane_compaction_request"):
            return
        compaction_result = kernel._maybe_apply_model_compaction_summary(model)
        if not isinstance(compaction_result, dict):
            return
        summary_message = str(compaction_result.get("summary_message") or "")
        if summary_message:
            history = manage_history(history, {"role": "system", "content": summary_message})
        control_plane_events.extend(kernel.drain_control_plane_events())

    layer2_fail_count = 0
    for step in range(max_steps):
        _sync_execution_artifact_gate_state(kernel.state, artifact_root, required_artifact_paths)
        if step > 0 or active_recovery_prompt:
            context_pack = before_model_call(kernel, history=history)
            control_plane_events.extend(kernel.drain_control_plane_events())
            prompt_payload = {
                "role": "system",
                "content": active_recovery_prompt or _recovery_card_text(kernel.state.recovery_card),
                "evidence_context_pack": context_pack,
            }
            history = manage_history(history, prompt_payload)
        else:
            context_pack = before_model_call(kernel, history=history)
            control_plane_events.extend(kernel.drain_control_plane_events())
            history = manage_history(
                history,
                {
                    "role": "system",
                    "content": "",
                    "evidence_context_pack": context_pack,
                },
            )
            history = manage_history(
                history,
                {
                    "role": "user",
                    "content": task_prompt.strip() if task_prompt.strip() else "Proceed with the task.",
                },
            )
        if kernel.feature_flags.get("model_led_success_contract"):
            curr_status = kernel.state.success_contract.get("status", "not_declared") if kernel.state.success_contract else "not_declared"
            if curr_status == "not_declared":
                kernel.state.open_obligations["success_contract_missing"] = ["declare_success_contract"]
                instruction = (
                    "Before substantial work, declare a Success Contract from visible task/workspace evidence.\n"
                    "Do not include hidden assumptions. You may revise it later only with cited visible evidence."
                )
                history = manage_history(history, {"role": "system", "content": instruction})
        _inject_compaction_summary_if_needed(context_pack)
        context_token_attribution = _estimate_context_token_attribution(
            history=history,
            context_pack=context_pack,
            task_prompt=task_prompt,
            tool_definitions=tool_definitions or [],
            recovery_prompt=active_recovery_prompt,
            call_kind="solver",
            step=step,
        )
        try:
            pruned_history = prune_context_packs_from_history(history)
            completion = model.complete(pruned_history, tools=tool_definitions or [])
        except Exception as error:
            recovery_action = handle_error(error, history, state=kernel.state)
            error_details = getattr(error, "details", None)
            sanitized_error_details = dict(error_details) if isinstance(error_details, dict) else {}
            if isinstance(error, ModelClientError):
                last_model_client_error = sanitized_error_details or {"message": str(error)}
            active_recovery_prompt = _recovery_card_text(recovery_action.get("recovery_card"))
            steps.append(
                {
                    "step": step,
                    "tool_calls": 0,
                    "status": "model_error",
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "error_details": sanitized_error_details,
                    "recovery_action": recovery_action,
                }
            )
            if recovery_action.get("action") == "stop":
                status = "max_steps_exhausted"
                break
            continue
        if not isinstance(completion, dict):
            completion = {"text": str(completion), "tool_calls": []}
        last_completion = completion

        if kernel.feature_flags.get("model_led_success_contract"):
            from runner.kernel_success_contract import (
                extract_success_contract,
                validate_success_contract,
                freeze_success_contract,
                propose_success_contract_revision,
            )
            extracted = extract_success_contract(completion)
            if extracted:
                valid_res = validate_success_contract(extracted)
                if valid_res["status"] == "accepted":
                    curr_status = kernel.state.success_contract.get("status", "not_declared") if kernel.state.success_contract else "not_declared"
                    receipt_id = f"r{len(kernel.state.receipts):04d}" if kernel.state.receipts else "r0000"
                    evidence_refs = extracted.get("visible_evidence_refs", [])
                    if curr_status not in ("frozen", "revised"):
                        freeze_success_contract(
                            state=kernel.state,
                            contract=extracted,
                            receipt_id=receipt_id,
                            evidence_refs=evidence_refs,
                        )
                    else:
                        propose_success_contract_revision(
                            state=kernel.state,
                            proposed=extracted,
                            receipt_id=receipt_id,
                            evidence_refs=evidence_refs,
                        )

        assistant_text = completion.get("text")
        if isinstance(assistant_text, str) and assistant_text:
            history = manage_history(history, {"role": "assistant", "content": assistant_text})

        tool_calls = completion.get("tool_calls")
        if not isinstance(tool_calls, list) or not tool_calls:
            decision = kernel.after_model_no_tool_calls(step=step, completion=completion, workspace_state=active_workspace_state)
            control_plane_events.extend(kernel.drain_control_plane_events())
            active_recovery_prompt = _recovery_card_text(decision.get("recovery_card") or kernel.state.recovery_card)
            steps.append(
                {
                    "step": step,
                    "tool_calls": 0,
                    "status": "no_tool_calls",
                    "completion": completion,
                    "decision": decision,
                    "context_token_attribution": context_token_attribution,
                }
            )
            if bool(decision.get("finish_claim")):
                finish_claim_observed = True
            if decision.get("action") == "finalize":
                if not kernel.feature_flags.get("layer2_success_audit"):
                    status = "completed"
                    break
                final_gate = finalize_governed_gate(
                    execution_result={"status": "completed", "active_kernel_state": kernel.state.to_dict(), "workspace_state": active_workspace_state},
                    recovery_action={"action": "none"},
                    workspace_state=active_workspace_state,
                    verified=True,
                )
                status_val = final_gate.get("governed_status") or final_gate.get("status")
                if status_val != "governed_pass":
                    failure_info = {
                        "failure_class": "deterministic_gate_failed",
                        "reason_code": final_gate.get("governed_status") or "deterministic_gate_failed",
                        "failure_signature": f"deterministic_gate_failed|{step}|{tuple(final_gate.get('reason_codes', []))}",
                        "repair_hint": f"Deterministic finalization gate failed. Reason codes: {final_gate.get('reason_codes')}. Please address these before claiming completion.",
                        "required_next_obligation": "address_open_obligations",
                        "stale_facts": [],
                    }
                    repeated_count = kernel.state.record_failure(failure_info["failure_signature"], failure_info)
                    kernel.state.recovery_card = build_recovery_card(
                        failure_info=failure_info,
                        repeated_count=repeated_count,
                        state=kernel.state,
                    )
                    kernel.state.refresh_open_obligations()
                    active_recovery_prompt = _recovery_card_text(kernel.state.recovery_card)
                    continue

                from runner.kernel_layer2_audit import should_run_layer2, build_layer2_audit_prompt, parse_layer2_audit_response, deterministic_layer2_fallback
                if should_run_layer2(route_manifest=route_manifest or {}, finalization_gate=final_gate):
                    audit_prompt = build_layer2_audit_prompt(
                        task_prompt=task_prompt,
                        success_contract=kernel.state.success_contract,
                        context_pack=before_model_call(kernel, history=history),
                        finalization_gate=final_gate,
                    )
                    try:
                        audit_completion = model.complete(audit_prompt, tools=[])
                        audit_result = parse_layer2_audit_response(audit_completion)
                    except Exception as error:
                        audit_result = deterministic_layer2_fallback(
                            finalization_gate=final_gate,
                            success_contract=kernel.state.success_contract,
                        )
                        audit_result.setdefault("reason_codes", []).append("layer2_model_unavailable")
                    from runner.kernel_layer2_audit import normalize_layer2_audit_state

                    normalized_audit = normalize_layer2_audit_state(audit_result)
                    kernel.state.layer2_audit_state = normalized_audit

                    if normalized_audit["verdict"] == "PASS":
                        status = "completed"
                        break
                    else:
                        layer2_fail_count += 1
                        mismatches = audit_result.get("mismatches", [])
                        missing_evidence = audit_result.get("missing_evidence", [])
                        repair_instruction = audit_result.get("repair_instruction", "")
                        failure_info = {
                            "failure_class": "layer2_audit_failed",
                            "reason_code": "layer2_completion_audit_failed",
                            "failure_signature": "layer2_audit_failed",
                            "repair_hint": f"Layer 2 completion check failed: {repair_instruction}. Mismatches: {mismatches}. Missing evidence: {missing_evidence}.",
                            "required_next_obligation": "address_open_obligations",
                            "stale_facts": [],
                        }
                        repeated_count = kernel.state.record_failure(failure_info["failure_signature"], failure_info)
                        kernel.state.recovery_card = build_recovery_card(
                            failure_info=failure_info,
                            repeated_count=repeated_count,
                            state=kernel.state,
                        )
                        kernel.state.refresh_open_obligations()
                        active_recovery_prompt = _recovery_card_text(kernel.state.recovery_card)
                        if layer2_fail_count >= 3:
                            status = "max_steps_exhausted"
                            break
                        continue
                else:
                    status = "completed"
                    break
            if decision.get("action") == "stop":
                status = "max_steps_exhausted"
                break
            continue

        step_result: dict[str, Any] = {
            "step": step,
            "tool_calls": len(tool_calls),
            "results": [],
            "completion": completion,
            "context_token_attribution": context_token_attribution,
        }
        history = manage_history(
            history,
            {
                "role": "assistant",
                "content": assistant_text if isinstance(assistant_text, str) and assistant_text else None,
                "tool_calls": tool_calls,
            },
        )
        step_failed = False
        for tool_index, tool_call in enumerate(tool_calls):
            if not isinstance(tool_call, dict):
                tool_result = {
                    "tool_name": "unknown",
                    "command": "",
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "malformed_tool_call",
                    "timed_out": False,
                    "result_class": "contract_error",
                    "reason_code": "tool_call_contract_malformed",
                }
            else:
                tool_name = tool_call.get("name")
                if not isinstance(tool_name, str) or tool_name not in tools:
                    tool_result = {
                        "tool_name": tool_name if isinstance(tool_name, str) else "unknown",
                        "command": _tool_command(tool_call, {}),
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": f"unsupported_tool:{tool_name}",
                        "timed_out": False,
                        "result_class": "contract_error",
                        "reason_code": "unsupported_tool",
                    }
                else:
                    try:
                        tool_result = tools[tool_name](tool_call)
                    except Exception as error:
                        recovery_action = handle_error(error, history, state=kernel.state)
                        tool_result = {
                            "tool_name": tool_name,
                            "command": _tool_command(tool_call, {}),
                            "exit_code": 1,
                            "stdout": "",
                            "stderr": str(error),
                            "timed_out": False,
                            "result_class": "runtime_error",
                            "reason_code": recovery_action.get("reason_code") or "tool_runtime_error",
                            "error": str(error),
                        }
                        active_recovery_prompt = _recovery_card_text(recovery_action.get("recovery_card"))
            receipt_update = after_tool_result(
                kernel,
                tool_call=tool_call if isinstance(tool_call, dict) else None,
                tool_result=tool_result,
                cwd=str(active_workspace_state.get("cwd") or env_info.get("cwd") or ""),
                step=step,
                tool_index=tool_index,
                phase="execute",
                action_id=f"{kernel.state.run_id}-a{len(kernel.state.receipts):04d}",
            )
            step_result["results"].append(tool_result)
            step_result.setdefault("receipts", []).append(receipt_update["receipt"])
            history = manage_history(
                history,
                {
                    "role": "tool",
                    "name": _tool_name(tool_call if isinstance(tool_call, dict) else None, tool_result),
                    "tool_call_id": tool_call.get("id") if isinstance(tool_call, dict) else None,
                    "content": _tool_observation(tool_call if isinstance(tool_call, dict) else None, tool_result),
                },
            )
            _sync_execution_artifact_gate_state(kernel.state, artifact_root, required_artifact_paths)
            control_plane_events.extend(kernel.drain_control_plane_events())
            if receipt_update["failure_signal"] is not None:
                step_failed = True
                active_recovery_prompt = _recovery_card_text(receipt_update["recovery_signal"])
                if receipt_update["recovery_signal"].get("repeated_count", 0) >= 3:
                    break
        if step_failed:
            step_result["status"] = "recovery_required"
        else:
            active_recovery_prompt = ""
            if not kernel.state.open_obligations:
                kernel.state.recovery_card = {}
        steps.append(step_result)
        if step_failed and kernel.state.recovery_card.get("repeated_count", 0) >= 3:
            status = "max_steps_exhausted"
            break

    if status != "completed":
        if _is_control_plane_route(route_manifest or {}) and not finish_claim_observed:
            status = "max_steps_exhausted"
        elif kernel.state.open_obligations:
            status = "max_steps_exhausted"
        elif any(step.get("status") == "recovery_required" for step in steps):
            status = "max_steps_exhausted"
        else:
            status = "completed"

    final_artifact_status = _sync_execution_artifact_gate_state(kernel.state, artifact_root, required_artifact_paths)
    final_context_pack = before_model_call(kernel, history=history)
    control_plane_events.extend(kernel.drain_control_plane_events())
    active_workspace_state.update(
        {
            "execution_status": status,
            "model_claimed_done": status == "completed",
            "history_length": len(history),
            "inline_assertion_pass": status == "completed",
            "verifier_artifact_present": final_artifact_status["status"] == "pass",
            "artifact_status": dict(final_artifact_status),
            "replay_layer_pass": True,
            "replay_or_state_grader_pass": True,
            "execution_result": {
                "status": status,
                "steps": steps,
                "step_count": len(steps),
                "last_completion": last_completion,
                "control_plane_state": dict(kernel.control_plane_state) if kernel.control_plane_state else {},
                "control_plane_working_window": dict(kernel.control_plane_state.get("last_working_window", {})) if isinstance(kernel.control_plane_state.get("last_working_window"), dict) else {},
            },
            "task_prompt": env_info.get("task_prompt") or context.get("task_prompt") or "",
            "canonical_workspace_root": env_info.get("canonical_workspace_root") or env_info.get("workspace_root") or env_info.get("cwd") or "",
            "active_kernel_state": kernel.state.to_dict(),
            "active_context_pack": final_context_pack,
            "open_obligations": dict(kernel.state.open_obligations),
            "native_tool_state": dict(kernel.state.native_tool_state),
            "service_state": {
                "service_registry": dict(kernel.state.service_registry),
                "process_registry": dict(kernel.state.process_registry),
            },
            "control_plane_state": dict(kernel.control_plane_state) if kernel.control_plane_state else {},
            "control_plane_working_window": dict(kernel.control_plane_state.get("last_working_window", {})) if isinstance(kernel.control_plane_state.get("last_working_window"), dict) else {},
        }
    )
    active_workspace_state["workspace_state"] = dict(active_workspace_state)
    active_workspace_state["control_plane_events"] = list(control_plane_events)
    active_workspace_state["verification_output_summary"] = ""
    if required_artifact_paths:
        active_workspace_state["required_artifact_paths"] = list(required_artifact_paths)
    if kernel.state.recovery_card:
        active_workspace_state["last_recovery_card"] = dict(kernel.state.recovery_card)
    if isinstance(last_model_client_error, dict):
        active_workspace_state["last_model_client_error"] = dict(last_model_client_error)
    final_gate_preview = finalize_governed_gate(
        execution_result={"status": status, "active_kernel_state": kernel.state.to_dict(), "workspace_state": active_workspace_state},
        recovery_action={"action": "stop" if kernel.state.open_obligations else "none"},
        workspace_state=active_workspace_state,
        verified=False,
    )
    active_workspace_state["governed_status"] = final_gate_preview["governed_status"]
    active_workspace_state["final_verdict"] = final_gate_preview["final_verdict"]
    active_workspace_state["verification_reason_codes"] = list(final_gate_preview["reason_codes"])
    return {
        "status": status,
        "history": history,
        "steps": steps,
        "step_count": len(steps),
        "last_completion": last_completion,
        "active_kernel_state": kernel.state.to_dict(),
        "active_context_pack": build_context_pack(kernel.state),
        "open_obligations": dict(kernel.state.open_obligations),
        "required_artifact_paths": list(required_artifact_paths),
        "governed_status": final_gate_preview["governed_status"],
        "final_verdict": final_gate_preview["final_verdict"],
        "verification_reason_codes": list(final_gate_preview["reason_codes"]),
        "workspace_state": active_workspace_state,
        "native_tool_state": dict(kernel.state.native_tool_state),
        "service_state": {
            "service_registry": dict(kernel.state.service_registry),
            "process_registry": dict(kernel.state.process_registry),
        },
        "control_plane_state": dict(kernel.control_plane_state) if kernel.control_plane_state else {},
        "control_plane_working_window": dict(kernel.control_plane_state.get("last_working_window", {})) if isinstance(kernel.control_plane_state.get("last_working_window"), dict) else {},
        "control_plane_events": list(control_plane_events),
        "recovery_card": dict(kernel.state.recovery_card),
        "last_model_client_error": dict(last_model_client_error or {}),
        "autopsy": _build_autopsy_summary(kernel.state),
    }


def _build_autopsy_summary(state: KernelState) -> dict[str, Any]:
    if not state.failure_signature_counts:
        return {}
    repeated = [
        signature
        for signature, count in state.failure_signature_counts.items()
        if int(count) >= 2
    ]
    if not repeated:
        return {}
    return {
        "triggered": True,
        "replan_required": True,
        "reason_codes": ["bounded_autopsy_replan_required_after_repeated_failure"],
        "repeated_failure_signatures": repeated,
    }


def _estimate_context_token_attribution(
    *,
    history: list[dict[str, Any]],
    context_pack: dict[str, Any],
    task_prompt: str,
    tool_definitions: list[dict[str, Any]],
    recovery_prompt: str,
    call_kind: str,
    step: int,
) -> dict[str, Any]:
    history_chars = _json_char_count(history)
    context_pack_chars = _json_char_count(context_pack)
    tool_schema_chars = _json_char_count(tool_definitions)
    task_prompt_chars = len(task_prompt or "")
    recovery_chars = len(recovery_prompt or "")
    bucket_chars = {
        "task_prompt": task_prompt_chars,
        "tool_schema": tool_schema_chars,
        "context_pack": context_pack_chars,
        "context_pack_task_contract": _json_char_count(context_pack.get("task_contract") if isinstance(context_pack, dict) else {}),
        "context_pack_environment": _json_char_count(context_pack.get("environment") if isinstance(context_pack, dict) else {}),
        "context_pack_recent_receipts": _json_char_count(context_pack.get("recent_receipts") if isinstance(context_pack, dict) else []),
        "context_pack_compression": _json_char_count(context_pack.get("compression") if isinstance(context_pack, dict) else {}),
        "context_pack_artifact_lineage": _json_char_count(context_pack.get("artifact_lineage") if isinstance(context_pack, dict) else {}),
        "context_pack_artifact_registry": _json_char_count(context_pack.get("artifact_registry_summary") if isinstance(context_pack, dict) else {}),
        "context_pack_verifier_state": _json_char_count(context_pack.get("verifier_state") if isinstance(context_pack, dict) else {}),
        "context_pack_service_state": _json_char_count(context_pack.get("service_state") if isinstance(context_pack, dict) else {}),
        "context_pack_native_tool_state": _json_char_count(context_pack.get("native_tool_state") if isinstance(context_pack, dict) else {}),
        "context_pack_evidence_trail_state": _json_char_count(context_pack.get("evidence_trail_state") if isinstance(context_pack, dict) else {}),
        "context_pack_open_obligations": _json_char_count(context_pack.get("open_obligations") if isinstance(context_pack, dict) else {}),
        "context_pack_success_contract": _json_char_count(context_pack.get("success_contract") if isinstance(context_pack, dict) else {}),
        "context_pack_layer2_audit_state": _json_char_count(context_pack.get("layer2_audit_state") if isinstance(context_pack, dict) else {}),
        "recovery_prompt": recovery_chars,
        "full_history_payload": history_chars,
    }
    bucket_tokens = {key: _estimate_tokens_from_chars(value) for key, value in bucket_chars.items()}
    known_repeated_chars = task_prompt_chars + tool_schema_chars + context_pack_chars + recovery_chars
    residual_history_chars = max(0, history_chars - known_repeated_chars)
    bucket_chars["history_residual_estimate"] = residual_history_chars
    bucket_tokens["history_residual_estimate"] = _estimate_tokens_from_chars(residual_history_chars)
    return {
        "schema_version": "model_input_context_attribution_estimate.v1",
        "call_kind": call_kind,
        "step": step,
        "estimation_method": "json_chars_div_4",
        "estimated_input_tokens": _estimate_tokens_from_chars(history_chars + tool_schema_chars),
        "bucket_chars": bucket_chars,
        "bucket_tokens": bucket_tokens,
        "message_count": len(history),
        "tool_definition_count": len(tool_definitions),
        "context_pack_version": context_pack.get("context_pack_version") if isinstance(context_pack, dict) else "",
    }


def _json_char_count(value: Any) -> int:
    try:
        return len(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    except Exception:
        return len(str(value))


def _estimate_tokens_from_chars(char_count: int) -> int:
    return max(0, int((int(char_count) + 3) // 4))


def _recovery_card_text(recovery_card: dict[str, Any] | None) -> str:
    if not isinstance(recovery_card, dict) or not recovery_card:
        return ""
    payload = {
        "active_evidence_recovery_card": recovery_card,
    }
    return (
        "Visible verifier success is necessary but not sufficient; ground any report or receipt claim in solver-visible evidence. "
        + json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )


def _tool_name(tool_call: dict[str, Any] | None, tool_result: dict[str, Any]) -> str:
    if isinstance(tool_call, dict):
        name = tool_call.get("name")
        if isinstance(name, str) and name:
            return name
    name = tool_result.get("tool_name")
    return name if isinstance(name, str) and name else "unknown"


def _tool_command(tool_call: dict[str, Any] | None, tool_result: dict[str, Any]) -> str:
    if isinstance(tool_call, dict):
        arguments = tool_call.get("arguments")
        if isinstance(arguments, dict):
            command = arguments.get("command")
            if isinstance(command, str):
                return command
        if isinstance(arguments, str):
            return arguments
    command = tool_result.get("command")
    return command if isinstance(command, str) else ""


def _tool_observation(tool_call: dict[str, Any] | None, tool_result: dict[str, Any]) -> str:
    name = _tool_name(tool_call, tool_result)
    if "error" in tool_result:
        return f"{name} error: {tool_result['error']}"
    return (
        f"{name} exit={tool_result.get('exit_code')}\n"
        f"stdout:\n{tool_result.get('stdout') or ''}\n"
        f"stderr:\n{tool_result.get('stderr') or ''}"
    ).strip()


def _result_failed(tool_result: dict[str, Any]) -> bool:
    if "error" in tool_result:
        return True
    if bool(tool_result.get("timed_out", False)):
        return True
    exit_code = tool_result.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return True
    return False


def _coerce_kernel_state(value: Any) -> KernelState | None:
    if isinstance(value, KernelState):
        return value
    if isinstance(value, dict):
        try:
            return KernelState.from_core_state(
                core_state=value,
                working_context_pack=value.get("working_context_pack", {}) if isinstance(value.get("working_context_pack"), dict) else {"open_obligations": {}},
                task_prompt=str(value.get("task_prompt", "")),
                cwd=str(value.get("cwd", "")),
                workspace_root=Path(str(value.get("workspace_root", "."))),
            )
        except Exception:
            return None
    return None


def _project_env_info(env_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "cwd": env_info.get("cwd", ""),
        "task_id": env_info.get("task_id", ""),
        "run_id": env_info.get("run_id", ""),
        "workspace_root": env_info.get("workspace_root", env_info.get("cwd", "")),
        "variant_id": env_info.get("variant_id", ""),
    }


def _ensure_required_artifact_paths(
    workspace_state: dict[str, Any],
    route_manifest: dict[str, Any] | None,
) -> list[str]:
    candidates = _as_string_list(workspace_state.get("required_artifact_paths"))
    if candidates:
        return candidates
    if isinstance(route_manifest, dict):
        route_files = _as_string_list(route_manifest.get("required_artifact_paths"))
        if route_files:
            return route_files
    return ["run_header.json", "run_events.jsonl", "route_manifest.json"]


def _sync_execution_artifact_gate_state(
    state: KernelState,
    artifact_root: Path,
    required_artifact_paths: list[str],
) -> dict[str, Any]:
    from runner.kernel_artifacts import check_required_artifacts
    execution_artifact_paths = {"run_header.json", "run_events.jsonl", "route_manifest.json"}
    required = set(required_artifact_paths)
    if required and required.issubset(execution_artifact_paths):
        artifact_status = {
            "status": "pass",
            "reason_codes": [],
            "output_summary": "",
            "required_paths": list(required_artifact_paths),
            "missing_paths": [],
            "observed_hashes": {},
        }
        empty_paths = []
    else:
        check_res = check_required_artifacts(
            workspace_root=artifact_root,
            required_paths=required_artifact_paths,
        )
        reason_codes = list(check_res["reason_codes"])
        if check_res["status"] == "fail":
            if "artifact_gate_failed" not in reason_codes:
                reason_codes.append("artifact_gate_failed")
        artifact_status = {
            "status": check_res["status"],
            "reason_codes": reason_codes,
            "output_summary": f"required_count={check_res['required_count']}, present_count={check_res['present_count']}, non_empty_count={check_res['non_empty_count']}",
            "required_paths": list(check_res["required_paths"]),
            "missing_paths": list(check_res["missing_paths"]),
            "observed_hashes": dict(check_res["observed_hashes"]),
        }
        empty_paths = list(check_res["empty_paths"])
    state.artifact_gate = {
        "status": artifact_status["status"],
        "reason_codes": list(artifact_status.get("reason_codes", [])),
        "required_paths": list(artifact_status["required_paths"]),
        "missing_paths": list(artifact_status["missing_paths"]),
        "empty_paths": list(empty_paths),
        "observed_hashes": dict(artifact_status["observed_hashes"]),
    }
    state.refresh_open_obligations()
    state.refresh_evidence_capsule()
    return artifact_status


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _tool_name_from_definition(entry: dict[str, Any]) -> str:
    if not isinstance(entry, dict):
        return ""
    name = entry.get("name")
    return name if isinstance(name, str) else ""


def _artifact_paths_present(cwd: Path, required_paths: list[str]) -> bool:
    if not required_paths:
        return False
    for rel_path in required_paths:
        candidate = Path(rel_path)
        if not candidate.is_absolute():
            candidate = cwd / candidate
        if not candidate.exists():
            return False
    return True


def _exit_code(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return 1


def _is_control_plane_route(route_manifest: dict[str, Any]) -> bool:
    return str(route_manifest.get("variant_id") or "") in ("active_evidence_kernel_control_plane_context_v1", "model_led_evidence_substrate_v1")


def _deterministic_compaction_summary(state: KernelState, compact_check: dict[str, Any]) -> dict[str, Any]:
    recent = [summarize_receipt(receipt) for receipt in state.receipts[-min(4, len(state.receipts)) :]]
    return {
        "model_led": False,
        "summary": "Deterministic compaction boundary recorded for control-plane working-window refresh.",
        "receipt_count": len(state.receipts),
        "recent_receipts": recent,
        "open_obligations": dict(state.open_obligations),
        "history_length": int(compact_check.get("history_length", 0) or 0),
        "trigger": compact_check.get("trigger"),
    }


def _build_model_compaction_fallback(
    state: KernelState,
    compact_check: dict[str, Any],
    compact_boundary: dict[str, Any],
    *,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    preview = dict((compact_check or {}).get("preview_window", {}))
    recent_receipts = preview.get("recent_receipts", []) if isinstance(preview.get("recent_receipts"), list) else []
    receipt_ids = [receipt.get("receipt_id") for receipt in recent_receipts if isinstance(receipt, dict) and isinstance(receipt.get("receipt_id"), str)]
    if not receipt_ids:
        receipt_ids = list(compact_boundary.get("preserved_receipt_ids", []))
    deterministic = _deterministic_compaction_summary(state, compact_check)
    return {
        "summary": deterministic.get("summary", ""),
        "receipt_ids": receipt_ids,
        "artifact_refs": [],
        "discoveries": [],
        "hypotheses": [],
        "evidence_targets": [],
        "candidate_next_checks": [],
        "subtasks": [],
        "open_questions": [],
        "next_action": "continue",
        "blocked_reason": "",
        "confidence": "",
        "proposed_success_criteria": [],
        "model_led": False,
        "source": "deterministic_fallback",
        "reason_codes": list(reason_codes or []) or ["compaction_model_summary_fallback"],
        "compact_id": str(compact_boundary.get("compact_id") or ""),
        "trigger": str((compact_check or {}).get("trigger") or ""),
        "history_length": int((compact_check or {}).get("history_length", 0) or 0),
        "receipt_count": int((compact_check or {}).get("receipt_count", 0) or 0),
        "receipt_range": list(compact_boundary.get("preserved_receipt_id_range", [])),
    }


def prune_context_packs_from_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of history with [active_evidence_context_pack] stripped from all but the last turn."""
    pruned = []
    last_idx = -1
    for idx, msg in enumerate(history):
        content = msg.get("content")
        if isinstance(content, str) and "[active_evidence_context_pack]" in content:
            last_idx = idx

    for idx, msg in enumerate(history):
        if idx == last_idx:
            pruned.append(msg)
            continue
        content = msg.get("content")
        if isinstance(content, str) and "[active_evidence_context_pack]" in content:
            new_msg = dict(msg)
            parts = content.split("[active_evidence_context_pack]")
            prefix = parts[0].strip()
            if prefix:
                new_msg["content"] = prefix
            else:
                new_msg["content"] = "(historical context pack omitted)"
            pruned.append(new_msg)
        else:
            pruned.append(msg)
    return pruned


def _truncate_output(text: str, limit: int = 4000) -> str:
    if not isinstance(text, str) or len(text) <= limit:
        return text
    head = text[:2000]
    tail = text[-1000:]
    omitted = len(text) - len(head) - len(tail)
    warning = f"\n\n... [TRUNCATED {omitted} CHARACTERS OF OUTPUT FOR EFFICIENCY - USE view_receipt TO READ FULL STDOUT/STDERR] ...\n\n"
    return f"{head}{warning}{tail}"


def _detect_file_read(tool_name: str, command: str, tool_call: dict[str, Any] | None, tool_result: dict[str, Any]) -> tuple[str, str, int] | None:
    if tool_result.get("exit_code") != 0:
        return None
    is_read = "view_file" in tool_name or "cat " in command or "read_file" in tool_name or "view_file" in command
    if not is_read:
        return None
        
    file_path = ""
    if tool_call and isinstance(tool_call, dict):
        args = tool_call.get("arguments") or {}
        file_path = args.get("AbsolutePath") or args.get("TargetFile") or args.get("path") or ""
        
    if not file_path:
        path_refs = extract_artifact_path_refs(command)
        if path_refs:
            file_path = path_refs[0]
                
    if file_path:
        content = tool_result.get("stdout") or ""
        line_count = len(content.splitlines())
        return file_path, content, line_count
    return None
