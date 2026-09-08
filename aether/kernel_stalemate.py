"""Verifier-disagreement stalemate check, extracted from kernel.py for the
500-LOC cap.

Pure move of ``AetherNextKernel.run``'s post-verdict stalemate-window body
(the ``if verdict is not None and verdict.verdict != "completed":`` block,
covering both the ``verifier_stalemate`` and ``verifier_blocked_stalemate``
outcomes) into a module-level function. ``KernelResult`` is defined in
kernel.py, which imports this module at load time, so it is imported here
only under ``TYPE_CHECKING`` (for the annotation) and via a deferred
in-function import (for actual construction) to avoid a cycle -- the same
pattern verify_inspection_requests.py already uses for ``_model_output_error``.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .ledger import ExecutionLedger, Receipt
from .runtime_ir import CompiledRuntime

if TYPE_CHECKING:
    from .kernel import KernelResult


def _stalemate_owner_attribution(active_findings: list[dict[str, Any]], verdict: Any) -> dict[str, Any]:
    """Expose mechanical disagreement ownership without adjudicating correctness."""
    aliases = {
        "primary_agent": "solver_state",
        "primary agent": "solver_state",
        "solver": "solver_state",
        "solver_state": "solver_state",
        "verifier": "verifier_tooling",
        "reviewer_tooling": "verifier_tooling",
        "verifier_tooling": "verifier_tooling",
        "harness": "harness_config",
        "harness_config": "harness_config",
        "environment": "environment",
        "provider": "provider",
        "task_ambiguity": "task_ambiguity",
    }
    raw_counts: dict[str, int] = {}
    normalized_counts: dict[str, int] = {}
    for finding in active_findings:
        raw = str(finding.get("owner") or "").strip() or "unattributed"
        raw_counts[raw] = raw_counts.get(raw, 0) + 1
        normalized = aliases.get(raw.lower(), raw.lower().replace(" ", "_") or "unattributed")
        normalized_counts[normalized] = normalized_counts.get(normalized, 0) + 1
    verdict_name = str(getattr(verdict, "verdict", "") or "").strip()
    if normalized_counts:
        classification = next(iter(normalized_counts)) if len(normalized_counts) == 1 else "mixed"
        basis = "active_finding_owner_fields"
    else:
        classification = {
            "blocked_by_tooling": "verifier_tooling",
            "blocked_by_harness_config": "harness_config",
            "environment_blocked": "environment",
            "timeout_or_budget_blocked": "verifier_infrastructure",
            "reviewer_tool_execution_failed": "verifier_tooling",
            "reviewer_capability_missing": "verifier_tooling",
            "probe_inconclusive": "verification_uncertainty",
            "uncertain_missing_evidence": "unresolved_evidence",
        }.get(verdict_name, "unattributed")
        basis = "final_verifier_verdict_without_active_findings"
    return {
        "classification": classification,
        "basis": basis,
        "finding_owner_counts": dict(sorted(raw_counts.items())),
        "normalized_owner_counts": dict(sorted(normalized_counts.items())),
        "final_verifier_verdict": verdict_name,
        "correctness_adjudicated": False,
    }


def check_verifier_stalemate(
    kernel: Any,
    verdict: Any,
    step: int,
    reconfigurations: int,
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    verifier_round_finding_sets: list[frozenset[str]],
) -> "KernelResult | None":
    """Record repeated Verifier disagreement without terminating the task.

    The official task timeout is the execution backstop. Repeated disagreement
    is valuable forensic evidence but is not correctness authority and must not
    remove the Solver's remaining opportunity to repair the task.
    """

    active_ids = frozenset(
        str(item.get("finding_id", ""))
        for item in ledger.active_finding_context(step + 1)
        if str(item.get("finding_id", "")).strip()
    )
    verifier_round_finding_sets.append(active_ids)
    window = verifier_round_finding_sets[-kernel.STALEMATE_ROUNDS:]
    if not (
        len(window) == kernel.STALEMATE_ROUNDS
        and all(entry == window[0] for entry in window)
    ):
        return None
    if not window[0]:
        # Empty finding sets do not carry disagreement identity. Three changing
        # no-finding states (for example tooling-blocked -> missing-evidence ->
        # environment-blocked) are progress through distinct failure modes, not
        # one repeated stalemate. Require the durable Verifier verdict class to
        # be stable across the same window before terminating.
        verifier_results = [
            receipt for receipt in ledger.all_receipts()
            if receipt.kind == "model_verifier_result"
        ][-kernel.STALEMATE_ROUNDS:]
        verdict_names = [
            str(receipt.payload.get("verdict", "")).strip()
            for receipt in verifier_results
        ]
        if (
            len(verdict_names) != kernel.STALEMATE_ROUNDS
            or not verdict_names[0]
            or any(name != verdict_names[0] for name in verdict_names)
        ):
            return None
    active_findings = ledger.active_finding_context(step + 1)
    owner_attribution = _stalemate_owner_attribution(active_findings, verdict)
    if window[0]:
        fingerprint = tuple(sorted(window[0]))
        already = any(
            receipt.kind == "verifier_stalemate_observed"
            and tuple((receipt.payload or {}).get("finding_ids", ())) == fingerprint
            for receipt in ledger.all_receipts()
        )
        if not already:
            ledger.record(Receipt(
                receipt_id=f"step-{step}:verifier_stalemate_observed",
                step=step,
                kind="verifier_stalemate_observed",
                success=True,
                summary=(
                    f"diagnostic: the same {len(window[0])} Verifier finding(s) "
                    f"survived {kernel.STALEMATE_ROUNDS} rounds; execution continues "
                    "under official task timeout authority"
                ),
                payload={
                    "rounds": kernel.STALEMATE_ROUNDS,
                    "finding_ids": list(fingerprint),
                    "round_history": [sorted(entry) for entry in verifier_round_finding_sets],
                    "final_verifier_verdict": verdict.as_dict(),
                    "active_findings": active_findings,
                    "owner_attribution": owner_attribution,
                    "diagnostic_only": True,
                    "task_termination_authority": False,
                },
            ))
        return None

    already = any(
        receipt.kind == "verifier_blocked_stalemate_observed"
        and str((receipt.payload or {}).get("final_verifier_verdict", {}).get("verdict", ""))
        == str(getattr(verdict, "verdict", ""))
        for receipt in ledger.all_receipts()
    )
    if not already:
        ledger.record(Receipt(
            receipt_id=f"step-{step}:verifier_blocked_stalemate_observed",
            step=step,
            kind="verifier_blocked_stalemate_observed",
            success=True,
            summary=(
                f"diagnostic: Verifier remained blocked/uncertain without actionable findings for "
                f"{kernel.STALEMATE_ROUNDS} rounds; execution continues under official timeout"
            ),
            payload={
                "rounds": kernel.STALEMATE_ROUNDS,
                "round_history": [sorted(entry) for entry in verifier_round_finding_sets],
                "final_verifier_verdict": verdict.as_dict(),
                "active_findings": active_findings,
                "owner_attribution": owner_attribution,
                "diagnostic_only": True,
                "task_termination_authority": False,
            },
        ))
    return None
