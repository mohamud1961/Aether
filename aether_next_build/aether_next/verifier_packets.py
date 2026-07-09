"""Evidence packet construction for model-led verification."""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from .runtime_ir import stable_json

from .ledger import ExecutionLedger
from .runtime_ir import CompiledRuntime


def _merged_config_realization(compiled: CompiledRuntime, ledger: ExecutionLedger) -> dict[str, Any]:
    realization = dict(compiled.config_realization)
    latest = ledger.latest_receipt("config_realization")
    if latest is not None:
        payload = latest.payload.get("config_realization", {})
        if isinstance(payload, dict):
            realization.update(payload)
    return realization


def _local_verification_limits(compiled: CompiledRuntime, realization: dict[str, Any]) -> list[dict[str, str]]:
    structured = realization.get("local_verification_limits")
    if isinstance(structured, list):
        normalized: list[dict[str, str]] = []
        for item in structured:
            if not isinstance(item, dict):
                continue
            statement = str(item.get("statement", "")).strip()
            if not statement:
                continue
            normalized.append({
                "source": str(item.get("source", "runtime_config")).strip() or "runtime_config",
                "statement": statement,
            })
        if normalized:
            return normalized
    return [
        {"source": "runtime_config", "statement": item}
        for item in compiled.local_verification_limits
        if str(item).strip()
    ]


def _config_realization_summary(realization: dict[str, Any]) -> dict[str, Any]:
    context_policy = realization.get("configured_context_policy")
    if not isinstance(context_policy, dict):
        context_policy = {
            "mode": realization.get("context_policy_mode", ""),
            "include_sections": realization.get("context_sections_declared", []),
            "compression_trigger_ratio": realization.get("context_compression_ratio"),
        }
    verification_policy = realization.get("configured_verification_policy")
    if not isinstance(verification_policy, dict):
        verification_policy = {
            "check_plan_ids": realization.get("checks_compiled", []),
        }
    verification_authority = realization.get("verification_authority")
    if isinstance(verification_authority, dict):
        official_grader = str(verification_authority.get("official_grader", "")).strip()
        if official_grader and "official_grader_authority" not in verification_policy:
            verification_policy = dict(verification_policy)
            verification_policy["official_grader_authority"] = official_grader

    summary = {
        "architect_path": realization.get("architect_path", ""),
        "tools_visible_to_solver": realization.get("tools_visible_to_solver", []),
        "tools_runtime_allowed": realization.get("tools_runtime_allowed", []),
        "context_policy": context_policy,
        "verification_policy": verification_policy,
    }
    optional_keys = (
        "harness_config_schema_version",
        "harness_config_realization_audit",
        "workbench_repair_warning_codes",
        "workbench_repair_warnings",
        "workbench_rejected_config_items",
        "verification_authority",
    )
    for key in optional_keys:
        if key in realization:
            summary[key] = realization[key]
    return summary


def _raw_state_candidates(realization: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    raw = realization.get("verifier_raw_state_candidates", ())
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        rows.append({
            "path": path,
            "source": str(item.get("source", "config_realization")).strip() or "config_realization",
            "authority": "candidate_only",
        })
    return rows[:8]


def _solver_reported_blockers(ledger: ExecutionLedger, *, limit: int = 6) -> list[dict[str, Any]]:
    """Blocker escalations the solver filed via the report_blocker action.

    report_blocker is the solver's only configuration signal and is
    deliberately routed to the verifier: an escalation request to judge,
    never proof that a blocker is real.
    """
    rows: list[dict[str, Any]] = []
    for receipt in ledger.all_receipts():
        if receipt.kind != "report_blocker":
            continue
        payload = receipt.payload or {}
        rows.append({
            "receipt_id": receipt.receipt_id,
            "step": receipt.step,
            "authority": "escalation_request_only",
            "blocked_component": str(payload.get("blocked_component", "")),
            "observed_evidence": str(payload.get("observed_evidence", ""))[:2000],
            "attempted_actions": str(payload.get("attempted_actions", ""))[:2000],
            "why_current_tools_or_config_prevent_progress": str(
                payload.get("why_current_tools_or_config_prevent_progress", "")
            )[:2000],
            "requested_harness_change": str(payload.get("requested_harness_change", ""))[:1000],
        })
    return rows[-max(0, limit):]


def build_verifier_packet(compiled: CompiledRuntime, ledger: ExecutionLedger, *, step: int, reason: str) -> dict[str, Any]:
    """Build a state-only verifier packet.

    The solver's submit_outcome is only a trigger.  This packet deliberately
    excludes solver journey/history: no solver claims, submit summaries,
    command history, local checks, memory/no-progress analyses, or proof
    contract outputs.  Solver history remains in traces/audit only.  The
    verifier receives the task, architect-authored contract, active verifier
    findings, and handles/candidates for independently inspecting current
    frozen state.
    """
    realization = _merged_config_realization(compiled, ledger)
    verification_authority = realization.get("verification_authority", {})
    official_grader_authority = ""
    if isinstance(verification_authority, dict):
        official_grader_authority = str(verification_authority.get("official_grader", "")).strip()

    state_handles: list[dict[str, Any]] = []
    recent_command_receipts: list[dict[str, Any]] = []
    for receipt in ledger.all_receipts():
        payload = receipt.payload or {}
        if payload.get("file_handle"):
            state_handles.append({
                "kind": "file",
                "handle": payload.get("file_handle"),
                "path": payload.get("path", ""),
                "bytes": payload.get("bytes"),
                "content_hash": payload.get("content_hash", ""),
            })
        for key, stream in (("stdout_handle", "stdout"), ("stderr_handle", "stderr")):
            if payload.get(key):
                state_handles.append({
                    "kind": "output",
                    "handle": payload.get(key),
                    "stream": stream,
                    "bytes": payload.get(f"{stream}_bytes", 0),
                })
        if receipt.kind == "run_command":
            recent_command_receipts.append({
                "receipt_id": receipt.receipt_id,
                "step": receipt.step,
                "command": str(payload.get("command", "")).strip(),
                "exit_code": payload.get("exit_code"),
                "stdout_handle": payload.get("stdout_handle", ""),
                "stderr_handle": payload.get("stderr_handle", ""),
                "authority": "audit_trail_only",
            })

    packet = {
        "reason": reason,
        "step": step,
        "task_prompt": compiled.task_prompt,
        "objective_graph": compiled.objective_graph.summary(),
        "success_definition": compiled.success_definition or realization.get("success_definition", ""),
        "architect_verifier_prompt": {
            "rendered": compiled.verifier_identity_prompt or str(realization.get("verifier_identity_prompt", "")),
            "summary": str(realization.get("verifier_system_prompt_summary", "")).strip(),
            "hash": str(realization.get("verifier_prompt_hash", "")).strip(),
        },
        "evidence_requirements": list(compiled.evidence_requirements) or list(realization.get("evidence_requirements", []) or []),
        "false_positive_risks": list(compiled.false_positive_risks) or list(realization.get("false_positive_risks", []) or []),
        "minimum_completion_evidence": list(compiled.minimum_completion_evidence) or list(realization.get("minimum_completion_evidence", []) or []),
        "re_derivable_claims": list(compiled.re_derivable_claims) or list(realization.get("re_derivable_claims", []) or []),
        "local_verification_limits": _local_verification_limits(compiled, realization),
        "config_realization": _config_realization_summary(realization),
        "official_grader_authority": official_grader_authority,
        "artifacts_present": sorted(ledger.current_artifacts()),
        "raw_state_candidates": _raw_state_candidates(realization),
        "state_inspection_handles": state_handles[-32:],
        "recent_command_receipts": recent_command_receipts[-8:],
        "open_obligations": [item.as_dict() for item in ledger.open_obligations()],
        "active_findings": ledger.active_finding_context(step),
        "solver_reported_blockers": _solver_reported_blockers(ledger),
    }
    forbidden = {
        "solver_claim",
        "submit_summary",
        "privileged_solver_proof",
        "solver_proof",
        "proof_contract",
        "proof_contract_analysis",
        "solver_authored_evidence",
        "recent_actions",
        "recent_receipts",
        "latest_file_reads",
        "command_results",
        "memory_loop_feedback",
        "automatic_memory_findings",
        "no_progress_controls",
        "artifact_history",
        "memory_events",
        "observations",
        "solver_system_prompt",
    }
    leaked = forbidden.intersection(packet)
    if leaked:
        raise AssertionError(f"verifier packet leaked solver journey fields: {sorted(leaked)}")
    return packet


def packet_state_signature(packet: Mapping[str, Any]) -> str:
    """Stable signature of the packet's MATERIAL state.

    Volatile bookkeeping (step counters, finding ages, handle ids embedding
    step numbers) is excluded: two packets with the same signature describe
    the same world, so re-judging the second is pure waste.
    """
    handles = []
    for handle in packet.get("state_inspection_handles") or ():
        if isinstance(handle, Mapping):
            handles.append({
                "kind": handle.get("kind"),
                "path": handle.get("path", ""),
                "stream": handle.get("stream", ""),
                "bytes": handle.get("bytes"),
                "content_hash": handle.get("content_hash", ""),
            })
    material = {
        "artifacts": sorted(str(a) for a in (packet.get("artifacts_present") or ())),
        "handles": handles,
        "obligations": sorted(
            str(o.get("obligation_id", "")) for o in (packet.get("open_obligations") or ())
            if isinstance(o, Mapping)
        ),
        "findings": sorted(
            str(f.get("finding_id", "")) for f in (packet.get("active_findings") or ())
            if isinstance(f, Mapping)
        ),
        "blockers": [
            {
                "component": b.get("blocked_component", ""),
                "evidence": b.get("observed_evidence", ""),
            }
            for b in (packet.get("solver_reported_blockers") or ())
            if isinstance(b, Mapping)
        ],
        "verifier_prompt_hash": str(
            (packet.get("architect_verifier_prompt") or {}).get("hash", "")
        ),
    }
    return sha256(stable_json(material).encode("utf-8")).hexdigest()[:16]
