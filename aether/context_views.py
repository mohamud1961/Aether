"""Receipt/section view builders for the solver context packet.

Extracted from context_compiler.py to honor the 500-LOC module cap.  Pure
functions over the ledger; no compiler state.
"""
from __future__ import annotations

import json
from typing import Any

from .attention_projection import project_command_stream_for_attention
from .ledger import ExecutionLedger, Receipt
from .memory_events import artifact_history

_TOOL_RESULT_KINDS = frozenset({
    "read_file",
    "write_file",
    "run_command",
    "bootstrap",
    "process_launch",
    "service_probe",
    "job_probe",
    "process_stop",
    "artifact_inspection",
    "query_artifact_history",
    "inspect_diff",
    "experiment",
    "terminal_start",
    "terminal_send",
    "terminal_read",
    "terminal_wait",
    "terminal_interrupt",
    "terminal_close",
    "environment_extension",
})


_RECENT_RECIPE_SELECTORS = frozenset({
    "recent_progress",
    "tool_results",
    "file_reads",
    "file_writes",
    "command_results",
    "check_results",
    "verifier_results",
    "artifact_history",
})


_STANDARD_SECTION_KEYS = (
    "open_obligations",
    "obligation_status",
    "monitor_alerts",
    "live_processes",
    "recent_progress",
    "failure_clusters",
    "artifacts_present",
    "candidate_leaderboard",
    "installed_capabilities",
    "planned_checks",
    "tool_results",
    "command_results",
)

# Exact section names accepted by ContextPolicy.include_sections.  This is a
# distinct contract from recipe selectors: recipe selectors can address
# additional dynamically derived views, while top-level sections must already
# exist in the base context packet.
TOP_LEVEL_CONTEXT_SECTION_SELECTORS = frozenset({
    "open_obligations",
    "obligation_status",
    "monitor_alerts",
    "live_processes",
    "recent_progress",
    "failure_clusters",
    "artifacts_present",
    "candidate_leaderboard",
    "installed_capabilities",
    "planned_checks",
    "pending_checks",
    "command_results",
})

_SUPPORTED_EXACT_RECIPE_SELECTORS = frozenset({
    *_STANDARD_SECTION_KEYS,
    "pending_checks",
    "active_completion_findings",
    "repeated_actions",
    "repeat_efficiency_guidance",
    "files_already_read",
    "latest_file_reads",
    "no_progress_controls",
    "action_constraints",
    "submission_recovery_directive",
    "stuck",
    "artifact_history",
    "memory_events",
    "latest_failure",
    "failed_checks",
})


def item_count(value: Any) -> int:
    if isinstance(value, (list, tuple, dict, set)):
        return len(value)
    if value in (None, "", False):
        return 0
    return 1


def recent_receipts(selector: str, ledger: ExecutionLedger, count: int) -> list[Receipt]:
    receipts = list(ledger.all_receipts())
    if selector == "recent_progress":
        matches = [
            receipt
            for receipt in receipts
            if receipt.state_change
            or (receipt.kind == "check_result" and receipt.success)
            or (receipt.kind == "schema_validation" and receipt.success)
            or (receipt.kind == "job_probe" and receipt.success)
        ]
    elif selector == "tool_results":
        matches = [receipt for receipt in receipts if receipt.kind in _TOOL_RESULT_KINDS]
    elif selector == "file_reads":
        matches = [receipt for receipt in receipts if receipt.kind == "read_file"]
    elif selector == "file_writes":
        matches = [receipt for receipt in receipts if receipt.kind == "write_file"]
    elif selector == "command_results":
        matches = [receipt for receipt in receipts if receipt.kind == "run_command"]
    elif selector == "check_results":
        matches = [receipt for receipt in receipts if receipt.kind == "check_result"]
    elif selector == "verifier_results":
        matches = [receipt for receipt in receipts if receipt.kind == "model_verifier_result"]
    elif selector == "artifact_history":
        matches = [receipt for receipt in receipts if artifact_history((receipt,), limit=1)]
    else:
        matches = []
    return matches[-count:]

def last_failures(ledger: ExecutionLedger, count: int) -> list[Receipt]:
    failures = [receipt for receipt in ledger.all_receipts() if not receipt.success]
    # A progress assessment is a derived classification of the same turn, not
    # the causal failure the Solver must repair. When a concrete failure exists
    # at that step, keep the concrete receipt and suppress only its same-step
    # diagnostic wrapper. Standalone later progress failures remain visible.
    causal_failure_steps = {
        receipt.step
        for receipt in failures
        if receipt.kind != "solver_progress_assessment"
    }
    selected = [
        receipt
        for receipt in failures
        if not (
            receipt.kind == "solver_progress_assessment"
            and receipt.step in causal_failure_steps
        )
    ]
    return selected[-count:]

def latest_tool_receipt(ledger: ExecutionLedger) -> dict[str, Any] | None:
    tool_kinds = {"read_file", "write_file", "run_command", "check_result", "schema_validation", "service_probe", "job_probe", "environment_extension"}
    for receipt in reversed(ledger.all_receipts()):
        if receipt.kind in tool_kinds:
            row = {
                "receipt_id": receipt.receipt_id,
                "step": receipt.step,
                "kind": receipt.kind,
                "success": receipt.success,
                "summary": receipt.summary,
                "failure_class": receipt.failure_class,
            }
            if receipt.kind == "job_probe":
                for key in (
                    "job_id", "job_status", "completed", "job_succeeded",
                    "process_generation", "process_generation_verified",
                    "lifecycle_authority",
                ):
                    value = (receipt.payload or {}).get(key)
                    if value not in (None, "", (), [], {}):
                        row[key] = value
            return row
    return None

def latest_solver_transition(ledger: ExecutionLedger) -> dict[str, Any] | None:
    """Return the latest model-authored decision paired with its real results.

    This is the causal observation boundary for the next Solver turn. It does
    not choose an action or interpret task semantics. It preserves the model's
    own compact commitment and the exact receipts produced by that one action,
    even when historical result sections are externalized.
    """
    receipts = list(ledger.all_receipts())
    decision: Receipt | None = None
    for receipt in reversed(receipts):
        if receipt.kind == "solver_decision_state":
            decision = receipt
            break
    if decision is None:
        return None
    payload = decision.payload if isinstance(decision.payload, dict) else {}
    action_id = str(payload.get("action_id", "")).strip()
    progress: Receipt | None = None
    for receipt in reversed(receipts):
        if receipt.step < decision.step:
            break
        if receipt.kind != "solver_progress_assessment":
            continue
        progress_payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        if receipt.step == decision.step and str(progress_payload.get("action_id", "")).strip() == action_id:
            progress = receipt
            break
    result_ids: list[str] = []
    if progress is not None and isinstance(progress.payload, dict):
        result_ids = [
            str(value) for value in progress.payload.get("result_receipt_ids", ())
            if str(value).strip()
        ]
    by_id = {receipt.receipt_id: receipt for receipt in receipts}
    results = [receipt_inline_view(by_id[receipt_id]) for receipt_id in result_ids if receipt_id in by_id]
    decision_row = {
        "receipt_id": decision.receipt_id,
        "step": decision.step,
        "current_subgoal": str(payload.get("current_subgoal", decision.summary)),
        "evidence_gap": str(payload.get("evidence_gap", "")),
        "action_id": action_id,
        "action_kind": str(payload.get("action_kind", "")),
        "intent": str(payload.get("intent", "")),
        "previous_model_expectation": str(payload.get("expected_observation", "")),
        "previous_model_contingency": str(payload.get("if_fail_next", "")),
        "mutation_generation": payload.get("mutation_generation"),
    }
    transition: dict[str, Any] = {
        "decision": decision_row,
        "results": results,
        "result_receipt_ids": result_ids,
        "observation_boundary": {
            "previous_decision_source": "model_authored",
            "result_source": "execution_receipts",
            "previous_expectation_is_nonbinding": True,
            "previous_contingency_is_nonbinding": True,
            "interpretation_authority": "solver",
        },
    }
    if progress is not None:
        progress_payload = progress.payload if isinstance(progress.payload, dict) else {}
        transition["mechanical_outcome"] = {
            "receipt_id": progress.receipt_id,
            "classification": str(progress_payload.get("classification", "")),
            "result_count": progress_payload.get("result_count"),
            "successful_result_count": progress_payload.get("successful_result_count"),
            "failed_result_count": progress_payload.get("failed_result_count"),
            "state_change_count": progress_payload.get("state_change_count"),
            "new_evidence_count": progress_payload.get("new_evidence_count"),
            "verification_count": progress_payload.get("verification_count"),
            "progress_signals": list(progress_payload.get("progress_signals", ())),
            "equivalent_repeat": bool(progress_payload.get("equivalent_repeat", False)),
            "no_relevant_progress": bool(progress_payload.get("no_relevant_progress", False)),
            "dispatch_performed": bool(progress_payload.get("dispatch_performed", False)),
            "interpretation_authority": "solver",
        }
    return transition

def submission_observation_routes(
    ledger: ExecutionLedger,
    *,
    progress_receipt_id: str,
) -> list[dict[str, Any]]:
    """Return exact direct-observation routes for the latest mutated result.

    These are control-plane affordances, not task-strategy recommendations.
    Only already-existing stdout/stderr handles from the result receipts bound
    to the cited solver_progress_assessment are exposed.  The Solver remains
    free to choose another genuine observation of current state.
    """
    progress = next(
        (r for r in ledger.all_receipts() if r.receipt_id == progress_receipt_id),
        None,
    )
    if progress is None or progress.kind != "solver_progress_assessment":
        return []
    payload = progress.payload if isinstance(progress.payload, dict) else {}
    result_ids = {
        str(value).strip()
        for value in payload.get("result_receipt_ids", ())
        if str(value).strip()
    }
    if not result_ids:
        return []
    routes: list[dict[str, Any]] = []
    for receipt in ledger.all_receipts():
        if receipt.receipt_id not in result_ids:
            continue
        result_payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        for stream in ("stdout", "stderr"):
            handle = str(result_payload.get(f"{stream}_handle", "")).strip()
            try:
                byte_count = int(result_payload.get(f"{stream}_bytes", 0) or 0)
            except (TypeError, ValueError):
                byte_count = 0
            if not handle or byte_count <= 0:
                continue
            routes.append({
                "kind": "read_output",
                "arguments": {"handle": handle},
                "source_receipt_id": receipt.receipt_id,
                "stream": stream,
                "bytes": byte_count,
                "authority": "existing_execution_result_handle",
            })
    return routes


def _compact_text(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    half = max(1, (limit - 80) // 2)
    return f"{text[:half]}\n... [truncated {len(text) - (2 * half)} chars] ...\n{text[-half:]}"


def _compact_text_with_retrieval(value: Any, receipt_id: str, limit: int = 4000) -> str:
    """Compact inline while naming the exact handle that restores every byte."""
    marker = f"... [truncated {{}} chars; exact output retrievable via read_output receipt_id={receipt_id}] ..."
    text = str(value or "")
    if len(text) <= limit:
        return text
    reserved = len(marker.format(0)) + 2
    half = max(1, (limit - reserved) // 2)
    return (
        f"{text[:half]}\n{marker.format(len(text) - (2 * half))}\n{text[-half:]}"
    )


def receipt_inline_view(receipt: Receipt) -> dict[str, Any]:
    row: dict[str, Any] = {
        "receipt_id": receipt.receipt_id,
        "step": receipt.step,
        "kind": receipt.kind,
        "success": receipt.success,
        "summary": receipt.summary,
    }
    if receipt.failure_class:
        row["failure_class"] = receipt.failure_class
    payload = receipt.payload
    for key in (
        "path", "command", "check_id", "exit_code", "bytes", "query", "detail",
        "blocker_code", "stdout_handle", "stderr_handle", "file_handle", "offset", "span",
        "target", "service_name", "live", "fresh", "process_id", "interactive",
        "mode", "media_type", "extraction_route", "extraction_authority",
        "content_hash", "sha256", "owner", "permissions", "file_type", "status",
        "job_id", "job_status", "completed", "job_succeeded", "process_generation",
        "process_generation_verified", "lifecycle_authority", "lifecycle_launch_receipt_id",
        "session_id", "cursor", "total_bytes", "bytes_read", "more_available",
        "bytes_sent", "signal",
        "server", "operation", "tool_name", "transport", "mutation_semantics",
        "state_change_basis", "bridge_provenance",
    ):
        value = payload.get(key)
        if value not in (None, "", (), [], {}):
            row[key] = value
    if receipt.kind in {"read_file", "write_file"} and payload.get("excerpt"):
        row["excerpt"] = _compact_text_with_retrieval(payload["excerpt"], receipt.receipt_id, 4000)
    if receipt.kind == "artifact_inspection":
        extracted = payload.get("extracted_text") or payload.get("transcription") or payload.get("description")
        if extracted:
            row["extracted_text"] = _compact_text_with_retrieval(extracted, receipt.receipt_id, 4000)
        metadata = payload.get("metadata")
        if isinstance(metadata, dict) and metadata:
            row["metadata"] = {k: v for k, v in metadata.items() if v not in (None, "", (), [], {})}
    if receipt.kind == "run_command":
        stdout = project_command_stream_for_attention(payload, "stdout")
        stderr = project_command_stream_for_attention(payload, "stderr")
        if stdout:
            row["stdout"] = stdout
        if stderr:
            row["stderr"] = stderr
    if receipt.kind == "environment_extension" and "result" in payload:
        # The next Primary decision must see the MCP observation it just
        # requested. Keep small structured results intact. Large/binary-heavy
        # results remain exact in the receipt and are exposed by receipt handle
        # instead of becoming an unbounded hot-context dump.
        result_json = json.dumps(
            payload.get("result"), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, default=str,
        )
        row["result_utf8_bytes"] = len(result_json.encode("utf-8"))
        row["result_receipt_handle"] = f"receipt:{receipt.receipt_id}"
        if len(result_json) <= 6000:
            row["result"] = payload.get("result")
        else:
            row["result_excerpt"] = _compact_text(result_json, 6000)
            row["full_result_available_by_receipt_handle"] = True
    if receipt.kind == "terminal_read":
        output = str(payload.get("output", ""))
        if output:
            # A terminal read is itself the observation action.  The next model
            # turn must see the bytes it just requested without requiring a
            # second read_output hop.  Keep the immediate view bounded while
            # exact receipt retrieval remains available for larger output.
            row["output"] = _compact_text(output, 4000)
    if receipt.kind in {"read_output", "grep_output", "read_file_page"}:
        chunk = str(payload.get("chunk", ""))
        if chunk:
            row["chunk"] = chunk
    if receipt.kind == "no_progress_control":
        for key in ("consequence", "target", "action_family", "repeat_count"):
            value = payload.get(key)
            if value not in (None, "", (), [], {}):
                row[key] = value
    if receipt.kind == "submission_coherence_blocked":
        for key in (
            "reason_code", "detail", "latest_progress_receipt_id",
            "latest_progress_classification", "progress_signals", "blocked_round",
        ):
            value = payload.get(key)
            if value not in (None, "", (), [], {}):
                row[key] = value
    return row

def latest_file_reads(ledger: ExecutionLedger, limit: int = 3) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for receipt in ledger.all_receipts():
        if receipt.kind != "read_file" or not receipt.success:
            continue
        payload = receipt.payload or {}
        row = {
            "receipt_id": receipt.receipt_id,
            "step": receipt.step,
            "path": payload.get("path", ""),
            "content_hash": payload.get("content_hash", ""),
            "bytes": payload.get("bytes", 0),
            "excerpt": payload.get("excerpt", ""),
        }
        rows.append({k: v for k, v in row.items() if v not in (None, "", (), [], {})})
    return rows[-max(0, limit):]

def action_constraints_from_no_progress(no_progress_controls: list[dict[str, Any]]) -> dict[str, Any]:
    latest = no_progress_controls[-1]
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
    target = str(payload.get("target", latest.get("target", ""))).strip()
    consequence = str(payload.get("consequence", latest.get("consequence", ""))).strip()
    action_family = payload.get("action_family", latest.get("action_family", "evidence_display_command"))
    return {
        "source": "no_progress_control",
        "consequence": consequence or "soft_block",
        "blocked_action_family": action_family,
        "blocked_target": target,
        "do_not_repeat": [
            {
                "action_family": action_family,
                "target": target,
            }
        ],
        "allowed_next_action_families": [
            "repair_or_write_artifact",
            "execute_or_semantically_validate_artifact",
            "inspect_new_target",
            "declare_concrete_blocker",
        ],
        "message": (
            "The runtime did not execute the repeated unchanged evidence action. The next action must repair "
            "or semantically validate the artifact, inspect a different target, justify a changed-state repeat, "
            "or declare a concrete blocker."
        ),
    }

def maybe_compress(packet: dict[str, Any], policy: Any) -> dict[str, Any]:
    budget = int(policy.model_context_window_tokens * policy.compression_trigger_ratio)
    estimated_tokens = max(1, len(json.dumps(packet, sort_keys=True, default=str)) // 4)
    if estimated_tokens <= budget:
        return packet
    compressed = dict(packet)
    preserved_exact = {"active_completion_findings", "pending_checks", "repeat_efficiency_guidance", "no_progress_controls", "action_constraints", "submission_recovery_directive", "stuck", "tool_results", "command_results", "latest_file_reads", "solver_parse_errors", "blocked_denied_receipts", "output_handles", "latest_solver_transition"}
    recipe = getattr(policy, "recipe", None)
    if recipe is not None:
        preserved_exact.update(str(item) for item in recipe.preserve_exact)
    for key in ("recent_progress", "failure_clusters", "candidate_leaderboard"):
        if key in preserved_exact:
            continue
        if isinstance(compressed.get(key), list):
            original = compressed[key]
            compressed[key] = original[-3:]
            compressed[f"{key}_compressed"] = {"original_count": len(original), "kept_last": len(compressed[key])}
    compressed["context_compression"] = {
        "triggered": True,
        "estimated_tokens_before": estimated_tokens,
        "budget_tokens": budget,
        "threshold_ratio": policy.compression_trigger_ratio,
        "preserved_exact": sorted(preserved_exact),
    }
    return compressed
