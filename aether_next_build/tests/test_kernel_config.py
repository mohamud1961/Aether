"""Tests for aether_next.kernel_config.resolve_runtime."""
from __future__ import annotations

import json
from typing import Any, Mapping

import pytest

from aether_next.compiler import CapabilityRegistry, ConfigCompiler
from aether_next.kernel_config import ResolvedRuntime, resolve_runtime
from aether_next.runtime_ir import (
    CapabilityDescriptor,
    CompletionPolicy,
    CompiledRuntime,
    EnvMap,
    RuntimeConfigIR,
    SolverTurn,
)
from aether_next.task_contract import (
    ContractDeliverable,
    ContractThreshold,
    TaskContract,
)
from aether_next.workbench_config import HarnessConfigIR, parse_harness_config_ir


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
) -> RuntimeConfigIR:
    return RuntimeConfigIR(
        architect_summary="Test summary.",
        solver_identity_prompt="You are a solver.",
        selected_capabilities=selected_capabilities,
        inspection_plan=("inspect workspace",),
        proof_plan=("verify output",),
    )


class _FakeHooks:
    """Minimal hooks for resolve_runtime tests."""

    def __init__(self, ir: RuntimeConfigIR) -> None:
        self._ir = ir

    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        return self._ir


class _FakeContractArchitect:
    """Stub contract architect returning a predefined contract or failure."""

    def __init__(
        self,
        contract: TaskContract | None,
        errors: list[str] | None = None,
    ) -> None:
        self._contract = contract
        self._errors = errors or []

    def extract(
        self,
        request: Mapping[str, Any],
        *,
        workspace_root: str = "/app",
    ) -> tuple[TaskContract | None, list[str]]:
        return self._contract, self._errors


class _FakeWorkbenchArchitect:
    """Stub workbench architect returning a predefined HarnessConfigIR or failure."""

    def __init__(
        self,
        config: HarnessConfigIR | None,
        errors: list[str] | None = None,
    ) -> None:
        self._config = config
        self._errors = errors or []

    def configure(self, request: Mapping[str, Any]) -> tuple[HarnessConfigIR | None, list[str]]:
        return self._config, self._errors


def _workbench_config_json(**overrides: Any) -> str:
    base = {
        "schema_version": "harness_config.v1",
        "task_understanding": "Create the requested output.",
        "success_definition": "The output exists and satisfies visible checks.",
        "solver_system_prompt": {
            "role": "Task-specific careful solver",
            "workflow": ["inspect inputs", "write output", "verify", "submit"],
            "self_verification": ["run configured checks before submitting"],
            "memory_use": ["query_memory before repeating reads or checks"],
        },
        "verifier_system_prompt": {
            "role": "Read-only current-state verifier for configured output",
            "success_criteria": ["output exists and satisfies visible checks"],
            "required_evidence": ["current output state or check evidence supports completion"],
            "false_positive_traps": ["existence alone can be a false positive"],
            "verdict_guidance": ["completed requires current evidence"],
            "feedback_guidance": ["name the missing evidence or broken artifact"],
        },
        "evidence_requirements": ["output exists in the current workspace", "visible check evidence supports completion"],
        "false_positive_risks": ["existence alone can be a false positive"],
        "minimum_completion_evidence": ["current output state or check evidence"],
        "tool_policy": {"enabled_tools": ["read_file", "write_file", "query_memory"]},
        "context_policy": {"mode": "failure_focused", "always_include": ["pending_checks"]},
        "model_verifier_policy": {"enabled": True},
    }
    base.update(overrides)
    return json.dumps(base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBaselineResolveMatchesCurrent:
    def test_baseline_resolve_compiles(self) -> None:
        """resolve_runtime with contract_architect=None returns a compiled
        runtime with objective_graph from analyze_envmap and contract=None."""
        envmap = _make_envmap()
        ir = _make_ir()
        hooks = _FakeHooks(ir)
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))

        resolved = resolve_runtime(envmap, compiler, hooks)

        assert resolved.contract is None
        assert resolved.compiled is not None
        assert resolved.config_invalid_blockers == ()
        assert len(resolved.objective_graph.obligations) > 0
        assert resolved.runtime_ir is not None

    def test_baseline_architect_parse_failure_is_config_invalid_not_safe_default(self) -> None:
        class RaisingHooks(_FakeHooks):
            def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
                raise RuntimeError("not json")

        envmap = _make_envmap()
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))

        resolved = resolve_runtime(envmap, compiler, RaisingHooks(_make_ir()))

        assert resolved.compiled is None
        assert resolved.config_invalid_blockers
        assert "architect_config_parse_failed" in resolved.config_invalid_blockers
        assert "safe default" not in resolved.runtime_ir.architect_summary
        assert resolved.runtime_ir.solver_identity_prompt == ""
        assert resolved.runtime_ir.selected_capabilities == ()


class TestContractResolvePopulatesObjectiveGraph:
    def test_contract_populates_deliverables_and_checks(self) -> None:
        """A contract architect returning a TaskContract with a deliverable
        and a file_size threshold produces a resolved runtime with those
        structures in the objective graph and eval index."""
        envmap = _make_envmap()
        contract = TaskContract(
            task_understanding="Create output file.",
            deliverables=(
                ContractDeliverable(path="/app/out.txt", description="output"),
            ),
            thresholds=(
                ContractThreshold(
                    name="output_size",
                    comparator="<",
                    target=10.0,
                    unit="MB",
                    source="file_size_bytes:/app/out.txt",
                ),
            ),
            capabilities=("shell", "filesystem"),
        )
        ca = _FakeContractArchitect(contract)
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))

        resolved = resolve_runtime(
            envmap, compiler, _FakeHooks(_make_ir()),
            contract_architect=ca,
        )

        assert resolved.contract is not None
        assert resolved.compiled is not None
        deliverable_paths = [d.path for d in resolved.objective_graph.deliverables]
        assert "out.txt" in deliverable_paths

        # Eval index should have a file existence check.
        check_commands = [c.command for c in resolved.eval_index.checks]
        assert any("test -e out.txt" in cmd for cmd in check_commands), (
            f"Expected existence check, got: {check_commands}"
        )

        # Compiled check_plan_ids should be non-empty.
        assert resolved.compiled.check_plan_ids


class TestContractExtractionFailureFallsBack:
    def test_extraction_failure_uses_baseline(self) -> None:
        """A contract architect that returns (None, errors) falls back to
        the baseline path: contract is None and the run still compiles."""
        envmap = _make_envmap()
        ca = _FakeContractArchitect(None, errors=["boom"])
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))

        resolved = resolve_runtime(
            envmap, compiler, _FakeHooks(_make_ir()),
            contract_architect=ca,
        )

        assert resolved.contract is None
        assert resolved.compiled is not None
        assert resolved.config_invalid_blockers == ()


class TestWorkbenchResolve:
    def test_workbench_architect_config_compiles_to_runtime(self) -> None:
        envmap = _make_envmap()
        config = parse_harness_config_ir(_workbench_config_json())
        wa = _FakeWorkbenchArchitect(config)
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))

        resolved = resolve_runtime(
            envmap, compiler, _FakeHooks(_make_ir()),
            workbench_architect=wa,
        )

        assert resolved.workbench_config is config
        assert resolved.contract is None
        assert resolved.compiled is not None
        assert resolved.runtime_ir.context_policy.mode == "failure_focused"
        assert "Task-specific careful solver" in resolved.runtime_ir.solver_identity_prompt
        sections = dict(resolved.compiled.stable_prefix_sections)
        assert "Task-specific careful solver" in sections["solver_identity"]

        tools = dict(resolved.compiled.action_schema)
        assert "read_file" in tools
        assert "write_file" in tools
        assert "query_memory" in tools
        assert "run_command" in tools
        assert "register_candidate" not in tools
        assert "run_experiment" not in tools
        assert (
            resolved.compiled.config_realization["tools_visible_to_solver"]
            == resolved.compiled.config_realization["tools_runtime_allowed"]
        )
        assert resolved.compiled.config_realization["tool_policy_mode"] == "stable_core"
        assert resolved.compiled.config_realization["architect_tool_selection_applied"] is False

    def test_workbench_architect_failure_is_config_invalid(self) -> None:
        envmap = _make_envmap()
        wa = _FakeWorkbenchArchitect(None, errors=["bad config"])
        compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))

        resolved = resolve_runtime(
            envmap, compiler, _FakeHooks(_make_ir()),
            workbench_architect=wa,
        )

        assert resolved.workbench_config is None
        assert resolved.compiled is None
        assert resolved.fallback_codes
        assert "workbench_architect_configure_failed" in resolved.fallback_codes
        assert "bad config" in resolved.fallback_codes
        assert resolved.config_invalid_blockers == resolved.fallback_codes
        assert "safe default" not in resolved.runtime_ir.architect_summary
        assert "invalid config" in resolved.runtime_ir.architect_summary
        assert resolved.runtime_ir.solver_identity_prompt == ""
        assert resolved.runtime_ir.selected_capabilities == ()
