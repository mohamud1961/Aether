"""Tests for AUTO-SUBMIT-ON-EVIDENCE: kernel auto-completes when all planned
checks pass after an act turn, without waiting for submit_outcome."""
from __future__ import annotations

from typing import Any, Mapping

import pytest

from aether_next.compiler import CapabilityRegistry, ConfigCompiler
from aether_next.execution import CommandResult, MemoryExecutor
from aether_next.kernel import AetherNextKernel, KernelHooks, KernelResult
from aether_next.ledger import ExecutionLedger
from aether_next.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    CheckSpec,
    CompletionPolicy,
    CompiledRuntime,
    ContextPolicy,
    DeliverableSpec,
    EnvMap,
    EvalIndex,
    ObjectiveGraph,
    ProofObligation,
    ReconfigurePolicy,
    RefusalPolicy,
    ModelVerifierPolicy,
    RuntimeConfigIR,
    SolverTurn,
)
from aether_next.contract_compile import contract_to_eval_index
from aether_next.task_contract import (
    ContractCheck,
    ContractDeliverable,
    ContractSchema,
    TaskContract,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_kernel.py / test_live_checks.py patterns)
# ---------------------------------------------------------------------------

_CAPS = {
    "shell": CapabilityDescriptor(capability_id="shell", summary="Run commands"),
    "filesystem": CapabilityDescriptor(capability_id="filesystem", summary="Read/write files"),
}


def _make_envmap(
    *,
    task_prompt: str = "Do the task.",
    workspace_root: str = "/app",
    grader_hints: Mapping[str, Any] | None = None,
    capabilities: Mapping[str, CapabilityDescriptor] | None = None,
) -> EnvMap:
    return EnvMap(
        task_prompt=task_prompt,
        workspace_root=workspace_root,
        capabilities=capabilities or dict(_CAPS),
        grader_hints=dict(grader_hints or {}),
    )


def _make_ir(
    *,
    selected_capabilities: tuple[str, ...] = ("shell", "filesystem"),
    completion_policy: CompletionPolicy | None = None,
    check_plan: tuple[str, ...] = (),
    forbidden_paths: tuple[str, ...] = (),
) -> RuntimeConfigIR:
    return RuntimeConfigIR(
        architect_summary="Test summary.",
        solver_identity_prompt="You are a solver.",
        selected_capabilities=selected_capabilities,
        completion_policy=completion_policy or CompletionPolicy(
            require_authoritative_check=False,
            require_all_obligations=False,
            require_recent_progress=False,
            require_clean_integrity=True,
        ),
        refusal_policy=RefusalPolicy(),
        reconfigure_policy=ReconfigurePolicy(),
        model_verifier_policy=ModelVerifierPolicy(enabled=False),
        check_plan=check_plan,
        forbidden_paths=forbidden_paths,
        inspection_plan=("inspect workspace",),
        proof_plan=("verify output",),
    )


class FakeHooks:
    """Configurable KernelHooks implementation for tests."""

    def __init__(
        self,
        ir: RuntimeConfigIR,
        turns: list[SolverTurn],
    ) -> None:
        self._ir = ir
        self._turns = list(turns)
        self.solve_call_count = 0

    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        return self._ir

    def solve(self, messages: list[dict[str, str]], compiled: CompiledRuntime) -> SolverTurn:
        self.solve_call_count += 1
        if self._turns:
            return self._turns.pop(0)
        # Fallback: keep acting (simulate over-verification), never submit.
        return SolverTurn(
            kind="act",
            summary=f"over-verify step {self.solve_call_count}",
            actions=(
                ActionRequest(
                    action_id=f"a-read-oververify-{self.solve_call_count}",
                    kind="read_file",
                    capability_id="filesystem",
                    arguments={"path": "out.txt"},
                    intent="re-reading to verify",
                    expected_observation="file contents",
                    if_fail_next="retry",
                ),
            ),
        )

    def reconfigure(
        self,
        request: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
    ) -> RuntimeConfigIR:
        return self._ir


def _action(
    kind: str,
    arguments: Mapping[str, Any],
    *,
    action_id: str = "",
    capability_id: str = "shell",
) -> ActionRequest:
    aid = action_id or f"a-{kind}-1"
    return ActionRequest(
        action_id=aid,
        kind=kind,
        capability_id=capability_id,
        arguments=arguments,
        intent="test intent",
        expected_observation="test observation",
        if_fail_next="retry",
    )


def _act_turn(*actions: ActionRequest) -> SolverTurn:
    return SolverTurn(kind="act", summary="acting", actions=tuple(actions))


def _submit_turn() -> SolverTurn:
    return SolverTurn(kind="submit_outcome", summary="submitting")


class _FakeContractArchitect:
    """Stub contract architect that returns a fixed contract."""

    def __init__(self, contract: TaskContract) -> None:
        self._contract = contract

    def extract(
        self, request: Any, *, workspace_root: str = "/app",
    ) -> tuple[TaskContract | None, list[str]]:
        return self._contract, []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAutoSubmitsWhenAllChecksPass:
    """Kernel with a contract-style compiled runtime: planned existence check
    for out.txt + artifact obligation.  The solver's step-0 act writes out.txt
    (so probe existence check passes, triggering _run_submit_turn which runs
    the full check set).  Subsequent turns are more act turns that never submit
    (simulating codex over-verification).  Assert the run returns
    status='completed' with an 'auto_submit' receipt at a step well before
    max_steps, and the model never emitted submit_outcome."""

    def test_auto_submits_when_all_checks_pass(self) -> None:
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        # Handler: `test -e out.txt` passes when out.txt exists.
        def existence_handler(ex: MemoryExecutor, cmd: str) -> CommandResult:
            if "out.txt" in ex.files:
                return CommandResult(command=cmd, exit_code=0, stdout="exists")
            return CommandResult(command=cmd, exit_code=1, stderr="not found")

        executor.register_command("test -e out.txt", existence_handler)

        contract = TaskContract(
            task_understanding="Create out.txt.",
            deliverables=(
                ContractDeliverable(path="/app/out.txt", description="output"),
            ),
            capabilities=("shell", "filesystem"),
        )

        # Step 0: write out.txt.  After this the probe runs, cheap checks pass,
        # _run_submit_turn fires the full check set, gate is ready -> auto-submit.
        write_action = _action(
            "write_file",
            {"path": "out.txt", "content": "hello world"},
            action_id="a-write-out",
            capability_id="filesystem",
        )
        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=True,
                allow_evidence_fallback=False,
                require_all_obligations=True,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
        )
        hooks = FakeHooks(ir, [_act_turn(write_action)])
        kernel = AetherNextKernel(max_steps=10, contract_architect=_FakeContractArchitect(contract))
        result = kernel.run(envmap, executor, hooks)

        # 1. Status should be completed.
        assert result.status == "completed", (
            f"Expected completed, got {result.status}. Blockers: {result.blockers}"
        )

        # 2. An auto_submit receipt must exist.
        auto_receipts = [r for r in result.receipts if r.kind == "auto_submit"]
        assert auto_receipts, (
            f"Expected auto_submit receipt but found none. "
            f"Kinds: {[r.kind for r in result.receipts]}"
        )

        # 3. Completed well before max_steps.
        assert result.step < 5, (
            f"Expected auto-submit at an early step, got step={result.step}"
        )

        # 4. Auto-submit now runs _run_submit_turn, which records authoritative
        #    check receipts.  Verify at least one authoritative check ran.
        auth_check_receipts = [
            r for r in result.receipts
            if r.kind == "check_result" and ":check:" in r.receipt_id
        ]
        assert auth_check_receipts, (
            "Expected authoritative check receipts from _run_submit_turn"
        )


class TestAutoSubmitsWhenSchemaCheckPasses:
    """Contract has a deliverable + an output schema.  When the file exists
    and satisfies the schema (both generated checks pass), auto-submit fires
    even though the model never emits submit_outcome."""

    def test_auto_submits_when_schema_check_passes(self) -> None:
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        contract = TaskContract(
            task_understanding="Write out.json with a result key.",
            deliverables=(ContractDeliverable(path="/app/out.json", description="output"),),
            output_schemas=(ContractSchema(target="/app/out.json", required_keys=("result",)),),
            capabilities=("shell", "filesystem"),
        )
        # Discover the exact generated check commands and register handlers.
        checks = contract_to_eval_index(contract, envmap).checks
        exist_cmd = next(c.command for c in checks if c.command.startswith("test -e"))
        schema_cmd = next(c.command for c in checks if "json.load" in c.command)

        executor.register_command(
            exist_cmd,
            lambda ex, cmd: CommandResult(
                command=cmd, exit_code=0 if "out.json" in ex.files else 1,
            ),
        )
        executor.register_command(
            schema_cmd,
            lambda ex, cmd: CommandResult(command=cmd, exit_code=0, stdout="ok"),
        )

        write_action = _action(
            "write_file",
            {"path": "out.json", "content": '{"result": 1}'},
            action_id="a-write-json",
            capability_id="filesystem",
        )
        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=True,
                allow_evidence_fallback=False,
                require_all_obligations=True,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
        )
        hooks = FakeHooks(ir, [_act_turn(write_action)])
        kernel = AetherNextKernel(max_steps=10, contract_architect=_FakeContractArchitect(contract))
        result = kernel.run(envmap, executor, hooks)

        assert result.status == "completed", (
            f"Expected completed, got {result.status}. Blockers: {result.blockers}"
        )
        assert any(r.kind == "auto_submit" for r in result.receipts), (
            f"Expected auto_submit receipt. Kinds: {[r.kind for r in result.receipts]}"
        )
        # The schema check must have actually executed.
        assert any(
            r.kind == "check_result" and "json.load" in str(r.payload.get("command", ""))
            for r in result.receipts
        ), "Expected the generated schema check to be executed"

    def test_auto_submit_csv_schema_uses_header_validation(self) -> None:
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        contract = TaskContract(
            task_understanding="Write summary.csv with date and count columns.",
            deliverables=(ContractDeliverable(path="/app/summary.csv", description="output"),),
            output_schemas=(
                ContractSchema(target="/app/summary.csv", required_keys=("date", "count")),
            ),
            capabilities=("shell", "filesystem"),
        )
        checks = contract_to_eval_index(contract, envmap).checks
        exist_cmd = next(c.command for c in checks if c.command.startswith("test -e"))
        schema_cmd = next(c.command for c in checks if c.label == "schema:summary.csv")

        assert "csv.DictReader" in schema_cmd
        assert "json.load" not in schema_cmd

        executor.register_command(
            exist_cmd,
            lambda ex, cmd: CommandResult(
                command=cmd, exit_code=0 if "summary.csv" in ex.files else 1,
            ),
        )
        executor.register_command(
            schema_cmd,
            lambda ex, cmd: CommandResult(command=cmd, exit_code=0, stdout="ok"),
        )

        write_action = _action(
            "write_file",
            {"path": "summary.csv", "content": "date,count\n2026-06-28,3\n"},
            action_id="a-write-csv",
            capability_id="filesystem",
        )
        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=True,
                allow_evidence_fallback=False,
                require_all_obligations=True,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
        )
        hooks = FakeHooks(ir, [_act_turn(write_action)])
        kernel = AetherNextKernel(max_steps=10, contract_architect=_FakeContractArchitect(contract))
        result = kernel.run(envmap, executor, hooks)

        assert result.status == "completed", (
            f"Expected completed, got {result.status}. Blockers: {result.blockers}"
        )
        assert any(r.kind == "schema_validation" and r.success for r in result.receipts)


class TestNoAutoSubmitWhenSchemaCheckFails:
    """The deliverable exists but FAILS its output-schema check.  Because a
    contract check fails, auto-submit must NOT fire and the run stays
    incomplete (no fake green)."""

    def test_no_auto_submit_when_schema_check_fails(self) -> None:
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        contract = TaskContract(
            task_understanding="Write out.json with a result key.",
            deliverables=(ContractDeliverable(path="/app/out.json", description="output"),),
            output_schemas=(ContractSchema(target="/app/out.json", required_keys=("result",)),),
            capabilities=("shell", "filesystem"),
        )
        checks = contract_to_eval_index(contract, envmap).checks
        exist_cmd = next(c.command for c in checks if c.command.startswith("test -e"))
        schema_cmd = next(c.command for c in checks if "json.load" in c.command)

        # Existence passes, but the schema check FAILS (missing key).
        executor.register_command(
            exist_cmd,
            lambda ex, cmd: CommandResult(
                command=cmd, exit_code=0 if "out.json" in ex.files else 1,
            ),
        )
        executor.register_command(
            schema_cmd,
            lambda ex, cmd: CommandResult(command=cmd, exit_code=1, stderr="KeyError"),
        )

        write_action = _action(
            "write_file",
            {"path": "out.json", "content": '{"wrong": 1}'},
            action_id="a-write-bad-json",
            capability_id="filesystem",
        )
        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=True,
                allow_evidence_fallback=False,
                require_all_obligations=True,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
        )

        class NeverSubmitHooks(FakeHooks):
            def solve(self, messages: list[dict[str, str]], compiled: CompiledRuntime) -> SolverTurn:
                self.solve_call_count += 1
                if self.solve_call_count == 1:
                    return _act_turn(write_action)
                return SolverTurn(
                    kind="act",
                    summary=f"busy step {self.solve_call_count}",
                    actions=(ActionRequest(
                        action_id=f"a-read-{self.solve_call_count}",
                        kind="read_file", capability_id="filesystem",
                        arguments={"path": "out.json"},
                        intent="read", expected_observation="ok", if_fail_next="retry",
                    ),),
                )

        hooks = NeverSubmitHooks(ir, [])
        kernel = AetherNextKernel(max_steps=5, contract_architect=_FakeContractArchitect(contract))
        result = kernel.run(envmap, executor, hooks)

        assert result.status == "incomplete", (
            f"Expected incomplete (schema check fails), got {result.status}"
        )
        assert not [r for r in result.receipts if r.kind == "auto_submit"], (
            "Expected no auto_submit receipt when the schema check fails"
        )


class TestNoAutoSubmitWhenCheapCheckFails:
    """Planned checks include a cheap check that FAILS.  The cheap-checks
    gate never triggers, so _run_submit_turn is never called and the run
    stays incomplete."""

    def test_no_auto_submit_when_a_check_fails(self) -> None:
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        # The existence check for out.txt always FAILS.
        def failing_handler(ex: MemoryExecutor, cmd: str) -> CommandResult:
            return CommandResult(command=cmd, exit_code=1, stderr="not found")

        executor.register_command("test -e out.txt", failing_handler)

        contract = TaskContract(
            task_understanding="Create out.txt.",
            deliverables=(
                ContractDeliverable(path="/app/out.txt", description="output"),
            ),
            capabilities=("shell", "filesystem"),
        )

        write_action = _action(
            "write_file",
            {"path": "other.txt", "content": "not the right file"},
            action_id="a-write-other",
            capability_id="filesystem",
        )
        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=True,
                allow_evidence_fallback=False,
                require_all_obligations=True,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
        )

        class NeverSubmitHooks(FakeHooks):
            def solve(self, messages: list[dict[str, str]], compiled: CompiledRuntime) -> SolverTurn:
                self.solve_call_count += 1
                if self.solve_call_count == 1:
                    return _act_turn(write_action)
                return SolverTurn(
                    kind="act",
                    summary=f"busy step {self.solve_call_count}",
                    actions=(ActionRequest(
                        action_id=f"a-write-{self.solve_call_count}",
                        kind="write_file", capability_id="filesystem",
                        arguments={"path": "other.txt", "content": f"v{self.solve_call_count}"},
                        intent="write", expected_observation="ok", if_fail_next="retry",
                    ),),
                )

        hooks = NeverSubmitHooks(ir, [])
        kernel = AetherNextKernel(max_steps=5, contract_architect=_FakeContractArchitect(contract))
        result = kernel.run(envmap, executor, hooks)

        assert result.status == "incomplete", (
            f"Expected incomplete (check fails), got {result.status}"
        )

        auto_receipts = [r for r in result.receipts if r.kind == "auto_submit"]
        assert not auto_receipts, (
            f"Expected no auto_submit receipt, found: {[r.receipt_id for r in auto_receipts]}"
        )

        assert result.step == 5


class TestNoAutoSubmitInBaseline:
    """No planned checks -> no auto_submit receipts ever; behavior unchanged."""

    def test_no_auto_submit_in_baseline(self) -> None:
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        write_action = _action(
            "write_file",
            {"path": "output.txt", "content": "data"},
            action_id="a-write-baseline",
            capability_id="filesystem",
        )

        # No contract architect, no check_plan -> baseline path.
        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=False,
                require_all_obligations=False,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
        )
        hooks = FakeHooks(ir, [_act_turn(write_action), _submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        result = kernel.run(envmap, executor, hooks)

        # No auto_submit receipts.
        auto_receipts = [r for r in result.receipts if r.kind == "auto_submit"]
        assert not auto_receipts, (
            f"Expected no auto_submit receipt in baseline, found: "
            f"{[r.receipt_id for r in auto_receipts]}"
        )

        # Run should still complete normally (via the submit_outcome turn).
        assert result.status == "completed"
