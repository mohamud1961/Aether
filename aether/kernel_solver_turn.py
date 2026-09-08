"""Solver parse-error handling (same-step retry), extracted from kernel.py
for the 500-LOC cap.

Pure move of ``AetherNextKernel.run``'s ``except ModelOutputError`` branch
for the solver turn into a module-level function. ``hooks`` is the
``KernelHooks`` instance (typed ``Any`` here to avoid an import cycle with
existing ``hooks: Any`` parameter, to avoid a cycle with kernel.py's
``KernelHooks`` Protocol).
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping, TYPE_CHECKING

from .ledger import ExecutionLedger, Receipt
from .model_hooks import ModelOutputError
from .redaction import redact_text_with_events
from .runtime_ir import CompiledRuntime, SolverTurn

if TYPE_CHECKING:
    from .tracing import RunTrace


def handle_solver_parse_error(
    hooks: Any,
    exc: ModelOutputError,
    step: int,
    compiled: CompiledRuntime,
    messages: list[dict[str, str]],
    ledger: ExecutionLedger,
    context_packet: Mapping[str, Any] | None,
    trace: "RunTrace | None",
    before_count: int,
) -> SolverTurn | None:
    """Record the parse-error receipt, retry once in the same step, and on a
    second failure record the retry receipt + trace step.

    Returns the retried ``SolverTurn`` on success. Returns ``None`` when the
    retry also failed -- the parse-error-retry receipt and trace step have
    already been recorded by this call; the caller must fire the step
    snapshot, advance ``step``, and ``continue`` the loop (a ``continue``
    cannot cross a function boundary, so that piece stays inline in
    kernel.py).
    """
    raw_output = str(getattr(hooks, "last_raw_solver_output", "") or "")
    redacted_output, redaction_events = redact_text_with_events(raw_output)
    ledger.record(Receipt(
        receipt_id=f"step-{step}:solver_parse_error",
        step=step,
        kind="solver_parse_error",
        success=False,
        summary=f"solver output parse/validation error: {exc}",
        failure_class="solver_protocol_error",
        payload={
            "error": str(exc),
            "redacted_output": redacted_output[:20000],
            "raw_output_sha256": hashlib.sha256(raw_output.encode("utf-8")).hexdigest(),
            "raw_output_bytes": len(raw_output.encode("utf-8")),
            "redaction_events": list(redaction_events),
            "raw_output_storage": "protected_provider_evidence_only",
            "retry_attempted": True,
        },
    ))
    ledger.record_accounting(
        receipt_id=f"step-{step}:solver_malformed_attempt:{ledger.accounting_value('solver_malformed_provider_attempts') + 1}",
        step=step,
        counter="solver_malformed_provider_attempts",
        event="primary_solver_call_malformed",
    )
    error_text = str(exc)
    distinct_candidate_failure = "provider_pcr_v0_multiple_distinct_semantic_payloads" in error_text
    protocol_field_failure = any(marker in error_text for marker in (
        "missing required fields",
        "must be non-empty",
        "must be a string",
        "unsupported fields",
        "actions must contain exactly one action",
        "may not carry actions",
        "provider_pcr_v0_schema_validation",
    ))
    retry_messages = list(messages)
    correction_mode = "copy_exact_format_correction"
    correction_event = "same_step_protocol_correction"
    provider_event = "protocol_correction_solver_call"
    rejected_output_provided_to_retry = False
    if distinct_candidate_failure:
        # Multiple distinct complete turns are an ambiguous provider response,
        # not an executable Solver decision. Preserve the raw response only in
        # evidence, expose the mechanical protocol fact, and ask the Solver to
        # make one fresh decision from the unchanged observed state.
        correction_mode = "fresh_single_turn_after_ambiguous_response"
        correction_event = "same_step_fresh_single_turn"
        provider_event = "ambiguous_response_fresh_solver_call"
        retry_messages.append({
            "role": "user",
            "content": (
                "[solver_protocol_observation] The previous provider response contained multiple distinct "
                "complete Solver turns, so it was ambiguous and none of its proposed actions or submissions "
                "executed. The observed task, workspace, process, and evidence state are unchanged. Make one "
                "fresh current Solver decision from the observed context. Do not assume that any action or "
                "outcome described in the rejected response occurred. Return exactly one strict provider JSON "
                "object whose sole key is turn, then stop generation immediately after that outer object closes. "
                "For an act turn, include exactly one action. Use finish_intent only to request advisory review "
                "of a candidate you believe complete; use finish for the final completion decision. Both require "
                "already observed supporting evidence."
            ),
        })
    else:
        if raw_output.strip():
            # The rejected response is non-executed evidence. Pure envelope
            # failures copy existing values; field failures may repair only the
            # explicitly invalid protocol field while freezing action semantics.
            retry_messages.append({"role": "assistant", "content": raw_output})
            rejected_output_provided_to_retry = True
        if protocol_field_failure:
            correction_mode = "bounded_protocol_field_correction"
            correction_event = "same_step_protocol_field_correction"
            provider_event = "protocol_field_correction_solver_call"
            correction_content = (
                "Your previous Primary Agent turn was rejected before execution because one or more fields or the "
                "envelope violated the active PCR V0 contract. The complete rejected assistant output appears "
                "immediately before this correction as non-executed context. This is a bounded protocol-field "
                "correction, not a new task-solving step. Preserve the selected action or submission and every "
                "task-specific literal unless the stated error names that exact field as invalid. Change only the "
                "minimum field or envelope structure required by the stated error. Do not simulate a result, emit "
                "a later dependent decision, or claim an action occurred. "
                f"Error: {exc}. Return exactly one strict provider JSON object whose sole key is turn, then stop "
                "generation immediately after that outer object closes."
            )
        else:
            correction_content = (
                "Your previous Primary Agent turn could not be parsed into one authorized PCR V0 turn, so none "
                "of its proposed actions or submissions executed. The complete rejected assistant output appears "
                "immediately before this correction as non-executed context. This is a selection-and-copy format "
                "correction, not replanning. Follow the active provider schema exactly and return one current turn "
                "only. Preserve the chosen action kind, arguments, claim, evidence references, and "
                "task-specific literals. Remove only invalid wrapping, prose, or extra candidate turns. "
                "Do not simulate an observation, emit a future dependent turn, or use completion controls from unobserved state. "
                f"Error: {exc}. Return exactly one strict provider JSON object whose sole key is turn, then stop "
                "generation immediately after that outer object closes."
            )
        retry_messages.append({"role": "user", "content": correction_content})
    try:
        ledger.record_accounting(
            receipt_id=f"step-{step}:solver_protocol_correction:{ledger.accounting_value('solver_protocol_correction_calls') + 1}",
            step=step,
            counter="solver_protocol_correction_calls",
            event=correction_event,
        )
        ledger.record_accounting(
            receipt_id=f"step-{step}:solver_provider_turn:{ledger.accounting_value('solver_provider_turns') + 1}",
            step=step,
            counter="solver_provider_turns",
            event=provider_event,
        )
        corrected_turn = hooks.solve(retry_messages, compiled)
        ledger.record(Receipt(
            receipt_id=f"step-{step}:solver_protocol_correction_result",
            step=step,
            kind="solver_protocol_correction_result",
            success=True,
            summary=(
                "Solver returned one fresh turn after ambiguous provider output"
                if distinct_candidate_failure
                else (
                    "Solver returned one valid turn after bounded protocol-field correction"
                    if protocol_field_failure
                    else "Solver returned one valid turn after bounded format correction"
                )
            ),
            payload={
                "correction_mode": correction_mode,
                "selected_turn_kind": corrected_turn.kind,
                "selected_turn_summary_sha256": hashlib.sha256(
                    corrected_turn.summary.encode("utf-8")
                ).hexdigest(),
                "rejected_output_sha256": hashlib.sha256(
                    raw_output.encode("utf-8")
                ).hexdigest(),
                "rejected_output_provided_to_retry": rejected_output_provided_to_retry,
                "candidate_execution_before_correction": False,
                "observed_state_changed_before_correction": False,
            },
        ))
        return corrected_turn
    except ModelOutputError as retry_exc:
        raw_retry = str(getattr(hooks, "last_raw_solver_output", "") or "")
        redacted_retry, retry_redaction_events = redact_text_with_events(raw_retry)
        ledger.record(Receipt(
            receipt_id=f"step-{step}:solver_parse_error_retry",
            step=step,
            kind="solver_parse_error",
            success=False,
            summary=f"solver retry still invalid: {retry_exc}",
            failure_class="solver_protocol_error",
            payload={
                "error": str(retry_exc),
                "redacted_output": redacted_retry[:20000],
                "raw_output_sha256": hashlib.sha256(raw_retry.encode("utf-8")).hexdigest(),
                "raw_output_bytes": len(raw_retry.encode("utf-8")),
                "redaction_events": list(retry_redaction_events),
                "raw_output_storage": "protected_provider_evidence_only",
                "retry_attempted": False,
                "correction_mode": correction_mode,
                "rejected_output_provided_to_retry": rejected_output_provided_to_retry,
                "candidate_execution_before_correction": False,
            },
        ))
        ledger.record_accounting(
            receipt_id=f"step-{step}:solver_malformed_attempt:{ledger.accounting_value('solver_malformed_provider_attempts') + 1}",
            step=step,
            counter="solver_malformed_provider_attempts",
            event="protocol_correction_malformed",
        )
        if trace is not None:
            trace.add_step(
                step,
                context_packet,
                SolverTurn(kind="act", summary="solver protocol correction failed", actions=()),
                ledger.all_receipts()[before_count:],
            )
        return None
