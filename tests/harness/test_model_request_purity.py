from __future__ import annotations

import copy
import json

import pytest

from aether.execution import MemoryExecutor
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop


FORBIDDEN = (
    '"arm_id"',
    '"m1_arm_id"',
    '"experiment_id"',
    '"campaign_id"',
    '"m1_rep"',
    '"run_id"',
    '"primary_agent_id"',
    '"source_commit"',
    "source_custody_gap",
    "external-grading",
    "treatment",
    "Frontier",
    "[raw_task_binding]",
)


class _CaptureHooks:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] | None = None

    def solve(self, messages, _compiled):
        self.messages = copy.deepcopy(messages)
        return SolverTurn(
            kind="act",
            summary="read the requested input",
            actions=(ActionRequest(
                action_id="read-input",
                kind="read_file",
                capability_id="filesystem",
                arguments={"path": "input.txt"},
                intent="observe the requested input",
                expected_observation="the current file contents",
                if_fail_next="inspect the read result",
            ),),
        )


def _thin_messages(model_view_mode: str, reasoning_mode: str) -> list[dict[str, str]]:
    hooks = _CaptureHooks()
    envmap = EnvMap(
        task_prompt="Read input.txt and report what it contains.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file"),
            ),
        },
    )
    result = run_thin_loop(
        envmap,
        MemoryExecutor(workspace_root="/app", files={"input.txt": "known input"}),
        hooks,
        config=ThinLoopConfig(
            max_steps=1,
            max_solver_turns=1,
            solver_reasoning_mode=reasoning_mode,
            solver_model_view_mode=model_view_mode,
            runtime_identity={
                "task_id": "task-x",
                "run_id": "exp-arm-123",
                "arm_id": "arm-x",
                "m1_arm_id": "m1-arm-x",
                "experiment_id": "experiment-x",
                "campaign_id": "campaign-x",
                "m1_rep": "rep-x",
                "primary_agent_id": "agent-x",
                "source_commit": "commit-x",
                "display_name": "Frontier",
            },
        ),
    )
    assert result.status != "config_invalid"
    assert hooks.messages is not None
    return hooks.messages


def _serialized_solver_messages(messages: list[dict[str, str]]) -> str:
    solver_messages = [
        message for message in messages
        if not str(message.get("content") or "").startswith("[raw_user_task]\n")
    ]
    return json.dumps(solver_messages, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@pytest.mark.parametrize("reasoning_mode", ["vertical_slice_v1", "discriminating_experiment_v1"])
@pytest.mark.parametrize("model_view_mode", ["hygiene_v1", "hygiene_lean_v1"])
def test_hygiene_literal_thin_request_contains_no_harness_or_experiment_labels(
    reasoning_mode: str,
    model_view_mode: str,
) -> None:
    # Establish that the same captured Thin request boundary is a known-bad
    # control before checking the serialization-only hygiene projection.
    control_messages = _thin_messages("control", reasoning_mode)
    control_text = _serialized_solver_messages(control_messages)
    assert any(token in control_text for token in FORBIDDEN)
    assert "exp-arm-123" in control_text
    assert "arm-x" in control_text

    hygiene_messages = _thin_messages(model_view_mode, reasoning_mode)
    assert any(
        str(message.get("content") or "").startswith("[raw_user_task]\n")
        for message in hygiene_messages
    )
    hygiene_text = _serialized_solver_messages(hygiene_messages)
    hits = [token for token in FORBIDDEN if token in hygiene_text]
    assert hits == []
    assert "exp-arm-123" not in hygiene_text
    assert "arm-x" not in hygiene_text
    # The anti-cheating clause is task-facing guidance, not a treatment label.
    assert "hidden ground truth" in hygiene_text
