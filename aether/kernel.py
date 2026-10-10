"""Aether-Next kernel: the solver/verifier control loop.

The solver-turn parse-error handling (same-step retry) lives in
kernel_solver_turn.py; the verifier-disagreement stalemate check lives in
kernel_stalemate.py. Both were extracted from this module to hold it under
the 500-LOC cap; each is a pure move of the corresponding branch out of
``AetherNextKernel.run``, called back in unchanged.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, TYPE_CHECKING

from .completion import CompletionGate, FailureParser
from .completion_record import (
    COMPLETION_RECORD_OFF,
    SUPPORTED_COMPLETION_RECORD_MODES,
    ensure_initial_nonadherence_receipt,
    project_completion_record_context,
    record_finish_metadata,
)
from .completion_disposition import (
    CONTROL as COMPLETION_DISPOSITION_CONTROL,
    SUPPORTED_MODES as SUPPORTED_COMPLETION_DISPOSITION_MODES,
    current_completion_finding_ids,
    evaluate_completion_dispositions,
)
from .boundary_verification import (
    CONTROL as BOUNDARY_VERIFICATION_CONTROL,
    SUPPORTED_MODES as SUPPORTED_BOUNDARY_VERIFICATION_MODES,
    project_boundary_verification_checkpoint,
)
from .execution import (
    BootstrapEngine, Executor, ExperimentEngine, PerceptionLane, ProcessOrchestratorV2,
)
from .persistent_runtime import (
    INCUMBENT_PREFIX_RENDERER, SOLVER_CONTEXT_MODES, SOLVER_PREFIX_RENDERERS,
    SOLVER_ASYNC_CONTROL, SOLVER_ASYNC_SERIAL_JOBS_V1,
    SOLVER_ASYNC_INDEPENDENT_JOBS_V1, SOLVER_ASYNC_MODES,
    SOLVER_TASK_CONTRACT_CONTROL, SOLVER_TASK_CONTRACT_MODES,
    SOLVER_REALITY_TRANSPORT_CONTROL, SOLVER_REALITY_TRANSPORT_MODES,
    SOLVER_HOSTED_TOOL_SEARCH_CONTROL, SOLVER_HOSTED_TOOL_SEARCH_MODES,
    VERIFIER_ACTIVATION_CONTINUITY_CONTROL, VERIFIER_ACTIVATION_CONTINUITY_MODES,
    build_persistent_runtime,
)
from .kernel_messages import build_solver_messages
from .context_cleanup import CONTEXT_CLEANUP_MODES, apply_context_cleanup
from .kernel_verifier import run_model_verifier_if_available
from .persistent_context import build_persistent_context
from .ledger import ExecutionLedger, Receipt
from .monitors import IntegrityGuards, LocalOnlySafetyGuard, MonitorRunner
from .kernel_dispatch import dispatch_action
from .kernel_solver_turn import handle_solver_parse_error
from .kernel_stalemate import check_verifier_stalemate
from .kernel_turns import run_act_turn, run_submit_turn
from .persistent_reanchor import CURRENT_FULL, SUPPORTED_REANCHOR_MODES, project_persistent_context_for_model
from .provider_frontier_recovery import (
    CONTROL as PROVIDER_FRONTIER_RECOVERY_CONTROL,
    NO_TOOL_MAX_OUTPUT_V1 as PROVIDER_FRONTIER_RECOVERY_TREATMENT,
    SUPPORTED_MODES as SUPPORTED_PROVIDER_FRONTIER_RECOVERY_MODES,
    classify_frontier_recovery,
)
from .persistent_submission import (
    record_persistent_submission_claim,
    validate_persistent_submission_binding,
)
from .submission_coherence import (
    coherence_block_allows_independent_review,
    evaluate_submission_coherence,
    record_submission_coherence_block,
)
from .model_hooks import ModelOutputError, ModelProviderError
from .run_cancellation import raise_if_run_cancelled
from .run_deadline import raise_if_run_deadline_exceeded
from .route_preflight import preflight_proof_routes
from .runtime_ir import (
    CompiledRuntime, EnvMap, SolverTurn, normalize_relpath,
)
from .world import WorldState
from .task_contract import TaskClause, TaskContract

if TYPE_CHECKING:
    from .tracing import RunTrace

@dataclass(frozen=True)
class KernelResult:
    status: str
    step: int
    reconfigurations: int
    used_check_ids: tuple[str, ...] = ()
    used_check_commands: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    env_digest: str = ""
    receipts: tuple[Receipt, ...] = ()
    accounting: Mapping[str, int] | None = None


def _provider_failure_result(
    *,
    exc: ModelProviderError,
    step: int,
    reconfigurations: int,
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    parse_correction_attempted: bool,
    provider_frontier_recoveries: int = 0,
) -> KernelResult:
    budget_refused = bool(getattr(exc, "pre_dispatch_budget_admission_refused", False))
    frontier_counterfactual = None
    if not budget_refused:
        # Observability only: classify the same mechanical provider boundary
        # under the research treatment without changing control behavior,
        # retrying, resetting continuity, or admitting another model call.
        observed = classify_frontier_recovery(
            exc,
            mode=PROVIDER_FRONTIER_RECOVERY_TREATMENT,
            used_recoveries=int(provider_frontier_recoveries),
            max_recoveries=1,
        )
        frontier_counterfactual = {
            "mode": PROVIDER_FRONTIER_RECOVERY_TREATMENT,
            "eligible": observed.eligible,
            "reason": observed.reason,
            "facts": dict(observed.facts),
            "behavior_changed": False,
        }
    receipt_kind = "provider_budget_admission" if budget_refused else "provider_failure"
    failure_class = "provider_budget_admission" if budget_refused else "provider_failure"
    receipt_id = (
        f"step-{step}:{exc.role}_provider_budget_admission"
        if budget_refused else f"step-{step}:solver_provider_failure"
    )
    ledger.record(Receipt(
        receipt_id=receipt_id,
        step=step,
        kind=receipt_kind,
        success=False,
        summary=(
            f"{exc.role} provider dispatch refused by finite budget admission before model output"
            if budget_refused else
            f"{exc.role} provider invocation failed before model output: {exc.cause_type}"
        ),
        failure_class=failure_class,
        payload={
            "role": exc.role,
            "error_type": exc.cause_type,
            "error": exc.cause_message[:2000],
            "model_output_available": False,
            "parse_correction_attempted": parse_correction_attempted,
            "provider_retry_attempted": False,
            "provider_dispatch_attempted": False if budget_refused else None,
            "budget_admission_refused": budget_refused,
            "provider_frontier_counterfactual": frontier_counterfactual,
        },
    ))
    return KernelResult(
        status="provider_budget_blocked" if budget_refused else "provider_failure",
        step=step,
        reconfigurations=reconfigurations,
        blockers=((f"{exc.role}_provider_budget_admission",) if budget_refused else (f"{exc.role}_provider_failure",)),
        env_digest=compiled.env_digest,
        receipts=ledger.all_receipts(),
        accounting=ledger.accounting_snapshot(),
    )


_TERMINAL_REVIEW_RESOLVABLE_BLOCKER_CODES = frozenset({
    "task_state_snapshot_unknown",
})


def _terminal_review_preflight(
    decision: Any,
) -> tuple[bool, tuple[Any, ...]]:
    """Whether semantic review may run at this mechanical boundary.

    Independent review can itself establish one narrow missing-currentness fact:
    an explicitly unknown task-state snapshot, via registered read-only
    inspection.  Every other completion blocker is execution reality that must
    be resolved by the Primary Agent before spending semantic review.
    """
    if decision is None:
        return False, ()
    blockers = tuple(getattr(decision, "blockers", ()) or ())
    nonreviewable = tuple(
        blocker for blocker in blockers
        if str(getattr(blocker, "code", ""))
        not in _TERMINAL_REVIEW_RESOLVABLE_BLOCKER_CODES
    )
    return not nonreviewable, nonreviewable


def _record_terminal_review_deferred(
    ledger: ExecutionLedger, *, step: int, blockers: tuple[Any, ...],
) -> None:
    """Record factual review deferral without turning it into task failure."""
    blocker_rows = [
        {
            "code": str(getattr(blocker, "code", "")),
            "detail": str(getattr(blocker, "detail", "")),
            "source": str(getattr(blocker, "source", "")),
        }
        for blocker in blockers
    ]
    blocker_codes = [row["code"] for row in blocker_rows if row["code"]]
    if not blocker_codes:
        blocker_codes = ["completion_preflight_missing"]
    ledger.record(Receipt(
        receipt_id=f"step-{step}:advisory_review_deferred_mechanical_readiness",
        step=step,
        kind="advisory_review_deferred_mechanical_readiness",
        success=True,
        summary=(
            "terminal advisory review deferred because deterministic "
            "completion reality is not mechanically ready"
        ),
        payload={
            "review_invoked": False,
            "blocker_codes": blocker_codes,
            "blockers": blocker_rows,
            "review_resolvable_blocker_codes": sorted(
                _TERMINAL_REVIEW_RESOLVABLE_BLOCKER_CODES
            ),
            "semantic_authority": "frontier",
        },
    ))


def _completed_result(
    step: int, reconfigurations: int, decision: Any,
    compiled: CompiledRuntime, ledger: ExecutionLedger,
) -> KernelResult:
    """Build a completed ``KernelResult`` only from a ready gate decision.

    This helper is the final mechanical completion boundary.  A model verdict
    may contribute semantic evidence, but it can never override current gate
    blockers.  Keep the guard here as defence in depth for every caller.
    """
    if not bool(getattr(decision, "ready", False)):
        raise ValueError("completed result requires a ready completion decision")
    used_ids = set(decision.used_check_ids)
    return KernelResult(
        status="completed", step=step, reconfigurations=reconfigurations,
        used_check_ids=decision.used_check_ids,
        used_check_commands=tuple(
            c.command for c in compiled.planned_checks() if c.check_id in used_ids
        ),
        blockers=(), env_digest=compiled.env_digest, receipts=ledger.all_receipts(),
        accounting=ledger.accounting_snapshot(),
    )


class KernelHooks(Protocol):
    def solve(self, messages: list[dict[str, str]], compiled: CompiledRuntime) -> SolverTurn:
        ...

class AetherNextKernel:
    # Bounded verifier-disagreement protocol: after this many consecutive
    # verification rounds in which the identical non-empty finding set
    # survives despite intervening solver evidence, the run terminates with
    # status ``verifier_stalemate``.  The harness records the disagreement;
    # it never adjudicates it.
    STALEMATE_ROUNDS = 3
    SUBMIT_STALEMATE_ROUNDS = 3

    def __init__(
        self,
        *,
        max_steps: int | None = 24,
        max_solver_turns: int | None = None,
        max_accepted_task_actions: int | None = None,
        runtime_identity: Mapping[str, Any] | None = None,
        solver_reanchor_mode: str = CURRENT_FULL,
        solver_context_mode: str = "full",
        context_cleanup_mode: str = "off",
        completion_record_mode: str = COMPLETION_RECORD_OFF,
        solver_reasoning_mode: str = "control",
        solver_async_mode: str = SOLVER_ASYNC_CONTROL,
        solver_task_contract_mode: str = SOLVER_TASK_CONTRACT_CONTROL,
        solver_prefix_renderer: str = INCUMBENT_PREFIX_RENDERER,
        solver_reality_transport_mode: str = SOLVER_REALITY_TRANSPORT_CONTROL,
        solver_hosted_tool_search_mode: str = SOLVER_HOSTED_TOOL_SEARCH_CONTROL,
        verifier_activation_continuity_mode: str = VERIFIER_ACTIVATION_CONTINUITY_CONTROL,
        boundary_verification_mode: str = BOUNDARY_VERIFICATION_CONTROL,
        completion_disposition_mode: str = COMPLETION_DISPOSITION_CONTROL,
        provider_frontier_recovery_mode: str = PROVIDER_FRONTIER_RECOVERY_CONTROL,
        refresh_runtime_operation_status: bool = False,
        snapshot_callback: Callable[[int], None] | None = None,
        snapshot_steps: tuple[int, ...] = (),
        cancellation_event: Any | None = None,
    ) -> None:
        self.max_steps = max(1, int(max_steps)) if max_steps is not None else None
        self.max_solver_turns = (
            max(1, int(max_solver_turns))
            if max_solver_turns is not None else self.max_steps
        )
        self.max_accepted_task_actions = (
            max(1, int(max_accepted_task_actions))
            if max_accepted_task_actions is not None else None
        )
        self.runtime_identity = dict(runtime_identity or {})
        self.solver_reanchor_mode = str(solver_reanchor_mode or CURRENT_FULL)
        self.solver_context_mode = str(solver_context_mode or "full").strip().lower()
        if self.solver_context_mode not in SOLVER_CONTEXT_MODES:
            raise ValueError(f"unsupported Solver context mode: {solver_context_mode}")
        self.context_cleanup_mode = str(context_cleanup_mode or "off").strip().lower()
        if self.context_cleanup_mode not in CONTEXT_CLEANUP_MODES:
            raise ValueError(f"unsupported context cleanup mode: {context_cleanup_mode}")
        self.completion_record_mode = str(completion_record_mode or COMPLETION_RECORD_OFF).strip().lower()
        if self.completion_record_mode not in SUPPORTED_COMPLETION_RECORD_MODES:
            raise ValueError(f"unsupported completion record mode: {completion_record_mode}")
        self.context_accounting_history: list[dict[str, Any]] = []
        self.solver_reasoning_mode = str(solver_reasoning_mode or "control").strip().lower()
        self.solver_async_mode = str(solver_async_mode or SOLVER_ASYNC_CONTROL).strip().lower()
        self.solver_task_contract_mode = str(
            solver_task_contract_mode or SOLVER_TASK_CONTRACT_CONTROL
        ).strip().lower()
        self.solver_prefix_renderer = str(
            solver_prefix_renderer or INCUMBENT_PREFIX_RENDERER
        ).strip().lower()
        self.solver_reality_transport_mode = str(
            solver_reality_transport_mode or SOLVER_REALITY_TRANSPORT_CONTROL
        ).strip().lower()
        self.solver_hosted_tool_search_mode = str(
            solver_hosted_tool_search_mode or SOLVER_HOSTED_TOOL_SEARCH_CONTROL
        ).strip().lower()
        self.verifier_activation_continuity_mode = str(
            verifier_activation_continuity_mode or VERIFIER_ACTIVATION_CONTINUITY_CONTROL
        ).strip().lower()
        self.boundary_verification_mode = str(
            boundary_verification_mode or BOUNDARY_VERIFICATION_CONTROL
        ).strip().lower()
        self.completion_disposition_mode = str(
            completion_disposition_mode or COMPLETION_DISPOSITION_CONTROL
        ).strip().lower()
        self.provider_frontier_recovery_mode = str(
            provider_frontier_recovery_mode or PROVIDER_FRONTIER_RECOVERY_CONTROL
        ).strip().lower()
        self.refresh_runtime_operation_status = bool(
            refresh_runtime_operation_status
            or self.solver_async_mode in {
                SOLVER_ASYNC_SERIAL_JOBS_V1,
                SOLVER_ASYNC_INDEPENDENT_JOBS_V1,
            }
        )
        if self.solver_reasoning_mode not in {
            "control", "discriminating_experiment_v1", "vertical_slice_v1", "commitment_v1",
        }:
            raise ValueError(f"unsupported Solver reasoning mode: {solver_reasoning_mode}")
        if self.solver_async_mode not in SOLVER_ASYNC_MODES:
            raise ValueError(f"unsupported Solver async mode: {solver_async_mode}")
        if self.solver_task_contract_mode not in SOLVER_TASK_CONTRACT_MODES:
            raise ValueError(
                f"unsupported Solver task-contract mode: {solver_task_contract_mode}"
            )
        if self.solver_prefix_renderer not in SOLVER_PREFIX_RENDERERS:
            raise ValueError(f"unsupported Solver prefix renderer: {solver_prefix_renderer}")
        if self.solver_reality_transport_mode not in SOLVER_REALITY_TRANSPORT_MODES:
            raise ValueError(
                f"unsupported Solver reality transport mode: {solver_reality_transport_mode}"
            )
        if self.solver_hosted_tool_search_mode not in SOLVER_HOSTED_TOOL_SEARCH_MODES:
            raise ValueError(
                f"unsupported Solver hosted tool search mode: {solver_hosted_tool_search_mode}"
            )
        if self.verifier_activation_continuity_mode not in VERIFIER_ACTIVATION_CONTINUITY_MODES:
            raise ValueError(
                f"unsupported Verifier activation continuity mode: {verifier_activation_continuity_mode}"
            )
        if self.boundary_verification_mode not in SUPPORTED_BOUNDARY_VERIFICATION_MODES:
            raise ValueError(
                f"unsupported boundary verification mode: {boundary_verification_mode}"
            )
        if self.completion_disposition_mode not in SUPPORTED_COMPLETION_DISPOSITION_MODES:
            raise ValueError(
                f"unsupported completion disposition mode: {completion_disposition_mode}"
            )
        if self.provider_frontier_recovery_mode not in SUPPORTED_PROVIDER_FRONTIER_RECOVERY_MODES:
            raise ValueError(
                f"unsupported provider frontier recovery mode: {provider_frontier_recovery_mode}"
            )
        if self.solver_reanchor_mode not in SUPPORTED_REANCHOR_MODES:
            raise ValueError(f"unsupported PERSISTENT Solver re-anchor mode: {self.solver_reanchor_mode}")
        self.snapshot_callback, self._snapshot_steps = snapshot_callback, frozenset(snapshot_steps)
        self.monitor_runner = MonitorRunner()
        self.completion_gate = CompletionGate()
        self.failure_parser = FailureParser()
        self.bootstrap_engine = BootstrapEngine()
        self.process_orchestrator = ProcessOrchestratorV2()
        self.perception_lane = PerceptionLane()
        self.experiment_engine = ExperimentEngine()
        self.integrity_guards = IntegrityGuards()
        self.safety_guard = LocalOnlySafetyGuard()
        self._active_ledger: ExecutionLedger | None = None
        self._active_env_digest = ""
        self._active_step = 0
        self._active_reconfigurations = 0
        self._cancellation_event = cancellation_event
        self._runtime_capability_cache: frozenset[str] | None = None
        # Model-invisible canonical wall-time telemetry for experiment/audit use.
        # This is never inserted into receipts or Solver context by itself.
        self.runtime_budget_history: list[dict[str, Any]] = []

    def build_solver_messages(
        self,
        compiled: CompiledRuntime,
        context_packet: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        return build_solver_messages(compiled, context_packet)

    @staticmethod
    def _probe_runtime_capability_ids(executor: Executor) -> set[str]:
        """Return current mechanically-probed dynamic executor capabilities."""
        result: set[str] = set()
        computer_probe = getattr(executor, "computer_available", None)
        if callable(computer_probe):
            try:
                if bool(computer_probe()):
                    result.add("computer_control")
            except Exception:
                # Availability is fail-closed. The executor action path probes
                # again before state change, so a transient false positive can
                # never authorize unobserved GUI mutation.
                pass
        return result

    def _live_runtime_capability_ids(self, executor: Executor) -> set[str]:
        """Return cached dynamic capabilities until a causal invalidation."""
        if self._runtime_capability_cache is None:
            self._runtime_capability_cache = frozenset(
                self._probe_runtime_capability_ids(executor)
            )
        return set(self._runtime_capability_cache)

    def invalidate_runtime_capability_cache(self) -> None:
        """Require a fresh capability probe after process/session state may change."""
        self._runtime_capability_cache = None

    def _refresh_runtime_operation_status(
        self, executor: Executor, ledger: ExecutionLedger, *, step: int,
    ) -> None:
        """Mechanically refresh registered live operations without semantic inference."""
        for process_id, process in tuple(ledger.live_processes().items()):
            generation = str(process.get("process_generation") or "")
            try:
                probe = executor.probe_job(process_id)
                payload = {
                    "process_id": probe.process_id or process_id,
                    "job_id": probe.job_id or probe.process_id or process_id,
                    "job_status": probe.status,
                    "completed": probe.completed,
                    "job_succeeded": probe.succeeded,
                    "exit_code": probe.exit_code,
                    "detail": probe.detail,
                    "process_generation": probe.process_generation or generation,
                    "process_generation_verified": probe.process_generation_verified,
                    "lifecycle_authority": probe.lifecycle_authority,
                    "pid": probe.pid,
                    "automatic_runtime_refresh": True,
                }
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:runtime_operation_status:{process_id}",
                    step=step, kind="runtime_operation_status_refresh",
                    success=bool(probe.found), state_change=False,
                    summary=f"runtime operation {process_id}: {probe.status}",
                    failure_class="" if probe.found else "runtime_operation_status_unavailable",
                    payload=payload,
                ))
            except Exception as exc:
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:runtime_operation_status:{process_id}",
                    step=step, kind="runtime_operation_status_refresh",
                    success=False, state_change=False,
                    summary=f"runtime operation status unavailable for {process_id}",
                    failure_class="runtime_operation_status_unavailable",
                    payload={
                        "process_id": process_id,
                        "job_id": process_id,
                        "job_status": "unknown",
                        "process_generation": generation,
                        "process_generation_verified": False,
                        "automatic_runtime_refresh": True,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:1000],
                    },
                ))

    def run(
        self,
        envmap: EnvMap,
        executor: Executor,
        hooks: KernelHooks,
        *,
        world_state: WorldState | None = None,
        trace: RunTrace | None = None,
        run_timeout_s: float | None = None,
        run_started_monotonic: float | None = None,
    ) -> KernelResult:
        # Perception (e.g. vision transcription) needs the model hooks at
        # dispatch time; scoped to this run.
        self.active_hooks = hooks
        self.context_accounting_history = []
        resolved = build_persistent_runtime(
            envmap,
            solver_context_mode=self.solver_context_mode,
            solver_reasoning_mode=self.solver_reasoning_mode,
            solver_async_mode=self.solver_async_mode,
            solver_task_contract_mode=self.solver_task_contract_mode,
            solver_prefix_renderer=self.solver_prefix_renderer,
            solver_reality_transport_mode=self.solver_reality_transport_mode,
            solver_hosted_tool_search_mode=self.solver_hosted_tool_search_mode,
            verifier_activation_continuity_mode=self.verifier_activation_continuity_mode,
        )
        if resolved.config_invalid_blockers:
            return KernelResult(
                status="config_invalid", step=0, reconfigurations=0,
                blockers=resolved.config_invalid_blockers,
                env_digest=envmap.digest(), receipts=(),
            )
        runtime_ir = resolved.runtime_ir
        compiled = resolved.compiled  # type: ignore[assignment]
        objective_graph = resolved.objective_graph
        eval_index = resolved.eval_index
        ledger = ExecutionLedger()
        self._runtime_capability_cache = None
        self._active_ledger = ledger
        self._active_env_digest = compiled.env_digest
        self._active_step = 0
        self._active_reconfigurations = 0
        identity = dict(self.runtime_identity)
        identity.setdefault("workspace_id", envmap.workspace_root)
        identity.setdefault("environment_id", envmap.digest())
        identity.setdefault("runtime_path", "persistent_v0")
        identity.setdefault("identity_complete", bool(
            identity.get("task_id") and identity.get("run_id")
            and identity.get("primary_agent_id")
        ))
        ledger.install_runtime_identity(identity)
        ledger.seed_capabilities(compiled.selected_capability_ids())
        ledger.ensure_objective(compiled.objective_graph)
        realization = dict(compiled.config_realization)
        realization.update({
            "runtime_path": "persistent_v0",
            "configuration_model_calls": 0,
            "primary_agent_identity": "task_run_stable",
            "model_authored_reconfiguration": False,
        })
        ledger.record_config_realization(realization)
        route_rows, route_issues = preflight_proof_routes(compiled, executor, envmap, hooks=hooks)
        ledger.record(Receipt(
            receipt_id="config:route_preflight",
            step=0,
            kind="route_preflight",
            success=not bool(route_issues),
            summary=(
                "compiled proof routes available"
                if not route_issues else "compiled proof routes unavailable"
            ),
            failure_class="config_invalid" if route_issues else "",
            payload={
                "rows": [row.as_dict() for row in route_rows],
                "issues": [issue.as_dict() for issue in route_issues],
            },
        ))
        if route_issues:
            return KernelResult(
                status="config_invalid", step=0, reconfigurations=0,
                blockers=tuple(f"{issue.code}:{issue.clause_id}" for issue in route_issues),
                env_digest=compiled.env_digest, receipts=ledger.all_receipts(),
                accounting=ledger.accounting_snapshot(),
            )
        if world_state is not None and compiled.task_contract is not None:
            world_state.task_contract = compiled.task_contract
        if world_state is None:
            # The compiled task truth becomes the initial immutable contract;
            # subsequent solver actions only update dynamic state.  This keeps
            # direct callers safe while allowing adapters to inject a richer
            # pre-existing WorldState when they have one.
            world_state = WorldState(
                task_contract=(
                    compiled.task_contract
                    if compiled.task_contract is not None
                    else TaskContract.create(
                        compiled.task_prompt,
                        (TaskClause(
                            "compiled:objective",
                            compiled.success_definition or compiled.task_prompt,
                        ),),
                    )
                ),
                env_facts={
                    "workspace_root": envmap.workspace_root,
                    "network_scope": envmap.network_scope,
                    "visible_file_count": len(envmap.visible_files),
                    "visible_dir_count": len(envmap.visible_dirs),
                },
            )
        if trace is not None:
            trace.set_runtime(runtime_ir, compiled.prefix_messages())
        reconfigurations = 0
        step = 0
        context_packet: Mapping[str, Any] | None = None
        turn: SolverTurn | None = None
        verifier_round_finding_sets: list[frozenset[str]] = []
        verifier_memo: dict[str, Any] = {}
        submit_without_evidence_rounds = 0
        provider_frontier_recoveries = 0
        run_started = (
            float(run_started_monotonic)
            if run_started_monotonic is not None
            else time.monotonic()
        )
        # Wall-clock backstop. The docker runner also arms a one-shot SIGALRM,
        # but that alarm can be swallowed if it fires inside a broad except (the
        # RC5 failure mode). This monotonic deadline is checked every iteration,
        # so the loop terminates even if an interrupt was absorbed somewhere the
        # re-raise guards did not cover -- belt to the SIGALRM suspenders.
        deadline = (
            run_started + run_timeout_s
            if run_timeout_s is not None and run_timeout_s > 0
            else None
        )
        while self.max_steps is None or step < self.max_steps:
            raise_if_run_cancelled(self._cancellation_event)
            if self.refresh_runtime_operation_status:
                self._refresh_runtime_operation_status(executor, ledger, step=step)
            now = time.monotonic()
            elapsed_s = max(0.0, now - run_started)
            ledger.update_runtime_budget_state({
                "used_kernel_steps": int(step),
                "run_timeout_sec": (float(run_timeout_s) if run_timeout_s is not None else None),
                "elapsed_run_sec": round(elapsed_s, 3),
                "remaining_run_sec": (round(max(0.0, deadline - now), 3) if deadline is not None else None),
                "wall_clock_authority": (
                    "runtime_supplied_timeout" if run_timeout_s is not None else "unknown"
                ),
            })
            self.runtime_budget_history.append({
                "step": int(step),
                "run_timeout_sec": (float(run_timeout_s) if run_timeout_s is not None else None),
                "elapsed_run_sec": round(elapsed_s, 3),
                "remaining_run_sec": (
                    round(max(0.0, deadline - now), 3) if deadline is not None else None
                ),
                "wall_clock_authority": (
                    "runtime_supplied_timeout" if run_timeout_s is not None else "unknown"
                ),
            })
            self._active_step = step
            self._active_reconfigurations = reconfigurations
            runtime_capability_ids = self._live_runtime_capability_ids(executor)
            runtime_caps_changed = ledger.set_runtime_capabilities(runtime_capability_ids)
            configure_runtime_capabilities = getattr(hooks, "configure_runtime_capabilities", None)
            if callable(configure_runtime_capabilities):
                configure_runtime_capabilities(runtime_capability_ids)
            if runtime_caps_changed:
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:runtime_capability_refresh",
                    step=step, kind="runtime_capability_refresh", success=True,
                    summary="refreshed current live executor capabilities",
                    payload={
                        "runtime_capability_ids": sorted(runtime_capability_ids),
                        "authority": "live_executor_probe",
                        "compiled_runtime_mutated": False,
                    },
                ))
            if (
                self.max_solver_turns is not None
                and ledger.accounting_value("solver_provider_turns") >= self.max_solver_turns
            ):
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:solver_turn_budget_exhausted",
                    step=step, kind="solver_turn_budget_exhausted", success=False,
                    summary=(
                        f"maximum solver provider turns reached: {self.max_solver_turns}; "
                        "accepted task-action budget is tracked separately"
                    ),
                    failure_class="solver_turn_budget_exhausted",
                    payload={"max_solver_turns": self.max_solver_turns,
                             "accounting": ledger.accounting_snapshot()},
                ))
                return KernelResult(
                    status="solver_turn_budget_exhausted", step=step,
                    reconfigurations=reconfigurations,
                    blockers=("solver_turn_budget_exhausted",),
                    env_digest=compiled.env_digest, receipts=ledger.all_receipts(),
                    accounting=ledger.accounting_snapshot(),
                )
            if deadline is not None and now >= deadline:
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:kernel_deadline_exceeded",
                    step=step,
                    kind="kernel_deadline_exceeded",
                    success=False,
                    summary=(
                        f"kernel loop deadline reached ({run_timeout_s:g}s); terminating "
                        "so the run can be graded instead of spinning past its budget"
                    ),
                    failure_class="timeout",
                ))
                return KernelResult(
                    status="timeout",
                    step=step,
                    reconfigurations=reconfigurations,
                    blockers=("run_deadline_exceeded",),
                    env_digest=compiled.env_digest,
                    receipts=ledger.all_receipts(),
                    accounting=ledger.accounting_snapshot(),
                )
            ensure_initial_nonadherence_receipt(
                ledger, step=step, mode=self.completion_record_mode,
            )
            alerts = self.monitor_runner.run(compiled, ledger)
            context_packet = build_persistent_context(compiled, ledger, alerts)
            model_context_packet = project_persistent_context_for_model(
                context_packet, mode=self.solver_reanchor_mode,
            )
            if self.refresh_runtime_operation_status:
                model_context_packet = dict(model_context_packet)
                linked = dict(model_context_packet.get("linked_history", {}) or {})
                linked.pop("live_processes", None)
                model_context_packet["linked_history"] = linked
                model_context_packet["runtime_operations"] = ledger.runtime_operation_statuses()
            model_context_packet = project_boundary_verification_checkpoint(
                model_context_packet, mode=self.boundary_verification_mode,
            )
            completion_record_projection = project_completion_record_context(
                ledger, mode=self.completion_record_mode, task_text=compiled.task_prompt,
            )
            if completion_record_projection is not None:
                model_context_packet = dict(model_context_packet)
                model_context_packet["completion_record"] = completion_record_projection
            context_budget = context_packet.get("context_budget", {})
            if (
                isinstance(context_budget, dict)
                and context_budget.get("within_budget") is False
            ):
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:persistent_context_budget_advisory_exceeded",
                    step=step,
                    kind="persistent_context_budget_advisory_exceeded",
                    success=True,
                    summary=(
                        "PERSISTENT context exceeded the local advisory threshold after "
                        "mechanical compaction; provider context authority retained"
                    ),
                    payload={
                        "context_budget": dict(context_budget),
                        "model_call_authorized": True,
                        "provider_context_authority": True,
                    },
                ))
            messages = self.build_solver_messages(compiled, model_context_packet)
            messages, context_accounting = apply_context_cleanup(messages, mode=self.context_cleanup_mode)
            self.context_accounting_history.append({"step": step, **context_accounting})
            configure_completion_mode = getattr(hooks, "configure_primary_completion_mode", None)
            if callable(configure_completion_mode):
                reviewed_generations = verifier_memo.get(
                    "advisory_reviewed_generations", set()
                )
                current_generation = ledger.task_state_generation()
                configure_completion_mode(
                    "finish_only"
                    if current_generation in reviewed_generations
                    else "finish_intent_only"
                )
            configure_completion_record_mode = getattr(
                hooks, "configure_completion_record_mode", None
            )
            if callable(configure_completion_record_mode):
                configure_completion_record_mode(self.completion_record_mode)
            configure_disposition_mode = getattr(
                hooks, "configure_completion_disposition_mode", None
            )
            if callable(configure_disposition_mode):
                disposition_mode_for_turn = (
                    self.completion_disposition_mode
                    if current_completion_finding_ids(model_context_packet)
                    else COMPLETION_DISPOSITION_CONTROL
                )
                configure_disposition_mode(disposition_mode_for_turn)
            before_count = len(ledger.all_receipts())
            try:
                ledger.record_accounting(
                    receipt_id=f"step-{step}:solver_provider_turn:{ledger.accounting_value('solver_provider_turns') + 1}",
                    step=step, counter="solver_provider_turns", event="primary_solver_call",
                )
                turn = hooks.solve(messages, compiled)
            except ModelOutputError as exc:
                try:
                    turn = handle_solver_parse_error(
                        hooks, exc, step, compiled, messages, ledger,
                        model_context_packet, trace, before_count,
                    )
                except ModelProviderError as provider_exc:
                    return _provider_failure_result(
                        exc=provider_exc,
                        step=step,
                        reconfigurations=reconfigurations,
                        compiled=compiled,
                        ledger=ledger,
                        parse_correction_attempted=True,
                        provider_frontier_recoveries=provider_frontier_recoveries,
                    )
                if turn is None:
                    self._fire_snapshot(step); step += 1; continue
            except ModelProviderError as exc:
                recovery = classify_frontier_recovery(
                    exc,
                    mode=self.provider_frontier_recovery_mode,
                    used_recoveries=provider_frontier_recoveries,
                    max_recoveries=1,
                )
                reset_continuity = getattr(
                    hooks, "reset_solver_continuity_for_recovery", None
                )
                continuity_reset = False
                if recovery.eligible and callable(reset_continuity):
                    continuity_reset = bool(reset_continuity())
                if recovery.eligible and continuity_reset:
                    provider_frontier_recoveries += 1
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:provider_frontier_failure",
                        step=step,
                        kind="provider_frontier_failure",
                        success=False,
                        summary=(
                            "accepted Solver provider response exhausted its output "
                            "allowance without yielding a native tool call"
                        ),
                        failure_class="provider_output_incomplete_no_tool",
                        payload={
                            **recovery.facts,
                            "error_type": exc.cause_type,
                            "model_output_available": False,
                            "continuity_reset": True,
                            "recovery_ordinal": provider_frontier_recoveries,
                        },
                    ))
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:provider_frontier_recovery_admitted",
                        step=step,
                        kind="provider_frontier_recovery_admission",
                        success=True,
                        summary=(
                            "admitted one fresh Solver re-anchor after a no-tool "
                            "provider output exhaustion; task semantics remain with Frontier"
                        ),
                        payload={
                            "recovery_mode": self.provider_frontier_recovery_mode,
                            "recovery_ordinal": provider_frontier_recoveries,
                            "max_recoveries": 1,
                            "continuity_reset": True,
                            "provider_response_replayed": False,
                            "task_state_mutated_by_recovery": False,
                        },
                    ))
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, None,
                            ledger.all_receipts()[before_count:],
                        )
                    self._fire_snapshot(step)
                    step += 1
                    continue
                return _provider_failure_result(
                    exc=exc,
                    step=step,
                    reconfigurations=reconfigurations,
                    compiled=compiled,
                    ledger=ledger,
                    parse_correction_attempted=False,
                    provider_frontier_recoveries=provider_frontier_recoveries,
                )
            raise_if_run_cancelled(self._cancellation_event)
            # The provider may return after the task deadline. Do not let a late
            # model decision authorize a new task-world action or completion
            # protocol frontier. In-flight mutations retain their own cleanup
            # authority; this check is strictly pre-dispatch.
            raise_if_run_deadline_exceeded()
            turn_errors = turn.validate(
                compiled.action_schema
            )
            if turn_errors:
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:turn_invalid", step=step, kind="turn_validation",
                    success=False, summary=f"invalid turn: {'; '.join(turn_errors)}",
                    failure_class="turn_validation",
                ))
                if trace is not None:
                    trace.add_step(step, model_context_packet, turn, ledger.all_receipts()[before_count:])
                self._fire_snapshot(step); step += 1; continue
            if turn.kind == "act":
                refreshed_envmap = run_act_turn(
                    self, turn, step, compiled, executor, envmap, ledger, world_state
                )
                if refreshed_envmap is not None:
                    envmap = refreshed_envmap
            elif turn.kind == "finish_intent":
                ledger.record_accounting(
                    receipt_id=f"step-{step}:solver_finish_intent_turn:{ledger.accounting_value('solver_finish_intent_turns') + 1}",
                    step=step, counter="solver_finish_intent_turns", event="finish_intent",
                )
                evidence_coherence, persistent_submission_binding = validate_persistent_submission_binding(
                    turn, context_packet, ledger, current_step=step, strict_snapshot_binding=True,
                )
                coherence = (
                    evidence_coherence
                    if evidence_coherence is not None and not evidence_coherence.allowed
                    else evaluate_submission_coherence(ledger, current_step=step)
                )
                if not coherence.allowed:
                    record_submission_coherence_block(
                        ledger, step=step, decision=coherence, blocked_round=1,
                        verifier_skipped=persistent_submission_binding is None,
                    )
                if persistent_submission_binding is None:
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                        )
                    self._fire_snapshot(step); step += 1; continue
                record_persistent_submission_claim(
                    ledger,
                    step=step,
                    binding=persistent_submission_binding,
                    task_state_custody=(
                        world_state.dynamic_snapshot() if world_state is not None else None
                    ),
                    submission_mode="finish_intent",
                )

                # Terminal semantic review is expensive and should not run while
                # deterministic execution reality is already known to be unready.
                # Run the same mechanical completion preflight used by final
                # submission before activating the Verifier.  The sole exception
                # is an explicitly unknown task-state snapshot: a registered
                # independent inspection performed by the Verifier can itself
                # provide the current-state observation that bridges that narrow
                # epistemic gap.  Lifecycle, integrity, monitor, schema and other
                # mechanical blockers are never review-resolvable.
                run_submit_turn(
                    self, step, compiled, executor, envmap, ledger, trace,
                )
                pre_review_decision = self._last_gate_decision
                review_allowed, nonreviewable_blockers = _terminal_review_preflight(
                    pre_review_decision
                )
                if not review_allowed:
                    _record_terminal_review_deferred(
                        ledger, step=step, blockers=nonreviewable_blockers,
                    )
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                        )
                    self._fire_snapshot(step); step += 1; continue

                candidate_generation = ledger.task_state_generation()
                reviewed_generations = verifier_memo.setdefault(
                    "advisory_reviewed_generations", set()
                )
                if candidate_generation in reviewed_generations:
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:advisory_review_skipped:already_reviewed",
                        step=step,
                        kind="advisory_review_skipped",
                        success=True,
                        summary=(
                            "advisory review already attempted for this candidate generation; "
                            "finish_intent does not silently recur"
                        ),
                        payload={
                            "candidate_generation": candidate_generation,
                            "reason": "already_reviewed_generation",
                        },
                    ))
                else:
                    reviewed_generations.add(candidate_generation)
                    review_receipt_count = len(ledger.all_receipts())
                    verdict = run_model_verifier_if_available(
                        hooks, compiled, ledger, step=step, reason="finish_intent",
                        executor=executor, envmap=envmap,
                        dynamic_state=(
                            world_state.dynamic_snapshot() if world_state is not None else None
                        ),
                        memo=verifier_memo,
                    )
                    if verdict is None or verdict.verdict in {
                        "blocked_by_tooling", "blocked_by_harness_config"
                    }:
                        verifier_memo["review_unavailable_generation"] = candidate_generation
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:advisory_review_unavailable",
                            step=step,
                            kind="advisory_review_unavailable",
                            success=False,
                            summary=(
                                "independent advisory review unavailable; this does not establish "
                                "a candidate defect and Frontier retains the finish decision"
                            ),
                            failure_class="verifier_review_unavailable",
                            payload={
                                "candidate_generation": candidate_generation,
                                "verdict": getattr(verdict, "verdict", "") if verdict is not None else "",
                            },
                        ))
                    else:
                        # Currentness and semantic judgment are separate facts.  A
                        # valid verifier round that performed an independent
                        # inspection establishes that this generation was observed,
                        # even when the reviewer remains uncertain.  Frontier still owns
                        # the semantic completion decision below.  Tooling-blocked or
                        # malformed rounds do not earn this marker.
                        receipts_before_review = ledger.all_receipts()[:review_receipt_count]
                        new_review_receipts = ledger.all_receipts()[review_receipt_count:]

                        # Find the receipt that created the current task-state
                        # generation.  This deliberately does not filter by
                        # ``modified_paths`` first: a newer opaque/process mutation
                        # must invalidate an older file observation rather than being
                        # skipped simply because its target set is unknown.
                        latest_boundary = None
                        previous_generation = 0
                        for receipt in receipts_before_review:
                            receipt_generation = ledger.receipt_task_state_generation(receipt.receipt_id)
                            if receipt_generation is None:
                                continue
                            if receipt_generation > previous_generation:
                                latest_boundary = receipt
                                previous_generation = receipt_generation

                        def normalized_path_target(value: Any, *, require_prefix: bool) -> str:
                            target = str(value or "").strip()
                            if not target:
                                return ""
                            if target.startswith("path:"):
                                target = target[5:]
                            elif require_prefix:
                                return ""
                            try:
                                return normalize_relpath(target, envmap.workspace_root)
                            except ValueError:
                                return ""

                        mutation_targets: set[str] = set()
                        if latest_boundary is not None and previous_generation == candidate_generation:
                            boundary_payload = (
                                latest_boundary.payload
                                if isinstance(latest_boundary.payload, Mapping) else {}
                            )
                            path_fields = (
                                "modified_paths", "created_paths", "artifact_paths", "removed_paths",
                            )
                            for field in path_fields:
                                values = boundary_payload.get(field, ())
                                if isinstance(values, str):
                                    values = (values,)
                                if isinstance(values, (list, tuple, set, frozenset)):
                                    for value in values:
                                        normalized = normalized_path_target(value, require_prefix=False)
                                        if normalized:
                                            mutation_targets.add(normalized)
                            state_delta = boundary_payload.get("state_delta")
                            if isinstance(state_delta, Mapping):
                                for field in (
                                    "modified_paths", "created_paths", "content_changed_paths",
                                    "metadata_changed_paths", "removed_paths",
                                ):
                                    values = state_delta.get(field, ())
                                    if isinstance(values, str):
                                        values = (values,)
                                    if isinstance(values, (list, tuple, set, frozenset)):
                                        for value in values:
                                            normalized = normalized_path_target(value, require_prefix=False)
                                            if normalized:
                                                mutation_targets.add(normalized)

                        observed_targets: set[str] = set()
                        for receipt in new_review_receipts:
                            if receipt.kind != "inspection_record":
                                continue
                            if not ledger.receipt_snapshot_binding_is_current(
                                receipt, expected_generation=candidate_generation,
                            ):
                                continue
                            payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
                            if str(payload.get("requester", "")).strip() != "model_verifier":
                                continue
                            if payload.get("observation_valid") is not True:
                                continue
                            if payload.get("target_binding_valid") is not True:
                                continue
                            if str(payload.get("admissibility", "")).strip() not in {
                                "direct_admissible", "verdict_eligible",
                            }:
                                continue
                            try:
                                observed_generation = int(
                                    payload.get("observed_task_state_generation",
                                                payload.get("task_state_generation", -1))
                                )
                            except (TypeError, ValueError):
                                continue
                            if observed_generation != candidate_generation:
                                continue
                            observation_type = str(payload.get("observation_type", "")).strip()
                            if observation_type in {"", "metadata", "execution_result"}:
                                continue
                            targets = payload.get("canonical_targets", ())
                            if isinstance(targets, str):
                                targets = (targets,)
                            if not isinstance(targets, (list, tuple, set, frozenset)):
                                continue
                            for target in targets:
                                normalized = normalized_path_target(target, require_prefix=True)
                                if normalized:
                                    observed_targets.add(normalized)

                        # A reviewer observation can clear only the exact known path
                        # set of the *latest* task-state boundary. Unknown-target
                        # boundaries fail closed. A semantic ``completed`` verdict by
                        # itself never manufactures observation authority.
                        has_current_observation = bool(
                            mutation_targets
                            and mutation_targets.issubset(observed_targets)
                        )
                        if has_current_observation:
                            verifier_memo["observed_review_generation"] = candidate_generation
                            verifier_memo["observed_review_signature"] = verifier_memo.get("signature", "")
                        if verdict.verdict == "completed":
                            # Bind a successful independent current-state review to the
                            # exact task-state generation it inspected. A later mutation
                            # changes the generation and therefore invalidates this proof.
                            verifier_memo["completed_review_generation"] = candidate_generation
                            verifier_memo["completed_review_signature"] = verifier_memo.get("signature", "")
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:advisory_review_result",
                            step=step,
                            kind="advisory_review_result",
                            success=True,
                            summary=f"advisory review returned {verdict.verdict}; Frontier retains final authority",
                            payload={
                                "candidate_generation": candidate_generation,
                                "verdict": verdict.verdict,
                                "semantic_authority": "frontier",
                            },
                        ))
                        if verdict.verdict == "completed":
                            # Frontier already declared semantic completion by issuing
                            # finish_intent. Once the deterministic preflight is
                            # mechanically ready and the independent terminal review
                            # returns completed, do not force an otherwise redundant
                            # second Solver completion turn. If review was admitted
                            # only because the task-state boundary was epistemically
                            # unknown, a bare PASS is insufficient: the review must
                            # have registered admissible current observation of that
                            # exact latest boundary before terminal completion can be
                            # considered.
                            terminal_review_can_close = bool(
                                (pre_review_decision is not None and pre_review_decision.ready)
                                or has_current_observation
                            )
                            ready_decision = self.completion_gate.evaluate(
                                compiled, ledger, self.monitor_runner.run(compiled, ledger),
                            )
                            if terminal_review_can_close and ready_decision.ready:
                                ledger.record(Receipt(
                                    receipt_id=f"step-{step}:frontier_finish",
                                    step=step,
                                    kind="frontier_finish",
                                    success=True,
                                    summary=(
                                        "Frontier's mechanically ready finish intent and one "
                                        "independent terminal review both completed"
                                    ),
                                    payload={
                                        "candidate_generation": ledger.task_state_generation(),
                                        "completion_source": "finish_intent_plus_terminal_verifier_pass",
                                        "review_invoked_by_finish": False,
                                        "semantic_authority": "frontier_and_independent_terminal_review",
                                    },
                                ))
                                if trace is not None:
                                    trace.add_step(
                                        step, model_context_packet, turn,
                                        ledger.all_receipts()[before_count:],
                                    )
                                return _completed_result(
                                    step, reconfigurations, ready_decision, compiled, ledger,
                                )
                            ledger.record(Receipt(
                                receipt_id=f"step-{step}:terminal_verifier_pass_gate_not_ready",
                                step=step,
                                kind="terminal_verifier_pass_gate_not_ready",
                                success=False,
                                summary=(
                                    "terminal Verifier returned completed, but fresh mechanical "
                                    "completion reality still has blockers"
                                ),
                                failure_class="completion_gate_not_ready",
                                payload={
                                    "candidate_generation": ledger.task_state_generation(),
                                    "review_established_current_boundary": has_current_observation,
                                    "pre_review_mechanically_ready": bool(
                                        pre_review_decision is not None and pre_review_decision.ready
                                    ),
                                    "blockers": [
                                        {"code": blocker.code, "detail": blocker.detail,
                                         "source": blocker.source}
                                        for blocker in ready_decision.blockers
                                    ],
                                },
                            ))
                if trace is not None:
                    trace.add_step(
                        step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                    )
                self._fire_snapshot(step); step += 1; continue
            elif turn.kind == "finish_outcome":
                ledger.record_accounting(
                    receipt_id=f"step-{step}:solver_finish_turn:{ledger.accounting_value('solver_finish_turns') + 1}",
                    step=step, counter="solver_finish_turns", event="finish",
                )
                disposition_decision = evaluate_completion_dispositions(
                    turn,
                    model_context_packet,
                    mode=self.completion_disposition_mode,
                )
                if not disposition_decision.allowed:
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:completion_finding_disposition_block",
                        step=step,
                        kind="completion_finding_disposition_block",
                        success=False,
                        summary=(
                            "final finish did not explicitly account for every current "
                            "completion finding under the enabled research protocol"
                        ),
                        failure_class="completion_finding_disposition_incomplete",
                        payload=disposition_decision.as_payload(),
                    ))
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    self._fire_snapshot(step); step += 1; continue
                if disposition_decision.required_finding_ids:
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:completion_finding_dispositions",
                        step=step,
                        kind="completion_finding_dispositions",
                        success=True,
                        summary=(
                            "Primary explicitly dispositioned every current completion finding; "
                            "semantic authority remains with Primary against task reality"
                        ),
                        payload=disposition_decision.as_payload(),
                    ))
                evidence_coherence, persistent_submission_binding = validate_persistent_submission_binding(
                    turn, context_packet, ledger, current_step=step, strict_snapshot_binding=True,
                )
                coherence = (
                    evidence_coherence
                    if evidence_coherence is not None and not evidence_coherence.allowed
                    else evaluate_submission_coherence(ledger, current_step=step)
                )
                prior_claim = ledger.latest_receipt("primary_submission_claim")
                prior_payload = (
                    prior_claim.payload
                    if prior_claim is not None and isinstance(prior_claim.payload, Mapping)
                    else {}
                )
                candidate_generation = ledger.task_state_generation()
                finish_after_intent = bool(
                    persistent_submission_binding is not None
                    and coherence.reason_code == "unchanged_resubmission"
                    and str(prior_payload.get("submission_mode", "")) == "finish_intent"
                    and int(prior_payload.get("task_state_generation", -1) or -1)
                    == candidate_generation
                )
                verifier_observed_current_generation = bool(
                    persistent_submission_binding is not None
                    and not coherence.allowed
                    and coherence_block_allows_independent_review(coherence)
                    and verifier_memo.get("observed_review_generation") == candidate_generation
                )
                if (
                    not coherence.allowed
                    and not finish_after_intent
                    and not verifier_observed_current_generation
                ) or persistent_submission_binding is None:
                    record_submission_coherence_block(
                        ledger, step=step, decision=coherence, blocked_round=1,
                        verifier_skipped=True,
                    )
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                        )
                    self._fire_snapshot(step); step += 1; continue
                if verifier_observed_current_generation:
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:submission_coherence_recovered_by_prior_verifier_observation",
                        step=step,
                        kind="submission_coherence_recovered_by_prior_verifier_observation",
                        success=True,
                        summary=(
                            "same-generation independent verification established the "
                            "current-state observation required for Frontier's final finish"
                        ),
                        payload={
                            "prior_coherence": coherence.as_payload(),
                            "candidate_generation": candidate_generation,
                            "verifier_packet_signature": verifier_memo.get(
                                "observed_review_signature",
                                verifier_memo.get("completed_review_signature", ""),
                            ),
                            "verifier_observation_status": "current_generation_observed",
                            "semantic_authority": "frontier",
                        },
                    ))
                reviewed_generations = verifier_memo.setdefault(
                    "advisory_reviewed_generations", set()
                )
                if candidate_generation not in reviewed_generations:
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:finish_outcome_review_required",
                        step=step,
                        kind="finish_outcome_review_required",
                        success=False,
                        summary=(
                            "final finish requires the advisory review stage to have been "
                            "attempted for the current task-state generation"
                        ),
                        failure_class="advisory_review_required",
                        payload={
                            "candidate_generation": candidate_generation,
                            "review_attempted_for_generation": False,
                            "required_predecessor": "finish_intent",
                        },
                    ))
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                        )
                    self._fire_snapshot(step); step += 1; continue
                record_finish_metadata(
                    ledger,
                    finish_metadata=turn.finish_metadata,
                    mode=self.completion_record_mode,
                    step=step,
                )
                record_persistent_submission_claim(
                    ledger,
                    step=step,
                    binding=persistent_submission_binding,
                    task_state_custody=(
                        world_state.dynamic_snapshot() if world_state is not None else None
                    ),
                    submission_mode="finish",
                )
                run_submit_turn(
                    self, step, compiled, executor, envmap, ledger, trace,
                )
                ready_decision = self._last_gate_decision
                if ready_decision is not None and ready_decision.ready:
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:frontier_finish",
                        step=step,
                        kind="frontier_finish",
                        success=True,
                        summary="Frontier finished the current candidate; no implicit review was invoked",
                        payload={
                            "candidate_generation": ledger.task_state_generation(),
                            "review_invoked_by_finish": False,
                            "semantic_authority": "frontier",
                        },
                    ))
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                        )
                    return _completed_result(
                        step, reconfigurations, ready_decision, compiled, ledger,
                    )
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:frontier_finish_blocked",
                    step=step,
                    kind="frontier_finish_blocked",
                    success=False,
                    summary="Frontier finish was mechanically blocked by current execution reality",
                    failure_class="completion_gate_not_ready",
                    payload={
                        "review_invoked_by_finish": False,
                        "blockers": [
                            {"code": blocker.code, "detail": blocker.detail, "source": blocker.source}
                            for blocker in (ready_decision.blockers if ready_decision is not None else ())
                        ],
                    },
                ))
                if trace is not None:
                    trace.add_step(
                        step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                    )
                self._fire_snapshot(step); step += 1; continue
            elif turn.kind == "submit_outcome":
                ledger.record_accounting(
                    receipt_id=f"step-{step}:solver_submission_turn:{ledger.accounting_value('solver_submission_turns') + 1}",
                    step=step, counter="solver_submission_turns", event="submit_outcome",
                )
                evidence_coherence, persistent_submission_binding = validate_persistent_submission_binding(
                    turn,
                    context_packet,
                    ledger,
                    current_step=step,
                    strict_snapshot_binding=True,
                )
                coherence = (
                    evidence_coherence
                    if evidence_coherence is not None and not evidence_coherence.allowed
                    else evaluate_submission_coherence(
                        ledger,
                        current_step=step,
                    )
                )
                if not coherence.allowed:
                    submit_without_evidence_rounds += 1
                    review_incoherent_candidate = (
                        persistent_submission_binding is not None
                        and coherence_block_allows_independent_review(coherence)
                    )
                    record_submission_coherence_block(
                        ledger,
                        step=step,
                        decision=coherence,
                        blocked_round=submit_without_evidence_rounds,
                        verifier_skipped=not review_incoherent_candidate,
                    )
                    # PERSISTENT production separates Solver evidence admission from independent
                    # verification activation.  A validly bound candidate can still be
                    # inspected when the current task-state boundary is uncertain; the
                    # coherence blocker remains authoritative and prevents terminal
                    # success on this turn.  Invalid claim/evidence bindings have no
                    # PCRSubmissionBinding and stay fail-closed without invoking the
                    # Verifier.
                    if review_incoherent_candidate:
                        record_persistent_submission_claim(
                            ledger,
                            step=step,
                            binding=persistent_submission_binding,
                            task_state_custody=(
                                world_state.dynamic_snapshot()
                                if world_state is not None else None
                            ),
                        )
                        run_submit_turn(
                            self, step, compiled, executor, envmap, ledger, trace,
                        )
                        pre_review_decision = self._last_gate_decision
                        review_allowed, nonreviewable_blockers = _terminal_review_preflight(
                            pre_review_decision
                        )
                        if not review_allowed:
                            _record_terminal_review_deferred(
                                ledger, step=step, blockers=nonreviewable_blockers,
                            )
                            if trace is not None:
                                trace.add_step(
                                    step, model_context_packet, turn,
                                    ledger.all_receipts()[before_count:],
                                )
                            self._fire_snapshot(step)
                            step += 1
                            continue
                        verdict = run_model_verifier_if_available(
                            hooks,
                            compiled,
                            ledger,
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
                        if verdict is not None and verdict.verdict == "completed":
                            # A reviewable coherence block describes missing current-state
                            # observation at the instant of submit. Independent Verifier
                            # inspections can establish that observation without changing
                            # task state. Re-evaluate the mechanical completion gate after
                            # those receipts are recorded rather than keeping the pre-
                            # Verifier coherence decision as stale permanent authority.
                            ready_decision = self.completion_gate.evaluate(
                                compiled, ledger, self.monitor_runner.run(compiled, ledger),
                            )
                            if ready_decision.ready:
                                ledger.record(Receipt(
                                    receipt_id=f"step-{step}:submission_coherence_recovered_by_verifier_observation",
                                    step=step,
                                    kind="submission_coherence_recovered_by_verifier_observation",
                                    success=True,
                                    summary=(
                                        "independent verification established a current "
                                        "authoritative observation for the submitted snapshot"
                                    ),
                                    payload={
                                        "prior_coherence": coherence.as_payload(),
                                        "verifier_verdict": verdict.verdict,
                                        "task_state_generation": ledger.task_state_generation(),
                                        "task_state_snapshot_digest": ledger.task_state_snapshot_digest(),
                                    },
                                ))
                                if trace is not None:
                                    trace.add_step(
                                        step, model_context_packet, turn,
                                        ledger.all_receipts()[before_count:],
                                    )
                                return _completed_result(
                                    step, reconfigurations, ready_decision, compiled, ledger,
                                )
                            ledger.record(Receipt(
                                receipt_id=f"step-{step}:verifier_completed_submission_incoherent",
                                step=step,
                                kind="verifier_completed_submission_incoherent",
                                success=False,
                                summary=(
                                    "independent verification completed, but the fresh "
                                    "deterministic completion gate still has blockers"
                                ),
                                failure_class=coherence.reason_code,
                                payload={
                                    "coherence": coherence.as_payload(),
                                    "verifier_verdict": verdict.verdict,
                                    "blockers": [
                                        {"code": blocker.code, "detail": blocker.detail,
                                         "source": blocker.source}
                                        for blocker in ready_decision.blockers
                                    ],
                                },
                            ))
                        if trace is not None:
                            trace.add_step(
                                step, model_context_packet, turn,
                                ledger.all_receipts()[before_count:],
                            )
                        if verdict is not None and verdict.verdict != "completed":
                            stalemate_result = check_verifier_stalemate(
                                self, verdict, step, reconfigurations, compiled, ledger,
                                verifier_round_finding_sets,
                            )
                            if stalemate_result is not None:
                                return stalemate_result
                        if submit_without_evidence_rounds == self.SUBMIT_STALEMATE_ROUNDS:
                            blockers = (coherence.reason_code,)
                            ledger.record(Receipt(
                                receipt_id=f"step-{step}:solver_submit_stalemate",
                                step=step,
                                kind="solver_submit_stalemate_observed",
                                success=False,
                                summary=(
                                    "diagnostic submit repetition: submission coherence remained "
                                    "blocked without an intervening observed-evidence action"
                                ),
                                failure_class="",
                                payload={
                                    "rounds": submit_without_evidence_rounds,
                                    "reason_code": coherence.reason_code,
                                    "coherence": coherence.as_payload(),
                                    "verifier_activated_before_stalemate": verdict is not None,
                                },
                            ))
                            # Diagnostic only: official task timeout remains the
                            # execution authority. The existing coherence blocker is
                            # still visible to the next Solver turn.
                        self._fire_snapshot(step)
                        step += 1
                        continue
                    if submit_without_evidence_rounds == self.SUBMIT_STALEMATE_ROUNDS:
                        blockers = (coherence.reason_code,)
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:solver_submit_stalemate",
                            step=step,
                            kind="solver_submit_stalemate_observed",
                            success=False,
                            summary=(
                                "diagnostic submit repetition: submission coherence remained blocked "
                                "without an intervening observed-evidence action"
                            ),
                            failure_class="",
                            payload={
                                "rounds": submit_without_evidence_rounds,
                                "reason_code": coherence.reason_code,
                                "coherence": coherence.as_payload(),
                            },
                        ))
                        if trace is not None:
                            trace.add_step(
                                step, model_context_packet, turn,
                                ledger.all_receipts()[before_count:],
                            )
                        # Diagnostic only; continue to the next Solver turn.
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    self._fire_snapshot(step)
                    step += 1
                    continue
                if persistent_submission_binding is not None:
                    record_persistent_submission_claim(
                        ledger,
                        step=step,
                        binding=persistent_submission_binding,
                        task_state_custody=(
                            world_state.dynamic_snapshot()
                            if world_state is not None else None
                        ),
                    )
                run_submit_turn(
                    self, step, compiled, executor, envmap, ledger, trace,
                )
                decision = self._last_gate_decision
                nominated_evidence_receipt_ids = (
                    persistent_submission_binding.receipt_ids
                    if persistent_submission_binding is not None else ()
                )
                submit_without_evidence_rounds = 0
                review_allowed, nonreviewable_blockers = _terminal_review_preflight(
                    decision
                )
                if not review_allowed:
                    _record_terminal_review_deferred(
                        ledger, step=step, blockers=nonreviewable_blockers,
                    )
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    self._fire_snapshot(step)
                    step += 1
                    continue
                verdict = run_model_verifier_if_available(
                    hooks,
                    compiled,
                    ledger,
                    step=step,
                    reason="solver_submit",
                    executor=executor,
                    envmap=envmap,
                    dynamic_state=(world_state.dynamic_snapshot() if world_state is not None else None),
                    memo=verifier_memo,
                )
                if verdict is not None and verdict.verdict == "completed":
                    # Verifier completion is semantic evidence, not completion
                    # authority.  Re-evaluate every mechanical blocker after
                    # the Verifier/proof bridge has recorded its current-round
                    # evidence.  Never reuse the pre-Verifier submit decision.
                    ready_decision = self.completion_gate.evaluate(
                        compiled, ledger, self.monitor_runner.run(compiled, ledger),
                    )
                    if not ready_decision.ready:
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:verifier_completed_gate_not_ready",
                            step=step,
                            kind="verifier_completed_gate_not_ready",
                            success=False,
                            summary=(
                                "Verifier returned completed but the fresh deterministic "
                                "completion gate still has blockers"
                            ),
                            failure_class="completion_gate_not_ready",
                            payload={
                                "blockers": [
                                    {"code": blocker.code, "detail": blocker.detail,
                                     "source": blocker.source}
                                    for blocker in ready_decision.blockers
                                ],
                            },
                        ))
                        if trace is not None:
                            trace.add_step(
                                step, model_context_packet, turn,
                                ledger.all_receipts()[before_count:],
                            )
                        self._fire_snapshot(step)
                        step += 1
                        continue
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn,
                            ledger.all_receipts()[before_count:],
                        )
                    return _completed_result(
                        step, reconfigurations, ready_decision, compiled, ledger,
                    )
                if trace is not None:
                    trace.add_step(step, model_context_packet, turn, ledger.all_receipts()[before_count:])
                if verdict is not None and verdict.verdict != "completed":
                    stalemate_result = check_verifier_stalemate(
                        self, verdict, step, reconfigurations, compiled, ledger,
                        verifier_round_finding_sets,
                    )
                    if stalemate_result is not None:
                        return stalemate_result
                if (
                    decision is not None
                    and verdict is None
                ):
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:verifier_required_for_completion",
                        step=step,
                        kind="verifier_required_for_completion",
                        success=False,
                        summary="certified runtime submit did not receive a verifier verdict; completion remains blocked until verifier runs",
                        failure_class="verifier_missing",
                    ))
                self._fire_snapshot(step); step += 1; continue
            if trace is not None:
                trace.add_step(step, model_context_packet, turn, ledger.all_receipts()[before_count:])
            self._fire_snapshot(step); step += 1
        return KernelResult(
            status="incomplete", step=step, reconfigurations=reconfigurations,
            blockers=tuple(ob.obligation_id for ob in ledger.open_obligations()),
            env_digest=compiled.env_digest, receipts=ledger.all_receipts(),
            accounting=ledger.accounting_snapshot(),
        )

    def interrupted_result(
        self, *, status: str, blockers: tuple[str, ...] = (),
    ) -> KernelResult:
        """Snapshot authoritative in-flight evidence after an outer interrupt.

        This is intentionally evidence-only. It does not infer semantic state or
        strategy; it preserves exactly what the kernel ledger had recorded before
        a wall-clock exception escaped the run loop.
        """
        ledger = self._active_ledger
        receipts = ledger.all_receipts() if ledger is not None else ()
        accounting = ledger.accounting_snapshot() if ledger is not None else None
        return KernelResult(
            status=status,
            step=self._active_step,
            reconfigurations=self._active_reconfigurations,
            blockers=blockers,
            env_digest=self._active_env_digest,
            receipts=receipts,
            accounting=accounting,
        )

    @staticmethod
    def _active_findings_need_intervening_evidence(
        ledger: ExecutionLedger,
        *,
        nominated_evidence_receipt_ids: tuple[str, ...] = (),
    ) -> bool:
        from .finding_evidence import active_findings_need_relevant_evidence

        return active_findings_need_relevant_evidence(
            ledger,
            nominated_evidence_receipts=nominated_evidence_receipt_ids,
        )

    def _fire_snapshot(self, step: int) -> None:
        if self.snapshot_callback is not None and step in self._snapshot_steps:
            self.snapshot_callback(step)
