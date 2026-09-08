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
from .execution import (
    BootstrapEngine, Executor, ExperimentEngine, PerceptionLane, ProcessOrchestratorV2,
)
from .pcr_runtime import build_pcr_runtime
from .kernel_messages import build_solver_messages
from .kernel_verifier import run_model_verifier_if_available
from .pcr_context import build_pcr_context
from .ledger import ExecutionLedger, Receipt
from .monitors import IntegrityGuards, LocalOnlySafetyGuard, MonitorRunner
from .kernel_dispatch import dispatch_action
from .kernel_solver_turn import handle_solver_parse_error
from .kernel_stalemate import check_verifier_stalemate
from .kernel_turns import run_act_turn, run_submit_turn
from .pcr_reanchor import CURRENT_FULL, SUPPORTED_REANCHOR_MODES, project_pcr_context_for_model
from .pcr_submission import (
    record_pcr_submission_claim,
    validate_pcr_submission_binding,
)
from .submission_coherence import (
    coherence_block_allows_independent_review,
    evaluate_submission_coherence,
    record_submission_coherence_block,
)
from .model_hooks import ModelOutputError, ModelProviderError
from .run_cancellation import raise_if_run_cancelled
from .route_preflight import preflight_proof_routes
from .runtime_ir import (
    CompiledRuntime, EnvMap, SolverTurn,
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
) -> KernelResult:
    ledger.record(Receipt(
        receipt_id=f"step-{step}:solver_provider_failure",
        step=step,
        kind="provider_failure",
        success=False,
        summary=(
            f"{exc.role} provider invocation failed before model output: "
            f"{exc.cause_type}"
        ),
        failure_class="provider_failure",
        payload={
            "role": exc.role,
            "error_type": exc.cause_type,
            "error": exc.cause_message[:2000],
            "model_output_available": False,
            "parse_correction_attempted": parse_correction_attempted,
            "provider_retry_attempted": False,
        },
    ))
    return KernelResult(
        status="provider_failure",
        step=step,
        reconfigurations=reconfigurations,
        blockers=(f"{exc.role}_provider_failure",),
        env_digest=compiled.env_digest,
        receipts=ledger.all_receipts(),
        accounting=ledger.accounting_snapshot(),
    )


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
        if self.solver_context_mode not in {"full", "compact"}:
            raise ValueError(f"unsupported Solver context mode: {solver_context_mode}")
        if self.solver_reanchor_mode not in SUPPORTED_REANCHOR_MODES:
            raise ValueError(f"unsupported PCR Solver re-anchor mode: {self.solver_reanchor_mode}")
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
        resolved = build_pcr_runtime(envmap, solver_context_mode=self.solver_context_mode)
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
        identity.setdefault("runtime_path", "pcr_v0")
        identity.setdefault("identity_complete", bool(
            identity.get("task_id") and identity.get("run_id")
            and identity.get("primary_agent_id")
        ))
        ledger.install_runtime_identity(identity)
        ledger.seed_capabilities(compiled.selected_capability_ids())
        ledger.ensure_objective(compiled.objective_graph)
        realization = dict(compiled.config_realization)
        realization.update({
            "runtime_path": "pcr_v0",
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
            now = time.monotonic()
            elapsed_s = max(0.0, now - run_started)
            ledger.update_runtime_budget_state({
                "run_timeout_sec": (float(run_timeout_s) if run_timeout_s is not None else None),
                "elapsed_run_sec": round(elapsed_s, 3),
                "remaining_run_sec": (round(max(0.0, deadline - now), 3) if deadline is not None else None),
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
                    blockers=(f"kernel_deadline_exceeded_{run_timeout_s:g}s",),
                    env_digest=compiled.env_digest,
                    receipts=ledger.all_receipts(),
                )
            alerts = self.monitor_runner.run(compiled, ledger)
            context_packet = build_pcr_context(compiled, ledger, alerts)
            model_context_packet = project_pcr_context_for_model(
                context_packet, mode=self.solver_reanchor_mode,
            )
            context_budget = context_packet.get("context_budget", {})
            if (
                isinstance(context_budget, dict)
                and context_budget.get("within_budget") is False
            ):
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:pcr_context_budget_advisory_exceeded",
                    step=step,
                    kind="pcr_context_budget_advisory_exceeded",
                    success=True,
                    summary=(
                        "PCR context exceeded the local advisory threshold after "
                        "mechanical compaction; provider context authority retained"
                    ),
                    payload={
                        "context_budget": dict(context_budget),
                        "model_call_authorized": True,
                        "provider_context_authority": True,
                    },
                ))
            messages = self.build_solver_messages(compiled, model_context_packet)
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
                    )
                if turn is None:
                    self._fire_snapshot(step); step += 1; continue
            except ModelProviderError as exc:
                return _provider_failure_result(
                    exc=exc,
                    step=step,
                    reconfigurations=reconfigurations,
                    compiled=compiled,
                    ledger=ledger,
                    parse_correction_attempted=False,
                )
            raise_if_run_cancelled(self._cancellation_event)
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
                evidence_coherence, pcr_submission_binding = validate_pcr_submission_binding(
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
                        verifier_skipped=pcr_submission_binding is None,
                    )
                if pcr_submission_binding is None:
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                        )
                    self._fire_snapshot(step); step += 1; continue
                record_pcr_submission_claim(
                    ledger,
                    step=step,
                    binding=pcr_submission_binding,
                    task_state_custody=(
                        world_state.dynamic_snapshot() if world_state is not None else None
                    ),
                    submission_mode="finish_intent",
                )
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
                                "a candidate defect and Luna retains the finish decision"
                            ),
                            failure_class="verifier_review_unavailable",
                            payload={
                                "candidate_generation": candidate_generation,
                                "verdict": getattr(verdict, "verdict", "") if verdict is not None else "",
                            },
                        ))
                    else:
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:advisory_review_result",
                            step=step,
                            kind="advisory_review_result",
                            success=True,
                            summary=f"advisory review returned {verdict.verdict}; Luna retains final authority",
                            payload={
                                "candidate_generation": candidate_generation,
                                "verdict": verdict.verdict,
                                "semantic_authority": "luna",
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
                evidence_coherence, pcr_submission_binding = validate_pcr_submission_binding(
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
                finish_after_intent = bool(
                    pcr_submission_binding is not None
                    and coherence.reason_code == "unchanged_resubmission"
                    and str(prior_payload.get("submission_mode", "")) == "finish_intent"
                    and int(prior_payload.get("task_state_generation", -1) or -1)
                    == ledger.task_state_generation()
                )
                if (not coherence.allowed and not finish_after_intent) or pcr_submission_binding is None:
                    record_submission_coherence_block(
                        ledger, step=step, decision=coherence, blocked_round=1,
                        verifier_skipped=True,
                    )
                    if trace is not None:
                        trace.add_step(
                            step, model_context_packet, turn, ledger.all_receipts()[before_count:]
                        )
                    self._fire_snapshot(step); step += 1; continue
                record_pcr_submission_claim(
                    ledger,
                    step=step,
                    binding=pcr_submission_binding,
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
                        receipt_id=f"step-{step}:luna_finish",
                        step=step,
                        kind="luna_finish",
                        success=True,
                        summary="Luna finished the current candidate; no implicit review was invoked",
                        payload={
                            "candidate_generation": ledger.task_state_generation(),
                            "review_invoked_by_finish": False,
                            "semantic_authority": "luna",
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
                    receipt_id=f"step-{step}:luna_finish_blocked",
                    step=step,
                    kind="luna_finish_blocked",
                    success=False,
                    summary="Luna finish was mechanically blocked by current execution reality",
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
                evidence_coherence, pcr_submission_binding = validate_pcr_submission_binding(
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
                        pcr_submission_binding is not None
                        and coherence_block_allows_independent_review(coherence)
                    )
                    record_submission_coherence_block(
                        ledger,
                        step=step,
                        decision=coherence,
                        blocked_round=submit_without_evidence_rounds,
                        verifier_skipped=not review_incoherent_candidate,
                    )
                    # PCR production separates Solver evidence admission from independent
                    # verification activation.  A validly bound candidate can still be
                    # inspected when the current task-state boundary is uncertain; the
                    # coherence blocker remains authoritative and prevents terminal
                    # success on this turn.  Invalid claim/evidence bindings have no
                    # PCRSubmissionBinding and stay fail-closed without invoking the
                    # Verifier.
                    if review_incoherent_candidate:
                        record_pcr_submission_claim(
                            ledger,
                            step=step,
                            binding=pcr_submission_binding,
                            task_state_custody=(
                                world_state.dynamic_snapshot()
                                if world_state is not None else None
                            ),
                        )
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
                if pcr_submission_binding is not None:
                    record_pcr_submission_claim(
                        ledger,
                        step=step,
                        binding=pcr_submission_binding,
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
                    pcr_submission_binding.receipt_ids
                    if pcr_submission_binding is not None else ()
                )
                submit_without_evidence_rounds = 0
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
