from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, TYPE_CHECKING

from .compiler import CapabilityRegistry, ConfigCompiler
from .completion import CompletionGate, FailureParser
from .execution import (
    BootstrapEngine, Executor, ExperimentEngine, PerceptionLane, ProcessOrchestratorV2,
)
from .kernel_config import ResolvedRuntime, resolve_runtime
from .kernel_messages import build_architect_request, build_solver_messages
from .kernel_verifier import run_model_verifier_if_available
from .context_compiler import ContextCompiler
from .ledger import ExecutionLedger, Receipt
from .monitors import IntegrityGuards, LocalOnlySafetyGuard, MonitorRunner
from .no_progress import NoProgressController
from .kernel_dispatch import dispatch_action
from .kernel_turns import run_act_turn, run_submit_turn
from .kernel_reconfigure import verifier_triggered_reconfigure
from .model_hooks import ModelOutputError
from .redaction import redact_text_with_events
from .runtime_ir import (
    CompiledRuntime, EnvMap, RuntimeConfigIR, SolverTurn,
)

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
    # An architect defect is recorded even when the task subsequently passes:
    # the initial config needed repair, or the verifier had to trigger a
    # reconfiguration.  Result rows must never launder architect defects into
    # clean passes.
    architect_defect: bool = False
    architect_defect_reasons: tuple[str, ...] = ()

def _completed_result(
    step: int, reconfigurations: int, decision: Any,
    compiled: CompiledRuntime, ledger: ExecutionLedger,
    architect_defect_reasons: tuple[str, ...] = (),
) -> KernelResult:
    """Build a completed ``KernelResult`` from a ready gate decision."""
    used_ids = set(decision.used_check_ids)
    return KernelResult(
        status="completed", step=step, reconfigurations=reconfigurations,
        used_check_ids=decision.used_check_ids,
        used_check_commands=tuple(
            c.command for c in compiled.planned_checks() if c.check_id in used_ids
        ),
        blockers=(), env_digest=compiled.env_digest, receipts=ledger.all_receipts(),
        architect_defect=bool(architect_defect_reasons),
        architect_defect_reasons=architect_defect_reasons,
    )


class KernelHooks(Protocol):
    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        ...

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
        max_steps: int = 24,
        workbench_architect: Any | None = None,
        snapshot_callback: Callable[[int], None] | None = None,
        snapshot_steps: tuple[int, ...] = (),
    ) -> None:
        self.max_steps = max(1, int(max_steps))
        self.workbench_architect = workbench_architect
        self.snapshot_callback, self._snapshot_steps = snapshot_callback, frozenset(snapshot_steps)
        self.monitor_runner = MonitorRunner()
        self.context_compiler = ContextCompiler()
        self.completion_gate = CompletionGate()
        self.failure_parser = FailureParser()
        self.bootstrap_engine = BootstrapEngine()
        self.process_orchestrator = ProcessOrchestratorV2()
        self.perception_lane = PerceptionLane()
        self.experiment_engine = ExperimentEngine()
        self.integrity_guards = IntegrityGuards()
        self.safety_guard = LocalOnlySafetyGuard()
        self.no_progress_controller = NoProgressController()

    def build_architect_request(
        self,
        envmap: EnvMap,
        compiler: ConfigCompiler,
    ) -> dict[str, Any]:
        return build_architect_request(envmap, compiler)

    def build_solver_messages(
        self,
        compiled: CompiledRuntime,
        context_packet: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        return build_solver_messages(compiled, context_packet)

    def run(
        self,
        envmap: EnvMap,
        executor: Executor,
        hooks: KernelHooks,
        *,
        trace: RunTrace | None = None,
    ) -> KernelResult:
        # Perception (e.g. vision transcription) needs the model hooks at
        # dispatch time; scoped to this run.
        self.active_hooks = hooks
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
        resolved = resolve_runtime(
            envmap, compiler, hooks,
            workbench_architect=self.workbench_architect,
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
        architect_repair_codes = resolved.repair_codes
        ledger = ExecutionLedger()
        ledger.seed_capabilities(compiled.selected_capability_ids())
        ledger.ensure_objective(compiled.objective_graph)
        realization = dict(compiled.config_realization)
        if resolved.workbench_config is not None:
            from .workbench_compile import config_realization_audit
            realization["architect_path"] = "workbench"
            realization["harness_config_schema_version"] = resolved.workbench_config.schema_version
            realization["workbench_repair_warning_codes"] = list(resolved.workbench_config.repair_warning_codes)
            realization["workbench_repair_warnings"] = list(resolved.workbench_config.repair_warnings)
            realization["workbench_rejected_config_items"] = [dict(item) for item in resolved.workbench_config.rejected_config_items]
            realization["harness_config_realization_audit"] = config_realization_audit(
                resolved.workbench_config, envmap,
            )
        else:
            realization["architect_path"] = "ir"
        ledger.record_config_realization(realization)
        if architect_repair_codes:
            ledger.record(Receipt(
                receipt_id="config:architect_repair", step=0,
                kind="config_repair", success=True,
                summary=f"Architect config repaired: {', '.join(architect_repair_codes)}",
            ))
        if trace is not None:
            trace.set_architect(
                runtime_ir, (),
                compiled.prefix_messages(),
                repair_codes=architect_repair_codes,
            )
        reconfigurations = 0
        step = 0
        context_packet: Mapping[str, Any] | None = None
        turn: SolverTurn | None = None
        architect_defect_reasons: list[str] = [
            f"initial_config_repaired:{code}" for code in architect_repair_codes
        ]
        verifier_reconfigure_used = False
        verifier_round_finding_sets: list[frozenset[str]] = []
        verifier_memo: dict[str, Any] = {}
        submit_without_evidence_rounds = 0
        while step < self.max_steps:
            alerts = self.monitor_runner.run(compiled, ledger)
            context_packet = self.context_compiler.compile(compiled, ledger, alerts)
            messages = self.build_solver_messages(compiled, context_packet)
            before_count = len(ledger.all_receipts())
            try:
                turn = hooks.solve(messages, compiled)
            except ModelOutputError as exc:
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
                        "raw_output": raw_output[:20000],
                        "raw_output_bytes": len(raw_output),
                        "retry_attempted": True,
                    },
                ))
                retry_messages = list(messages) + [{
                    "role": "user",
                    "content": (
                        "Your previous turn could not be parsed or validated. "
                        f"Error: {exc}. Emit exactly one valid solver turn JSON object using the allowed schema. "
                        "Do not request reconfiguration; report a blocker only through the report_blocker action if needed."
                    ),
                }]
                try:
                    turn = hooks.solve(retry_messages, compiled)
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
                            "raw_output": raw_retry[:20000],
                            "raw_output_bytes": len(raw_retry),
                            "retry_attempted": False,
                        },
                    ))
                    if trace is not None:
                        trace.add_step(step, context_packet, SolverTurn(kind="submit_outcome", summary="solver parse error placeholder"), ledger.all_receipts()[before_count:])
                    self._fire_snapshot(step); step += 1; continue
            turn_errors = turn.validate(compiled.action_schema)
            if turn_errors:
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:turn_invalid", step=step, kind="turn_validation",
                    success=False, summary=f"invalid turn: {'; '.join(turn_errors)}",
                    failure_class="turn_validation",
                ))
                if trace is not None:
                    trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                self._fire_snapshot(step); step += 1; continue
            if turn.kind == "act":
                submit_without_evidence_rounds = 0
                run_act_turn(self, turn, step, compiled, executor, envmap, ledger)
            elif turn.kind == "submit_outcome":
                run_submit_turn(
                    self, step, compiled, executor, envmap, ledger, trace,
                )
                decision = self._last_gate_decision
                canonical_workbench = self.workbench_architect is not None
                if canonical_workbench and self._active_findings_need_intervening_evidence(ledger):
                    verdict = None
                    submit_without_evidence_rounds += 1
                    active_findings = ledger.active_finding_context(step)
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:model_verifier_skipped:active_findings",
                        step=step,
                        kind="model_verifier_skipped",
                        success=True,
                        summary=(
                            "model verifier skipped: active verifier findings require "
                            "an intervening solver action or evidence before another submit"
                        ),
                        failure_class="",
                        payload={
                            "reason": "active_findings_without_intervening_evidence",
                            "active_findings": active_findings,
                            "submit_without_evidence_rounds": submit_without_evidence_rounds,
                        },
                    ))
                    if submit_without_evidence_rounds >= self.SUBMIT_STALEMATE_ROUNDS:
                        active_ids = tuple(sorted(
                            str(item.get("finding_id", ""))
                            for item in active_findings
                            if str(item.get("finding_id", "")).strip()
                        ))
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:solver_submit_stalemate",
                            step=step,
                            kind="solver_submit_stalemate",
                            success=False,
                            summary=(
                                "solver submit stalemate: active verifier findings "
                                "required intervening evidence, but the solver kept "
                                "submitting without adding evidence"
                            ),
                            failure_class="solver_submit_stalemate",
                            payload={
                                "rounds": submit_without_evidence_rounds,
                                "finding_ids": active_ids,
                                "active_findings": active_findings,
                            },
                        ))
                        if trace is not None:
                            trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                        return KernelResult(
                            status="solver_submit_stalemate",
                            step=step,
                            reconfigurations=reconfigurations,
                            blockers=active_ids,
                            env_digest=compiled.env_digest,
                            receipts=ledger.all_receipts(),
                            architect_defect=bool(architect_defect_reasons),
                            architect_defect_reasons=tuple(architect_defect_reasons),
                        )
                else:
                    submit_without_evidence_rounds = 0
                    verdict = run_model_verifier_if_available(
                        hooks,
                        compiled,
                        ledger,
                        step=step,
                        reason="solver_submit",
                        executor=executor,
                        envmap=envmap,
                        memo=verifier_memo,
                    )
                if verdict is not None and verdict.verdict == "completed":
                    if trace is not None:
                        trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                    ready_decision = decision
                    if ready_decision is None:
                        ready_decision = self.completion_gate.evaluate(compiled, ledger, self.monitor_runner.run(compiled, ledger))
                    return _completed_result(
                        step, reconfigurations, ready_decision, compiled, ledger,
                        tuple(architect_defect_reasons),
                    )
                if decision is not None and decision.ready and verdict is None and not canonical_workbench:
                    if trace is not None:
                        trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                    return _completed_result(
                        step, reconfigurations, decision, compiled, ledger,
                        tuple(architect_defect_reasons),
                    )
                if trace is not None:
                    trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                if verdict is not None and verdict.verdict != "completed":
                    active_ids = frozenset(
                        str(item.get("finding_id", ""))
                        for item in ledger.active_finding_context(step + 1)
                        if str(item.get("finding_id", "")).strip()
                    )
                    verifier_round_finding_sets.append(active_ids)
                    window = verifier_round_finding_sets[-self.STALEMATE_ROUNDS:]
                    if (
                        len(window) == self.STALEMATE_ROUNDS
                        and window[0]
                        and all(entry == window[0] for entry in window)
                    ):
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:verifier_stalemate",
                            step=step,
                            kind="verifier_stalemate",
                            success=False,
                            summary=(
                                f"verifier stalemate: the same {len(window[0])} finding(s) "
                                f"survived {self.STALEMATE_ROUNDS} verification rounds with "
                                "intervening solver evidence; harness records the disagreement "
                                "and terminates without picking a winner"
                            ),
                            failure_class="verifier_stalemate",
                            payload={
                                "rounds": self.STALEMATE_ROUNDS,
                                "finding_ids": sorted(window[0]),
                                "round_history": [sorted(entry) for entry in verifier_round_finding_sets],
                                "final_verifier_verdict": verdict.as_dict(),
                                "active_findings": ledger.active_finding_context(step + 1),
                            },
                        ))
                        return KernelResult(
                            status="verifier_stalemate", step=step,
                            reconfigurations=reconfigurations,
                            blockers=tuple(sorted(window[0])),
                            env_digest=compiled.env_digest,
                            receipts=ledger.all_receipts(),
                            architect_defect=bool(architect_defect_reasons),
                            architect_defect_reasons=tuple(architect_defect_reasons),
                        )
                if (
                    verdict is not None
                    and verdict.verdict == "blocked_by_harness_config"
                    and canonical_workbench
                ):
                    if not verifier_reconfigure_used:
                        verifier_reconfigure_used = True
                        compiled, reconfigured = verifier_triggered_reconfigure(
                            self, hooks, compiler, envmap, compiled, ledger, verdict,
                            current_step=step,
                        )
                        if reconfigured:
                            reconfigurations += 1
                            architect_defect_reasons.append("verifier_triggered_reconfigure")
                    else:
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:verifier_reconfigure_exhausted",
                            step=step,
                            kind="verifier_reconfigure_exhausted",
                            success=False,
                            summary=(
                                "verifier reported blocked_by_harness_config again but the "
                                "single-shot reconfiguration was already used"
                            ),
                            failure_class="config_invalid",
                            payload={"architect_defect": True},
                        ))
                if (
                    decision is not None
                    and canonical_workbench
                    and verdict is None
                ):
                    ledger.record(Receipt(
                        receipt_id=f"step-{step}:verifier_required_for_completion",
                        step=step,
                        kind="verifier_required_for_completion",
                        success=False,
                        summary="canonical workbench submit did not receive a verifier verdict; completion remains solver-driven until verifier runs",
                        failure_class="verifier_missing",
                    ))
                self._fire_snapshot(step); step += 1; continue
            if trace is not None:
                trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
            self._fire_snapshot(step); step += 1
        return KernelResult(
            status="incomplete", step=step, reconfigurations=reconfigurations,
            blockers=tuple(ob.obligation_id for ob in ledger.open_obligations()),
            env_digest=compiled.env_digest, receipts=ledger.all_receipts(),
            architect_defect=bool(architect_defect_reasons),
            architect_defect_reasons=tuple(architect_defect_reasons),
        )

    @staticmethod
    def _active_findings_need_intervening_evidence(ledger: ExecutionLedger) -> bool:
        active_findings = ledger.active_finding_context(len(ledger.all_receipts()))
        if not active_findings:
            return False
        evidence_kinds = {
            "read_file",
            "write_file",
            "run_command",
            "bootstrap_acquire",
            "launch_process",
            "probe_service",
            "stop_process",
            "inspect_artifact",
            "query_artifact_history",
            "inspect_diff",
            "record_observation",
            "query_memory",
            "register_candidate",
            "run_experiment",
            # A verifier-triggered reconfiguration changes the workbench the
            # findings were raised against; the verifier must re-judge rather
            # than being starved by its own config finding.
            "verifier_triggered_reconfigure",
        }
        # Compare by ledger position, not step number: evidence recorded in
        # the same step as (but after) the verifier result still counts.
        receipts = ledger.all_receipts()
        last_verifier_index = -1
        for index, receipt in enumerate(receipts):
            if receipt.kind == "model_verifier_result":
                last_verifier_index = index
        for receipt in receipts[last_verifier_index + 1:]:
            if receipt.kind in evidence_kinds:
                return False
        return True

    def _fire_snapshot(self, step: int) -> None:
        if self.snapshot_callback is not None and step in self._snapshot_steps:
            self.snapshot_callback(step)
