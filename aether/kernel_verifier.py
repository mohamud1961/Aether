"""Optional model-verifier gate integration for the kernel."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import threading
import time
from typing import Any, Mapping

from .ledger import ExecutionLedger, Receipt
from .inspection_registry import register_inspection_results
from .runtime_ir import CompiledRuntime
from .verifier import ModelVerifierResult, classify_verifier_outcome, parse_model_verifier_result
from .verifier_inspector import (
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
)
from .verifier_overlay import VerifierOverlay
from .verifier_packets import build_verifier_packet, packet_state_signature
from .run_cancellation import RunCancellationRequested
from .verifier_recovery import VerifierRecoveryAction, VerifierRecoveryRouter
from .verifier_generation import (
    GenerationBoundLedger, VerifierGeneration, VerifierGenerationExpired,
)
from .verifier_deadline import verifier_generation_deadline
from .verifier_budget import (
    PRODUCTION_VERIFIER_CALL_TIMEOUT_S,
    PRODUCTION_VERIFIER_PHASE_BUDGET,
    PRODUCTION_VERIFIER_WALL_CLOCK_BUDGET_S,
)



def _task_agent_timeout_s(envmap: Any | None) -> float | None:
    """Return the task-declared outer agent clock, if one exists.

    The internal Verifier must never invent an earlier cognition deadline.
    Harbor's outer agent timeout remains the actual run authority; this value
    is only a non-earlier generation quarantine envelope for late worker state.
    """
    if envmap is None:
        return None
    metadata = getattr(envmap, "task_metadata", {}) or {}
    budget = metadata.get("resource_budget") if isinstance(metadata.get("resource_budget"), dict) else {}
    for source in (budget, metadata):
        value = source.get("agent_timeout_sec") if isinstance(source, dict) else None
        try:
            if value is not None and float(value) > 0:
                return float(value)
        except (TypeError, ValueError):
            pass
    return None

def _verifier_command_budget_s(envmap: Any) -> int:
    """Task-declared verifier budget bounds overlay command execution."""
    metadata = getattr(envmap, "task_metadata", {}) or {}
    budget = metadata.get("resource_budget") if isinstance(metadata.get("resource_budget"), dict) else {}
    for source in (budget, metadata):
        value = source.get("verifier_timeout_sec") if isinstance(source, dict) else None
        try:
            if value is not None and float(value) > 0:
                return int(float(value))
        except (TypeError, ValueError):
            pass
    return 300


_REASON_ALIASES = {
    "solver_submit_success_candidate": "solver_submit",
    "finish_intent": "solver_submit",
    "deterministic_success_candidate": "deterministic_success_candidate",
    "deterministic_failure": "deterministic_failure",
    "max_steps": "deterministic_failure",
    "no_progress": "deterministic_failure",
    "blocked_by_harness_config": "deterministic_failure",
    "uncertain_missing_evidence": "deterministic_failure",
}


def _model_verifier_failure_class(exc: Exception) -> str:
    """Classify a caught verifier-call failure without judging task semantics."""
    if isinstance(exc, TimeoutError):
        return "verifier_model_timeout"
    name = type(exc).__name__
    message = str(exc)
    if name in {"AzureProviderOutputError", "AzureModelError"}:
        return "verifier_provider_invalid"
    if name == "ModelOutputError":
        if message in {
            "verifier exceeded bounded inspection rounds without returning a verdict",
            "verifier requested inspection after the final synthesis turn",
        }:
            return "verifier_protocol_round_exhaustion"
        return "verifier_protocol_invalid"
    if isinstance(exc, ValueError):
        return "verifier_protocol_invalid"
    return "verifier_runtime_failure"



def _inspection_evidence_summary(receipts: tuple[Receipt, ...]) -> dict[str, Any]:
    """Summarise verifier-side inspection evidence for audit/result rows."""
    inspection_receipts = [receipt for receipt in receipts if receipt.kind == "model_verifier_inspection"]
    tools: list[str] = []
    inspected_items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for receipt in inspection_receipts:
        payload = receipt.payload or {}
        requests = payload.get("requests", ()) if isinstance(payload, dict) else ()
        results = payload.get("results", ()) if isinstance(payload, dict) else ()
        if isinstance(requests, list):
            for request in requests:
                if not isinstance(request, dict):
                    continue
                kind = str(request.get("kind", "")).strip()
                if kind:
                    tools.append(kind)
        if isinstance(results, list):
            for row in results:
                if not isinstance(row, dict):
                    continue
                item = {
                    "kind": row.get("kind", ""),
                    "path": row.get("path", ""),
                    "handle": row.get("handle", ""),
                    "request_id": row.get("request_id", ""),
                    "bytes": row.get("bytes", row.get("stdout_bytes", row.get("stderr_bytes", 0))),
                    "content_hash": row.get("content_hash", ""),
                    "read_only": bool(row.get("read_only", False)),
                }
                if row.get("matched_paths"):
                    item["matched_paths"] = row.get("matched_paths")
                if any(str(value).strip() for value in item.values() if not isinstance(value, bool)):
                    inspected_items.append(item)
                if row.get("error"):
                    errors.append({
                        "kind": row.get("kind", ""),
                        "path": row.get("path", ""),
                        "handle": row.get("handle", ""),
                        "error": str(row.get("error", ""))[:1000],
                    })
    # stable order + concise payload
    unique_tools = list(dict.fromkeys(tools))
    return {
        "inspection_receipt_ids": [receipt.receipt_id for receipt in inspection_receipts],
        "inspection_count": len(inspection_receipts),
        "inspection_tools_used": unique_tools,
        "inspected_items": inspected_items[:20],
        "inspection_error_count": len(errors),
        "inspection_errors": errors[:10],
    }

def run_model_verifier_if_available(
    hooks: Any,
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    *,
    step: int,
    reason: str,
    executor: Any | None = None,
    envmap: Any | None = None,
    dynamic_state: Mapping[str, Any] | None = None,
    memo: dict[str, Any] | None = None,
) -> ModelVerifierResult | None:
    verify = getattr(hooks, "verify", None)
    if verify is None:
        return None
    allowed = _verifier_reason_allowed(compiled, reason)
    if not allowed:
        ledger.record(Receipt(
            receipt_id=f"step-{step}:model_verifier_skipped:{reason}",
            step=step,
            kind="model_verifier_skipped",
            success=True,
            summary=f"model verifier skipped by policy for {reason}",
            payload={
                "reason": reason,
                "policy": {
                    "enabled": compiled.model_verifier_policy.enabled,
                    "runs_on": list(compiled.model_verifier_policy.runs_on),
                },
            },
        ))
        return None
    # A live kernel run may have a WorldState snapshot that is richer than the
    # receipt ledger (named sections and explicit removals in particular).  Do
    # not silently discard it at this boundary.  The verifier is fail-closed
    # until both authorities are present: a missing snapshot or EnvMap must
    # not be allowed to produce a completed model verdict from an incomplete
    # packet.
    if dynamic_state is None or envmap is None:
        missing = []
        if dynamic_state is None:
            missing.append("dynamic_state")
        if envmap is None:
            missing.append("stable_envmap")
        summary = "verifier state unavailable: missing " + ", ".join(missing)
        ledger.record(Receipt(
            receipt_id=f"step-{step}:verifier_state_unavailable:{reason}",
            step=step,
            kind="verifier_state_unavailable",
            success=False,
            summary=summary,
            failure_class="dynamic_state_unavailable",
            payload={
                "reason": reason,
                "available": False,
                "missing": missing,
                "source": "kernel",
            },
        ))
        blocked = ModelVerifierResult(
            verdict="blocked_by_harness_config",
            confidence="high",
            summary=summary,
        )
        ledger.record_model_verifier_result(
            blocked,
            receipt_id=f"step-{step}:model_verifier_result:state_unavailable:{reason}",
            step=step,
            summary=f"model verifier verdict: {blocked.verdict}",
            failure_class=blocked.verdict,
            compiled=compiled,
            extra_payload={"reason": reason},
        )
        return blocked
    # Pass the stable environment authority and dynamic world snapshot into
    # the neutral packet.  The packet builder deliberately does not receive
    # Solver prompts, journey history, or model-authored proof.
    packet = build_verifier_packet(
        compiled,
        ledger,
        step=step,
        reason=reason,
        envmap=envmap,
        dynamic_state=dynamic_state,
    )
    signature = packet_state_signature(packet)
    candidate_generation = packet.get("task_state_generation")
    if (
        memo is not None
        and "review_unavailable_generation" in memo
        and memo.get("review_unavailable_generation") == candidate_generation
    ):
        summary = (
            "independent review unavailable for the current candidate generation; "
            "this does not establish a candidate defect"
        )
        ledger.record(Receipt(
            receipt_id=f"step-{step}:model_verifier_skipped:review_unavailable",
            step=step,
            kind="model_verifier_skipped",
            success=False,
            summary=summary,
            failure_class="verifier_review_unavailable",
            payload={
                "reason": "review_unavailable",
                "candidate_generation": candidate_generation,
                "incident_key": memo.get("review_unavailable_incident", ""),
            },
        ))
        return ModelVerifierResult(
            verdict="blocked_by_tooling", confidence="high", summary=summary
        )
    if (
        memo is not None
        and memo.get("signature") == signature
        and memo.get("result") is not None
        and getattr(memo.get("result"), "verdict", "") != "completed"
    ):
        # The material state is identical to the last judged packet; the same
        # deterministic-input judgment applies.  Skipping the model call saves
        # a full verifier round (observed live: 16 rounds on identical state)
        # while the repeated identical round still counts toward stalemate.
        previous = memo["result"]
        ledger.record(Receipt(
            receipt_id=f"step-{step}:model_verifier_skipped:unchanged_state",
            step=step,
            kind="model_verifier_skipped",
            success=True,
            summary=(
                "model verifier not re-invoked: packet state unchanged since the "
                f"last verdict ({previous.verdict}); produce new evidence or state"
            ),
            payload={
                "reason": "unchanged_state",
                "signature": signature,
                "reused_verdict": previous.verdict,
            },
        ))
        return previous
    receipt_count_before_verify = len(ledger.all_receipts())
    ledger.record(Receipt(
        receipt_id=f"step-{step}:model_verifier_packet:{reason}",
        step=step,
        kind="model_verifier_packet",
        success=True,
        summary=f"model verifier packet built for {reason}",
        payload={"reason": reason, "packet": packet},
    ))
    try:
        ledger.record_accounting(
            receipt_id=f"step-{step}:verifier_provider_call:{ledger.accounting_value('verifier_provider_calls') + 1}",
            step=step,
            counter="verifier_provider_calls",
            event="verifier_call",
        )
        raw = _call_verify_with_timeout(
            hooks,
            verify,
            packet,
            compiled,
            ledger,
            step=step,
            executor=executor,
            envmap=envmap,
        )
        result = parse_model_verifier_result(raw)
        if _inspection_tooling_blocked(ledger, packet_signature=signature, step=step):
            result = ModelVerifierResult(
                verdict="blocked_by_tooling",
                confidence="high",
                summary="compiled Verifier inspection primary and fallback routes both failed",
            )
    except Exception as exc:
        # A kernel wall-time interrupt is control flow, not a verifier failure.
        # If it fires inside a verifier model call it must propagate so the
        # runner terminates and grades -- otherwise it is recorded as a
        # model_verifier_error and the loop keeps running past the budget
        # Historical evidence showed this signal could otherwise be swallowed on
        # the verifier path. The verifier's own bounded timeout remains a normal
        # raises TimeoutError, which is a real verifier error and still handled
        # below -- only the kernel-terminate signal is re-raised here.
        if isinstance(exc, RunCancellationRequested):
            raise
        if exc.__class__.__name__ == "KernelRunTimeout":
            raise
        failure_class = _model_verifier_failure_class(exc)
        ledger.record(Receipt(
            receipt_id=f"step-{step}:model_verifier_error:{reason}",
            step=step,
            kind="model_verifier_error",
            success=False,
            summary=f"model verifier failed for {reason}: {exc}",
            failure_class=failure_class,
            payload={
                "reason": reason,
                "error": str(exc),
                "failure_class": failure_class,
                "error_type": type(exc).__name__,
            },
        ))
        # Provider/protocol/tool failures remain verifier-owned.  Record the
        # bounded recovery decision, but do not manufacture a Solver finding
        # or return a needs_repair verdict from this path.
        recovery_router = _recovery_router(memo)
        blocker_owner, blocker_verified = _verified_blocker_receipt(ledger, step=step, packet_signature=signature)
        recovery = recovery_router.route(
            ModelVerifierResult(
                verdict="blocked_by_tooling",
                confidence="high",
                summary=f"verifier call failed: {exc}",
            ),
            packet_signature=signature,
            blocker_owner=blocker_owner or "verifier_tooling",
            blocker_verified=blocker_verified,
            incident_key=failure_class,
            candidate_generation=packet.get("task_state_generation"),
            )
        ledger.record(Receipt(
            receipt_id=f"step-{step}:verifier_recovery_route:{reason}",
            step=step,
            kind="verifier_recovery_route",
            success=recovery not in {
                VerifierRecoveryAction.TERMINAL_INFRASTRUCTURE,
                VerifierRecoveryAction.REVIEW_UNAVAILABLE,
            },
            summary=f"verifier recovery route: {recovery.value}",
            failure_class=(
                "" if recovery is VerifierRecoveryAction.RETURN_TO_SOLVER
                else "verifier_review_unavailable"
                if recovery is VerifierRecoveryAction.REVIEW_UNAVAILABLE
                else "verifier_tooling"
            ),
            payload={
                "reason": reason,
                "packet_signature": signature,
                "action": recovery.value,
                "solver_repair_allowed": recovery is VerifierRecoveryAction.RETURN_TO_SOLVER,
                "blocker_owner": blocker_owner or "verifier_tooling",
                "blocker_verified": blocker_verified,
                "error": str(exc),
                "incident_key": failure_class,
                "candidate_generation": packet.get("task_state_generation"),
            },
        ))
        if memo is not None and recovery is VerifierRecoveryAction.REVIEW_UNAVAILABLE:
            memo["review_unavailable_generation"] = candidate_generation
            memo["review_unavailable_incident"] = failure_class
        _persist_verifier_bundle(
            step=step,
            reason=reason,
            packet=packet,
            raw_output=None,
            parsed_result=None,
            active_findings_after=ledger.active_finding_context(step + 1),
            error=str(exc),
        )
        # A verifier/tool/provider failure is not an absent verdict.  Returning
        # None here allowed the kernel's solver-driven completion path to run
        # after a failed verifier call, creating a false clean.  Return an
        # explicit verifier-owned block so completion remains impossible until
        # the bounded recovery route succeeds or infrastructure terminates.
        blocked = ModelVerifierResult(
            verdict="blocked_by_tooling",
            confidence="high",
            summary=f"verifier call failed: {exc}",
        )
        ledger.record_model_verifier_result(
            blocked,
            receipt_id=f"step-{step}:model_verifier_result:{reason}:tooling_blocked",
            step=step,
            summary=blocked.summary,
            failure_class="verifier_tooling",
            compiled=compiled,
            packet_signature=signature,
            extra_payload={"reason": reason},
        )
        return blocked
    # Build all verifier-derived diagnostics before appending the result
    # receipt. Mutating that receipt after ``ledger.record`` would invalidate
    # its append-time payload digest and make a valid verdict inadmissible.
    inspection_summary = _inspection_evidence_summary(
        ledger.all_receipts()[receipt_count_before_verify:]
    )
    reviewer_classification = classify_verifier_outcome(
        result,
        inspection_summary=inspection_summary,
    )
    ledger.apply_verifier_result(
        result,
        step=step,
        compiled=compiled,
        packet_signature=signature,
        extra_payload={
            "reason": reason,
            "verifier_packet": packet,
            "raw_verifier_output": raw,
            "parsed_verifier_result": result.as_dict(),
            "reviewer_classification": reviewer_classification,
            "reviewer_evidence_receipt": inspection_summary,
        },
    )
    # Independent Verifier evidence is consumed directly; no legacy clause reconstruction.
    recovery_router = _recovery_router(memo)
    blocker_owner, blocker_verified = _verified_blocker_receipt(ledger, step=step, packet_signature=signature)
    recovery = recovery_router.route(
        result,
        packet_signature=signature,
        blocker_owner=blocker_owner,
        blocker_verified=blocker_verified,
        incident_key=str(result.verdict),
        candidate_generation=packet.get("task_state_generation"),
    )
    ledger.record(Receipt(
        receipt_id=f"step-{step}:verifier_recovery_route:{reason}",
        step=step,
        kind="verifier_recovery_route",
        success=recovery not in {
            VerifierRecoveryAction.TERMINAL_INFRASTRUCTURE,
            VerifierRecoveryAction.REVIEW_UNAVAILABLE,
        },
        summary=f"verifier recovery route: {recovery.value}",
        failure_class=(
            "" if recovery in {VerifierRecoveryAction.TERMINATE_SUCCESS, VerifierRecoveryAction.RETURN_TO_SOLVER}
            else "verifier_review_unavailable"
            if recovery is VerifierRecoveryAction.REVIEW_UNAVAILABLE
            else "verifier_tooling"
        ),
        payload={
            "reason": reason,
            "packet_signature": signature,
            "action": recovery.value,
            "solver_repair_allowed": recovery is VerifierRecoveryAction.RETURN_TO_SOLVER,
            "blocker_owner": blocker_owner or ("harness_config" if result.verdict == "blocked_by_harness_config" else ""),
            "blocker_verified": blocker_verified,
            "verdict": result.verdict,
            "incident_key": str(result.verdict),
            "candidate_generation": packet.get("task_state_generation"),
        },
    ))
    if memo is not None and recovery is VerifierRecoveryAction.REVIEW_UNAVAILABLE:
        memo["review_unavailable_generation"] = candidate_generation
        memo["review_unavailable_incident"] = str(result.verdict)
    active_after = ledger.active_finding_context(step + 1)
    ledger.record(Receipt(
        receipt_id=f"step-{step}:model_verifier_evidence:{reason}",
        step=step,
        kind="model_verifier_evidence",
        success=not bool(inspection_summary.get("inspection_errors")),
        summary=(
            f"reviewer evidence summary: {inspection_summary.get('inspection_count', 0)} inspection receipt(s); "
            f"classification={reviewer_classification}"
        ),
        failure_class="" if not inspection_summary.get("inspection_errors") else "reviewer_tool_execution_failed",
        payload={
            "reason": reason,
            "reviewer_classification": reviewer_classification,
            **inspection_summary,
        },
    ))
    _persist_verifier_bundle(
        step=step,
        reason=reason,
        packet=packet,
        raw_output=raw,
        parsed_result=result.as_dict(),
        active_findings_after=active_after,
    )
    if memo is not None:
        memo["signature"] = signature
        memo["result"] = result
    return result


def _recovery_router(memo: dict[str, Any] | None) -> VerifierRecoveryRouter:
    """Get a per-run bounded router without changing the public kernel API."""
    if memo is None:
        return VerifierRecoveryRouter()
    router = memo.get("recovery_router")
    if isinstance(router, VerifierRecoveryRouter):
        return router
    router = VerifierRecoveryRouter()
    memo["recovery_router"] = router
    return router


def _verified_blocker_receipt(ledger: ExecutionLedger, *, step: int, packet_signature: str) -> tuple[str, bool]:
    """Read only a harness-issued blocker verification marker.

    Read only a harness-issued blocker verification marker.
    """
    for receipt in reversed(ledger.all_receipts()):
        if receipt.kind != "verifier_blocker_verified" or receipt.step > step:
            continue
        payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        owner = str(payload.get("blocker_owner", "")).strip()
        receipt_signature = str(payload.get("packet_signature", "")).strip()
        if receipt.success and owner and receipt_signature == packet_signature:
            return owner, True
    return "", False


def _inspection_tooling_blocked(
    ledger: ExecutionLedger, *, packet_signature: str, step: int,
) -> bool:
    for receipt in reversed(ledger.all_receipts()):
        if receipt.kind != "verifier_blocker_verified" or receipt.step > step:
            continue
        payload = receipt.payload if isinstance(receipt.payload, dict) else {}
        return (
            receipt.success
            and str(payload.get("blocker_owner", "")) == "verifier_tooling"
            and str(payload.get("packet_signature", "")) == packet_signature
        )
    return False


def _call_verify_with_timeout(
    hooks: Any,
    verify: Any,
    packet: dict[str, Any],
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    *,
    step: int,
    executor: Any | None = None,
    envmap: Any | None = None,
) -> Any:
    # Provider turns and the complete verifier generation are distinct
    # budgets.  A valid observe -> verify -> verdict path can contain several
    # bounded provider turns, so the wall-clock envelope is derived from the
    # phase budget unless an operator explicitly narrows it.
    call_timeout_s = PRODUCTION_VERIFIER_CALL_TIMEOUT_S
    max_model_calls = PRODUCTION_VERIFIER_PHASE_BUDGET.max_model_calls
    tool_budget_s = PRODUCTION_VERIFIER_PHASE_BUDGET.max_tool_execution_s_per_batch
    timeout_s = (
        PRODUCTION_VERIFIER_WALL_CLOCK_BUDGET_S
        if PRODUCTION_VERIFIER_WALL_CLOCK_BUDGET_S is not None
        else _task_agent_timeout_s(envmap)
    )
    generation = VerifierGeneration()
    guarded_ledger = GenerationBoundLedger(ledger, generation)

    def invoke() -> Any:
        return _call_verify(
            hooks,
            verify,
            packet,
            compiled,
            guarded_ledger,
            step=step,
            executor=executor,
            envmap=envmap,
            generation=generation,
        )

    if timeout_s is None or timeout_s <= 0:
        try:
            return invoke()
        finally:
            generation.expire("completed_without_thread_timeout")

    # Carry the worker completion timestamp with the result.  A supervising
    # thread can itself be descheduled past the deadline; queue availability at
    # wake-up is therefore not proof that the Verifier finished on time.
    results: queue.Queue[tuple[bool, Any, float]] = queue.Queue(maxsize=1)
    deadline_monotonic = time.monotonic() + timeout_s

    def _raise_timeout(
        reason: str,
        *,
        cause: BaseException | None = None,
        worker_completed_at: float | None = None,
    ) -> None:
        generation.expire(reason)
        overrun_s = (
            max(0.0, worker_completed_at - deadline_monotonic)
            if worker_completed_at is not None else None
        )
        ledger.record(Receipt(
            receipt_id=f"step-{step}:verifier_generation_expired:{generation.generation_id}",
            step=step,
            kind="verifier_generation_expired",
            success=False,
            summary=f"Verifier generation expired after {timeout_s:.3f}s",
            failure_class="verifier_timeout",
            payload={
                "generation_id": generation.generation_id,
                "wall_clock_budget_s": timeout_s,
                "model_call_timeout_s": call_timeout_s,
                "max_model_calls": max_model_calls,
                "tool_execution_budget_s": tool_budget_s,
                "authority_revoked": True,
                "late_ledger_mutations_allowed": False,
                "late_tool_dispatch_allowed": False,
                "worker_completed_after_deadline": worker_completed_at is not None,
                "deadline_overrun_s": overrun_s,
            },
        ))
        error = TimeoutError(
            f"model verifier timed out after {timeout_s:.3f}s; "
            f"generation={generation.generation_id} authority revoked"
        )
        if cause is not None:
            raise error from cause
        raise error

    def _target() -> None:
        try:
            with verifier_generation_deadline(deadline_monotonic):
                value = invoke()
            finished_at = time.monotonic()
            try:
                results.put_nowait((True, value, finished_at))
            except queue.Full:
                generation.quarantine("late_verifier_result", value)
        except Exception as exc:  # pragma: no cover - exercised through caller
            finished_at = time.monotonic()
            try:
                results.put_nowait((False, exc, finished_at))
            except queue.Full:
                generation.quarantine("late_verifier_exception", exc)

    thread = threading.Thread(
        target=_target,
        name=f"aether-model-verifier:{generation.generation_id}",
        daemon=True,
    )
    thread.start()
    try:
        ok, value, worker_completed_at = results.get(timeout=timeout_s)
    except queue.Empty as exc:
        _raise_timeout(f"timeout_after_{timeout_s:.3f}s", cause=exc)
    # Fail closed on the worker's completion time, not on when the supervisor
    # happened to wake and inspect the queue.  This closes the race where a
    # result completed after the deadline but was already queued before a late
    # supervisor call to Queue.get().
    if worker_completed_at > deadline_monotonic:
        generation.quarantine(
            "late_verifier_result" if ok else "late_verifier_exception", value,
        )
        _raise_timeout(
            f"worker_completed_after_deadline_by_{worker_completed_at - deadline_monotonic:.6f}s",
            worker_completed_at=worker_completed_at,
        )
    generation.expire("result_delivered")
    if ok:
        return value
    raise value


def _call_verify(
    hooks: Any,
    verify: Any,
    packet: dict[str, Any],
    compiled: CompiledRuntime,
    ledger: Any,
    *,
    step: int,
    executor: Any | None = None,
    envmap: Any | None = None,
    generation: VerifierGeneration | None = None,
) -> Any:
    if generation is not None:
        generation.require_active()
    signature = packet_state_signature(packet)
    verify_with_inspector = getattr(hooks, "verify_with_inspector", None)
    if callable(verify_with_inspector) and executor is not None and envmap is not None:
        require_independent_isolation = True
        overlay = VerifierOverlay(
            executor,
            envmap.workspace_root,
            max_command_timeout_s=_verifier_command_budget_s(envmap),
            require_independent_isolation=require_independent_isolation,
        )

        def _inspector(requests: tuple[VerifierInspectionRequest, ...]) -> list[dict[str, Any]]:
            if generation is not None:
                generation.require_active()
            for request in requests:
                ledger.record_accounting(
                    receipt_id=(
                        f"step-{step}:verifier_inspection_request:"
                        f"{request.request_id}:{ledger.accounting_value('verifier_inspection_requests') + 1}"
                    ),
                    step=step,
                    counter="verifier_inspection_requests",
                    event="verifier_read_only_inspection",
                    detail=f"verifier inspection requested: {request.kind}",
                )
            results = execute_verifier_inspection_requests(
                requests,
                compiled=compiled,
                ledger=ledger,
                executor=executor,
                envmap=envmap,
                overlay=overlay,
                hooks=hooks,
            )
            results, recovery_rows = _execute_compiled_inspection_fallbacks(
                requests,
                results,
                compiled=compiled,
                ledger=ledger,
                executor=executor,
                envmap=envmap,
                overlay=overlay,
                hooks=hooks,
            )
            if generation is not None:
                generation.require_active()
            # Register actual performed inspections before returning them to
            # the Verifier.  The enriched rows expose the only IDs completion
            # evidence may cite; route/ceiling/generation are kernel-derived.
            from .proof_contract import proof_requirements_identity
            results = register_inspection_results(
                requests,
                results,
                ledger=ledger,
                step=step,
                requester="model_verifier",
                executor=executor,
                overlay=overlay,
                packet_signature=signature,
                proof_contract_identity=(
                    compiled.proof_requirements_identity
                    or (
                        proof_requirements_identity(compiled.proof_requirements)
                        if compiled.proof_requirements else ""
                    )
                ),
                require_independent_isolation=require_independent_isolation,
                strict_snapshot_binding=True,
            )
            ledger.record(Receipt(
                receipt_id=f"step-{step}:model_verifier_inspection:{len(ledger.all_receipts())}",
                step=step,
                kind="model_verifier_inspection",
                success=True,
                summary=f"model verifier inspection executed: {', '.join(request.kind for request in requests)}",
                payload={
                    "requests": [
                        {
                            "request_id": request.request_id,
                            "kind": request.kind,
                            "path": request.path,
                            "handle": getattr(request, "handle", ""),
                            "check_id": request.check_id,
                            "receipt_kind": request.receipt_kind,
                            "limit": request.limit,
                            "command": getattr(request, "command", ""),
                        }
                        for request in requests
                    ],
                    "results": results,
                },
            ))
            if recovery_rows:
                failed_recovery = [row for row in recovery_rows if not bool(row.get("fallback_success"))]
                if failed_recovery:
                    # This is harness-issued evidence that the compiled
                    # primary and fallback routes both failed.  It is the
                    # only marker that may authorize verifier_tooling-owned
                    # reconfiguration; the model's prose cannot do so.
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:verifier_blocker_verified:{len(ledger.all_receipts())}",
                        step=step,
                        kind="verifier_blocker_verified",
                        success=True,
                        summary="compiled primary and fallback inspection routes both failed",
                        failure_class="verifier_tooling",
                        payload={
                            "blocker_owner": "verifier_tooling",
                            "packet_signature": signature,
                            "attempts": failed_recovery,
                        },
                    ))
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:verifier_inspection_recovery:{len(ledger.all_receipts())}",
                    step=step,
                    kind="verifier_inspection_recovery",
                    success=all(bool(row.get("fallback_success")) for row in recovery_rows),
                    summary="compiled Verifier inspection fallback attempted",
                    failure_class="verifier_tooling" if not all(bool(row.get("fallback_success")) for row in recovery_rows) else "",
                    payload={"attempts": recovery_rows},
                ))
            return results

        try:
            return verify_with_inspector(packet, compiled, ledger, _inspector)
        finally:
            # Rollback is unconditional: the overlay never outlives the
            # verification round, pass or fail.
            teardown = overlay.teardown()
            if teardown.get("overlay_root"):
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:model_verifier_overlay_teardown",
                    step=step,
                    kind="model_verifier_overlay_teardown",
                    success=bool(teardown.get("removed")),
                    summary=f"verifier overlay removed: {teardown.get('overlay_root')}",
                    payload=teardown,
                ))
    if generation is not None:
        generation.require_active()
    return verify(packet, compiled, ledger)


def _execute_compiled_inspection_fallbacks(
    requests: tuple[VerifierInspectionRequest, ...],
    results: list[dict[str, Any]],
    *,
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    executor: Any,
    envmap: Any,
    overlay: Any,
    hooks: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run one compiler-declared fallback after a failed primary inspection."""
    requirements = compiled.config_realization.get("compiled_evidence_requirements", ())
    if not isinstance(requirements, (list, tuple)):
        return results, []
    by_route = {
        str(item.get("inspection_route", "")).strip(): item
        for item in requirements
        if isinstance(item, Mapping) and str(item.get("inspection_route", "")).strip()
    }
    attempts: list[dict[str, Any]] = []
    expanded = list(results)
    for request, primary in zip(requests, results):
        if not isinstance(primary, Mapping) or not primary.get("error"):
            continue
        route = _inspection_route(request)
        contract = by_route.get(route)
        fallback = str(contract.get("fallback_route", "")).strip() if contract else ""
        if not fallback or fallback == route:
            continue
        fallback_request = _request_from_compiled_route(fallback, request)
        if fallback_request is None:
            attempts.append({"primary_route": route, "fallback_route": fallback, "fallback_success": False, "error": "unsupported fallback route"})
            continue
        fallback_rows = execute_verifier_inspection_requests(
            (fallback_request,), compiled=compiled, ledger=ledger,
            executor=executor, envmap=envmap, overlay=overlay, hooks=hooks,
        )
        fallback_row = dict(fallback_rows[0]) if fallback_rows else {"error": "fallback produced no result"}
        fallback_row["route_role"] = "compiled_fallback"
        expanded.append(fallback_row)
        attempts.append({
            "primary_route": route,
            "fallback_route": fallback,
            "primary_error": str(primary.get("error", "")),
            "fallback_success": not bool(fallback_row.get("error")),
            "fallback_request_id": fallback_request.request_id,
        })
    return expanded, attempts


def _inspection_route(request: VerifierInspectionRequest) -> str:
    target = request.path or request.handle or request.check_id or request.target
    return f"{request.kind}:{target}" if target else request.kind


def _request_from_compiled_route(route: str, original: VerifierInspectionRequest) -> VerifierInspectionRequest | None:
    kind, separator, target = route.partition(":")
    if not kind.strip():
        return None
    kind = kind.strip()
    target = target.strip() if separator else ""
    if kind not in {"read_file", "read_output", "inspect_artifact", "probe_port", "probe_http", "probe_process", "probe_job", "rerun_check", "inspect_recent_receipts", "inspect_action_receipts", "inspect_artifact_history"}:
        return None
    return VerifierInspectionRequest(
        request_id=f"fallback:{original.request_id}",
        kind=kind,
        path=target if kind not in {"read_output", "probe_port", "probe_http", "probe_process"} else (original.path if kind == "read_output" else ""),
        handle=target if kind == "read_output" else "",
        check_id=target if kind == "rerun_check" else "",
        target=target if kind in {"probe_port", "probe_http", "probe_process"} else "",
        limit=original.limit,
        span=original.span,
    )


def _verifier_reason_allowed(compiled: CompiledRuntime, reason: str) -> bool:
    policy = compiled.model_verifier_policy
    if not policy.enabled:
        return False
    runs_on = set(policy.runs_on)
    alias = _REASON_ALIASES.get(reason, reason)
    return reason in runs_on or alias in runs_on


def _persist_verifier_bundle(
    *,
    step: int,
    reason: str,
    packet: dict[str, Any],
    raw_output: Any,
    parsed_result: dict[str, Any] | None,
    active_findings_after: list[dict[str, Any]],
    error: str = "",
) -> None:
    root = os.environ.get("AETHER_VERIFIER_EVIDENCE_DIR", "").strip()
    if not root:
        return
    safe_reason = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in reason)[:80]
    out_dir = Path(root) / f"step_{step:04d}_{safe_reason}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verifier_packet.json").write_text(json.dumps(packet, indent=2, sort_keys=True, default=str))
    # Verifier prompt/strategy are not part of the model-visible state packet;
    # retain an explicit empty marker for bundle schema compatibility.
    (out_dir / "verifier_prompt.txt").write_text("")
    if raw_output is not None:
        if isinstance(raw_output, str):
            (out_dir / "raw_verifier_output.txt").write_text(raw_output)
        else:
            (out_dir / "raw_verifier_output.txt").write_text(json.dumps(raw_output, indent=2, sort_keys=True, default=str))
    if parsed_result is not None:
        (out_dir / "parsed_verifier_result.json").write_text(json.dumps(parsed_result, indent=2, sort_keys=True, default=str))
    (out_dir / "active_findings_after.json").write_text(json.dumps(active_findings_after, indent=2, sort_keys=True, default=str))
    if error:
        (out_dir / "verifier_error.txt").write_text(error)
