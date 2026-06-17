"""Deterministic verifier, artifact, and finalization gates for the active kernel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runner.kernel_artifacts import build_first_verified_success_record
from runner.kernel_evidence_trail import evaluate_evidence_trail_requirements
from runner.kernel_layer2_audit import normalize_layer2_audit_state


GOVERNED_STATUSES = (
    "governed_pass",
    "ungoverned_model_claim",
    "verifier_failed",
    "artifact_gate_failed",
    "provenance_gate_failed",
    "native_tool_contract_failed",
    "service_not_ready",
    "invalid_environment",
    "budget_exhausted_open_obligations",
)


def _lock_first_verified_success(workspace_state: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    active_state = workspace_state.get("active_kernel_state")
    if not isinstance(active_state, dict):
        active_state = {}
    existing = active_state.get("first_verified_success") if isinstance(active_state.get("first_verified_success"), dict) else {}
    if isinstance(existing, dict) and existing:
        workspace_state["first_verified_success"] = dict(existing)
        regression = active_state.get("verified_success_regression")
        if isinstance(regression, dict) and regression:
            workspace_state["verified_success_regression"] = dict(regression)
        return dict(existing)
    if evaluation.get("governed_status") != "governed_pass":
        regression = active_state.get("verified_success_regression")
        if isinstance(regression, dict) and regression:
            workspace_state["verified_success_regression"] = dict(regression)
        return {}
    artifact_registry = active_state.get("artifact_registry")
    if not isinstance(artifact_registry, dict):
        artifact_registry = workspace_state.get("artifact_registry") if isinstance(workspace_state.get("artifact_registry"), dict) else {}
    artifact_gate = workspace_state.get("artifact_status") or workspace_state.get("artifact_gate") or active_state.get("artifact_gate") or {}
    if not isinstance(artifact_gate, dict):
        artifact_gate = {}
    verifier_status = workspace_state.get("verifier_status") or active_state.get("verifier_status") or {}
    if not isinstance(verifier_status, dict):
        verifier_status = {}
    if evaluation.get("governed_status") == "governed_pass" and str(verifier_status.get("status") or "") != "pass":
        verifier_status = {
            "status": "pass",
            "reason_codes": [],
            "output_summary": "verification_gate_pass",
        }
    receipt_id = ""
    receipts = active_state.get("receipts")
    if isinstance(receipts, list):
        for receipt in reversed(receipts):
            if not isinstance(receipt, dict):
                continue
            candidate = receipt.get("receipt_id")
            if isinstance(candidate, str) and candidate:
                receipt_id = candidate
                break
    snapshot = build_first_verified_success_record(
        artifact_registry=artifact_registry,
        artifact_gate=artifact_gate,
        verifier_status=verifier_status,
        receipt_id=receipt_id or None,
    )
    active_state["first_verified_success"] = dict(snapshot)
    workspace_state["first_verified_success"] = dict(snapshot)
    return snapshot


def check(task: str, workspace_state: dict[str, Any]) -> bool:
    """Run the deterministic verification gate and annotate workspace state."""
    _ = task
    verification_workspace_state = dict(workspace_state)
    open_obligations = dict(verification_workspace_state.get("open_obligations", {}))
    open_obligations.pop("verifier_gate_status", None)
    verification_workspace_state["open_obligations"] = open_obligations
    verification_workspace_state["verified"] = True
    verification_workspace_state["verifier_status"] = {
        "status": "pass",
        "reason_codes": [],
        "output_summary": "verification_gate_checked",
    }
    evaluation = _evaluate_finalization_gate(
        workspace_state=verification_workspace_state,
        verified=True,
        recovery_action=None,
    )
    _lock_first_verified_success(workspace_state, evaluation)
    _project_verification_state(workspace_state, evaluation)
    workspace_state["verifier_status"] = {
        "status": "pass" if evaluation["governed_status"] == "governed_pass" else "fail",
        "reason_codes": list(evaluation["reason_codes"]),
        "output_summary": "verification_gate_pass"
        if evaluation["governed_status"] == "governed_pass"
        else "verification_gate_fail",
    }
    if evaluation["governed_status"] == "governed_pass":
        workspace_state["open_obligations"] = open_obligations
    return evaluation["governed_status"] == "governed_pass"


def finalize(
    *,
    execution_result: dict[str, Any],
    recovery_action: dict[str, Any] | None = None,
    workspace_state: dict[str, Any] | None = None,
    verified: bool | None = None,
) -> dict[str, Any]:
    """Produce the governed finalization verdict and evidence bundle."""
    active_workspace_state = workspace_state or _extract_workspace_state(execution_result)
    evaluation = _evaluate_finalization_gate(
        workspace_state=active_workspace_state,
        execution_result=execution_result,
        recovery_action=recovery_action,
        verified=verified,
    )
    _project_verification_state(active_workspace_state, evaluation)
    evidence_bundle = _build_evidence_bundle(
        execution_result=execution_result,
        workspace_state=active_workspace_state,
        evaluation=evaluation,
        recovery_action=recovery_action,
    )
    return {
        "status": evaluation["governed_status"],
        "governed_status": evaluation["governed_status"],
        "final_verdict": evaluation["final_verdict"],
        "reason_codes": list(evaluation["reason_codes"]),
        "gate_status": evaluation["gate_status"],
        "verifier_status": dict(evaluation["verifier_status"]),
        "artifact_status": dict(evaluation["artifact_status"]),
        "provenance_status": dict(evaluation["provenance_status"]),
        "service_status": dict(evaluation["service_status"]),
        "native_tool_status": dict(evaluation["native_tool_status"]),
        "open_obligations": dict(evaluation["open_obligations"]),
        "evidence_bundle": evidence_bundle,
    }


def _evaluate_finalization_gate(
    *,
    workspace_state: dict[str, Any] | None,
    execution_result: dict[str, Any] | None = None,
    recovery_action: dict[str, Any] | None = None,
    verified: bool | None = None,
) -> dict[str, Any]:
    workspace_state = dict(workspace_state or {})
    execution_result = dict(execution_result or {})
    active_state = workspace_state.get("active_kernel_state")
    if not isinstance(active_state, dict):
        active_state = dict(execution_result.get("active_kernel_state", {})) if isinstance(execution_result.get("active_kernel_state"), dict) else {}
    open_obligations = _merge_open_obligations(workspace_state, active_state)
    required_paths = _as_string_list(
        workspace_state.get("required_artifact_paths") or execution_result.get("required_artifact_paths")
    )
    verifier_status = _project_status_dict(
        workspace_state.get("verifier_status") or active_state.get("verifier_status"),
        default_status="not_run",
        output_summary_key="output_summary",
    )
    artifact_status = _project_status_dict(
        workspace_state.get("artifact_status") or active_state.get("artifact_status"),
        default_status="unknown",
        output_summary_key="output_summary",
    )
    provenance_status = _project_status_dict(
        workspace_state.get("provenance_status") or active_state.get("provenance_status"),
        default_status="pass",
        output_summary_key="output_summary",
    )
    service_status = _project_status_dict(
        workspace_state.get("service_status") or active_state.get("service_status"),
        default_status="unknown",
        output_summary_key="output_summary",
    )
    native_tool_state = _project_native_tool_state(
        workspace_state.get("native_tool_status") or active_state.get("native_tool_state") or workspace_state.get("native_tool_state")
    )
    evidence_trail_state = workspace_state.get("evidence_trail_state") or active_state.get("evidence_trail_state")
    success_contract = workspace_state.get("success_contract") or active_state.get("success_contract") or {}
    evidence_trail_requirements = evaluate_evidence_trail_requirements(success_contract, evidence_trail_state)
    if evidence_trail_requirements["status"] == "fail":
        missing_evidence = _as_string_list(evidence_trail_requirements.get("missing_evidence_ids"))
        missing_claims = _as_string_list(evidence_trail_requirements.get("missing_claim_requirements"))
        open_obligations.setdefault(
            "evidence_trail_missing",
            _dedupe_strings([*missing_evidence, *missing_claims]) or ["evidence_trail_missing"],
        )
    layer2_audit_state = normalize_layer2_audit_state(
        active_state.get("layer2_audit_state") or workspace_state.get("layer2_audit_state")
    )

    execution_status = str(workspace_state.get("execution_status") or execution_result.get("status") or "unknown")
    model_claimed_done = bool(workspace_state.get("model_claimed_done"))
    if verified is None:
        verified = bool(workspace_state.get("verified"))
    reason_codes: list[str] = []
    governed_status = "budget_exhausted_open_obligations"

    invalid_environment = (
        bool(workspace_state.get("invalid_environment"))
        or bool(active_state.get("invalid_environment"))
        or bool(open_obligations.get("native_tool_runtime_unavailable"))
        or native_tool_state["status"] == "unavailable"
    )
    if invalid_environment:
        governed_status = "invalid_environment"
        reason_codes.append("invalid_environment")
        if (
            bool(open_obligations.get("native_tool_runtime_unavailable"))
            or native_tool_state["status"] == "unavailable"
        ):
            reason_codes.append("native_tool_runtime_unavailable")
            reason_codes.extend(_as_string_list(native_tool_state.get("reason_codes")))
    elif native_tool_state["status"] == "fail":
        governed_status = "native_tool_contract_failed"
        reason_codes.extend(_as_string_list(native_tool_state.get("reason_codes")))
        reason_codes.append("native_tool_contract_failed")
    elif service_status["status"] in {"not_ready", "failed"} or _as_string_list(open_obligations.get("service_not_ready")):
        governed_status = "service_not_ready"
        reason_codes.extend(_as_string_list(service_status.get("reason_codes")))
        reason_codes.append("service_not_ready")
    elif (
        artifact_status["status"] == "fail"
        or _as_string_list(open_obligations.get("artifact_gate_missing_paths"))
        or _as_string_list(open_obligations.get("artifact_gate_empty_paths"))
    ):
        governed_status = "artifact_gate_failed"
        reason_codes.extend(_as_string_list(artifact_status.get("reason_codes")))
        reason_codes.append("artifact_gate_failed")
    elif provenance_status["status"] == "fail" or _as_string_list(open_obligations.get("report_provenance_missing")):
        governed_status = "provenance_gate_failed"
        reason_codes.extend(_as_string_list(provenance_status.get("reason_codes")))
        reason_codes.append("provenance_gate_failed")
    elif verifier_status["status"] == "fail" or bool(workspace_state.get("verification_failed")):
        governed_status = "verifier_failed"
        reason_codes.extend(_as_string_list(verifier_status.get("reason_codes")))
        reason_codes.append("verifier_failed")
    elif _as_string_list(open_obligations.get("evidence_trail_missing")):
        governed_status = "ungoverned_model_claim" if model_claimed_done or verified else "budget_exhausted_open_obligations"
        reason_codes.extend(_as_string_list(open_obligations.get("evidence_trail_missing")))
        reason_codes.append("evidence_trail_missing")
    elif model_claimed_done and (
        artifact_status["status"] != "pass"
        or verifier_status["status"] != "pass"
        or required_paths and not bool(workspace_state.get("verifier_artifact_present"))
    ):
        governed_status = "ungoverned_model_claim"
        reason_codes.append("ungoverned_model_claim")
        if artifact_status["status"] != "pass":
            reason_codes.append("artifact_gate_failed")
        if verifier_status["status"] != "pass":
            reason_codes.append("verifier_failed")
    elif not model_claimed_done and (open_obligations or execution_status in {"max_steps_exhausted", "error"}):
        governed_status = "budget_exhausted_open_obligations"
        reason_codes.append("budget_exhausted_open_obligations")
    elif "success_contract_missing" in open_obligations:
        governed_status = "ungoverned_model_claim"
        reason_codes.append("success_contract_missing")
    elif bool((workspace_state.get("route_manifest") or {}).get("feature_flags", {}).get("layer2_success_audit")) and (
        layer2_audit_state.get("status") in {"fail", "unclear"}
        or layer2_audit_state.get("verdict") in {"FAIL", "UNCLEAR"}
    ):
        governed_status = "ungoverned_model_claim"
        reason_codes.append("layer2_audit_failed")
        reason_codes.extend(_as_string_list(layer2_audit_state.get("reason_codes")))
    elif (
        verified is True
        and not open_obligations
        and artifact_status["status"] == "pass"
        and provenance_status["status"] == "pass"
        and verifier_status["status"] == "pass"
    ):
        governed_status = "governed_pass"
        reason_codes.append("governed_pass")
    elif (
        model_claimed_done
        and not open_obligations
        and verified is True
        and artifact_status["status"] == "pass"
        and provenance_status["status"] == "pass"
        and verifier_status["status"] == "pass"
    ):
        governed_status = "governed_pass"
        reason_codes.append("governed_pass")
    elif execution_status == "error":
        governed_status = "budget_exhausted_open_obligations"
        reason_codes.append("execution_error")

    verified_success_regression = active_state.get("verified_success_regression") or workspace_state.get("verified_success_regression")
    first_verified_success = active_state.get("first_verified_success") or workspace_state.get("first_verified_success")
    if (
        isinstance(first_verified_success, dict)
        and first_verified_success
        and governed_status != "governed_pass"
        and (
            str(verifier_status.get("status") or "") == "fail"
            or str(artifact_status.get("status") or "") == "fail"
            or (isinstance(verified_success_regression, dict) and verified_success_regression.get("status") == "fail")
        )
    ):
        reason_codes.append("verified_success_overwritten")
        if isinstance(verified_success_regression, dict):
            reason_codes.extend(_as_string_list(verified_success_regression.get("reason_codes")))

    if recovery_action and isinstance(recovery_action, dict):
        recovery_reason = recovery_action.get("reason") or recovery_action.get("reason_code")
        if isinstance(recovery_reason, str) and recovery_reason:
            reason_codes.append(recovery_reason)
        if recovery_action.get("action") == "stop" and governed_status == "budget_exhausted_open_obligations":
            reason_codes.append("same_signature_recovery_exhausted")

    if governed_status == "governed_pass":
        final_verdict = "pass"
    elif governed_status == "invalid_environment":
        final_verdict = "blocked_non_promotable"
    elif governed_status in {
        "artifact_gate_failed",
        "provenance_gate_failed",
        "verifier_failed",
        "native_tool_contract_failed",
        "service_not_ready",
    }:
        final_verdict = "fail"
    elif governed_status == "ungoverned_model_claim":
        final_verdict = "unresolved"
    else:
        final_verdict = "unresolved"

    gate_status = {
        "execution_status": execution_status,
        "model_claimed_done": model_claimed_done,
        "verified": bool(verified),
        "required_artifact_paths": list(required_paths),
        "open_obligations_count": len(open_obligations),
    }
    return {
        "governed_status": governed_status,
        "final_verdict": final_verdict,
        "reason_codes": _dedupe_strings(reason_codes),
        "gate_status": gate_status,
        "verifier_status": verifier_status,
        "artifact_status": artifact_status,
        "provenance_status": provenance_status,
        "service_status": service_status,
        "native_tool_status": native_tool_state,
        "open_obligations": open_obligations,
    }


def _project_verification_state(workspace_state: dict[str, Any], evaluation: dict[str, Any]) -> None:
    active_state = workspace_state.get("active_kernel_state")
    if not isinstance(active_state, dict):
        active_state = {}
    workspace_state["verification_reason_codes"] = list(evaluation["reason_codes"])
    workspace_state["provenance_status"] = dict(evaluation["provenance_status"])
    if isinstance(active_state.get("first_verified_success"), dict):
        workspace_state["first_verified_success"] = dict(active_state["first_verified_success"])
    elif isinstance(workspace_state.get("first_verified_success"), dict):
        active_state["first_verified_success"] = dict(workspace_state["first_verified_success"])
    if isinstance(active_state.get("verified_success_regression"), dict):
        workspace_state["verified_success_regression"] = dict(active_state["verified_success_regression"])
    elif isinstance(workspace_state.get("verified_success_regression"), dict):
        active_state["verified_success_regression"] = dict(workspace_state["verified_success_regression"])
    workspace_state["verification_layer_statuses"] = {
        "L0_inline_assertion": "pass" if workspace_state.get("inline_assertion_pass") else "fail",
        "L1_verifier_artifact": "pass" if workspace_state.get("verifier_artifact_present") else "fail",
        "L2_replay_or_state_grader": "pass" if workspace_state.get("replay_or_state_grader_pass") else "fail",
        "L3_provenance_grounding": "pass" if workspace_state.get("provenance_status", {}).get("status") == "pass" else "fail",
        "L4_final_acceptance": "pass" if evaluation["governed_status"] == "governed_pass" else "fail",
    }
    workspace_state["verification_substitution_violations"] = _dedupe_strings(
        evaluation["reason_codes"]
        + (
            ["verifier_artifact_missing"]
            if evaluation["governed_status"] == "ungoverned_model_claim" and not workspace_state.get("verifier_artifact_present")
            else []
        )
    )
    workspace_state["verification_governed_status"] = evaluation["governed_status"]
    workspace_state["verification_final_verdict"] = evaluation["final_verdict"]
    workspace_state["verified"] = evaluation["governed_status"] == "governed_pass"


def _build_evidence_bundle(
    *,
    execution_result: dict[str, Any],
    workspace_state: dict[str, Any],
    evaluation: dict[str, Any],
    recovery_action: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "execution_status": workspace_state.get("execution_status") or execution_result.get("status"),
        "governed_status": evaluation["governed_status"],
        "final_verdict": evaluation["final_verdict"],
        "reason_codes": list(evaluation["reason_codes"]),
        "open_obligations": dict(evaluation["open_obligations"]),
        "verifier_status": dict(evaluation["verifier_status"]),
        "artifact_status": dict(evaluation["artifact_status"]),
        "service_status": dict(evaluation["service_status"]),
        "native_tool_status": dict(evaluation["native_tool_status"]),
        "recovery_action": dict(recovery_action or {}),
        "required_artifact_paths": list(_as_string_list(workspace_state.get("required_artifact_paths"))),
        "active_kernel_state": dict(workspace_state.get("active_kernel_state", {}))
        if isinstance(workspace_state.get("active_kernel_state"), dict)
        else {},
        "first_verified_success": dict(workspace_state.get("first_verified_success", {}))
        if isinstance(workspace_state.get("first_verified_success"), dict)
        else {},
        "verified_success_regression": dict(workspace_state.get("verified_success_regression", {}))
        if isinstance(workspace_state.get("verified_success_regression"), dict)
        else {},
        "control_plane_state": dict(workspace_state.get("control_plane_state", {}))
        if isinstance(workspace_state.get("control_plane_state"), dict)
        else {},
        "control_plane_working_window": dict(workspace_state.get("control_plane_working_window", {}))
        if isinstance(workspace_state.get("control_plane_working_window"), dict)
        else {},
    }


def _extract_workspace_state(execution_result: dict[str, Any]) -> dict[str, Any]:
    workspace_state = execution_result.get("workspace_state")
    if isinstance(workspace_state, dict):
        return dict(workspace_state)
    active_kernel_state = execution_result.get("active_kernel_state")
    if isinstance(active_kernel_state, dict):
        state_workspace = active_kernel_state.get("workspace_state")
        if isinstance(state_workspace, dict):
            return dict(state_workspace)
    return {}


def _merge_open_obligations(workspace_state: dict[str, Any], active_state: dict[str, Any]) -> dict[str, Any]:
    obligations: dict[str, Any] = {}
    for source in (
        workspace_state.get("open_obligations"),
        active_state.get("open_obligations"),
        workspace_state.get("verification_open_obligations"),
    ):
        if isinstance(source, dict):
            obligations.update(source)
    missing_paths = _as_string_list(
        workspace_state.get("artifact_gate_missing_paths")
        or active_state.get("artifact_gate_missing_paths")
    )
    if missing_paths:
        obligations.setdefault("artifact_gate_missing_paths", missing_paths)
    empty_paths = _as_string_list(
        workspace_state.get("artifact_gate_empty_paths")
        or active_state.get("artifact_gate_empty_paths")
    )
    if empty_paths:
        obligations.setdefault("artifact_gate_empty_paths", empty_paths)
    service_not_ready = _as_string_list(workspace_state.get("service_not_ready") or active_state.get("service_not_ready"))
    if service_not_ready:
        obligations.setdefault("service_not_ready", service_not_ready)
    process_not_running = _as_string_list(
        workspace_state.get("process_not_running") or active_state.get("process_not_running")
    )
    if process_not_running:
        obligations.setdefault("process_not_running", process_not_running)
    tool_violations = _as_string_list(
        workspace_state.get("tool_contract_violations") or active_state.get("tool_contract_violations")
    )
    if tool_violations:
        obligations.setdefault("tool_contract_violations", tool_violations)
    if workspace_state.get("same_signature_recovery_exhausted"):
        obligations.setdefault(
            "same_signature_recovery_exhausted",
            workspace_state.get("same_signature_recovery_exhausted"),
        )
    if active_state.get("same_signature_recovery_exhausted"):
        obligations.setdefault(
            "same_signature_recovery_exhausted",
            active_state.get("same_signature_recovery_exhausted"),
        )
    return obligations


def _project_status_dict(value: Any, *, default_status: str, output_summary_key: str) -> dict[str, Any]:
    if isinstance(value, dict):
        status = value.get("status")
        if not isinstance(status, str) or not status:
            status = default_status
        reason_codes = _as_string_list(value.get("reason_codes"))
        output_summary = value.get(output_summary_key)
        if not isinstance(output_summary, str):
            output_summary = ""
        return {"status": status, "reason_codes": reason_codes, output_summary_key: output_summary}
    return {"status": default_status, "reason_codes": [], output_summary_key: ""}


def _project_native_tool_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"status": "shell_only", "reason_codes": [], "output_summary": ""}
    projected_status = str(value.get("status") or "")
    if projected_status in {"fail", "unavailable", "not_run", "pass", "shell_only"}:
        return {
            "status": projected_status,
            "reason_codes": _as_string_list(value.get("reason_codes")),
            "output_summary": str(value.get("output_summary") or ""),
        }
    runtime_status = str(value.get("runtime_status") or "native_tool_runtime_unknown")
    contract_status = str(value.get("contract_status") or "not_run")
    attempted = bool(value.get("attempted_native_tool_call"))
    reason_codes = _as_string_list(value.get("violation_receipt_ids"))
    if contract_status == "fail" or reason_codes:
        return {
            "status": "fail",
            "reason_codes": reason_codes or ["native_tool_contract_failed"],
            "output_summary": f"contract_status={contract_status}",
        }
    if runtime_status == "native_tool_runtime_unavailable":
        return {
            "status": "unavailable",
            "reason_codes": ["native_tool_runtime_unavailable"],
            "output_summary": runtime_status,
        }
    if value.get("mode") == "native":
        return {
            "status": "not_run" if not attempted else "pass",
            "reason_codes": [] if attempted else ["native_tool_runtime_not_probed"],
            "output_summary": runtime_status,
        }
    return {"status": "shell_only", "reason_codes": [], "output_summary": runtime_status}


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _dedupe_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
