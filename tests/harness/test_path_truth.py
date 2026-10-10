import pytest

from aether.kernel_dispatch import _resolved_display_path
from aether.runtime_ir import normalize_relpath


@pytest.mark.parametrize("root,path,expected", [
    ("/app/workspace", "/app/workspace/a.py", "a.py"),
    ("/app", "/app/x", "x"),
    ("", "/app/x", "x"),
    ("/tmp/abc", "/app/x", "x"),
    ("/app/workspace", "a.py", "a.py"),
])
def test_alias_rules_preserved(root, path, expected):
    assert normalize_relpath(path, root) == expected


def test_app_path_outside_workspace_is_rejected_not_rebased():
    with pytest.raises(ValueError, match="outside declared workspace"):
        normalize_relpath("/app/instruction.md", "/app/workspace")


def test_display_path_is_absolute():
    assert _resolved_display_path("instruction.md", "/app/workspace") == "/app/workspace/instruction.md"
    assert _resolved_display_path(".", "/app/workspace") == "/app/workspace"
    assert _resolved_display_path("x", "/") == "/x"


def test_thin_loop_reports_wrong_world_path_before_next_decision():
    import json

    from aether.execution import MemoryExecutor
    from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn
    from aether.thin_loop import ThinLoopConfig, run_thin_loop

    env = EnvMap(
        task_prompt="Read a file in the workspace.",
        workspace_root="/app/workspace",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file",),
            )
        },
    )

    class Hooks:
        def __init__(self):
            self.requests = []

        def solve(self, messages, compiled):
            self.requests.append(messages)
            path = "/app/instruction.md" if len(self.requests) == 1 else "missing.txt"
            return SolverTurn(
                kind="act",
                summary="read the requested file",
                actions=(ActionRequest(
                    action_id=f"read-{len(self.requests)}",
                    kind="read_file",
                    capability_id="filesystem",
                    arguments={"path": path},
                    intent="read the requested file",
                    expected_observation="file contents",
                    if_fail_next="read the workspace file",
                ),),
            )

    hooks = Hooks()
    result = run_thin_loop(
        env,
        MemoryExecutor(workspace_root="/app/workspace", files={}),
        hooks,
        config=ThinLoopConfig(max_steps=2, max_solver_turns=2),
    )
    assert len(hooks.requests) == 2
    packet = next(
        json.loads(message["content"][len("[context_packet]\n"):])
        for message in hooks.requests[1]
        if message.get("content", "").startswith("[context_packet]\n")
    )
    receipt = packet["latest_primary_result"]["outcome_receipts"][0]
    assert receipt["success"] is False
    # The current model-view schema exposes the receipt text as
    # ``mechanical_description`` (the blueprint calls it ``summary``).
    description = receipt["mechanical_description"]
    assert "outside declared workspace" in description
    assert "file tools operate only inside /app/workspace" in description
    missing = next(
        receipt for receipt in result.receipts
        if receipt.failure_class == "missing_artifact"
    )
    assert missing.summary == "file not found: /app/workspace/missing.txt"
    assert missing.payload["resolved_path"] == "/app/workspace/missing.txt"
