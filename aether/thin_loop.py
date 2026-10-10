"""Small matched Thin Frontier execution loop.

The loop accepts the same ``EnvMap``, executor, ``ModelHooks``-compatible
solver hook, action schema, budgets, and ledger-owned evidence machinery as the
incumbent.  It deliberately has no verifier callback and never performs a
semantic completion decision.  A mechanically admissible submission is
returned as ``submitted`` for external grading; it is never returned as a task
pass.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Mapping, Protocol

from .completion import CompletionDecision
from .context_file.adapter import apply_turn_surface
from .context_tree.adapter import ContextTreeAdapter, ContextTreeContinuityError
from .context_tree.epoch import MTreeEpochOverflow
from .completion_disposition import (
    COMPLETION_DISPOSITION_V1,
    CONTROL as COMPLETION_DISPOSITION_CONTROL,
    evaluate_completion_dispositions,
)
from .independent_review_projection import (
    INDEPENDENT_REVIEW_KEY,
    project_independent_review,
)
from .completion_signal import (
    CONTROL as COMPLETION_SIGNAL_CONTROL,
    completion_signal_context,
    normalize_mode as normalize_completion_signal_mode,
)
from .completion_record import (
    COMPLETION_RECORD_OFF,
    ensure_initial_nonadherence_receipt,
    project_completion_record_context,
    record_finish_metadata,
)
from .context_cleanup import CONTEXT_CLEANUP_MODES, apply_context_cleanup
from .delivery_hygiene import (
    CONTROL as DELIVERY_HYGIENE_CONTROL,
    DELIVERY_HYGIENE_V1,
    delivery_hygiene_context,
    normalize_mode as normalize_delivery_hygiene_mode,
)
from .execution import Executor
from .failed_observation_disposition import (
    CONTROL as FAILED_OBSERVATION_CONTROL,
    SUPPORTED_MODES as SUPPORTED_FAILED_OBSERVATION_MODES,
    current_candidate_failed_observations,
)
from .glm_model_view import MODEL_VIEW_CONTROL, normalize_model_view_mode
from .oracle_finish_hold import (
    CONTROL as ORACLE_FINISH_RESPONSE_CONTROL,
    ORACLE_HOLD_ONCE_V1,
    current_v1b_finding_ids,
    mark_v1b_obligations_current,
    normalize_mode as normalize_oracle_finish_response_mode,
    record_finish_hold as record_oracle_finish_hold,
    record_validated_disposition as record_validated_v1b_disposition,
    should_hold_finish as should_hold_oracle_finish,
    validate_disposition as validate_v1b_disposition,
)
from .kernel import AetherNextKernel
from .kernel_verifier import run_model_verifier_if_available
from .kernel_turns import run_act_turn, run_submit_turn
from .ledger import ExecutionLedger, Receipt
from .model_hooks import ModelOutputError, ModelProviderError
from .persistent_flat_advanced import decode_error_note
from .long_command_mode import selected_long_command_mode
from .persistent_provider_protocol import persistent_filter_context_for_tool_surface
from .persistent_submission import (
    record_persistent_submission_claim,
    validate_persistent_submission_binding,
)
from .tolerant_arguments import compact_interpreted_arguments
from .persistent_runtime import (
    SOLVER_ASYNC_CONTROL,
    SOLVER_ASYNC_SERIAL_JOBS_V1,
    SOLVER_ASYNC_INDEPENDENT_JOBS_V1,
    SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1,
    SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1,
    SOLVER_WORKING_CONTEXT_MODES,
    SOLVER_WORKING_CONTEXT_OFF,
    build_persistent_runtime,
)
from .route_preflight import preflight_proof_routes
from .run_cancellation import RunCancellationRequested, raise_if_run_cancelled
from .deadline_visibility import visible_clock_fields
from .env_lean import CONTROL as ENV_CONTROL
from .packet_lean import CONTROL as PACKET_CONTROL, lean_packet, recent_changed_paths
from . import protocol_resilience as _resilience
from .run_deadline import (
    KernelRunTimeout,
    raise_if_run_deadline_exceeded,
    remaining_run_s,
)
from .runtime_ir import CompiledRuntime, EnvMap, SolverTurn
from .submission_coherence import evaluate_submission_coherence
from .verifier import SOLVER_EVIDENCE_GATHERING_VERDICTS, SOLVER_REPAIR_VERDICTS
from .task_contract import TaskClause, TaskContract
from .thin_context import build_thin_context, build_thin_solver_messages, thin_prefix_messages
from .tracing import RunTrace
from .world import WorldState


THIN_TERMINAL_VERIFIER_CONTROL = "control"
THIN_TERMINAL_VERIFIER_V1 = "terminal_verifier_v1"
THIN_TERMINAL_VERIFIER_MODES = frozenset({
    THIN_TERMINAL_VERIFIER_CONTROL,
    THIN_TERMINAL_VERIFIER_V1,
})
THIN_TERMINAL_VERIFIER_MAX_CYCLES = 3


def _normalize_terminal_verifier_mode(value: str | None) -> str:
    mode = str(value or THIN_TERMINAL_VERIFIER_CONTROL).strip().lower()
    if mode not in THIN_TERMINAL_VERIFIER_MODES:
        raise ValueError(f"unsupported Thin terminal verifier mode: {value!r}")
    return mode


def _next_terminal_verifier_cycle(completed_cycles: int) -> int | None:
    """Return the next 1-based VF1 cycle, or None after the sealed ceiling."""
    count = int(completed_cycles)
    if count < 0:
        raise ValueError("terminal verifier cycle count must be non-negative")
    if count >= THIN_TERMINAL_VERIFIER_MAX_CYCLES:
        return None
    return count + 1


class ThinSolverHooks(Protocol):
    """The only model interface Thin needs: one canonical Solver turn."""

    def solve(self, messages: list[dict[str, str]], compiled: CompiledRuntime) -> SolverTurn:
        ...


@dataclass(frozen=True)
class ThinLoopConfig:
    """Run budgets and identity forwarded from the shared launch boundary."""

    max_steps: int | None = 24
    max_solver_turns: int | None = None
    max_accepted_task_actions: int | None = None
    runtime_identity: Mapping[str, Any] | None = None
    run_timeout_s: float | None = None
    # Opt-in (deadline_visibility): the hard agent timeout, shown to the model as facts only.
    visible_deadline_sec: float | None = None
    # Opt-in (packet_lean_v1): shorten the per-turn workspace listing / old evidence rows.
    packet_mode: str = PACKET_CONTROL
    # Opt-in (env_lean_v1): counts and a fixed toolchain list instead of the full environment inventories.
    env_mode: str = ENV_CONTROL
    # Opt-in (protocol_resilience): an unparseable turn becomes a failed observation, not a terminal.
    protocol_resilience: str = _resilience.CONTROL
    run_started_monotonic: float | None = None
    refresh_runtime_operation_status: bool = False
    probe_runtime_capabilities: bool = True
    cancellation_event: Any | None = None
    solver_reanchor_mode: str = "current_full"
    solver_context_mode: str = "full"
    context_cleanup_mode: str = "off"
    completion_record_mode: str = COMPLETION_RECORD_OFF
    solver_completion_signal_mode: str = COMPLETION_SIGNAL_CONTROL
    solver_reasoning_mode: str = "control"
    solver_async_mode: str = SOLVER_ASYNC_CONTROL
    solver_task_contract_mode: str = "raw_task_control"
    solver_reality_transport_mode: str = "full_snapshot_control"
    solver_working_context_mode: str = SOLVER_WORKING_CONTEXT_OFF
    solver_hosted_tool_search_mode: str = "control"
    solver_model_view_mode: str = MODEL_VIEW_CONTROL
    failed_observation_disposition_mode: str = FAILED_OBSERVATION_CONTROL
    semantic_assistance: Any | None = None
    solver_tool_surface_mode: str = "control"
    solver_long_command_mode: str | None = None
    terminal_verifier_mode: str = THIN_TERMINAL_VERIFIER_CONTROL
    oracle_finish_response_mode: str = ORACLE_FINISH_RESPONSE_CONTROL
    delivery_hygiene_mode: str = DELIVERY_HYGIENE_CONTROL
    context_tree_adapter: Any | None = None
    claim_ledger_controller: Any | None = None  # opt-in CHALLENGER (aether.challenger_runtime)
    run_evidence_finish_observer: Any | None = None  # host-owned opt-in state snapshot callback


@dataclass(frozen=True)
class ThinLoopResult:
    """Preparation/runtime result; external grading owns task success."""

    status: str
    step: int
    env_digest: str
    blockers: tuple[str, ...] = ()
    receipts: tuple[Receipt, ...] = ()
    accounting: Mapping[str, int] | None = None
    requests: tuple[Mapping[str, Any], ...] = ()
    external_grade: str = "not_run"

    def as_dict(self) -> dict[str, Any]:
        return {
            "runtime_mode": "thin_frontier",
            "status": self.status,
            "step": self.step,
            "env_digest": self.env_digest,
            "blockers": list(self.blockers),
            "external_grade": self.external_grade,
            "accounting": dict(self.accounting or {}),
            "requests": [deepcopy(dict(item)) for item in self.requests],
            "receipts": [
                {
                    "receipt_id": receipt.receipt_id,
                    "step": receipt.step,
                    "kind": receipt.kind,
                    "success": receipt.success,
                    "summary": receipt.summary,
                    "state_change": receipt.state_change,
                    "failure_class": receipt.failure_class,
                    "payload": deepcopy(dict(receipt.payload)),
                }
                for receipt in self.receipts
            ],
        }


def _identity_for(config: ThinLoopConfig, envmap: EnvMap) -> dict[str, Any]:
    identity = dict(config.runtime_identity or {})
    identity.setdefault("workspace_id", envmap.workspace_root)
    identity.setdefault("environment_id", envmap.digest())
    identity.setdefault("runtime_path", "persistent_v0")
    identity.setdefault("identity_complete", bool(
        identity.get("task_id") and identity.get("run_id") and identity.get("primary_agent_id")
    ))
    return identity


def _world_state(envmap: EnvMap, compiled: CompiledRuntime) -> WorldState:
    task_contract = compiled.task_contract or TaskContract.create(
        compiled.task_prompt,
        (TaskClause("compiled:objective", compiled.task_prompt),),
    )
    return WorldState(
        task_contract=task_contract,
        env_facts={
            "workspace_root": envmap.workspace_root,
            "network_scope": envmap.network_scope,
            "visible_file_count": len(envmap.visible_files),
            "visible_dir_count": len(envmap.visible_dirs),
        },
    )


def _result(
    status: str,
    *,
    step: int,
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    blockers: tuple[str, ...] = (),
    requests: list[Mapping[str, Any]],
) -> ThinLoopResult:
    return ThinLoopResult(
        status=status,
        step=step,
        env_digest=compiled.env_digest,
        blockers=blockers,
        receipts=ledger.all_receipts(),
        accounting=ledger.accounting_snapshot(),
        requests=tuple(deepcopy(dict(item)) for item in requests),
    )


def _record_m_tree_receipt_note(adapter: Any | None, receipt: Receipt) -> None:
    """Copy only actual public protocol/refusal/gate feedback into the tree."""
    if adapter is None:
        return
    kind = str(receipt.kind)
    is_refusal = (
        kind.startswith("refused_")
        or kind in {
            "action_validation", "safety_block", "integrity_block",
            "action_budget_refused", "persistent_action_execution_block",
            "turn_validation",
        }
    )
    is_gate = kind in {
        "m_tree_epoch_overflow",
        "solver_turn_budget_exhausted",
        "thin_submission_blocked",
        "thin_failed_observation_disposition_block",
        "thin_failed_observation_dispositions",
        "v1b_oracle_finish_reentry",
        "v1b_oracle_disposition_block",
        "v1b_oracle_resolution_block",
        "thin_terminal_verifier_cycle_exhausted",
        "thin_terminal_verifier_missing",
        "thin_terminal_verifier_gate_not_ready",
        "thin_terminal_verifier_evidence_reentry",
    }
    if (is_refusal or is_gate) and str(receipt.summary):
        adapter.record_note(str(receipt.summary))


def _canonical_tree_note(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str,
    )


def _record_submission_block(
    ledger: ExecutionLedger,
    *,
    step: int,
    reason: str,
    detail: str,
    binding_present: bool,
    context_tree_adapter: Any | None = None,
) -> None:
    receipt = Receipt(
        receipt_id=f"step-{step}:thin_submission_blocked",
        step=step,
        kind="thin_submission_blocked",
        success=False,
        summary=f"Thin submission blocked: {reason}",
        failure_class=reason,
        payload={
            "reason_code": reason,
            "detail": detail,
            "binding_present": bool(binding_present),
            "semantic_decision_invoked": False,
            "external_grader_pending": True,
        },
    )
    ledger.record(receipt)
    _record_m_tree_receipt_note(context_tree_adapter, receipt)


def _record_submission_ready(
    ledger: ExecutionLedger,
    *,
    step: int,
    decision: CompletionDecision,
    context_tree_adapter: Any | None = None,
) -> None:
    receipt = Receipt(
        receipt_id=f"step-{step}:thin_submitted",
        step=step,
        kind="thin_submitted",
        success=True,
        summary="Thin mechanically submitted the current candidate for external grading",
        payload={
            "mechanical_gate_ready": True,
            "used_check_ids": list(decision.used_check_ids),
            "external_grader_pending": True,
            "task_pass_not_claimed": True,
            "semantic_decision_invoked": False,
        },
    )
    ledger.record(receipt)
    _record_m_tree_receipt_note(context_tree_adapter, receipt)


def _record_protocol_failure(
    ledger: ExecutionLedger,
    *,
    step: int,
    error: BaseException,
    kind: str = "thin_protocol_failure",
) -> None:
    raw = str(getattr(error, "cause_message", "") or getattr(error, "last_raw_solver_output", ""))
    if not raw:
        raw = str(error)
    ledger.record(Receipt(
        receipt_id=f"step-{step}:{kind}",
        step=step,
        kind=kind,
        success=False,
        summary=f"Thin Solver boundary failed before task dispatch: {error}",
        failure_class=(
            "solver_protocol_error" if isinstance(error, ModelOutputError)
            else _context_overflow_code(error) if _context_overflow_code(error)
            else "harness_context_capacity" if _is_context_capacity_failure(error)
            else "provider_route_identity_mismatch" if _is_route_identity_failure(error)
            else "provider_failure"
        ),
        payload={
            "error_type": type(error).__name__,
            "error": str(error)[:2000],
            "raw_output_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "model_output_available": bool(raw),
            "task_action_dispatched": False,
        },
    ))


def _record_context_policy_events(hooks: Any, ledger: ExecutionLedger, *, step: int) -> None:
    """Record GLM-written checkpoints (or their truthful failure) as ledger receipts.

    The content is stored unchanged in the receipt payload, so it stays
    retrievable through query_history and read_output after the transcript
    itself has been compacted.
    """
    drain = getattr(hooks, "drain_solver_context_events", None)
    if not callable(drain):
        return
    for event in drain():
        if event.get("kind") == "managed_context_checkpoint":
            ordinal = int(event["ordinal"])
            attempts = int(event.get("attempts") or 1)
            for attempt in range(1, attempts + 1):
                ledger.record_accounting(
                    receipt_id=f"step-{step}:managed_context_checkpoint_call:{ordinal}:{attempt}",
                    step=step,
                    counter="solver_checkpoint_calls",
                    event="context_checkpoint_call",
                )
            payload = {k: v for k, v in event.items() if k != "kind"}
            payload.update({"semantic_decision_invoked": False, "content_edited_by_runtime": False})
            ledger.record(Receipt(
                receipt_id=f"step-{step}:managed_context_checkpoint:{ordinal}",
                step=step,
                kind="managed_context_checkpoint",
                success=True,
                summary=(
                    f"Solver wrote checkpoint {ordinal} at step {event.get('step')} "
                    f"({event.get('content_bytes')} bytes)"
                ),
                payload=payload,
            ))
        elif event.get("kind") == "managed_context_checkpoint_failed":
            ordinal = int(event["attempted_ordinal"])
            for attempt in range(1, len(event.get("attempts") or ()) + 1):
                ledger.record_accounting(
                    receipt_id=f"step-{step}:managed_context_checkpoint_call:{ordinal}:{attempt}",
                    step=step,
                    counter="solver_checkpoint_calls",
                    event="context_checkpoint_call",
                )
            ledger.record(Receipt(
                receipt_id=f"step-{step}:managed_context_checkpoint_failed:{ordinal}",
                step=step,
                kind="managed_context_checkpoint_failed",
                success=False,
                summary="Solver checkpoint was not produced; transcript left uncut",
                failure_class="managed_context_checkpoint_failed",
                payload={k: v for k, v in event.items() if k != "kind"},
            ))


def _is_context_capacity_failure(error: BaseException) -> bool:
    return (
        getattr(error, "cause_type", "") == "ChatContextCapacityError"
        or "harness_context_capacity:" in str(getattr(error, "cause_message", "") or error)
    )


def _context_overflow_code(error: BaseException) -> str:
    """Code of an arm-owned provider capacity failure (M-TREE epoch or context file), else ''."""
    if getattr(error, "cause_type", "") != "ChatContextCapacityError":
        return ""
    message = str(getattr(error, "cause_message", "") or "")
    return next((
        code for code in ("m_tree_epoch_overflow", "managed_context_context_overflow")
        if message.startswith(f"{code}:")
    ), "")


def _is_route_identity_failure(error: BaseException) -> bool:
    return getattr(error, "cause_type", "") == "ChatRouteIdentityError"


OUTPUT_CAP_MESSAGE = (
    "Your previous response reached the output limit before producing a tool call. "
    "Reply with exactly one tool call."
)


def _is_output_cap_truncation(error: BaseException | None) -> bool:
    """True when the provider cut the turn at the output cap (not a schema error)."""
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if (
            getattr(error, "code", "") == "provider_output_truncated"
            and getattr(error, "detail", "") in {"length", "max_tokens"}
        ):
            return True
        error = error.__cause__
    return False


def _thin_protocol_retry_messages(
    messages: list[dict[str, str]],
    exc: ModelOutputError,
    previous_exc: ModelOutputError | None = None,
) -> list[dict[str, str]]:
    """Add one mechanical schema correction without strategy or completion advice.

    If the provider selected one native tool but its argument serialization was
    locally rejected, preserve that rejected call as inert repair context.  It
    is never executed and never counts as an observation.
    """
    retry = list(messages)
    tool_name = str(getattr(exc, "rejected_tool_name", "") or "").strip()
    tool_arguments = str(getattr(exc, "rejected_tool_arguments", "") or "")
    if tool_name and tool_arguments:
        bounded_arguments = tool_arguments[:12000]
        truncation_note = (
            " The captured arguments were bounded for repair context."
            if len(tool_arguments) > len(bounded_arguments) else ""
        )
        repeat_note = ""
        if (
            previous_exc is not None
            and str(getattr(previous_exc, "rejected_tool_name", "") or "").strip() == tool_name
            and str(getattr(previous_exc, "rejected_tool_arguments", "") or "") == tool_arguments
        ):
            located = decode_error_note(tool_name, tool_arguments)
            if located:
                repeat_note = (
                    " The previous attempt sent byte-identical arguments, so the same error "
                    f"recurred. {located}"
                )
        retry.append({
            "role": "user",
            "content": (
                "[solver_protocol_observation] The previous provider-native tool call was rejected "
                "before execution, so no task action occurred. Treat the following as inert "
                "non-executed repair context, not as an observation or successful action. "
                f"Rejected tool name: {tool_name}. Rejected raw arguments: {bounded_arguments}."
                f"{truncation_note} Preserve the selected tool and task-specific literals when they "
                "are recoverable; repair only the invalid envelope/argument serialization named by "
                f"this error: {exc}.{repeat_note} Return exactly one valid response under the active schema. "
                "Do not re-plan merely because transport serialization failed, do not invent missing "
                "argument content, and do not claim the rejected action occurred."
            ),
        })
        return retry
    retry.append({
        "role": "user",
        "content": (
            "The previous response was rejected before execution by the active response schema. "
            "No task action occurred. Return exactly one valid response object under the same schema; "
            "change only the invalid envelope or field named by this error. Do not add prose or another "
            f"response. Error: {exc}"
        ),
    })
    return retry


def _run_thin_loop_impl(
    envmap: EnvMap,
    executor: Executor,
    hooks: ThinSolverHooks,
    *,
    config: ThinLoopConfig | None = None,
    world_state: WorldState | None = None,
    trace: RunTrace | None = None,
) -> ThinLoopResult:
    """Run the matched loop over real shared execution seams.

    The caller owns provider construction and executor lifecycle.  This function
    performs no launch, VM, package, credential, watcher, or grader action by
    itself; it only invokes the supplied Solver hook and shared executor for
    model-authorized task actions.
    """
    selected = config or ThinLoopConfig()
    context_tree_adapter = selected.context_tree_adapter
    terminal_verifier_mode = _normalize_terminal_verifier_mode(
        selected.terminal_verifier_mode
    )
    oracle_finish_response_mode = normalize_oracle_finish_response_mode(
        selected.oracle_finish_response_mode
    )
    delivery_hygiene_mode = normalize_delivery_hygiene_mode(
        selected.delivery_hygiene_mode
    )
    completion_signal_mode = normalize_completion_signal_mode(
        selected.solver_completion_signal_mode
    )
    if str(selected.context_cleanup_mode or "off").strip().lower() not in CONTEXT_CLEANUP_MODES:
        raise ValueError(f"unsupported context cleanup mode: {selected.context_cleanup_mode}")
    failed_observation_mode = str(
        selected.failed_observation_disposition_mode or FAILED_OBSERVATION_CONTROL
    ).strip().lower()
    if failed_observation_mode not in SUPPORTED_FAILED_OBSERVATION_MODES:
        raise ValueError(
            f"unsupported failed observation disposition mode: {selected.failed_observation_disposition_mode}"
        )
    model_view_mode = normalize_model_view_mode(selected.solver_model_view_mode)
    working_context_mode = str(
        selected.solver_working_context_mode or SOLVER_WORKING_CONTEXT_OFF
    ).strip().lower()
    if working_context_mode not in SOLVER_WORKING_CONTEXT_MODES:
        raise ValueError(
            f"unsupported Solver working-context mode: {selected.solver_working_context_mode}"
        )
    if (
        working_context_mode != SOLVER_WORKING_CONTEXT_OFF
        and selected.solver_reality_transport_mode != SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1
    ):
        raise ValueError("non-off Solver working context requires latest_exchange_v1 reality transport")
    kernel = AetherNextKernel(
        max_steps=selected.max_steps,
        max_solver_turns=selected.max_solver_turns,
        max_accepted_task_actions=selected.max_accepted_task_actions,
        runtime_identity=_identity_for(selected, envmap),
        solver_reanchor_mode=selected.solver_reanchor_mode,
        solver_context_mode=selected.solver_context_mode,
        completion_record_mode=selected.completion_record_mode,
        solver_reasoning_mode=selected.solver_reasoning_mode,
        solver_async_mode=selected.solver_async_mode,
        solver_task_contract_mode=selected.solver_task_contract_mode,
        solver_prefix_renderer="incumbent_context",
        solver_reality_transport_mode=selected.solver_reality_transport_mode,
        solver_hosted_tool_search_mode=selected.solver_hosted_tool_search_mode,
        cancellation_event=selected.cancellation_event,
        refresh_runtime_operation_status=(
            selected.refresh_runtime_operation_status
            or selected.solver_async_mode in {
                SOLVER_ASYNC_SERIAL_JOBS_V1,
                SOLVER_ASYNC_INDEPENDENT_JOBS_V1,
            }
        ),
    )
    kernel.active_hooks = hooks
    resolved = build_persistent_runtime(
        envmap,
        solver_context_mode=selected.solver_context_mode,
        solver_reasoning_mode=selected.solver_reasoning_mode,
        solver_async_mode=selected.solver_async_mode,
        solver_task_contract_mode=selected.solver_task_contract_mode,
        solver_prefix_renderer="incumbent_context",
        solver_reality_transport_mode=selected.solver_reality_transport_mode,
        solver_working_context_mode=working_context_mode,
        solver_hosted_tool_search_mode=selected.solver_hosted_tool_search_mode,
        solver_tool_surface_mode=selected.solver_tool_surface_mode,
        solver_long_command_mode=selected.solver_long_command_mode,
        solver_env_mode=selected.env_mode,
    )
    if resolved.config_invalid_blockers or resolved.compiled is None:
        compiled = resolved.compiled
        # There is no canonical packet when compilation fails; retain a stable
        # environment digest and a configuration receipt in a small local ledger.
        ledger = ExecutionLedger()
        for blocker in resolved.config_invalid_blockers:
            ledger.record(Receipt(
                receipt_id="config:thin_runtime_invalid",
                step=0,
                kind="config_invalid",
                success=False,
                summary=str(blocker),
                failure_class="config_invalid",
            ))
        return ThinLoopResult(
            status="config_invalid",
            step=0,
            env_digest=envmap.digest(),
            blockers=tuple(resolved.config_invalid_blockers),
            receipts=ledger.all_receipts(),
            accounting=ledger.accounting_snapshot(),
        )
    compiled = resolved.compiled
    solver_compiled = (
        context_tree_adapter.solver_compiled(compiled)
        if context_tree_adapter is not None else compiled
    )
    turn_compiled = solver_compiled  # per-turn surface; narrowed only by the context-file arm
    identity = _identity_for(selected, envmap)
    ledger = ExecutionLedger()
    kernel._active_ledger = ledger
    kernel._active_env_digest = compiled.env_digest
    kernel._active_step = 0
    ledger.install_runtime_identity(identity)
    ledger.seed_capabilities(compiled.selected_capability_ids())
    ledger.ensure_objective(compiled.objective_graph)
    realization = dict(compiled.config_realization)
    realization.update({
        "runtime_path": "persistent_v0",
        "comparison_arm": "thin_frontier",
        "configuration_model_calls": 0,
        "model_authored_reconfiguration": False,
        "semantic_decision_invoked": (
            terminal_verifier_mode != THIN_TERMINAL_VERIFIER_CONTROL
        ),
        "solver_model_view_mode": model_view_mode,
        "thin_terminal_verifier_mode": terminal_verifier_mode,
        "oracle_finish_response_mode": oracle_finish_response_mode,
        "delivery_hygiene_mode": delivery_hygiene_mode,
    })
    ledger.record_config_realization(realization)

    route_rows, route_issues = preflight_proof_routes(
        compiled, executor, envmap, hooks=hooks,
        require_verifier=terminal_verifier_mode != THIN_TERMINAL_VERIFIER_CONTROL,
    )
    ledger.record(Receipt(
        receipt_id="config:route_preflight",
        step=0,
        kind="route_preflight",
        success=not bool(route_issues),
        summary="compiled proof routes available" if not route_issues else "compiled proof routes unavailable",
        failure_class="config_invalid" if route_issues else "",
        payload={
            "rows": [row.as_dict() for row in route_rows],
            "issues": [issue.as_dict() for issue in route_issues],
            "semantic_decision_invoked": False,
        },
    ))
    if route_issues:
        return _result(
            "config_invalid",
            step=0,
            compiled=compiled,
            ledger=ledger,
            blockers=tuple(f"{issue.code}:{issue.clause_id}" for issue in route_issues),
            requests=[],
        )

    if world_state is None:
        world_state = _world_state(envmap, compiled)
    elif compiled.task_contract is not None:
        world_state.task_contract = compiled.task_contract
    if trace is not None:
        trace.set_runtime(resolved.runtime_ir, thin_prefix_messages(compiled))
    challenger = selected.claim_ledger_controller
    if challenger is not None:
        challenger.bind(kernel=kernel, compiled=compiled, executor=executor, exec_ledger=ledger,
                 world_state=world_state, context_tree_adapter=context_tree_adapter)

    requests: list[Mapping[str, Any]] = []
    verifier_memo: dict[str, Any] = {}
    terminal_verifier_cycles = 0
    last_completion_signal_note = ""
    step = 0
    resilient = selected.protocol_resilience in _resilience.RESILIENT_MODES
    resilient_v2 = selected.protocol_resilience in _resilience.OUTPUT_CAP_MODES
    resilient_v3 = selected.protocol_resilience == _resilience.RESILIENT_V3
    retry_sampling = selected.protocol_resilience in _resilience.RETRY_TEMPERATURE_MODES
    retry_temp: float | None = (
        _resilience.retry_temperature(hooks.solver_temperature()) if retry_sampling else None
    )
    retry_turn_pending = False
    unparseable_streak = 0
    cap_streak = 0
    configured_effort: str | None = None
    if resilient_v3:
        read_effort = getattr(hooks, "solver_reasoning_effort", None)
        configured_effort = read_effort() if callable(read_effort) else None
        if configured_effort is None:
            raise _resilience.ProtocolResilienceError(
                "resilient_v3 requires a solver with a configured reasoning effort"
            )
    pending_protocol_observation = ""

    def solve_and_record(
        solver_messages: list[dict[str, str]],
        *,
        provider_turn_event: str = "primary_solver_call",
        temperature: float | None = None,
    ) -> SolverTurn:
        configure_step = getattr(hooks, "configure_solver_step", None)
        if callable(configure_step):
            configure_step(step)
        try:
            if context_tree_adapter is not None and context_tree_adapter.consume_epoch_reset():
                reset_continuity = getattr(hooks, getattr(
                    context_tree_adapter, "continuity_reset_hook",
                    "reset_solver_continuity_for_recovery",
                ), None)
                if callable(reset_continuity) and not bool(reset_continuity()):
                    raise ContextTreeContinuityError(
                        "ModelHooks could not clear native Solver continuity at an M-TREE epoch boundary"
                    )
            ledger.record_accounting(
                receipt_id=f"step-{step}:solver_provider_turn:{ledger.accounting_value('solver_provider_turns') + 1}",
                step=step,
                counter="solver_provider_turns",
                event=provider_turn_event,
            )
            if retry_sampling and temperature is not None:
                hooks.configure_solver_temperature(temperature)
            return hooks.solve(solver_messages, turn_compiled)
        finally:
            if retry_sampling:
                hooks.configure_solver_temperature(None)
            _record_context_policy_events(hooks, ledger, step=step)

    run_started = (
        float(selected.run_started_monotonic)
        if selected.run_started_monotonic is not None
        else time.monotonic()
    )
    if challenger is not None:
        challenger.start_progress_schedule(
            run_started_monotonic=run_started,
            deadline_sec=selected.visible_deadline_sec,
        )
    deadline = (
        run_started + float(selected.run_timeout_s)
        if selected.run_timeout_s is not None and float(selected.run_timeout_s) > 0
        else None
    )
    while kernel.max_steps is None or step < kernel.max_steps:
        try:
            raise_if_run_cancelled(selected.cancellation_event)
            now = time.monotonic()
            elapsed = max(0.0, now - run_started)
            clock_fields = {
                "run_timeout_sec": selected.run_timeout_s,
                "elapsed_run_sec": round(elapsed, 3),
                "remaining_run_sec": round(max(0.0, deadline - now), 3) if deadline is not None else None,
                "wall_clock_authority": "runtime_supplied_timeout" if selected.run_timeout_s is not None else "unknown",
            }
            if selected.visible_deadline_sec is not None:
                clock_fields.update(visible_clock_fields(selected.visible_deadline_sec, elapsed))
            ledger.update_runtime_budget_state({"used_kernel_steps": int(step), **clock_fields})
            kernel.runtime_budget_history.append({"step": step, **clock_fields})
            kernel._active_step = step
            runtime_caps = (
                kernel._live_runtime_capability_ids(executor)
                if selected.probe_runtime_capabilities
                else set()
            )
            if ledger.set_runtime_capabilities(runtime_caps):
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:runtime_capability_refresh",
                    step=step,
                    kind="runtime_capability_refresh",
                    success=True,
                    summary="refreshed current live executor capabilities",
                    payload={"runtime_capability_ids": sorted(runtime_caps), "compiled_runtime_mutated": False},
                ))
            configure_caps = getattr(hooks, "configure_runtime_capabilities", None)
            if callable(configure_caps):
                configure_caps(runtime_caps)
            if kernel.max_solver_turns is not None and ledger.accounting_value("solver_provider_turns") >= kernel.max_solver_turns:
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:solver_turn_budget_exhausted",
                    step=step,
                    kind="solver_turn_budget_exhausted",
                    success=False,
                    summary=f"maximum solver provider turns reached: {kernel.max_solver_turns}",
                    failure_class="solver_turn_budget_exhausted",
                    payload={"max_solver_turns": kernel.max_solver_turns},
                ))
                return _result("solver_turn_budget_exhausted", step=step, compiled=compiled, ledger=ledger, blockers=("solver_turn_budget_exhausted",), requests=requests)
            if deadline is not None and now >= deadline:
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:thin_deadline_exceeded",
                    step=step,
                    kind="thin_deadline_exceeded",
                    success=False,
                    summary="Thin loop deadline reached before a new Solver request",
                    failure_class="timeout",
                ))
                return _result("timeout", step=step, compiled=compiled, ledger=ledger, blockers=("thin_deadline_exceeded",), requests=requests)

            if kernel.refresh_runtime_operation_status:
                kernel._refresh_runtime_operation_status(executor, ledger, step=step)
            ensure_initial_nonadherence_receipt(
                ledger, step=step, mode=selected.completion_record_mode,
            )
            alerts = kernel.monitor_runner.run(compiled, ledger)
            canonical_context = build_thin_context(
                compiled,
                ledger,
                alerts,
                solver_working_context_mode=working_context_mode,
                retain_completion_findings=(
                    terminal_verifier_mode != THIN_TERMINAL_VERIFIER_CONTROL
                    or oracle_finish_response_mode != ORACLE_FINISH_RESPONSE_CONTROL
                ),
            )
            if kernel.refresh_runtime_operation_status:
                canonical_context = dict(canonical_context)
                canonical_context["runtime_operations"] = ledger.runtime_operation_statuses()
            failed_observation_findings = current_candidate_failed_observations(
                ledger, mode=failed_observation_mode,
            )
            if failed_observation_findings:
                canonical_context = dict(canonical_context)
                canonical_context["open_completion_findings"] = [
                    dict(item) for item in failed_observation_findings
                ]
                canonical_context["failed_observation_disposition"] = {
                    "mode": failed_observation_mode,
                    "required_finding_ids": [
                        str(item["finding_id"]) for item in failed_observation_findings
                    ],
                    "semantic_interpretation_authority": "solver",
                    "harness_role": "mechanical_disposition_coverage_only",
                }
            completion_record_projection = project_completion_record_context(
                ledger, mode=selected.completion_record_mode, task_text=compiled.task_prompt,
            )
            if completion_record_projection is not None:
                canonical_context = dict(canonical_context)
                canonical_context["completion_record"] = completion_record_projection
            completion_signal = completion_signal_context(
                ledger, mode=completion_signal_mode,
            )
            if completion_signal is not None:
                canonical_context = dict(canonical_context)
                canonical_context["completion_signal"] = completion_signal
                completion_signal_note = _canonical_tree_note(completion_signal)
                if (
                    context_tree_adapter is not None
                    and completion_signal_note != last_completion_signal_note
                ):
                    context_tree_adapter.record_note(completion_signal_note)
                last_completion_signal_note = completion_signal_note
            if delivery_hygiene_mode != DELIVERY_HYGIENE_CONTROL:
                canonical_context = dict(canonical_context)
                canonical_context["delivery_hygiene"] = delivery_hygiene_context(
                    world_state.dynamic_snapshot() if world_state is not None else None
                )
            if oracle_finish_response_mode != ORACLE_FINISH_RESPONSE_CONTROL:
                canonical_context = mark_v1b_obligations_current(canonical_context)
            v1b_finding_ids = (
                current_v1b_finding_ids(canonical_context)
                if oracle_finish_response_mode != ORACLE_FINISH_RESPONSE_CONTROL
                else ()
            )
            if selected.completion_record_mode == COMPLETION_RECORD_OFF:
                canonical_context = dict(canonical_context)
                available = dict(canonical_context.get("available_capabilities") or {})
                available["action_kinds"] = [
                    str(kind)
                    for kind in available.get("action_kinds", ())
                    if str(kind) != "update_completion_record"
                ]
                canonical_context["available_capabilities"] = available
            canonical_context = persistent_filter_context_for_tool_surface(
                canonical_context, selected.solver_tool_surface_mode,
            )
            if (compiled.config_realization or {}).get("solver_long_command_mode") == "background_v1":
                canonical_context = dict(canonical_context)
                available = dict(canonical_context.get("available_capabilities") or {})
                visible = list(available.get("action_kinds") or ())
                available["action_kinds"] = [
                    *visible, *(kind for kind in ("job_output", "job_wait", "job_stop") if kind not in visible),
                ]
                canonical_context["available_capabilities"] = available
            if (compiled.config_realization or {}).get("solver_long_command_mode") == "background_v1":
                job_ids = list(getattr(kernel, "_long_command_jobs", ()))
                terminal_reads = getattr(kernel, "_long_command_terminal_reads", set())
                previous_tails = getattr(kernel, "_long_command_previous_tails", {})
                observations: list[str] = []
                output_reader = getattr(executor, "job_output", None)
                for job_id in job_ids:
                    if job_id in terminal_reads:
                        continue
                    probe = executor.probe_job(job_id)
                    if not probe.found:
                        continue
                    output = output_reader(job_id, tail_lines=20) if callable(output_reader) else {}
                    tails = []
                    for channel in ("stdout", "stderr"):
                        current_lines = str(output.get(channel, "")).splitlines()
                        prior_lines = previous_tails.get((job_id, channel), [])
                        new_lines = current_lines
                        if prior_lines:
                            overlap = max(
                                (size for size in range(1, min(len(prior_lines), len(current_lines)) + 1)
                                 if prior_lines[-size:] == current_lines[:size]),
                                default=0,
                            )
                            new_lines = current_lines[overlap:]
                        previous_tails[(job_id, channel)] = current_lines
                        if new_lines:
                            tails.append(f"{channel}: {' | '.join(new_lines[-20:])}")
                    state = "running" if not probe.completed else f"{probe.status}, exit_code={probe.exit_code}"
                    observations.append(f"job {job_id}: {state}" + (f"; new output: {'; '.join(tails)}" if tails else ""))
                    if probe.completed:
                        terminal_reads.add(job_id)
                        try:
                            kernel._long_command_jobs.remove(job_id)
                        except (ValueError, AttributeError):
                            pass
                        try:
                            executor._aether_long_command_jobs.remove(job_id)
                        except (ValueError, AttributeError):
                            pass
                kernel._long_command_previous_tails = previous_tails
                kernel._long_command_terminal_reads = terminal_reads
                if observations:
                    canonical_context = dict(canonical_context)
                    canonical_context["background_job_status"] = observations
            challenger_feedback = challenger.pop_feedback() if challenger is not None else None
            if challenger_feedback is not None:
                canonical_context = dict(canonical_context)
                canonical_context["claim_ledger_feedback"] = challenger_feedback
            semantic_advice = None
            if selected.semantic_assistance is not None:
                semantic_advice = selected.semantic_assistance(
                    task_text=compiled.task_prompt, ledger=ledger, step=step,
                    runtime_identity=_identity_for(selected, envmap),
                )
                expose_semantic_advice = not (
                    isinstance(semantic_advice, Mapping)
                    and semantic_advice.get("schema") == "aether.semantic_advice.v1"
                    and not list(semantic_advice.get("items") or ())
                )
                if expose_semantic_advice:
                    canonical_context = dict(canonical_context)
                    review = project_independent_review(semantic_advice)
                    if review is not None:
                        canonical_context[INDEPENDENT_REVIEW_KEY] = review
                        if context_tree_adapter is not None:
                            context_tree_adapter.record_note(_canonical_tree_note(review))
                    else:
                        canonical_context["semantic_advice"] = semantic_advice
            model_packet = (
                canonical_context if selected.packet_mode == PACKET_CONTROL
                else lean_packet(canonical_context, recent_changed_paths(ledger))
            )
            messages = build_thin_solver_messages(
                compiled,
                model_packet,
                model_view_mode=model_view_mode,
                solver_working_context_mode=working_context_mode,
            )
            messages, context_accounting = apply_context_cleanup(
                messages, mode=selected.context_cleanup_mode,
            )
            if context_tree_adapter is not None:
                messages = context_tree_adapter.prepare_messages(
                    messages,
                    compiled=compiled,
                    task_workspace=envmap.workspace_root,
                    cancellation_event=selected.cancellation_event,
                    settle_timeout=(
                        None if deadline is None
                        else max(0.0, deadline - time.monotonic())
                    ),
                )
                turn_compiled = apply_turn_surface(
                    context_tree_adapter, hooks, solver_compiled, ledger=ledger, step=step,
                )
            if pending_protocol_observation:
                messages = [*messages, {"role": "user", "content": pending_protocol_observation}]
                pending_protocol_observation = ""
            turn_temperature = retry_temp if retry_turn_pending else None
            retry_turn_pending = False
            request = {
                "step": step,
                "messages": deepcopy(messages),
                "context_accounting": deepcopy(context_accounting),
                "context_sha256": hashlib.sha256(stable_json_for_hash(canonical_context).encode("utf-8")).hexdigest(),
                "action_schema_sha256": hashlib.sha256(stable_json_for_hash(turn_compiled.action_schema).encode("utf-8")).hexdigest(),
            }
            if context_tree_adapter is not None:
                request["context_tree"] = context_tree_adapter.request_metadata()
            if semantic_advice is not None:
                # Telemetry keeps the full internal record; the model saw only the
                # neutral projection built above.
                request["internal_semantic_advice"] = deepcopy(semantic_advice)
            if retry_sampling:
                request["retry_temperature"] = turn_temperature
            requests.append(request)
            configure_disposition_mode = getattr(
                hooks, "configure_completion_disposition_mode", None
            )
            if (
                (
                    failed_observation_mode != FAILED_OBSERVATION_CONTROL
                    or oracle_finish_response_mode != ORACLE_FINISH_RESPONSE_CONTROL
                )
                and callable(configure_disposition_mode)
            ):
                configure_disposition_mode(
                    COMPLETION_DISPOSITION_V1
                    if failed_observation_findings or v1b_finding_ids
                    else COMPLETION_DISPOSITION_CONTROL
                )
            configure_completion_record_mode = getattr(
                hooks, "configure_completion_record_mode", None
            )
            if callable(configure_completion_record_mode):
                configure_completion_record_mode(selected.completion_record_mode)
            before_count = len(ledger.all_receipts())
            if context_tree_adapter is not None:
                try:
                    context_tree_adapter.note_request(messages)
                except MTreeEpochOverflow as exc:
                    receipt = Receipt(
                        receipt_id=f"step-{step}:{exc.code}",
                        step=step,
                        kind=exc.code,
                        success=False,
                        summary=str(exc),
                        failure_class=exc.code,
                        payload={
                            "estimated_tokens": exc.estimated_tokens,
                            "request_limit": exc.request_limit,
                            "provider_call_dispatched": False,
                        },
                    )
                    ledger.record(receipt)
                    _record_m_tree_receipt_note(context_tree_adapter, receipt)
                    return _result(
                        exc.code, step=step, compiled=compiled,
                        ledger=ledger, blockers=(exc.code,), requests=requests,
                    )
            raise_if_run_cancelled(selected.cancellation_event)
            raise_if_run_deadline_exceeded()
            if deadline is not None and time.monotonic() >= deadline:
                raise KernelRunTimeout("task run deadline exceeded before Solver dispatch")
            if resilient_v3:
                turn_effort = _resilience.stepped_effort(configured_effort, cap_streak)
                hooks.configure_solver_reasoning_effort(turn_effort if cap_streak else None)
                ledger.record_accounting(
                    receipt_id=f"step-{step}:solver_effort_turn:{ledger.accounting_value(_resilience.EFFORT_TURN_COUNTER) + 1}",
                    step=step,
                    counter=_resilience.EFFORT_TURN_COUNTER,
                    event=f"effort={turn_effort}",
                )
            try:
                turn = solve_and_record(messages, temperature=turn_temperature)
            except ContextTreeContinuityError as exc:
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:m_tree_continuity_reset_failed",
                    step=step,
                    kind="m_tree_continuity_reset_failed",
                    success=False,
                    summary=str(exc),
                    failure_class="m_tree_continuity_reset_failed",
                    payload={"provider_call_dispatched": False},
                ))
                return _result(
                    "m_tree_continuity_reset_failed", step=step, compiled=compiled,
                    ledger=ledger, blockers=("m_tree_continuity_reset_failed",), requests=requests,
                )
            except ModelOutputError as exc:
                if resilient_v2 and _is_output_cap_truncation(exc):
                    unparseable_streak += 1
                    ledger.record_accounting(
                        receipt_id=f"step-{step}:output_cap_turn:{unparseable_streak}",
                        step=step,
                        counter=_resilience.OUTPUT_CAP_COUNTER,
                        event="output_cap_without_action",
                    )
                    if unparseable_streak >= _resilience.MAX_CONSECUTIVE_UNPARSEABLE_TURNS:
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:thin_output_cap_exhausted",
                            step=step,
                            kind="thin_output_cap_exhausted",
                            success=False,
                            summary=f"Provider output cap reached on {unparseable_streak} consecutive turns: {exc}",
                            failure_class="provider_output_cap_exhausted",
                            payload={"error": str(exc)[:2000], "task_action_dispatched": False},
                        ))
                        return _result(
                            "provider_output_cap_exhausted", step=step, compiled=compiled, ledger=ledger,
                            blockers=("provider_output_cap_exhausted",), requests=requests,
                        )
                    next_effort: str | None = None
                    if resilient_v3:
                        cap_streak += 1
                        next_effort = _resilience.stepped_effort(configured_effort, cap_streak)
                        if next_effort != _resilience.stepped_effort(configured_effort, cap_streak - 1):
                            ledger.record_accounting(
                                receipt_id=f"step-{step}:effort_stepdown:{cap_streak}",
                                step=step,
                                counter=_resilience.EFFORT_STEPDOWN_COUNTER,
                                event=f"{_resilience.stepped_effort(configured_effort, cap_streak - 1)}->{next_effort}",
                            )
                        if next_effort == configured_effort:
                            next_effort = None  # floor reached from the floor: nothing was reduced
                    pending_protocol_observation = _resilience.output_cap_observation_for(exc, next_effort)
                    if context_tree_adapter is not None:
                        context_tree_adapter.record_note(pending_protocol_observation)
                    step += 1
                    continue
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:thin_parse_error",
                    step=step,
                    kind="thin_parse_error",
                    success=False,
                    summary=f"Thin response rejected before execution: {exc}",
                    failure_class="solver_protocol_error",
                    payload={
                        "error": str(exc)[:2000],
                        "task_action_dispatched": False,
                        "retry_attempted": True,
                        "max_protocol_corrections": 2,
                    },
                ))
                correction_error: ModelOutputError = exc
                previous_correction_error: ModelOutputError | None = None
                turn = None
                skip_unparseable_turn = False
                cap_message_sent = False
                for correction_attempt in range(1, 3):
                    if (
                        kernel.max_solver_turns is not None
                        and ledger.accounting_value("solver_provider_turns") >= kernel.max_solver_turns
                    ):
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:solver_turn_budget_exhausted",
                            step=step,
                            kind="solver_turn_budget_exhausted",
                            success=False,
                            summary=f"maximum solver provider turns reached: {kernel.max_solver_turns}",
                            failure_class="solver_turn_budget_exhausted",
                            payload={
                                "max_solver_turns": kernel.max_solver_turns,
                                "phase": "protocol_correction",
                                "correction_attempt": correction_attempt,
                            },
                        ))
                        return _result(
                            "solver_turn_budget_exhausted",
                            step=step,
                            compiled=compiled,
                            ledger=ledger,
                            blockers=("solver_turn_budget_exhausted",),
                            requests=requests,
                        )
                    cap_retry = _is_output_cap_truncation(correction_error)
                    cap_message_sent = cap_message_sent or cap_retry
                    ledger.record_accounting(
                        receipt_id=f"step-{step}:thin_protocol_correction:{ledger.accounting_value('solver_protocol_correction_calls') + 1}",
                        step=step,
                        counter="solver_protocol_correction_calls",
                        event="output_cap_factual_message" if cap_retry else "same_step_schema_correction",
                    )
                    corrected_messages = (
                        [*messages, {"role": "user", "content": OUTPUT_CAP_MESSAGE}]
                        if cap_retry
                        else _thin_protocol_retry_messages(
                            messages, correction_error, previous_correction_error,
                        )
                    )
                    requests.append({
                        "step": step,
                        "retry": True,
                        "correction_attempt": correction_attempt,
                        "messages": deepcopy(corrected_messages),
                        "context_sha256": request["context_sha256"],
                        "action_schema_sha256": request["action_schema_sha256"],
                        **({"retry_temperature": None if cap_retry else retry_temp} if retry_sampling else {}),
                    })
                    if context_tree_adapter is not None:
                        try:
                            context_tree_adapter.note_request(corrected_messages)
                        except MTreeEpochOverflow as overflow:
                            receipt = Receipt(
                                receipt_id=f"step-{step}:{overflow.code}",
                                step=step,
                                kind=overflow.code,
                                success=False,
                                summary=str(overflow),
                                failure_class=overflow.code,
                                payload={
                                    "estimated_tokens": overflow.estimated_tokens,
                                    "request_limit": overflow.request_limit,
                                    "provider_call_dispatched": False,
                                    "phase": "protocol_correction",
                                },
                            )
                            ledger.record(receipt)
                            _record_m_tree_receipt_note(context_tree_adapter, receipt)
                            return _result(
                                overflow.code, step=step, compiled=compiled,
                                ledger=ledger, blockers=(overflow.code,), requests=requests,
                            )
                        raise_if_run_cancelled(selected.cancellation_event)
                        raise_if_run_deadline_exceeded()
                        if deadline is not None and time.monotonic() >= deadline:
                            raise KernelRunTimeout(
                                "task run deadline exceeded before correction dispatch"
                            )
                        feedback_text = str(corrected_messages[-1].get("content") or "")
                        if feedback_text:
                            context_tree_adapter.record_note(feedback_text)
                    try:
                        turn = solve_and_record(
                            corrected_messages,
                            provider_turn_event="protocol_correction_solver_call",
                            temperature=None if cap_retry else retry_temp,
                        )
                    except ModelOutputError as retry_exc:
                        if _is_output_cap_truncation(retry_exc) and (cap_message_sent or correction_attempt >= 2):
                            ledger.record(Receipt(
                                receipt_id=f"step-{step}:thin_output_cap_exhausted",
                                step=step,
                                kind="thin_output_cap_exhausted",
                                success=False,
                                summary=(
                                    "Provider output cap was reached before a tool call, "
                                    f"including after the escalated request: {retry_exc}"
                                ),
                                failure_class="provider_output_cap_exhausted",
                                payload={
                                    "error": str(retry_exc)[:2000],
                                    "task_action_dispatched": False,
                                },
                            ))
                            return _result(
                                "provider_output_cap_exhausted",
                                step=step,
                                compiled=compiled,
                                ledger=ledger,
                                blockers=("provider_output_cap_exhausted",),
                                requests=requests,
                            )
                        if correction_attempt < 2:
                            ledger.record(Receipt(
                                receipt_id=f"step-{step}:thin_parse_error_correction:{correction_attempt}",
                                step=step,
                                kind="thin_parse_error_correction",
                                success=False,
                                summary=f"Thin schema correction {correction_attempt} was still invalid: {retry_exc}",
                                failure_class="solver_protocol_error",
                                payload={
                                    "error": str(retry_exc)[:2000],
                                    "correction_attempt": correction_attempt,
                                    "task_action_dispatched": False,
                                    "retry_attempted": True,
                                },
                            ))
                            previous_correction_error = correction_error
                            correction_error = retry_exc
                            continue
                        _record_protocol_failure(
                            ledger,
                            step=step,
                            error=retry_exc,
                            kind="thin_parse_error_retry",
                        )
                        if resilient:
                            cap_streak = 0
                            unparseable_streak += 1
                            ledger.record_accounting(
                                receipt_id=f"step-{step}:protocol_failed_turn:{unparseable_streak}",
                                step=step,
                                counter=_resilience.FAILED_TURNS_COUNTER,
                                event="unparseable_turn",
                            )
                        if resilient and unparseable_streak < _resilience.MAX_CONSECUTIVE_UNPARSEABLE_TURNS:
                            pending_protocol_observation = _resilience.failure_observation(retry_exc)
                            retry_turn_pending = True
                            if context_tree_adapter is not None:
                                context_tree_adapter.record_note(pending_protocol_observation)
                            skip_unparseable_turn = True
                            break
                        return _result(
                            "solver_protocol_failure",
                            step=step,
                            compiled=compiled,
                            ledger=ledger,
                            blockers=("solver_protocol_failure",),
                            requests=requests,
                        )
                    except ModelProviderError as retry_exc:
                        _record_protocol_failure(
                            ledger,
                            step=step,
                            error=retry_exc,
                            kind="thin_protocol_correction_provider_failure",
                        )
                        if (
                            context_tree_adapter is not None
                            and _context_overflow_code(retry_exc)
                        ):
                            return _result(
                                _context_overflow_code(retry_exc), step=step, compiled=compiled, ledger=ledger,
                                blockers=(_context_overflow_code(retry_exc),), requests=requests,
                            )
                        if _is_context_capacity_failure(retry_exc):
                            return _result(
                                "harness_context_capacity", step=step, compiled=compiled, ledger=ledger,
                                blockers=("harness_context_capacity",), requests=requests,
                            )
                        if _is_route_identity_failure(retry_exc):
                            return _result(
                                "provider_route_identity_mismatch", step=step, compiled=compiled, ledger=ledger,
                                blockers=("provider_route_identity_mismatch",), requests=requests,
                            )
                        return _result(
                            "provider_failure",
                            step=step,
                            compiled=compiled,
                            ledger=ledger,
                            blockers=("solver_provider_failure",),
                            requests=requests,
                        )
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:thin_protocol_correction_result",
                        step=step,
                        kind="thin_protocol_correction_result",
                        success=True,
                        summary=(
                            f"Thin received one valid turn after {correction_attempt} "
                            "schema correction call(s)"
                        ),
                        payload={
                            "task_action_dispatched_before_correction": False,
                            "correction_attempts_used": correction_attempt,
                        },
                    ))
                    break
                if skip_unparseable_turn:
                    step += 1
                    continue
                if turn is None:
                    raise RuntimeError("protocol correction loop exited without a turn")
            except ModelProviderError as exc:
                _record_protocol_failure(ledger, step=step, error=exc)
                if _is_route_identity_failure(exc):
                    return _result(
                        "provider_route_identity_mismatch", step=step, compiled=compiled, ledger=ledger,
                        blockers=("provider_route_identity_mismatch",), requests=requests,
                    )
                if context_tree_adapter is not None and _context_overflow_code(exc):
                    return _result(
                        _context_overflow_code(exc), step=step, compiled=compiled, ledger=ledger,
                        blockers=(_context_overflow_code(exc),), requests=requests,
                    )
                if _is_context_capacity_failure(exc):
                    return _result(
                        "harness_context_capacity", step=step, compiled=compiled, ledger=ledger,
                        blockers=("harness_context_capacity",), requests=requests,
                    )
                return _result("provider_failure", step=step, compiled=compiled, ledger=ledger, blockers=("solver_provider_failure",), requests=requests)

            cap_streak = 0
            if unparseable_streak:
                ledger.record_accounting(
                    receipt_id=f"step-{step}:protocol_recovered",
                    step=step,
                    counter=_resilience.RECOVERED_COUNTER,
                    event="parseable_turn_after_unparseable",
                )
                unparseable_streak = 0
            raise_if_run_cancelled(selected.cancellation_event)
            raise_if_run_deadline_exceeded()
            errors = turn.validate(turn_compiled.action_schema)
            if challenger is not None:
                challenger.on_turn_boundary(
                    step=step, elapsed_sec=max(0.0, time.monotonic() - run_started),
                    deadline_sec=selected.visible_deadline_sec, envmap=envmap,
                )
            if errors:
                receipt = Receipt(
                    receipt_id=f"step-{step}:thin_turn_validation",
                    step=step,
                    kind="turn_validation",
                    success=False,
                    summary=f"invalid Thin turn: {'; '.join(errors)}",
                    failure_class="turn_validation",
                )
                ledger.record(receipt)
                _record_m_tree_receipt_note(context_tree_adapter, receipt)
                if trace is not None:
                    trace.add_step(step, canonical_context, turn, ledger.all_receipts()[before_count:])
                step += 1
                continue
            if turn.protocol_salvage is not None:
                interpreted = (
                    dict(turn.actions[0].arguments)
                    if turn.kind == "act" and turn.actions else {}
                )
                note = (
                    "note: your previous tool arguments were malformed; interpreted as "
                    + compact_interpreted_arguments(interpreted)
                )
                pending_protocol_observation = note
                if context_tree_adapter is not None:
                    context_tree_adapter.record_note(note)
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:protocol_salvage",
                    step=step,
                    kind="protocol_salvage",
                    success=True,
                    summary="recovered one complete native tool argument object",
                    payload={
                        **dict(turn.protocol_salvage),
                        "interpreted_arguments": interpreted,
                        "tool_name": turn.actions[0].kind if turn.kind == "act" and turn.actions else "",
                    },
                ))
            if context_tree_adapter is not None:
                context_tree_adapter.record_solver_turn(turn, step=step)
            if turn.kind == "act":
                if (
                    context_tree_adapter is not None
                    and turn.actions
                    and turn.actions[0].kind in context_tree_adapter.owned_actions
                ):
                    context_tree_adapter.dispatch_owned_action(turn, step=step, ledger=ledger)
                    if trace is not None:
                        trace.add_step(step, canonical_context, turn, ledger.all_receipts()[before_count:])
                    step += 1
                    continue
                if challenger is not None:
                    envmap = challenger.before_act(turn, messages=messages, step=step, envmap=envmap) or envmap
                action_receipt_start = len(ledger.all_receipts())
                refreshed = run_act_turn(kernel, turn, step, compiled, executor, envmap, ledger, world_state)
                if context_tree_adapter is not None:
                    context_tree_adapter.record_public_action_result(
                        turn, step=step, receipts=ledger.all_receipts()[action_receipt_start:],
                    )
                    for receipt in ledger.all_receipts()[action_receipt_start:]:
                        _record_m_tree_receipt_note(context_tree_adapter, receipt)
                if refreshed is not None:
                    envmap = refreshed
                if trace is not None:
                    trace.add_step(step, canonical_context, turn, ledger.all_receipts()[before_count:])
                step += 1
                continue

            if (selected.run_evidence_finish_observer is not None
                    and turn.kind in {"submit_outcome", "finish_intent", "finish_outcome"}):
                selected.run_evidence_finish_observer(step=step, executor=executor, ledger=ledger)

            if challenger is not None and challenger.on_finish_attempt(
                turn, messages=messages, step=step,
                # The packet's own remaining_run_sec (same clock, same safety margin) under deadline visibility.
                remaining_sec=(
                    (lambda: visible_clock_fields(
                        selected.visible_deadline_sec, max(0.0, time.monotonic() - run_started))["remaining_run_sec"])
                    if selected.visible_deadline_sec is not None else None),
            ):
                if trace is not None:
                    trace.add_step(step, canonical_context, turn, ledger.all_receipts()[before_count:])
                step += 1
                continue

            # V1b: a deterministic oracle-edit observation holds the first
            # completion once.  The next Solver turn receives a factual,
            # typed completion obligation.  No semantic judgment is made here.
            if (
                oracle_finish_response_mode == ORACLE_HOLD_ONCE_V1
                and completion_signal is not None
                and should_hold_oracle_finish(
                    ledger, completion_signal, mode=oracle_finish_response_mode
                )
            ):
                finding_id = record_oracle_finish_hold(
                    ledger, step=step, signal=completion_signal
                )
                receipt = Receipt(
                    receipt_id=f"step-{step}:v1b_oracle_finish_reentry",
                    step=step,
                    kind="v1b_oracle_finish_reentry",
                    success=True,
                    summary=(
                        "completion held once; Solver will receive the mechanical "
                        "verification-edit observation on the next turn"
                    ),
                    payload={
                        "finding_id": finding_id,
                        "response_mode": oracle_finish_response_mode,
                        "semantic_authority": "primary_solver",
                    },
                )
                ledger.record(receipt)
                _record_m_tree_receipt_note(context_tree_adapter, receipt)
                if trace is not None:
                    trace.add_step(
                        step, canonical_context, turn,
                        ledger.all_receipts()[before_count:],
                    )
                step += 1
                continue

            # Completion remains model-owned. In the research treatments,
            # require only mechanical disposition coverage for current
            # obligations; the harness does not judge task semantics.
            disposition_decision = evaluate_completion_dispositions(
                turn,
                canonical_context,
                mode=(
                    COMPLETION_DISPOSITION_V1
                    if failed_observation_findings or v1b_finding_ids
                    else COMPLETION_DISPOSITION_CONTROL
                ),
            )
            if not disposition_decision.allowed:
                if v1b_finding_ids:
                    receipt = Receipt(
                        receipt_id=f"step-{step}:v1b_oracle_disposition_block",
                        step=step,
                        kind="v1b_oracle_disposition_block",
                        # An incomplete semantic disposition is not a harness
                        # execution failure and must not poison the next attempt.
                        success=True,
                        summary=(
                            "V1b completion held because the oracle-edit "
                            "observation was not explicitly dispositioned"
                        ),
                        payload={
                            **disposition_decision.as_payload(),
                            "block_reason": disposition_decision.reason,
                        },
                    )
                    ledger.record(receipt)
                    _record_m_tree_receipt_note(context_tree_adapter, receipt)
                else:
                    receipt = Receipt(
                        receipt_id=f"step-{step}:thin_failed_observation_disposition_block",
                        step=step,
                        kind="thin_failed_observation_disposition_block",
                        success=False,
                        summary=(
                            "Thin completion blocked because current-candidate failed "
                            "observations were not mechanically dispositioned"
                        ),
                        failure_class="failed_observation_disposition_incomplete",
                        payload=disposition_decision.as_payload(),
                    )
                    ledger.record(receipt)
                    _record_m_tree_receipt_note(context_tree_adapter, receipt)
                if trace is not None:
                    trace.add_step(
                        step, canonical_context, turn, ledger.all_receipts()[before_count:]
                    )
                step += 1
                continue
            if failed_observation_findings:
                receipt = Receipt(
                    receipt_id=f"step-{step}:thin_failed_observation_dispositions",
                    step=step,
                    kind="thin_failed_observation_dispositions",
                    success=True,
                    summary=(
                        "Primary mechanically accounted for all current-candidate "
                        "failed observations before Thin submission"
                    ),
                    payload=disposition_decision.as_payload(),
                )
                ledger.record(receipt)
                _record_m_tree_receipt_note(context_tree_adapter, receipt)
            pending_v1b_routes: tuple[Mapping[str, Any], ...] = ()
            if v1b_finding_ids:
                v1b_allowed, v1b_reason, pending_v1b_routes = validate_v1b_disposition(
                    ledger,
                    turn=turn,
                    finding_ids=v1b_finding_ids,
                )
                if not v1b_allowed:
                    receipt = Receipt(
                        receipt_id=f"step-{step}:v1b_oracle_resolution_block",
                        step=step,
                        kind="v1b_oracle_resolution_block",
                        success=True,
                        summary=(
                            "V1b completion held because the selected resolution "
                            "route did not meet its mechanical condition"
                        ),
                        payload={
                            "finding_ids": list(v1b_finding_ids),
                            "reason": v1b_reason,
                            "semantic_authority": "primary_solver",
                        },
                    )
                    ledger.record(receipt)
                    _record_m_tree_receipt_note(context_tree_adapter, receipt)
                    if trace is not None:
                        trace.add_step(
                            step, canonical_context, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    step += 1
                    continue

            # All completion-shaped protocol turns share one mechanical
            # submission path in Thin. Readiness still comes only from the
            # shared gate; disposition coverage is not a semantic pass.
            ledger.record_accounting(
                receipt_id=f"step-{step}:thin_submission_turn:{ledger.accounting_value('solver_submission_turns') + 1}",
                step=step,
                counter="solver_submission_turns",
                event="thin_submission",
            )
            binding_decision, binding = validate_persistent_submission_binding(
                turn,
                canonical_context,
                ledger,
                current_step=step,
                strict_snapshot_binding=True,
            )
            coherence = binding_decision if not binding_decision.allowed else evaluate_submission_coherence(ledger, current_step=step)
            if binding is None or not coherence.allowed:
                _record_submission_block(
                    ledger,
                    step=step,
                    reason=coherence.reason_code or "submission_binding_invalid",
                    detail=coherence.detail or "current evidence binding was not admissible",
                    binding_present=binding is not None,
                    context_tree_adapter=context_tree_adapter,
                )
                if trace is not None:
                    trace.add_step(step, canonical_context, turn, ledger.all_receipts()[before_count:])
                step += 1
                continue
            record_finish_metadata(
                ledger,
                finish_metadata=turn.finish_metadata,
                mode=selected.completion_record_mode,
                step=step,
            )
            record_persistent_submission_claim(
                ledger,
                step=step,
                binding=binding,
                task_state_custody=world_state.dynamic_snapshot() if world_state is not None else None,
                submission_mode="thin_submit",
            )
            run_submit_turn(kernel, step, compiled, executor, envmap, ledger, trace)
            decision = kernel._last_gate_decision
            if decision is not None and decision.ready:
                if v1b_finding_ids:
                    record_validated_v1b_disposition(
                        ledger,
                        finding_ids=v1b_finding_ids,
                        routes=pending_v1b_routes,
                        step=step,
                    )
                if terminal_verifier_mode == THIN_TERMINAL_VERIFIER_CONTROL:
                    _record_submission_ready(
                        ledger, step=step, decision=decision,
                        context_tree_adapter=context_tree_adapter,
                    )
                    if trace is not None:
                        trace.add_step(
                            step, canonical_context, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    return _result(
                        "submitted", step=step, compiled=compiled,
                        ledger=ledger, requests=requests,
                    )

                # VF1: terminal-only independent review.  The Solver still owns
                # the semantic completion intent; this hook fires only after
                # current binding/coherence and the shared mechanical gate are
                # already ready.  It reuses the canonical Verifier packet,
                # inspection overlay, evidence registry and recovery router.
                next_verifier_cycle = _next_terminal_verifier_cycle(
                    terminal_verifier_cycles
                )
                if next_verifier_cycle is None:
                    receipt = Receipt(
                        receipt_id=f"step-{step}:thin_terminal_verifier_cycle_exhausted",
                        step=step,
                        kind="thin_terminal_verifier_cycle_exhausted",
                        success=False,
                        summary=(
                            "VF1 terminal review cycle limit reached; completion "
                            "remains unadmitted"
                        ),
                        failure_class="verifier_cycle_exhausted",
                        payload={
                            "mode": terminal_verifier_mode,
                            "max_cycles": THIN_TERMINAL_VERIFIER_MAX_CYCLES,
                            "completed_cycles": terminal_verifier_cycles,
                        },
                    )
                    ledger.record(receipt)
                    _record_m_tree_receipt_note(context_tree_adapter, receipt)
                    if trace is not None:
                        trace.add_step(
                            step, canonical_context, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    return _result(
                        "verifier_cycle_exhausted",
                        step=step,
                        compiled=compiled,
                        ledger=ledger,
                        blockers=("verifier_cycle_exhausted",),
                        requests=requests,
                    )
                terminal_verifier_cycles = next_verifier_cycle
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:thin_terminal_verifier_hook",
                    step=step,
                    kind="thin_terminal_verifier_hook",
                    success=True,
                    summary="Thin terminal verifier hook activated after mechanical readiness",
                    payload={
                        "mode": terminal_verifier_mode,
                        "reason": "solver_submit",
                        "task_state_generation": ledger.task_state_generation(),
                        "cycle": terminal_verifier_cycles,
                        "max_cycles": THIN_TERMINAL_VERIFIER_MAX_CYCLES,
                    },
                ))
                verdict = run_model_verifier_if_available(
                    hooks, compiled, ledger,
                    step=step,
                    reason="solver_submit",
                    executor=executor,
                    envmap=envmap,
                    dynamic_state=(
                        world_state.dynamic_snapshot()
                        if world_state is not None else None
                    ),
                    memo=verifier_memo,
                )
                if verdict is None:
                    receipt = Receipt(
                        receipt_id=f"step-{step}:thin_terminal_verifier_missing",
                        step=step,
                        kind="thin_terminal_verifier_missing",
                        success=False,
                        summary="VF1 required terminal review but no verifier callable was available",
                        failure_class="verifier_missing",
                    )
                    ledger.record(receipt)
                    _record_m_tree_receipt_note(context_tree_adapter, receipt)
                    if trace is not None:
                        trace.add_step(
                            step, canonical_context, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    return _result(
                        "verifier_missing", step=step, compiled=compiled,
                        ledger=ledger, blockers=("verifier_missing",),
                        requests=requests,
                    )

                verifier_receipt = Receipt(
                    receipt_id=f"step-{step}:thin_terminal_verifier_result",
                    step=step,
                    kind="thin_terminal_verifier_result",
                    # A schema-valid verifier rejection is semantic evidence,
                    # not an execution/harness failure. Marking needs_repair as
                    # a failed receipt would poison the next deterministic
                    # completion gate and make the review loop one-shot.
                    success=True,
                    summary=f"Thin terminal verifier verdict: {verdict.verdict}",
                    payload={
                        "mode": terminal_verifier_mode,
                        "verdict": verdict.verdict,
                        "confidence": verdict.confidence,
                        "solver_repair_allowed": verdict.verdict in SOLVER_REPAIR_VERDICTS,
                    },
                )
                ledger.record(verifier_receipt)
                if context_tree_adapter is not None:
                    as_dict = getattr(verdict, "as_dict", None)
                    public_result = as_dict() if callable(as_dict) else {
                        "verdict": verdict.verdict,
                        "confidence": verdict.confidence,
                        "summary": str(getattr(verdict, "summary", "") or ""),
                        "findings": [
                            str(getattr(finding, "summary", "") or "")
                            for finding in getattr(verdict, "findings", ())
                        ],
                    }
                    context_tree_adapter.record_note(_canonical_tree_note(public_result))
                if verdict.verdict == "completed":
                    # Independent observations may change currentness receipts,
                    # so final admission always re-runs the deterministic gate.
                    ready_decision = kernel.completion_gate.evaluate(
                        compiled, ledger, kernel.monitor_runner.run(compiled, ledger),
                    )
                    if ready_decision.ready:
                        _record_submission_ready(
                            ledger, step=step, decision=ready_decision,
                            context_tree_adapter=context_tree_adapter,
                        )
                        if trace is not None:
                            trace.add_step(
                                step, canonical_context, turn,
                                ledger.all_receipts()[before_count:],
                            )
                        return _result(
                            "submitted", step=step, compiled=compiled,
                            ledger=ledger, requests=requests,
                        )
                    receipt = Receipt(
                        receipt_id=f"step-{step}:thin_terminal_verifier_gate_not_ready",
                        step=step,
                        kind="thin_terminal_verifier_gate_not_ready",
                        success=False,
                        summary=(
                            "VF1 completed review but the fresh deterministic "
                            "completion gate still has blockers"
                        ),
                        failure_class="completion_gate_not_ready",
                        payload={
                            "blockers": [
                                {
                                    "code": blocker.code,
                                    "detail": blocker.detail,
                                    "source": blocker.source,
                                }
                                for blocker in ready_decision.blockers
                            ],
                        },
                    )
                    ledger.record(receipt)
                    _record_m_tree_receipt_note(context_tree_adapter, receipt)
                    if trace is not None:
                        trace.add_step(
                            step, canonical_context, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    step += 1
                    continue

                if verdict.verdict in SOLVER_REPAIR_VERDICTS:
                    # Verifier findings have already been applied to the ledger.
                    # Re-enter the Solver without prescribing the next action.
                    if trace is not None:
                        trace.add_step(
                            step, canonical_context, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    step += 1
                    continue

                if (
                    verdict.verdict in SOLVER_EVIDENCE_GATHERING_VERDICTS
                    and bool(verdict.findings)
                ):
                    # Missing evidence is not a production defect. The parsed
                    # verifier result has already materialized blocking,
                    # Solver-visible evidence obligations in the ledger. Re-enter
                    # only to gather fresh current-state evidence; the existing
                    # finding/evidence gate prevents blind resubmission.
                    receipt = Receipt(
                        receipt_id=f"step-{step}:thin_terminal_verifier_evidence_reentry",
                        step=step,
                        kind="thin_terminal_verifier_evidence_reentry",
                        success=True,
                        summary=(
                            "Thin terminal verifier requested fresh completion "
                            "evidence; returning control to Solver"
                        ),
                        payload={
                            "mode": terminal_verifier_mode,
                            "verdict": verdict.verdict,
                            "confidence": verdict.confidence,
                            "active_finding_count": len(
                                ledger.active_finding_context(step + 1, limit=1000)
                            ),
                            "task_state_generation": ledger.task_state_generation(),
                            "semantic_role": "evidence_gathering_not_production_repair",
                        },
                    )
                    ledger.record(receipt)
                    _record_m_tree_receipt_note(context_tree_adapter, receipt)
                    if trace is not None:
                        trace.add_step(
                            step, canonical_context, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    step += 1
                    continue

                # Tool/provider/protocol/harness review failures are verifier-
                # owned and must never be converted into a candidate defect or
                # bypassed into submission.
                if trace is not None:
                    trace.add_step(
                        step, canonical_context, turn,
                        ledger.all_receipts()[before_count:],
                    )
                return _result(
                    "verifier_review_unavailable",
                    step=step,
                    compiled=compiled,
                    ledger=ledger,
                    blockers=("verifier_review_unavailable",),
                    requests=requests,
                )
            blockers = tuple(
                str(getattr(blocker, "code", "completion_gate_not_ready"))
                for blocker in getattr(decision, "blockers", ())
            ) or ("completion_gate_not_ready",)
            _record_submission_block(
                ledger,
                step=step,
                reason="completion_gate_not_ready",
                detail=", ".join(blockers),
                binding_present=True,
                context_tree_adapter=context_tree_adapter,
            )
            if trace is not None:
                trace.add_step(step, canonical_context, turn, ledger.all_receipts()[before_count:])
            step += 1
        except KernelRunTimeout:
            ledger.record(Receipt(
                receipt_id=f"step-{step}:thin_deadline_exception",
                step=step,
                kind="thin_deadline_exception",
                success=False,
                summary="Thin loop deadline expired at a shared boundary",
                failure_class="timeout",
            ))
            return _result("timeout", step=step, compiled=compiled, ledger=ledger, blockers=("run_deadline_exceeded",), requests=requests)
        except RunCancellationRequested:
            ledger.record(Receipt(
                receipt_id=f"step-{step}:thin_cancelled",
                step=step,
                kind="thin_cancelled",
                success=False,
                summary="Thin loop cancelled before another task action",
                failure_class="external_run_cancellation",
            ))
            return _result("timeout", step=step, compiled=compiled, ledger=ledger, blockers=("external_run_cancellation",), requests=requests)

    ledger.record(Receipt(
        receipt_id=f"step-{step}:thin_step_budget_exhausted",
        step=step,
        kind="thin_step_budget_exhausted",
        success=False,
        summary="Thin loop exhausted its step budget without external submission",
        failure_class="step_budget_exhausted",
    ))
    return _result("step_budget_exhausted", step=step, compiled=compiled, ledger=ledger, blockers=("step_budget_exhausted",), requests=requests)


def run_thin_loop(
    envmap: EnvMap,
    executor: Executor,
    hooks: ThinSolverHooks,
    *,
    config: ThinLoopConfig | None = None,
    world_state: WorldState | None = None,
    trace: RunTrace | None = None,
) -> ThinLoopResult:
    """Run Thin and release an injected task-local context tree on every exit."""
    adapter = None if config is None else config.context_tree_adapter
    result: ThinLoopResult | None = None
    cleanup_receipts: list[Receipt] = []
    failure: BaseException | None = None
    try:
        result = _run_thin_loop_impl(
            envmap, executor, hooks, config=config, world_state=world_state, trace=trace,
        )
    except BaseException as exc:
        failure = exc
    finally:
        selected_mode = (
            getattr(config, "solver_long_command_mode", None) if config is not None else None
        ) or selected_long_command_mode()
        if selected_mode == "background_v1":
            job_ids = list(getattr(executor, "_aether_long_command_jobs", ()))
            for index, job_id in enumerate(job_ids):
                try:
                    probe = executor.probe_job(job_id)
                    stopped = executor.stop_process(job_id) if probe.found and not probe.completed else False
                    after = executor.probe_job(job_id)
                    cleanup_receipts.append(Receipt(
                        receipt_id=f"run_end:background_job_cleanup:{index}:{job_id}",
                        step=(result.step if result is not None else 0),
                        kind="background_job_cleanup",
                        success=bool(not after.found or after.completed),
                        summary=(f"run-end cleanup stopped job {job_id}" if stopped else
                                 f"run-end cleanup observed job {job_id} {after.status}"),
                        payload={"job_id": job_id, "status_before": probe.status,
                            "status_after": after.status, "exit_code": after.exit_code,
                            "stopped": bool(stopped), "cleanup_scope": "background_v1_run_end"},
                    ))
                except Exception as exc:
                    cleanup_receipts.append(Receipt(
                        receipt_id=f"run_end:background_job_cleanup:{index}:{job_id}",
                        step=(result.step if result is not None else 0),
                        kind="background_job_cleanup", success=False,
                        summary=f"run-end cleanup failed for job {job_id}: {type(exc).__name__}",
                        failure_class="background_job_cleanup_failed",
                        payload={"job_id": job_id, "error_type": type(exc).__name__},
                    ))
            try:
                setattr(executor, "_aether_long_command_jobs", [])
                setattr(executor, "_aether_long_command_cleanup_receipts", list(cleanup_receipts))
            except Exception:
                pass
        if adapter is not None:
            adapter.close()
    if failure is not None:
        if cleanup_receipts and trace is not None:
            trace.add_step(
                step=(result.step if result is not None else 0),
                context_packet={"run_end_cleanup": "background_v1"},
                turn=None,
                step_receipts=cleanup_receipts,
            )
        try:
            setattr(failure, "background_job_cleanup_receipts", tuple(cleanup_receipts))
        except Exception:
            pass
        raise failure.with_traceback(failure.__traceback__)
    if result is None:
        raise RuntimeError("Thin loop returned no result after cleanup")
    if cleanup_receipts:
        result = replace(result, receipts=(*result.receipts, *cleanup_receipts))
    return result


def stable_json_for_hash(value: Any) -> str:
    """Local wrapper keeps request hashing independent of provider imports."""
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True)


__all__ = [
    "ContextTreeAdapter",
    "ThinLoopConfig",
    "ThinLoopResult",
    "ThinSolverHooks",
    "run_thin_loop",
]
