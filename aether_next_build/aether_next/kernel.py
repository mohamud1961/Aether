from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from hashlib import sha256
from typing import Any, Callable, Mapping, Protocol, TYPE_CHECKING

from .compiler import CapabilityRegistry, ConfigCompiler
from .completion import CompletionGate, FailureParser
from .execution import (
    BootstrapEngine, Executor, ExperimentEngine, PerceptionLane, ProcessOrchestratorV2,
)
from .kernel_config import ResolvedRuntime, resolve_runtime
from .kernel_messages import build_architect_request, build_solver_messages
from .kernel_actions import handle_kernel_owned_action
from .kernel_verifier import run_model_verifier_if_available
from .context_compiler import ContextCompiler
from .automatic_memory import automatic_memory_receipt
from .no_progress import NoProgressController
from .ledger import ExecutionLedger, Receipt
from .monitors import IntegrityGuards, LocalOnlySafetyGuard, MonitorRunner
from .kernel_checks import cheap_checks_all_passed, probe_checks
from .model_hooks import ModelOutputError
from .redaction import redact_text_with_events
from .runtime_ir import (
    ActionRequest, CompiledRuntime, EnvMap, EvalIndex, ObjectiveGraph,
    RuntimeConfigIR, SolverTurn, normalize_relpath,
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

def _completed_result(
    step: int, reconfigurations: int, decision: Any,
    compiled: CompiledRuntime, ledger: ExecutionLedger,
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
    )


def _head_tail(text: str, cap: int) -> str:
    """Return a marked head+tail excerpt without destroying full payloads."""
    if len(text) <= cap:
        return text
    half = max(1, cap // 2)
    omitted = len(text) - (half * 2)
    return text[:half] + f"\n... [omitted {omitted} chars; full output available by handle]\n" + text[-half:]



def _action_timeout_s(action: ActionRequest, envmap: EnvMap) -> tuple[int, str]:
    """Bound solver-requested command timeout by generic task budget metadata.

    The solver may request a longer timeout for builds/training/service setup,
    but the harness remains in charge of the ceiling.  Task metadata comes from
    task.toml when available; this is generic budget information, not hidden
    grader logic.
    """
    requested_raw = action.arguments.get("timeout_s", None)
    default_timeout = 30
    metadata = envmap.task_metadata if isinstance(envmap.task_metadata, Mapping) else {}
    budget = metadata.get("resource_budget") if isinstance(metadata.get("resource_budget"), Mapping) else {}
    timeout_candidates = [300]
    for key in ("agent_timeout_sec", "timeout_sec", "verifier_timeout_sec"):
        value = budget.get(key) or metadata.get(key)
        try:
            if value is not None:
                timeout_candidates.append(max(30, int(float(value))))
        except (TypeError, ValueError):
            pass
    max_timeout = min(max(timeout_candidates), 12_000)
    if requested_raw is None:
        return default_timeout, f"default={default_timeout}; max_available={max_timeout}"
    try:
        requested = int(float(requested_raw))
    except (TypeError, ValueError):
        return default_timeout, f"invalid_requested={requested_raw!r}; default={default_timeout}; max_available={max_timeout}"
    if requested <= 0:
        return default_timeout, f"nonpositive_requested={requested}; default={default_timeout}; max_available={max_timeout}"
    effective = min(requested, max_timeout)
    return effective, f"requested={requested}; effective={effective}; max_available={max_timeout}"

class KernelHooks(Protocol):
    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        ...

    def solve(self, messages: list[dict[str, str]], compiled: CompiledRuntime) -> SolverTurn:
        ...

    def reconfigure(
        self,
        request: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
    ) -> RuntimeConfigIR:
        ...

class AetherNextKernel:
    def __init__(
        self,
        *,
        max_steps: int = 24,
        contract_architect: Any | None = None,
        workbench_architect: Any | None = None,
        snapshot_callback: Callable[[int], None] | None = None,
        snapshot_steps: tuple[int, ...] = (),
    ) -> None:
        self.max_steps = max(1, int(max_steps))
        self.contract_architect = contract_architect
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
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
        resolved = resolve_runtime(
            envmap, compiler, hooks,
            contract_architect=self.contract_architect,
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
        elif resolved.contract is not None:
            realization["architect_path"] = "contract"
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
                self._run_act_turn(turn, step, compiled, executor, envmap, ledger)
                if compiled.planned_checks() and cheap_checks_all_passed(compiled, ledger):
                    self._run_submit_turn(step, compiled, executor, envmap, ledger, trace)
                    decision = self._last_gate_decision
                    if (
                        decision is not None
                        and decision.ready
                        and self.workbench_architect is None
                    ):
                        ledger.record(Receipt(
                            receipt_id=f"step-{step}:auto_submit", step=step,
                            kind="auto_submit", success=True,
                            summary="auto-submitted: contract checks passed",
                        ))
                        if trace is not None:
                            trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                        return _completed_result(step, reconfigurations, decision, compiled, ledger)
            elif turn.kind == "submit_outcome":
                self._run_submit_turn(
                    step, compiled, executor, envmap, ledger, trace,
                )
                decision = self._last_gate_decision
                canonical_workbench = self.workbench_architect is not None
                if canonical_workbench and self._active_findings_need_intervening_evidence(ledger):
                    verdict = None
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
                            "active_findings": ledger.active_finding_context(step),
                        },
                    ))
                else:
                    verdict = run_model_verifier_if_available(
                        hooks,
                        compiled,
                        ledger,
                        step=step,
                        reason="solver_submit",
                        executor=executor,
                        envmap=envmap,
                    )
                if verdict is not None and verdict.verdict == "completed":
                    if trace is not None:
                        trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                    ready_decision = decision
                    if ready_decision is None:
                        ready_decision = self.completion_gate.evaluate(compiled, ledger, self.monitor_runner.run(compiled, ledger))
                    return _completed_result(step, reconfigurations, ready_decision, compiled, ledger)
                if decision is not None and decision.ready and verdict is None and not canonical_workbench:
                    if trace is not None:
                        trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                    return _completed_result(step, reconfigurations, decision, compiled, ledger)
                if trace is not None:
                    trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                if (
                    not canonical_workbench
                    and decision is not None
                    and decision.recommend_reconfigure
                    and reconfigurations < compiled.reconfigure_policy.max_reconfigurations
                ):
                    runtime_ir, compiled, reconfigurations = self._do_reconfigure(
                        hooks, compiler, envmap, compiled, ledger,
                        objective_graph, eval_index, reconfigurations,
                        reason="completion_gate_recommend", current_step=step, trace=trace,
                    )
                    self._fire_snapshot(step); step += 1; continue
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
            elif turn.kind == "request_reconfigure":
                ledger.record(Receipt(
                    receipt_id=f"step-{step}:solver_reconfigure_unsupported",
                    step=step,
                    kind="unsupported_solver_reconfigure",
                    success=False,
                    summary="solver-requested reconfiguration is not supported; use report_blocker with concrete evidence",
                    failure_class="unsupported_solver_reconfigure",
                    payload={"reconfigure_reason": turn.reconfigure_reason},
                ))
                if trace is not None:
                    trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
                self._fire_snapshot(step); step += 1; continue
            if trace is not None:
                trace.add_step(step, context_packet, turn, ledger.all_receipts()[before_count:])
            self._fire_snapshot(step); step += 1
        return KernelResult(
            status="incomplete", step=step, reconfigurations=reconfigurations,
            blockers=tuple(ob.obligation_id for ob in ledger.open_obligations()),
            env_digest=compiled.env_digest, receipts=ledger.all_receipts(),
        )

    @staticmethod
    def _active_findings_need_intervening_evidence(ledger: ExecutionLedger) -> bool:
        active_findings = ledger.active_finding_context(len(ledger.all_receipts()))
        if not active_findings:
            return False
        newest_finding_step = max(int(item.get("created_step", 0)) for item in active_findings)
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
        }
        for receipt in ledger.all_receipts():
            if receipt.step <= newest_finding_step:
                continue
            if receipt.kind in evidence_kinds:
                return False
        return True

    def _fire_snapshot(self, step: int) -> None:
        if self.snapshot_callback is not None and step in self._snapshot_steps:
            self.snapshot_callback(step)

    def _run_act_turn(self, turn: SolverTurn, step: int, compiled: CompiledRuntime,
                      executor: Executor, envmap: EnvMap, ledger: ExecutionLedger) -> None:
        step_receipts: list[Receipt] = []

        def _record(r: Receipt) -> None:
            ledger.record(r)
            step_receipts.append(r)

        for action in turn.actions:
            action_errors = action.validate(compiled.action_schema)
            if action_errors:
                _record(Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:validation", step=step,
                    kind="action_validation", success=False,
                    summary=f"invalid action: {'; '.join(action_errors)}",
                    failure_class="action_validation",
                ))
                continue
            safety_violation = self.safety_guard.violation(compiled, action)
            if safety_violation:
                _record(Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:safety", step=step,
                    kind="safety_block", success=False,
                    summary=safety_violation, failure_class="safety_violation",
                ))
                continue
            if action.kind == "write_file":
                path = str(action.arguments.get("path", "")).strip()
                if path:
                    norm = normalize_relpath(path, envmap.workspace_root)
                    violation = self.integrity_guards.explain_path_violation(
                        compiled.objective_graph, norm,
                    )
                    if violation:
                        _record(Receipt(
                            receipt_id=f"step-{step}:{action.action_id}:integrity",
                            step=step, kind="integrity_block", success=False,
                            summary=violation, failure_class="integrity_violation",
                            payload={"integrity_violation": violation},
                        ))
                        continue
            if compiled.automatic_memory_policy.mode != "off":
                automatic = automatic_memory_receipt(
                    action, step=step, envmap=envmap, ledger=ledger,
                )
                if automatic is not None:
                    _record(automatic)
                    block_reason = self._automatic_memory_block_reason(compiled, automatic)
                    if block_reason:
                        _record(Receipt(
                            receipt_id=f"step-{step}:{action.action_id}:automatic_memory_advisory",
                            step=step,
                            kind="automatic_memory_advisory",
                            success=True,
                            summary=block_reason,
                            failure_class="",
                            payload={
                                "source_receipt_id": automatic.receipt_id,
                                "policy": compiled.automatic_memory_policy.mode,
                                "target": automatic.payload.get("target"),
                                "authority": "advisory_only",
                            },
                        ))
            no_progress = self.no_progress_controller.evaluate(action, ledger)
            if no_progress is not None:
                _record(NoProgressController.receipt(no_progress, step=step, action_id=action.action_id))
            handled = handle_kernel_owned_action(action, step, compiled, executor, envmap, ledger)
            if handled is not None:
                _record(handled); continue
            for receipt in self._dispatch_action(action, step, compiled, executor, envmap, ledger):
                _record(receipt)
        probe_checks(step, compiled, executor, envmap, ledger, tuple(step_receipts))

    @staticmethod
    def _automatic_memory_block_reason(compiled: CompiledRuntime, receipt: Receipt) -> str:
        mode = compiled.automatic_memory_policy.mode
        if mode not in {"require_justification", "soft_block_exact_repeat"}:
            return ""
        payload = receipt.payload or {}
        if bool(payload.get("repeat_justified")):
            return ""
        target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
        action_kind = str(payload.get("action_kind", ""))
        exact_repeat = bool(payload.get("same_content_hash")) or action_kind in {"run_command", "run_check"}
        if mode == "require_justification":
            return (
                "automatic memory requires repeat_justification before repeating "
                f"{action_kind} on {target.get('key', 'this target')}"
            )
        if mode == "soft_block_exact_repeat" and exact_repeat:
            return (
                "automatic memory soft-blocked an exact repeated action without new state or repeat_justification: "
                f"{action_kind} on {target.get('key', 'this target')}"
            )
        return ""

    def _run_submit_turn(
        self,
        step: int,
        compiled: CompiledRuntime,
        executor: Executor,
        envmap: EnvMap,
        ledger: ExecutionLedger,
        trace: RunTrace | None,
    ) -> None:
        """Execute submit_outcome logic; stores gate decision in ``_last_gate_decision``."""
        for check in compiled.planned_checks():
            result = executor.run_command(check.command, cwd=envmap.workspace_root)
            failure_class = self.failure_parser.classify(
                result.stdout + "\n" + result.stderr, exit_code=result.exit_code,
            ) if not result.success else ""
            ledger.record(Receipt(
                receipt_id=f"step-{step}:check:{check.check_id}", step=step,
                kind="check_result", success=result.success,
                summary=f"check {check.label}: exit={result.exit_code}",
                state_change=result.success, failure_class=failure_class,
                payload={
                    "check_id": check.check_id, "command": check.command,
                    "passed": result.success, "origin": check.origin,
                    "detail": (result.stderr or result.stdout)[:500],
                },
            ))
        if compiled.objective_graph.output_schema and compiled.objective_graph.output_schema_target:
            target_path = compiled.objective_graph.output_schema_target
            try:
                content = executor.read_file(target_path)
                schema = dict(compiled.objective_graph.output_schema)
                if target_path.lower().endswith(".csv"):
                    reader = csv.DictReader(content.splitlines())
                    fields = reader.fieldnames or []
                    missing_keys = [k for k in schema if k not in fields]
                else:
                    parsed = json.loads(content)
                    missing_keys = [k for k in schema if k not in parsed]
                valid = not missing_keys
                detail = "" if valid else f"missing keys: {', '.join(missing_keys)}"
            except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
                valid = False
                detail = str(exc)
            ledger.record(Receipt(
                receipt_id=f"step-{step}:schema_validation", step=step,
                kind="schema_validation", success=valid,
                summary=f"schema validation: {'pass' if valid else detail}",
                failure_class="" if valid else "schema_mismatch",
            ))
        alerts = self.monitor_runner.run(compiled, ledger)
        decision = self.completion_gate.evaluate(compiled, ledger, alerts)
        if trace is not None:
            trace.add_gate(step, decision)
        self._last_gate_decision = decision

    def _do_reconfigure(self, hooks: KernelHooks, compiler: ConfigCompiler,
                        envmap: EnvMap, compiled: CompiledRuntime,
                        ledger: ExecutionLedger, objective_graph: ObjectiveGraph,
                        eval_index: EvalIndex, reconfigurations: int, *,
                        reason: str,
                        current_step: int,
        trace: RunTrace | None = None,
    ) -> tuple[RuntimeConfigIR, CompiledRuntime, int]:
        reconfig_request = {
            "reason": reason,
            "failure_clusters": ledger.failure_clusters(),
            "open_obligations": [ob.as_dict() for ob in ledger.open_obligations()],
            "reconfigure_causes": list(ledger.reconfigure_causes),
        }
        if self.workbench_architect is not None:
            return self._do_reconfigure_workbench(
                hooks, compiler, envmap, compiled, ledger,
                objective_graph, eval_index, reconfigurations,
                reason=reason, current_step=current_step, trace=trace,
                reconfig_request=reconfig_request,
            )
        new_ir = hooks.reconfigure(reconfig_request, compiled, ledger)
        issues = compiler.validate(
            new_ir, envmap,
            objective_graph=objective_graph, eval_index=eval_index,
        )
        fatal_issues = [issue for issue in issues if issue.fatal]
        if fatal_issues:
            ledger.record(Receipt(
                receipt_id=f"step-{current_step}:reconfig-{reconfigurations}:invalid", step=current_step,
                kind="reconfigure_validation", success=False,
                summary=f"reconfiguration invalid: {'; '.join(i.code for i in fatal_issues)}",
                failure_class="config_invalid",
            ))
            return new_ir, compiled, reconfigurations + 1
        new_compiled = compiler.compile(
            new_ir, envmap,
            objective_graph=objective_graph, eval_index=eval_index,
        )
        ledger.seed_capabilities(new_compiled.selected_capability_ids())
        ledger.record(Receipt(
            receipt_id=f"step-{current_step}:reconfig-{reconfigurations}:ok", step=current_step,
            kind="reconfigure", success=True,
            summary=f"reconfigured: {reason}", state_change=True,
            payload={"reconfigure_cause": reason},
        ))
        ledger.record_config_realization(
            dict(new_compiled.config_realization),
            receipt_id=f"reconfig-{reconfigurations}:realization",
        )
        if trace is not None:
            trace.add_reconfigure(reconfigurations, reason, new_ir)
        return new_ir, new_compiled, reconfigurations + 1

    def _do_reconfigure_workbench(self, hooks: KernelHooks, compiler: ConfigCompiler,
                        envmap: EnvMap, compiled: CompiledRuntime,
                        ledger: ExecutionLedger, objective_graph: ObjectiveGraph,
                        eval_index: EvalIndex, reconfigurations: int, *,
                        reason: str,
                        current_step: int,
                        reconfig_request: dict[str, Any],
        trace: RunTrace | None = None,
    ) -> tuple[RuntimeConfigIR, CompiledRuntime, int]:
        """Reconfigure through the same workbench architect interface used for
        the initial config, instead of the legacy ``hooks.reconfigure()`` path
        (a thinner prompt/parser that silently collapses a rich architect
        contract to a generic default on any parse hiccup). The architect
        should never be forced through a weaker interface mid-run just because
        a reconfiguration was requested.
        """
        resolved = resolve_runtime(
            envmap, compiler, hooks,
            workbench_architect=self.workbench_architect,
            reconfigure_context=reconfig_request,
        )
        if resolved.compiled is None:
            codes = ", ".join(resolved.fallback_codes) or "workbench_reconfigure_failed"
            ledger.record(Receipt(
                receipt_id=f"step-{current_step}:reconfig-{reconfigurations}:invalid", step=current_step,
                kind="reconfigure_validation", success=False,
                summary=f"workbench reconfiguration invalid: {codes}",
                failure_class="config_invalid",
                payload={
                    "architect_path": "workbench",
                    "blockers": list(resolved.config_invalid_blockers),
                    "fallback_codes": list(resolved.fallback_codes),
                },
            ))
            return resolved.runtime_ir, compiled, reconfigurations + 1
        new_ir, new_compiled = resolved.runtime_ir, resolved.compiled
        ledger.seed_capabilities(new_compiled.selected_capability_ids())
        ledger.record(Receipt(
            receipt_id=f"step-{current_step}:reconfig-{reconfigurations}:ok", step=current_step,
            kind="reconfigure", success=True,
            summary=f"reconfigured via workbench architect: {reason}", state_change=True,
            payload={"reconfigure_cause": reason, "architect_path": "workbench"},
        ))
        ledger.record_config_realization(
            dict(new_compiled.config_realization),
            receipt_id=f"reconfig-{reconfigurations}:realization",
        )
        if trace is not None:
            trace.add_reconfigure(reconfigurations, reason, new_ir)
        return new_ir, new_compiled, reconfigurations + 1

    def _dispatch_action(self, action: ActionRequest, step: int, compiled: CompiledRuntime,
                         executor: Executor, envmap: EnvMap, ledger: ExecutionLedger) -> list[Receipt]:
        kind = action.kind
        if kind == "read_file":
            path = normalize_relpath(str(action.arguments.get("path", "")), envmap.workspace_root)
            base = {"path": path, "candidate_id": action.candidate_id}
            try:
                content = executor.read_file(path)
                payload = dict(base)
                payload.update({
                    "content_hash": sha256(content.encode("utf-8", "replace")).hexdigest()[:16],
                    "bytes": len(content),
                    "content": content,
                    "excerpt": _head_tail(content, 4000),
                    "file_handle": f"file:{path}",
                })
                return [Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:read", step=step,
                    kind="read_file", success=True,
                    summary=f"read {path} ({len(content)} bytes)", payload=payload,
                )]
            except FileNotFoundError:
                return [Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:read", step=step,
                    kind="read_file", success=False, summary=f"file not found: {path}",
                    failure_class="missing_artifact", payload=base,
                )]
        if kind == "read_file_page":
            path = normalize_relpath(str(action.arguments.get("path", "")), envmap.workspace_root)
            try:
                content = executor.read_file(path)
                offset = max(0, int(action.arguments.get("offset", 0) or 0))
                span = max(1, min(20000, int(action.arguments.get("span", 8000) or 8000)))
                chunk = content[offset: offset + span]
                return [Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:read_page",
                    step=step, kind="read_file_page", success=True,
                    summary=f"read {path} bytes {offset}:{offset + len(chunk)}",
                    payload={"path": path, "offset": offset, "span": span, "bytes": len(content), "chunk": chunk, "file_handle": f"file:{path}"},
                )]
            except FileNotFoundError:
                return [Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:read_page", step=step,
                    kind="read_file_page", success=False, summary=f"file not found: {path}",
                    failure_class="missing_artifact", payload={"path": path},
                )]
        if kind in {"read_output", "grep_output"}:
            handle = str(action.arguments.get("handle", "")).strip()
            pattern = str(action.arguments.get("pattern", ""))
            full = ""
            source_receipt = ""
            stream = ""
            for receipt in ledger.all_receipts():
                payload = receipt.payload or {}
                if payload.get("stdout_handle") == handle:
                    full = str(payload.get("stdout_full", "")); source_receipt = receipt.receipt_id; stream = "stdout"; break
                if payload.get("stderr_handle") == handle:
                    full = str(payload.get("stderr_full", "")); source_receipt = receipt.receipt_id; stream = "stderr"; break
            if not source_receipt:
                return [Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:output", step=step,
                    kind=kind, success=False, summary=f"output handle not found: {handle}",
                    failure_class="missing_context_handle", payload={"handle": handle},
                )]
            if kind == "grep_output":
                lines = [line for line in full.splitlines() if pattern in line]
                chunk = "\n".join(lines[:200])
                summary = f"grep_output {handle!r} pattern={pattern!r}: {len(lines)} matching lines"
                payload = {"handle": handle, "pattern": pattern, "matches": len(lines), "chunk": chunk, "source_receipt_id": source_receipt, "stream": stream}
            else:
                offset = max(0, int(action.arguments.get("offset", 0) or 0))
                span = max(1, min(20000, int(action.arguments.get("span", 8000) or 8000)))
                chunk = full[offset: offset + span]
                summary = f"read_output {handle!r} bytes {offset}:{offset + len(chunk)}"
                payload = {"handle": handle, "offset": offset, "span": span, "bytes": len(full), "chunk": chunk, "source_receipt_id": source_receipt, "stream": stream}
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:output", step=step, kind=kind, success=True, summary=summary, payload=payload,
            )]
        if kind == "report_blocker":
            payload = {
                "blocked_component": str(action.arguments.get("blocked_component", "")),
                "observed_evidence": str(action.arguments.get("observed_evidence", "")),
                "attempted_actions": str(action.arguments.get("attempted_actions", "")),
                "why_current_tools_or_config_prevent_progress": str(action.arguments.get("why_current_tools_or_config_prevent_progress", "")),
                "requested_harness_change": str(action.arguments.get("requested_harness_change", "")),
                "candidate_id": action.candidate_id,
            }
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:blocker", step=step,
                kind="report_blocker", success=False,
                summary=f"solver reported blocker: {payload['blocked_component']}",
                failure_class="solver_reported_blocker", payload=payload,
            )]
        if kind == "write_file":
            path = normalize_relpath(str(action.arguments.get("path", "")), envmap.workspace_root)
            before_hash = ""
            before_bytes = None
            try:
                before_content = executor.read_file(path)
                before_hash = sha256(before_content.encode("utf-8", "replace")).hexdigest()[:16]
                before_bytes = len(before_content)
            except FileNotFoundError:
                before_content = ""
            content = str(action.arguments.get("content", ""))
            executor.write_file(path, content)
            after_hash = sha256(content.encode("utf-8", "replace")).hexdigest()[:16]
            payload = {
                "path": path,
                "modified_paths": (path,),
                "artifact_paths": (path,),
                "candidate_id": action.candidate_id,
                "before_content_hash": before_hash,
                "after_content_hash": after_hash,
                "before_bytes": before_bytes,
                "bytes": len(content),
                "content": content,
                "excerpt": _head_tail(content, 4000),
                "file_handle": f"file:{path}",
            }
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:write", step=step,
                kind="write_file", success=True, summary=f"wrote {path}", state_change=True,
                payload={k: v for k, v in payload.items() if v is not None and v != ""},
            )]
        if kind == "run_command":
            command = str(action.arguments.get("command", ""))
            timeout_s, timeout_note = _action_timeout_s(action, envmap)
            result = executor.run_command(command, cwd=envmap.workspace_root, timeout_s=timeout_s)
            failure_class = self.failure_parser.classify(
                result.stdout + "\n" + result.stderr,
                exit_code=result.exit_code,
            ) if not result.success else ""
            integrity_violation = self.integrity_guards.validate_modified_paths(
                compiled.objective_graph, result.modified_paths,
            )
            payload: dict[str, Any] = {
                "command": command,
                "timeout_s": timeout_s,
                "timeout_policy": timeout_note,
                "exit_code": result.exit_code,
                "stdout": _head_tail(result.stdout, 8000),
                "stderr": _head_tail(result.stderr, 8000),
                "stdout_full": result.stdout,
                "stderr_full": result.stderr,
                "stdout_handle": f"{step}:{action.action_id}:stdout",
                "stderr_handle": f"{step}:{action.action_id}:stderr",
                "stdout_bytes": len(result.stdout),
                "stderr_bytes": len(result.stderr),
                "modified_paths": tuple(
                    normalize_relpath(p, envmap.workspace_root) for p in result.modified_paths
                ),
                "artifact_paths": tuple(
                    normalize_relpath(p, envmap.workspace_root) for p in result.produced_artifacts
                ),
                "candidate_id": action.candidate_id,
            }
            if integrity_violation:
                payload["integrity_violation"] = integrity_violation
            if result.metrics:
                first_key = sorted(result.metrics)[0]
                payload["metric_name"] = first_key
                payload["metric_value"] = result.metrics[first_key]
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:cmd",
                step=step,
                kind="run_command",
                success=result.success,
                summary=f"command exit={result.exit_code}: {command}",
                state_change=bool(result.modified_paths or result.produced_artifacts),
                failure_class=failure_class,
                payload=payload,
            )]
        if kind == "bootstrap_acquire":
            return [self.bootstrap_engine.execute(action, step, executor, envmap)[0]]
        if kind == "launch_process":
            interactive = compiled.process_policy.mode == "interactive_detachable"
            return [self.process_orchestrator.launch(
                action, step, executor,
                workspace_root=envmap.workspace_root, interactive=interactive,
            )]
        if kind == "probe_service":
            return [self.process_orchestrator.probe(action, step, executor)]
        if kind == "stop_process":
            return [self.process_orchestrator.stop(action, step, executor)]
        if kind == "inspect_artifact":
            return [self.perception_lane.inspect(
                action, step, executor, workspace_root=envmap.workspace_root,
            )]
        if kind == "register_candidate":
            cid = str(action.arguments.get("candidate_id", "")).strip()
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:register", step=step,
                kind="register_candidate", success=True,
                summary=f"registered candidate {cid}", state_change=True,
                payload={"candidate_id": cid,
                         "candidate_summary": str(action.arguments.get("summary", "")).strip(),
                         "candidate_status": "active"},
            )]
        if kind == "run_experiment":
            return [self.experiment_engine.run(
                action, step, executor, workspace_root=envmap.workspace_root,
            )]
        return [Receipt(
            receipt_id=f"step-{step}:{action.action_id}:unknown", step=step,
            kind="unknown_action", success=False,
            summary=f"unknown action kind: {kind}", failure_class="action_validation",
        )]
