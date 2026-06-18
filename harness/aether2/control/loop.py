"""Continuous executor loop composing tools, context, mirror, and verification into one run."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import json
import time

from harness.aether2.runtime.bridge_harbor import TaskSpec
from harness.aether2.runtime.compactor import rebase, should_rebase
from harness.aether2.runtime.context import ContextManager
from harness.aether2.hooks.registry import HookRegistry
from harness.aether2.traces.delta import (
    StateSnapshot,
    build_evidence_ledger,
    diff as delta_diff,
    ensure_stated_requirements,
    mark_blockers_candidate_resolved,
    mark_blockers_exhausted,
    record_check_results,
    record_verifier_report,
    should_suppress_verifier_call,
    snapshot as delta_snapshot,
    with_evidence_ledger,
)
from harness.aether2.traces.envelope import ObservationEnvelope, build_envelope
from harness.aether2.runtime.executor import ContainerExecutor
from harness.aether2.runtime.jobs import JobRegistry
from harness.aether2.traces.mirror import Mirror, MirrorNote, SemanticObservation
from harness.aether2.runtime.orientation import orient
from harness.aether2.runtime.prompts import (
    SYSTEM_PROMPT,
)
from harness.aether2.traces.receipts import ReceiptWriter
from harness.aether2.runtime.sessions import SessionRegistry
from harness.aether2.tools.permissions import PermissionManager
from harness.aether2.tools.registry import ToolRegistry
from harness.aether2.runtime.verify import replay_checks, verify_fresh_context
from harness.aether2.traces.redaction import _clean_hidden_refs

# --- Extracted sub-modules (pure extraction; public API unchanged) ---
from harness.aether2.control.requirements import (
    _current_evidence_ledger,
    _extract_stated_requirements,
    _extract_verifier_task_contract,
    _primary_requirement,
    _relevant_requirement,
    _tail_evidence_ledger,
)
from harness.aether2.control.completion import (
    _build_completion_contract,
    _build_completion_evidence_gate_report,
    _build_suppressed_blocker_report,
)
from harness.aether2.control.reasoning_trace import (
    _build_reasoning_trace_step,
    _response_cost,
    _response_usage,
    _trace_non_step_model_calls,
    _write_reasoning_trace,
)
from harness.aether2.control.verification_context import _ReadOnlyVerificationContext
from harness.aether2.control.runtime_support import (
    _SERVICE_MONITOR_WINDOW_SEC,
    _check_runs_in_workspace,
    _env_contract_drift,
    _env_contract_metadata,
    _job_status_payload,
    _monitor_persistent_runtime,
    _service_monitoring_candidate,
    _service_pid,
)
from harness.aether2.control.action_helpers import (
    _error_raw,
)
from harness.aether2.control.tail_helpers import (
    _build_tail_state,
    _check_result_summary,
    _collect_tail_events,
    _diff_to_dict,
    _estimate_transcript_tokens,
    _job_alive_safe,
    _model_requested_rebase,
    _model_requested_verification,
    _sync_fact_ledger_state,
    _update_plan_text,
)
from harness.aether2.control.execution_context import (
    ExecutionContext,
    RunResult,
    ToolInvocationRecord,
)
from harness.aether2.control.tool_dispatch import _execute_tool_calls

STEP_CAP = 120
MAX_VERIFICATION_ROUNDS = 3
CONTEXT_WINDOW_TOKENS = 128_000
_REQUIREMENT_PREVIEW_LIMIT = 4

def run_aether2_loop(
    task: TaskSpec,
    model_client: Any,
    executor: ContainerExecutor,
    *,
    deadline_ts: float,
    hook_registry: HookRegistry | None = None,
    permission_manager: PermissionManager | None = None,
    tool_registry: ToolRegistry | None = None,
) -> RunResult:
    """Run the orientation-to-finalize continuity loop for a single task against the live workspace."""

    if model_client is None:
        raise ValueError(
            "run_aether2_loop requires a model_client (e.g. runner.aether2.model_client.Aether2ModelClient); "
            "got None. Construct one from a model route before calling the loop."
        )

    started_at = time.monotonic()

    state_dir = task.workspace_root / ".aether2" / "state"
    raw_log_dir = task.workspace_root / ".aether2" / "raw_logs"
    receipts_root = task.task_dir / ".aether2" / "host_receipts"

    job_registry = JobRegistry(state_dir, backend=executor.backend, container_path_fn=executor.to_container_path)
    session_registry = SessionRegistry(state_dir, backend=executor.backend)
    ctx = ExecutionContext(
        executor=executor,
        job_registry=job_registry,
        session_registry=session_registry,
        raw_log_dir=raw_log_dir,
        hook_registry=hook_registry,
        permission_manager=permission_manager,
        tool_registry=tool_registry,
    )
    receipts = ReceiptWriter(receipts_root)

    orientation_snapshot = orient(executor)
    orientation_dict = orientation_snapshot.as_dict()
    stated_requirements = _extract_stated_requirements(task.instruction)
    verifier_task_contract = _extract_verifier_task_contract(task.instruction)
    seeded_ledger = ensure_stated_requirements(build_evidence_ledger(stated_requirements), stated_requirements)
    ctx.last_snapshot = with_evidence_ledger(ctx.last_snapshot, seeded_ledger)

    active_tool_schemas = ctx.tool_registry.tool_schemas()
    context = ContextManager(delta_state=ctx.last_snapshot)
    context.build_prefix(
        system_prompt=SYSTEM_PROMPT,
        task_instruction=task.instruction,
        orientation=orientation_dict,
        tool_schemas=active_tool_schemas,
    )
    context.set_completion_contract(_build_completion_contract(verifier_task_contract, seeded_ledger))

    mirror = Mirror()
    failure_tracker: dict[str, Any] = {"last_failure_signature": None, "last_failure_class": None, "streak": 0}
    job_ids: list[str] = []
    session_ids: list[str] = []
    seen_artifacts: set[str] = set()
    known_job_status: dict[str, tuple[bool, int | None]] = {}
    pending_tail_events: list[str] = []
    tool_invocations: list[ToolInvocationRecord] = []
    mirror_notes: list[MirrorNote] = []
    discrepancy_reports: list[Any] = []
    reasoning_trace_steps: list[dict[str, Any]] = []

    model_calls = 0
    tokens_cached = 0
    tokens_fresh = 0
    total_cost = 0.0
    compaction_count = 0
    verification_rounds = 0
    suppressed_verifier_calls = 0
    completion_precheck_rejections = 0
    recoveries = 0
    no_delta_streaks = 0

    finalize_reason: str | None = None
    finalize_summary = ""
    finalize_pass = False
    most_recent_checks: list[str] = []

    plan_text: str | None = None

    def record_exchange(
        call_idx: int,
        request_messages: list[dict[str, Any]],
        response: Any,
        *,
        tool_schemas: Any,
        call_role: str,
    ) -> None:
        receipts.record_model_exchange(
            call_idx,
            request_messages,
            response,
            tool_schemas=tool_schemas,
            call_role=call_role,
            tail_state=context.current_tail_payload(),
            ledger_state=_current_evidence_ledger(context),
        )

    def make_exchange_recorder(counter: dict[str, int]):
        def _record(
            request_messages: list[dict[str, Any]],
            response: Any,
            tool_schemas: Any,
            *,
            call_role: str,
            **_: Any,
        ) -> None:
            call_idx = counter["next"]
            counter["next"] += 1
            record_exchange(
                call_idx,
                request_messages,
                response,
                tool_schemas=tool_schemas,
                call_role=call_role,
            )

        return _record

    def append_trace_step(
        *,
        step_index: int | None,
        model_call_idx: int,
        call_role: str,
        response: Any,
        visible_tail_state: Mapping[str, Any],
        completion_contract: Mapping[str, Any],
        pre_step_ledger: Mapping[str, Any],
        post_step_ledger: Mapping[str, Any],
        tool_invocations_for_step: list[ToolInvocationRecord],
        task_done_call: tuple[dict[str, Any], ObservationEnvelope] | None,
        decision_kind: str,
        finalize_reason: str | None = None,
        verification_round_index: int | None = None,
        blocker_state: Mapping[str, Any] | None = None,
    ) -> None:
        reasoning_trace_steps.append(
            _build_reasoning_trace_step(
                step=step_index,
                model_call_idx=model_call_idx,
                call_role=call_role,
                response=response,
                input_digests=context.digest_snapshot(),
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=pre_step_ledger,
                post_step_ledger=post_step_ledger,
                tool_invocations=tool_invocations_for_step,
                task_done_call=task_done_call,
                decision_kind=decision_kind,
                plan_text=plan_text,
                model_exchange_ref=str(receipts.receipts_dir / f"model_exchange_{model_call_idx}.json"),
                verification_round_index=verification_round_index,
                blocker_state=blocker_state,
                finalize_reason=finalize_reason,
            )
        )

    step = 0
    while step < STEP_CAP:
        elapsed_sec = time.monotonic() - started_at
        remaining_sec = deadline_ts - time.time()
        if remaining_sec <= 0:
            finalize_reason = "budget_exhaustion"
            break

        step += 1

        if context.transcript:
            window_used_frac = (context.prefix.token_estimate + _estimate_transcript_tokens(context)) / CONTEXT_WINDOW_TOKENS
            if should_rebase(window_used_frac, False):
                _sync_fact_ledger_state(context, ctx)
                compaction_counter = {"next": model_calls + 1}
                context = rebase(
                    context,
                    model_client,
                    record_exchange=make_exchange_recorder(compaction_counter),
                )
                compaction_count += 1
                model_calls = compaction_counter["next"] - 1

        visible_ledger_before = _current_evidence_ledger(context)
        visible_tail_state = _build_tail_state(
            plan_text=plan_text,
            elapsed_sec=elapsed_sec,
            remaining_sec=remaining_sec,
            evidence_ledger=visible_ledger_before,
            mirror=mirror,
            streak=mirror.streak,
            job_registry=job_registry,
            session_registry=session_registry,
            job_ids=job_ids,
            session_ids=session_ids,
            note=None,
            events=pending_tail_events,
        )
        completion_contract = _build_completion_contract(verifier_task_contract, visible_ledger_before)
        messages = [*context.message_history()]
        tail_text = context.render_tail(visible_tail_state, completion_contract=completion_contract)
        if tail_text:
            messages = [*messages, {"role": "system", "content": tail_text}]
        pending_tail_events = []

        response = model_client.call(messages, active_tool_schemas, cache_prefix_len=context.prefix.token_estimate)
        model_calls += 1
        record_exchange(model_calls, messages, response, tool_schemas=active_tool_schemas, call_role="normal")
        usage = _response_usage(response)
        tokens_cached += int(usage.get("cached_input_tokens", 0))
        tokens_fresh += int(usage.get("fresh_input_tokens", 0))
        total_cost += _response_cost(response)

        assistant_message: dict[str, Any] = {"role": "assistant", "content": response.text}
        if response.tool_calls:
            assistant_message["tool_calls"] = [dict(tool_call) for tool_call in response.tool_calls]
        context.append_turn(assistant_message)

        plan_text = _update_plan_text(plan_text, response.text)

        if _model_requested_rebase(response.text, response.tool_calls):
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="normal",
                response=response,
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=visible_ledger_before,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=[],
                task_done_call=None,
                decision_kind="rebase_request",
            )
            _sync_fact_ledger_state(context, ctx)
            compaction_counter = {"next": model_calls + 1}
            context = rebase(
                context,
                model_client,
                record_exchange=make_exchange_recorder(compaction_counter),
            )
            compaction_count += 1
            model_calls = compaction_counter["next"] - 1
            continue

        if _model_requested_verification(response.text, response.tool_calls):
            finalize_reason = "verification_requested"
            finalize_summary = response.text
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="normal",
                response=response,
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=visible_ledger_before,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=[],
                task_done_call=None,
                decision_kind="verification_requested",
                finalize_reason=finalize_reason,
            )
            break

        if not response.tool_calls:
            finalize_reason = "implicit_stop"
            finalize_summary = response.text
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="normal",
                response=response,
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=visible_ledger_before,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=[],
                task_done_call=None,
                decision_kind="implicit_stop",
                finalize_reason=finalize_reason,
            )
            break

        step_tool_invocation_start = len(tool_invocations)
        failure_tracker, recoveries, no_delta_streaks, new_checks, task_done_call = _execute_tool_calls(
            response=response,
            response_messages=messages,
            step=step,
            executor=executor,
            ctx=ctx,
            context=context,
            receipts=receipts,
            mirror=mirror,
            tool_invocations=tool_invocations,
            mirror_notes=mirror_notes,
            failure_tracker=failure_tracker,
            recoveries=recoveries,
            no_delta_streaks=no_delta_streaks,
            job_ids=job_ids,
            session_ids=session_ids,
            stated_requirements=stated_requirements,
            plan_text=plan_text,
            elapsed_sec=elapsed_sec,
            remaining_sec=remaining_sec,
            model_request_index=model_calls,
        )
        if new_checks:
            most_recent_checks = new_checks

        step_tool_invocations = tool_invocations[step_tool_invocation_start:]

        pending_tail_events.extend(
            _collect_tail_events(
                ctx=ctx,
                job_registry=job_registry,
                job_ids=job_ids,
                seen_artifacts=seen_artifacts,
                known_job_status=known_job_status,
            )
        )

        if task_done_call is not None:
            finalize_reason = "task_done"
            finalize_summary = str(task_done_call[0].get("summary", ""))
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="normal",
                response=response,
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=visible_ledger_before,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=step_tool_invocations,
                task_done_call=task_done_call,
                decision_kind="task_done",
                finalize_reason=finalize_reason,
            )
            break

        append_trace_step(
            step_index=step,
            model_call_idx=model_calls,
            call_role="normal",
            response=response,
            visible_tail_state=visible_tail_state,
            completion_contract=completion_contract,
            pre_step_ledger=visible_ledger_before,
            post_step_ledger=_current_evidence_ledger(context),
            tool_invocations_for_step=step_tool_invocations,
            task_done_call=None,
            decision_kind="tool_calls",
        )

    if finalize_reason is None:
        finalize_reason = "budget_exhaustion"
        finalize_summary = "step cap safety rail reached before an explicit completion claim"

    if finalize_reason == "budget_exhaustion":
        check_results = replay_checks(most_recent_checks, executor) if most_recent_checks else []
        closing_messages = [
            *context.message_history(),
            {
                "role": "system",
                "content": (
                    "Wall-clock deadline reached. Here are the results of replaying your "
                    "most recently declared checks (if any). This is your final turn."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"checks_results": [result.__dict__ for result in check_results]},
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ),
            },
        ]
        response = model_client.call(closing_messages, [], cache_prefix_len=context.prefix.token_estimate)
        model_calls += 1
        record_exchange(model_calls, closing_messages, response, tool_schemas=[], call_role="closing")
        usage = _response_usage(response)
        tokens_cached += int(usage.get("cached_input_tokens", 0))
        tokens_fresh += int(usage.get("fresh_input_tokens", 0))
        total_cost += _response_cost(response)
        finalize_summary = response.text
        finalize_pass = bool(check_results) and all(
            result.exit_code == 0 for result in check_results
        )
        closing_elapsed_sec = time.monotonic() - started_at
        current_ledger = _current_evidence_ledger(context)
        append_trace_step(
            step_index=step if step > 0 else None,
            model_call_idx=model_calls,
            call_role="closing",
            response=response,
            visible_tail_state=_build_tail_state(
                plan_text=plan_text,
                elapsed_sec=closing_elapsed_sec,
                remaining_sec=deadline_ts - time.time(),
                evidence_ledger=current_ledger,
                mirror=mirror,
                streak=mirror.streak,
                job_registry=job_registry,
                session_registry=session_registry,
                job_ids=job_ids,
                session_ids=session_ids,
                note=None,
                events=pending_tail_events,
            ),
            completion_contract=_build_completion_contract(verifier_task_contract, current_ledger),
            pre_step_ledger=current_ledger,
            post_step_ledger=current_ledger,
            tool_invocations_for_step=[],
            task_done_call=None,
            decision_kind="closing",
            finalize_reason=finalize_reason,
        )
    else:
        rounds = 0
        claim_summary = finalize_summary
        claim_checks = most_recent_checks
        while rounds < MAX_VERIFICATION_ROUNDS:
            rounds += 1
            verification_rounds += 1
            check_results = replay_checks(claim_checks, executor) if claim_checks else []
            verification_ledger = _current_evidence_ledger(context)
            successful_check_summaries = [
                _check_result_summary(result)
                for result in check_results
                if getattr(result, "exit_code", None) == 0 and not bool(getattr(result, "timed_out", False))
            ]
            if check_results:
                verification_ledger = record_check_results(
                    verification_ledger,
                    requirement=_primary_requirement(verification_ledger, stated_requirements),
                    check_results=check_results,
                    step=step,
                    raw_log_path=None,
                )
            curr_snapshot = delta_snapshot(task.workspace_root)
            workspace_diff = delta_diff(ctx.last_snapshot, curr_snapshot)
            relevant_artifact_paths = [*workspace_diff.added_paths, *workspace_diff.modified_paths]
            verification_ledger = mark_blockers_candidate_resolved(
                verification_ledger,
                step=step,
                relevant_failed_checks=successful_check_summaries,
                relevant_artifact_paths=relevant_artifact_paths,
            )
            curr_snapshot = with_evidence_ledger(curr_snapshot, verification_ledger)
            service_monitoring, monitored_snapshot = _monitor_persistent_runtime(
                ctx=ctx,
                job_registry=job_registry,
                session_registry=session_registry,
                job_ids=job_ids,
                session_ids=session_ids,
                claim_checks=claim_checks,
                check_results=check_results,
                remaining_sec=deadline_ts - time.time(),
                start_snapshot=curr_snapshot,
            )
            curr_snapshot = monitored_snapshot
            workspace_diff = delta_diff(ctx.last_snapshot, curr_snapshot)
            relevant_artifact_paths = [*workspace_diff.added_paths, *workspace_diff.modified_paths]
            ctx.last_snapshot = curr_snapshot
            context.delta_state = curr_snapshot
            verification_orientation_dict = orient(executor).as_dict()

            action_digest = {
                "environment_contract": _env_contract_drift(orientation_dict, verification_orientation_dict),
                "service_monitoring": service_monitoring,
                "tool_calls": [
                    {"step": record.step, "tool": record.tool_name, "arguments": record.arguments}
                    for record in tool_invocations[-20:]
                ]
            }
            completion_gate_report = _build_completion_evidence_gate_report(
                verification_ledger,
                stated_requirements=stated_requirements,
                finalize_reason=finalize_reason,
                check_results=check_results,
                action_digest=action_digest,
            )
            if completion_gate_report is not None:
                completion_precheck_rejections += 1
                discrepancy_report = completion_gate_report
                updated_ledger = record_verifier_report(
                    _current_evidence_ledger(context),
                    report=discrepancy_report,
                    verifier_ref=f"completion_evidence_gate_round={verification_rounds}",
                    step=step,
                    exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                )
                if rounds >= MAX_VERIFICATION_ROUNDS:
                    updated_ledger = mark_blockers_exhausted(
                        updated_ledger,
                        step=step,
                        exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                        force=True,
                    )
            elif should_suppress_verifier_call(
                verification_ledger,
                relevant_failed_checks=successful_check_summaries,
                relevant_artifact_paths=relevant_artifact_paths,
            ):
                suppressed_verifier_calls += 1
                completion_precheck_rejections += 1
                if rounds >= MAX_VERIFICATION_ROUNDS:
                    verification_ledger = mark_blockers_exhausted(
                        verification_ledger,
                        step=step,
                        exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                        force=True,
                    )
                discrepancy_report = _build_suppressed_blocker_report(verification_ledger)
                updated_ledger = verification_ledger
            else:
                verifier_counter = {"next": model_calls + 1}
                discrepancy_report = verify_fresh_context(
                    verifier_task_contract,
                    orientation_dict,
                    _diff_to_dict(workspace_diff),
                    {"summary": claim_summary, "trigger": finalize_reason},
                    check_results,
                    action_digest,
                    model_client,
                    inspection_ctx=_ReadOnlyVerificationContext(ctx, receipts),
                    record_exchange=make_exchange_recorder(verifier_counter),
                    stated_requirements=stated_requirements,
                )
                model_calls = verifier_counter["next"] - 1
                updated_ledger = record_verifier_report(
                    _current_evidence_ledger(context),
                    report=discrepancy_report,
                    verifier_ref=f"verification_round={verification_rounds}",
                    step=step,
                    exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                )
                if discrepancy_report.has_discrepancies and rounds >= MAX_VERIFICATION_ROUNDS:
                    updated_ledger = mark_blockers_exhausted(
                        updated_ledger,
                        step=step,
                        exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                        force=True,
                    )
            discrepancy_reports.append(discrepancy_report)
            ctx.last_snapshot = with_evidence_ledger(ctx.last_snapshot, updated_ledger)
            context.delta_state = ctx.last_snapshot

            remaining_sec = deadline_ts - time.time()
            if not discrepancy_report.has_discrepancies or remaining_sec <= 0 or rounds >= MAX_VERIFICATION_ROUNDS:
                finalize_pass = not discrepancy_report.has_discrepancies
                finalize_summary = claim_summary if finalize_pass else discrepancy_report.summary
                break

            report_message = {
                "role": "system",
                "content": json.dumps(
                    _clean_hidden_refs(
                        {
                            "verification_blocker": discrepancy_report.summary,
                            "verification_report": {
                                "requirements": [item.__dict__ for item in discrepancy_report.requirements],
                                "reason_codes": list(discrepancy_report.reason_codes),
                                "summary": discrepancy_report.summary,
                            },
                            "checks_results": [result.__dict__ for result in check_results],
                            "time_remaining_sec": remaining_sec,
                        }
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ),
            }
            context.append_turn(report_message)

            messages = [*context.message_history()]
            repair_pre_ledger = _current_evidence_ledger(context)
            repair_completion_contract = _build_completion_contract(verifier_task_contract, repair_pre_ledger)
            repair_tail_state = context.current_tail_payload()
            response = model_client.call(messages, active_tool_schemas, cache_prefix_len=context.prefix.token_estimate)
            model_calls += 1
            record_exchange(model_calls, messages, response, tool_schemas=active_tool_schemas, call_role="repair")
            usage = _response_usage(response)
            tokens_cached += int(usage.get("cached_input_tokens", 0))
            tokens_fresh += int(usage.get("fresh_input_tokens", 0))
            total_cost += _response_cost(response)

            assistant_message = {"role": "assistant", "content": response.text}
            if response.tool_calls:
                assistant_message["tool_calls"] = [dict(tool_call) for tool_call in response.tool_calls]
            context.append_turn(assistant_message)

            claim_summary = response.text
            if _model_requested_rebase(response.text, response.tool_calls):
                append_trace_step(
                    step_index=step,
                    model_call_idx=model_calls,
                    call_role="repair",
                    response=response,
                    visible_tail_state=repair_tail_state,
                    completion_contract=repair_completion_contract,
                    pre_step_ledger=repair_pre_ledger,
                    post_step_ledger=_current_evidence_ledger(context),
                    tool_invocations_for_step=[],
                    task_done_call=None,
                    decision_kind="repair_rebase_request",
                    verification_round_index=rounds,
                    blocker_state={
                        "verification_summary": discrepancy_report.summary,
                        "reason_codes": list(discrepancy_report.reason_codes),
                    },
                )
                _sync_fact_ledger_state(context, ctx)
                compaction_counter = {"next": model_calls + 1}
                context = rebase(
                    context,
                    model_client,
                    record_exchange=make_exchange_recorder(compaction_counter),
                )
                compaction_count += 1
                model_calls = compaction_counter["next"] - 1
                continue

            repair_step_tool_invocation_start = len(tool_invocations)
            previous_claim_checks = list(claim_checks)
            failure_tracker, recoveries, no_delta_streaks, new_checks, new_task_done = _execute_tool_calls(
                response=response,
                response_messages=messages,
                step=step,
                executor=executor,
                ctx=ctx,
                context=context,
                receipts=receipts,
                mirror=mirror,
                tool_invocations=tool_invocations,
                mirror_notes=mirror_notes,
                failure_tracker=failure_tracker,
                recoveries=recoveries,
                no_delta_streaks=no_delta_streaks,
                job_ids=job_ids,
                session_ids=session_ids,
                stated_requirements=stated_requirements,
                plan_text=plan_text,
                elapsed_sec=time.monotonic() - started_at,
                remaining_sec=remaining_sec,
                model_request_index=model_calls,
            )
            repair_step_tool_invocations = tool_invocations[repair_step_tool_invocation_start:]
            if new_task_done is not None:
                claim_summary = str(new_task_done[0].get("summary", claim_summary))
            if new_checks:
                claim_checks = new_checks
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="repair",
                response=response,
                visible_tail_state=repair_tail_state,
                completion_contract=repair_completion_contract,
                pre_step_ledger=repair_pre_ledger,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=repair_step_tool_invocations,
                task_done_call=new_task_done,
                decision_kind="repair_task_done" if new_task_done is not None else ("repair_tool_calls" if response.tool_calls else "repair_implicit_stop"),
                verification_round_index=rounds,
                blocker_state={
                    "verification_summary": discrepancy_report.summary,
                    "reason_codes": list(discrepancy_report.reason_codes),
                    "previous_checks": previous_claim_checks,
                },
                finalize_reason=finalize_reason if new_task_done is not None else None,
            )
            if new_task_done is None and not response.tool_calls:
                # implicit stop during a verification round: treat as resubmission with no new checks
                continue

    job_survival = all(_job_alive_safe(job_registry, job_id) for job_id in job_ids) if job_ids else True
    session_survival = (
        all(sid in session_registry.list_session_ids() for sid in session_ids) if session_ids else True
    )

    wall_time = time.monotonic() - started_at
    step_model_call_indices = {
        int(step_payload["model_call_idx"])
        for step_payload in reasoning_trace_steps
        if isinstance(step_payload.get("model_call_idx"), int)
    }
    reasoning_trace_ref = str(
        _write_reasoning_trace(
            trace_path=receipts_root / "traces" / "reasoning_trace.json",
            task_id=task.task_id,
            task_dir=task.task_dir,
            workspace_root=task.workspace_root,
            receipts_root=receipts_root,
            steps=reasoning_trace_steps,
            non_step_model_calls=_trace_non_step_model_calls(
                receipts_dir=receipts.receipts_dir,
                step_model_call_indices=step_model_call_indices,
            ),
            model_call_count=model_calls,
            finalize_reason=finalize_reason,
            finalize_pass=finalize_pass,
        )
    )

    return RunResult(
        verifier_clean=finalize_pass,
        finalize_reason=finalize_reason,
        summary=finalize_summary,
        steps=step,
        model_calls=model_calls,
        tokens_cached=tokens_cached,
        tokens_fresh=tokens_fresh,
        cost=total_cost,
        wall_time=wall_time,
        no_delta_streaks=no_delta_streaks,
        verification_rounds=verification_rounds,
        suppressed_verifier_calls=suppressed_verifier_calls,
        completion_precheck_rejections=completion_precheck_rejections,
        recoveries=recoveries,
        compaction_count=compaction_count,
        job_survival=job_survival,
        session_survival=session_survival,
        reasoning_trace_ref=reasoning_trace_ref,
        tool_invocations=tool_invocations,
        mirror_notes=mirror_notes,
        discrepancy_reports=discrepancy_reports,
    )

__all__ = ["ExecutionContext", "RunResult", "ToolInvocationRecord", "run_aether2_loop"]
