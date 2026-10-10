from __future__ import annotations

from aether.execution import MemoryExecutor
from aether.model_hooks import ModelHooks, ModelOutputError
from aether.persistent_runtime import build_persistent_runtime
from aether.providers.chat_model import ChatContextCapacityError
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.thin_context import (
    project_thin_context,
    thin_action_schema,
    thin_prefix_messages,
)
from aether.thin_loop import ThinLoopConfig, run_thin_loop


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Read input.txt and report what it contains.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file"),
            )
        },
    )


def test_thin_context_removes_only_declared_completion_scaffolding() -> None:
    packet = {
        "raw_task_authority": {"task": "keep"},
        "current_state": {"generation": 4},
        "open_completion_findings": ["remove"],
        "submission_coherence": {"remove": True},
        "submit_reentry_gate": {"remove": True},
        "linked_history": {
            "latest_result": {"kind": "read_file", "content": "keep"},
            "active_completion_findings": ["remove"],
            "submission_recovery_directive": "remove",
            "repair_instruction": "remove",
        },
    }
    thin = project_thin_context(packet)
    assert thin["raw_task_authority"] == {"task": "keep"}
    assert thin["current_state"] == {"generation": 4}
    assert "open_completion_findings" not in thin
    assert "submission_coherence" not in thin
    assert "submit_reentry_gate" not in thin
    assert thin["linked_history"] == {
        "latest_result": {"kind": "read_file", "content": "keep"}
    }


def test_thin_prefix_preserves_raw_task_and_tool_semantics_but_not_completion_controls() -> None:
    resolved = build_persistent_runtime(_env())
    assert resolved.compiled is not None and not resolved.config_invalid_blockers
    compiled = resolved.compiled
    incumbent = [message["content"].splitlines()[0] for message in compiled.prefix_messages()]
    thin = [message["content"].splitlines()[0] for message in thin_prefix_messages(compiled)]
    assert "[raw_user_task]" in thin
    assert "[raw_task_binding]" in thin
    assert "[tool_semantics]" in thin
    assert "[completion_controls]" in incumbent
    assert "[completion_controls]" not in thin
    assert thin_action_schema(compiled) == tuple(compiled.action_schema)


def test_thin_loop_has_two_bounded_protocol_corrections_and_no_semantic_reviewer_call() -> None:
    class Hooks:
        def __init__(self) -> None:
            self.solve_calls = 0
            self.verify_calls = 0

        def solve(self, messages, compiled):
            del messages, compiled
            self.solve_calls += 1
            raise ModelOutputError("invalid response envelope")

        def verify(self, *args, **kwargs):
            del args, kwargs
            self.verify_calls += 1
            raise AssertionError("Thin must not invoke semantic review")

    hooks = Hooks()
    result = run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "x"}),
        hooks,
        config=ThinLoopConfig(max_steps=1, max_solver_turns=3),
    )
    assert result.status == "solver_protocol_failure"
    assert hooks.solve_calls == 3
    assert hooks.verify_calls == 0
    assert result.accounting["solver_provider_turns"] == 3
    assert result.accounting["solver_protocol_correction_calls"] == 2
    assert not any(receipt.kind == "model_verifier_result" for receipt in result.receipts)
    assert not any(receipt.state_change for receipt in result.receipts)


def test_capacity_error_from_model_hooks_is_harness_invalid_thin_result() -> None:
    def capacity_limited_solver(messages, *, max_output_tokens=None):
        del messages, max_output_tokens
        raise ChatContextCapacityError(
            "harness_context_capacity: chat request exceeds declared provider capacity"
        )

    hooks = ModelHooks(
        capacity_limited_solver,
        lambda _messages, **_kwargs: "{}",
        run_id="run-capacity-classification",
        task_id="task-capacity-classification",
    )
    result = run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "x"}),
        hooks,
        config=ThinLoopConfig(max_steps=1, max_solver_turns=1),
    )

    assert result.status == "harness_context_capacity"
    assert result.blockers == ("harness_context_capacity",)
    failure = next(receipt for receipt in result.receipts if receipt.kind == "thin_protocol_failure")
    assert failure.failure_class == "harness_context_capacity"


def test_capacity_error_during_protocol_correction_is_harness_invalid() -> None:
    class InvalidThenCapacitySolver:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, messages, *, max_output_tokens=None):
            del messages, max_output_tokens
            self.calls += 1
            if self.calls == 1:
                return "not a JSON solver response"
            raise ChatContextCapacityError(
                "harness_context_capacity: correction request exceeds route capacity"
            )

    solver = InvalidThenCapacitySolver()
    hooks = ModelHooks(
        solver,
        lambda _messages, **_kwargs: "{}",
        run_id="run-capacity-correction",
        task_id="task-capacity-correction",
    )
    result = run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "x"}),
        hooks,
        config=ThinLoopConfig(max_steps=1, max_solver_turns=2),
    )

    assert solver.calls == 2
    assert result.status == "harness_context_capacity"
    assert result.blockers == ("harness_context_capacity",)
    failure = next(
        receipt for receipt in result.receipts
        if receipt.kind == "thin_protocol_correction_provider_failure"
    )
    assert failure.failure_class == "harness_context_capacity"


def test_thin_protocol_correction_budget_is_scoped_to_each_step() -> None:
    from aether.runtime_ir import ActionRequest, SolverTurn

    class Hooks:
        def __init__(self) -> None:
            self.calls = 0

        def solve(self, messages, compiled):
            del messages, compiled
            self.calls += 1
            if self.calls in {1, 3}:
                raise ModelOutputError(f"invalid envelope at call {self.calls}")
            index = 1 if self.calls == 2 else 2
            return SolverTurn(
                kind="act",
                summary=f"read input {index}",
                actions=(ActionRequest(
                    action_id=f"read-{index}",
                    kind="read_file",
                    capability_id="filesystem",
                    arguments={"path": f"input-{index}.txt"},
                    intent="observe current bytes",
                    expected_observation="file contents",
                    if_fail_next="report the read failure",
                ),),
            )

    hooks = Hooks()
    result = run_thin_loop(
        _env(),
        MemoryExecutor(
            workspace_root="/app",
            files={"input-1.txt": "one", "input-2.txt": "two"},
        ),
        hooks,
        config=ThinLoopConfig(max_steps=2, max_solver_turns=4),
    )
    assert result.status == "step_budget_exhausted"
    assert hooks.calls == 4
    assert result.accounting["solver_protocol_correction_calls"] == 2
    assert result.accounting["solver_provider_turns"] == 4
    assert len([r for r in result.receipts if r.kind == "thin_protocol_correction_result"]) == 2


def test_harbor_thin_selector_is_default_off_and_identity_bound(monkeypatch) -> None:
    from aether import harbor_runtime as hr
    monkeypatch.delenv(hr.SOLVER_LOOP_ENV, raising=False)
    assert hr.selected_solver_loop(hr.build_selected_frontier_models) == "incumbent"
    monkeypatch.setenv(hr.SOLVER_LOOP_ENV, "thin")
    assert hr.selected_solver_loop(hr.build_selected_frontier_models) == "thin"

    class Env:
        task_metadata = {}
        def digest(self): return "env-digest"
    class Context:
        metadata = {}
        context_id = "ctx"

    identity = hr._runtime_identity(Context(), Env(), model_factory=hr.build_selected_frontier_models)
    assert identity["research_solver_loop"] == "thin"
    assert identity["research_solver_loop_authority"] == hr.SOLVER_LOOP_ENV


def test_harbor_thin_selector_rejects_unknown_arm(monkeypatch) -> None:
    from aether import harbor_runtime as hr
    import pytest
    monkeypatch.setenv(hr.SOLVER_LOOP_ENV, "mystery")
    with pytest.raises(RuntimeError, match=hr.SOLVER_LOOP_ENV):
        hr.selected_solver_loop(hr.build_selected_frontier_models)


def test_thin_route_preflight_does_not_require_verifier_isolation() -> None:
    from types import SimpleNamespace
    from aether.route_preflight import preflight_proof_routes

    compiled = SimpleNamespace(
        proof_contract=({
            "clause_id": "proof:thin-solver-route",
            "verifier_route": "overlay_run_command:validate-output",
        },),
        eval_index=SimpleNamespace(get=lambda _key: None),
    )
    executor = MemoryExecutor(workspace_root="/app")
    rows, thin_issues = preflight_proof_routes(
        compiled, executor, _env(), require_verifier=False,
    )
    assert rows[0].solver_available is True
    assert thin_issues == ()

    _rows, incumbent_issues = preflight_proof_routes(
        compiled, executor, _env(), require_verifier=True,
    )
    assert {issue.code for issue in incumbent_issues} == {
        "verifier_route_preflight_failed",
        "solver_verifier_route_parity_failed",
    }



def test_thin_failed_observation_treatment_blocks_undispositioned_finish() -> None:
    from aether.failed_observation_disposition import CURRENT_CANDIDATE_V1
    from aether.runtime_ir import ActionRequest, SolverTurn

    class Hooks:
        def __init__(self) -> None:
            self.calls = 0
            self.disposition_modes: list[str] = []

        def configure_completion_disposition_mode(self, mode: str) -> None:
            self.disposition_modes.append(mode)

        def solve(self, messages, compiled):
            del messages, compiled
            self.calls += 1
            if self.calls == 1:
                return SolverTurn(
                    kind="act",
                    summary="inspect missing evidence",
                    actions=(ActionRequest(
                        action_id="read-missing",
                        kind="read_file",
                        capability_id="filesystem",
                        arguments={"path": "missing.txt"},
                        intent="observe the requested file",
                        expected_observation="the file is readable",
                        if_fail_next="account for the failed observation before completion",
                    ),),
                )
            return SolverTurn(
                kind="finish_outcome",
                summary="finish without accounting for failure",
                claim="the task is complete",
                evidence_refs=("evidence:0000000000000000",),
            )

    hooks = Hooks()
    result = run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "x"}),
        hooks,
        config=ThinLoopConfig(
            max_steps=2,
            failed_observation_disposition_mode=CURRENT_CANDIDATE_V1,
        ),
    )
    assert result.status == "step_budget_exhausted"
    blocks = [
        receipt for receipt in result.receipts
        if receipt.kind == "thin_failed_observation_disposition_block"
    ]
    assert len(blocks) == 1
    assert blocks[0].failure_class == "failed_observation_disposition_incomplete"
    assert blocks[0].payload["reason"] == "open_finding_not_dispositioned"
    assert len(blocks[0].payload["required_finding_ids"]) == 1
    assert hooks.disposition_modes == ["control", "completion_disposition_v1"]
    assert not any(receipt.kind == "model_verifier_result" for receipt in result.receipts)


def _context_packet_from_messages(messages):
    import json
    marker = "[context_packet]\n"
    for message in messages:
        content = str(message.get("content", ""))
        if content.startswith(marker):
            return json.loads(content[len(marker):])
    raise AssertionError("context packet missing")


def _one_read_turn():
    from aether.runtime_ir import ActionRequest, SolverTurn
    return SolverTurn(
        kind="act",
        summary="read current input",
        actions=(ActionRequest(
            action_id="read-input",
            kind="read_file",
            capability_id="filesystem",
            arguments={"path": "input.txt"},
            intent="observe current bytes",
            expected_observation="file contents",
            if_fail_next="inspect the read failure",
        ),),
    )


def test_hygiene_lean_view_reaches_model_and_keeps_raw_task() -> None:
    class CaptureHooks:
        messages = None

        def solve(self, messages, compiled):
            del compiled
            self.messages = messages
            return _one_read_turn()

    hooks = CaptureHooks()
    result = run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt": "x"}),
        hooks,
        config=ThinLoopConfig(
            max_steps=1,
            max_solver_turns=1,
            solver_model_view_mode="hygiene_lean_v1",
            runtime_identity={
                "task_id": "t",
                "run_id": "exp-arm-1",
                "arm_id": "arm",
                "experiment_id": "E",
            },
        ),
    )

    assert result.status == "step_budget_exhausted"
    assert hooks.messages is not None
    text = "\n".join(message["content"] for message in hooks.messages)
    assert "[raw_user_task]" in text
    assert "[raw_task_binding]" not in text
    for token in ('"arm_id"', '"experiment_id"', '"run_id"', "external-grading"):
        assert token not in text
    packet = _context_packet_from_messages(hooks.messages)
    assert "runtime_identity" not in packet
    assert "latest_primary_result" in packet


def test_empty_flat_semantic_advice_is_not_model_visible() -> None:
    class EmptyFlat:
        def __call__(self, **_kwargs):
            return {
                "schema": "aether.semantic_advice.v1",
                "authority": "advisory_only",
                "status": "no_solver_conditions",
                "items": [],
                "calls_total": 0,
            }

    class Hooks:
        def __init__(self):
            self.messages = None
        def solve(self, messages, compiled):
            del compiled
            self.messages = messages
            return _one_read_turn()

    hooks=Hooks()
    result=run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt":"x"}),
        hooks,
        config=ThinLoopConfig(max_steps=1, max_solver_turns=1, semantic_assistance=EmptyFlat()),
    )
    assert result.status == "step_budget_exhausted"
    packet=_context_packet_from_messages(hooks.messages)
    assert "semantic_advice" not in packet


def test_graph_projection_remains_model_visible_without_judge_items() -> None:
    class GraphOnly:
        def __call__(self, **_kwargs):
            return {
                "schema": "aether.semantic_graph_advice.v0",
                "authority": "advisory_only",
                "status": "no_solver_conditions",
                "graph": {"schema":"aether.evidence_graph_summary.v0","items":[]},
                "items": [],
                "calls_total": 0,
            }

    class Hooks:
        def __init__(self):
            self.messages = None
        def solve(self, messages, compiled):
            del compiled
            self.messages = messages
            return _one_read_turn()

    hooks=Hooks()
    result=run_thin_loop(
        _env(),
        MemoryExecutor(workspace_root="/app", files={"input.txt":"x"}),
        hooks,
        config=ThinLoopConfig(max_steps=1, max_solver_turns=1, semantic_assistance=GraphOnly()),
    )
    assert result.status == "step_budget_exhausted"
    packet=_context_packet_from_messages(hooks.messages)
    assert packet["semantic_advice"]["schema"] == "aether.semantic_graph_advice.v0"
    assert packet["semantic_advice"]["items"] == []
