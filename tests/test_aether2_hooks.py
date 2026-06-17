from __future__ import annotations

import json
import time
from pathlib import Path

from harness.aether2.control.loop import ExecutionContext, run_aether2_loop
from harness.aether2.hooks import HookRegistry, HookResult, PermissionDecision, PermissionDecisionReason
from harness.aether2.runtime.bridge_harbor import TaskSpec
from harness.aether2.runtime.executor import ContainerExecutor
from harness.aether2.runtime.jobs import JobRegistry
from harness.aether2.runtime.model_client import ModelResponse
from harness.aether2.runtime.sessions import SessionRegistry
from harness.aether2.tools.native import dispatch_with_hooks


def _make_execution_context(tmp_path: Path, hook_registry: HookRegistry | None = None) -> tuple[ExecutionContext, Path]:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    state_dir = tmp_path / "state"
    raw_log_dir = tmp_path / "raw_logs"
    executor = ContainerExecutor(workspace_root=workspace_root)
    job_registry = JobRegistry(state_dir, backend=executor.backend, container_path_fn=executor.to_container_path)
    session_registry = SessionRegistry(state_dir, backend=executor.backend)
    ctx = ExecutionContext(
        executor=executor,
        job_registry=job_registry,
        session_registry=session_registry,
        raw_log_dir=raw_log_dir,
        hook_registry=hook_registry,
    )
    return ctx, workspace_root


def _response(text: str = "", tool_calls: tuple[dict, ...] = ()) -> ModelResponse:
    return ModelResponse(
        text=text,
        tool_calls=tool_calls,
        usage={"cached_input_tokens": 0, "fresh_input_tokens": 0},
        status="completed",
        raw_response={},
    )


def _tool_call(name: str, arguments: dict, call_id: str = "call-1") -> dict:
    return {"id": call_id, "type": "function", "name": name, "arguments": json.dumps(arguments)}


def _verify_response() -> ModelResponse:
    payload = {
        "requirements": [
            {
                "requirement": "task complete",
                "verdict": "satisfied",
                "evidence": "checked",
                "evidence_refs": ["checks_results[0]"],
            }
        ],
        "reason_codes": [],
        "summary": "ok",
    }
    return _response(text=json.dumps(payload))


class _ScriptedModelClient:
    def __init__(self, turns: list[ModelResponse]) -> None:
        self.turns = list(turns)

    def call(self, messages, tools, *, cache_prefix_len):  # noqa: ANN001
        tool_names = {
            tool.get("function", {}).get("name")
            for tool in tools
            if isinstance(tool, dict)
        }
        if tool_names and tool_names.issubset({"run_command", "read_file", "job_status", "session_read"}):
            return _verify_response()
        if self.turns:
            return self.turns.pop(0)
        return _response(text="done")


def _make_task(tmp_path: Path, instruction: str = "write the file") -> TaskSpec:
    task_dir = tmp_path / "task"
    workspace_root = task_dir / "workspace"
    artifacts_dir = task_dir / "artifacts"
    workspace_root.mkdir(parents=True)
    artifacts_dir.mkdir(parents=True)
    return TaskSpec(
        task_id="hook-smoke-task",
        instruction=instruction,
        task_dir=task_dir,
        workspace_root=workspace_root,
        artifacts_dir=artifacts_dir,
    )


def test_dispatch_with_hooks_runs_permission_pre_and_post_hooks_in_order(tmp_path: Path) -> None:
    order: list[str] = []
    registry = HookRegistry()

    def permission_hook(_context):
        order.append("permission")
        return HookResult(note="permission")

    def pre_hook(_context):
        order.append("pre")
        return HookResult(note="pre")

    def post_hook(_context):
        order.append("post")
        return HookResult(note="post")

    registry.register("permission_request", hook_name="permission", callback=permission_hook)
    registry.register("pre_tool_use", hook_name="pre", callback=pre_hook)
    registry.register("post_tool_use", hook_name="post", callback=post_hook)

    ctx, workspace_root = _make_execution_context(tmp_path, hook_registry=registry)
    outcome = dispatch_with_hooks(
        "write_file",
        {"path": "out.txt", "content": "hello"},
        ctx,
        call_id="call-1",
    )

    assert order == ["permission", "pre", "post"]
    assert (workspace_root / "out.txt").read_text(encoding="utf-8") == "hello"
    assert outcome.permission_decision == {
        "behavior": "allow",
        "message": None,
        "reason": {"type": "default", "source": "policy", "hook_name": None, "message": None, "rule_id": None},
        "updated_input": None,
        "metadata": {},
    }
    assert [entry["event"] for entry in outcome.hook_trace] == [
        "permission_request",
        "pre_tool_use",
        "post_tool_use",
    ]


def test_denied_action_is_visible_and_does_not_mutate_workspace(tmp_path: Path) -> None:
    order: list[str] = []
    registry = HookRegistry()

    def permission_hook(_context):
        order.append("permission")
        return HookResult(
            permission_decision=PermissionDecision(
                behavior="deny",
                message="blocked by hook",
                reason=PermissionDecisionReason(type="hook", source="test", hook_name="deny_write"),
            ),
            note="deny",
        )

    def pre_hook(_context):
        order.append("pre")
        return HookResult(note="pre")

    def post_hook(context):
        order.append("post")
        assert context.permission_decision is not None
        assert context.permission_decision.behavior == "deny"
        return HookResult(note="post")

    registry.register("permission_request", hook_name="deny_write", callback=permission_hook)
    registry.register("pre_tool_use", hook_name="pre", callback=pre_hook)
    registry.register("post_tool_use", hook_name="post", callback=post_hook)

    ctx, workspace_root = _make_execution_context(tmp_path, hook_registry=registry)
    outcome = dispatch_with_hooks(
        "write_file",
        {"path": "out.txt", "content": "hello"},
        ctx,
        call_id="call-1",
    )

    assert order == ["permission", "post"]
    assert not (workspace_root / "out.txt").exists()
    assert outcome.envelope.exit_code == 1
    assert outcome.envelope.error is not None
    assert outcome.envelope.error.reason_code == "tool_permission_denied"
    assert outcome.envelope.files_changed == []
    assert "blocked by hook" in outcome.envelope.stderr_head


def test_permission_argument_mutation_is_denied_in_first_port_slice(tmp_path: Path) -> None:
    registry = HookRegistry()
    original_arguments = {"path": "out.txt", "content": "hello"}

    def mutating_permission_hook(context):
        mutated = dict(context.arguments)
        mutated["path"] = "rewritten.txt"
        return HookResult(
            permission_decision=PermissionDecision(
                behavior="allow",
                updated_input=mutated,
                reason=PermissionDecisionReason(type="hook", source="test", hook_name="mutate"),
            ),
            note="mutate",
        )

    registry.register("permission_request", hook_name="mutate", callback=mutating_permission_hook)
    ctx, workspace_root = _make_execution_context(tmp_path, hook_registry=registry)
    outcome = dispatch_with_hooks("write_file", original_arguments, ctx, call_id="call-1")

    assert original_arguments == {"path": "out.txt", "content": "hello"}
    assert not (workspace_root / "out.txt").exists()
    assert not (workspace_root / "rewritten.txt").exists()
    assert outcome.permission_decision is not None
    assert outcome.permission_decision["behavior"] == "deny"
    assert "mutation" in (outcome.permission_decision["message"] or "").lower()


def test_hook_and_permission_exports_are_public() -> None:
    import harness.aether2 as public_api

    assert public_api.HookRegistry is HookRegistry
    assert public_api.PermissionDecision is PermissionDecision
    assert public_api.PermissionManager is not None


def test_loop_records_hook_and_permission_metadata_in_trace_and_receipts(tmp_path: Path) -> None:
    registry = HookRegistry()
    registry.register("permission_request", hook_name="permission", callback=lambda _context: HookResult(note="permission"))
    registry.register("pre_tool_use", hook_name="pre", callback=lambda _context: HookResult(note="pre"))
    registry.register("post_tool_use", hook_name="post", callback=lambda _context: HookResult(note="post"))

    task = _make_task(tmp_path)
    executor = ContainerExecutor(workspace_root=task.workspace_root)
    client = _ScriptedModelClient(
        [
            _response(
                text="write",
                tool_calls=(_tool_call("write_file", {"path": "out.txt", "content": "hello"}),),
            ),
            _response(
                text="done",
                tool_calls=(_tool_call("task_done", {"summary": "done", "checks": ["cat out.txt"]}, call_id="call-2"),),
            ),
        ]
    )

    result = run_aether2_loop(
        task,
        client,
        executor,
        deadline_ts=time.time() + 60,
        hook_registry=registry,
    )

    assert result.finalize_reason == "task_done"
    assert result.tool_invocations[0].permission_decision is not None
    assert result.tool_invocations[0].permission_decision["behavior"] == "allow"
    assert [entry["event"] for entry in result.tool_invocations[0].hook_trace] == [
        "permission_request",
        "pre_tool_use",
        "post_tool_use",
    ]

    receipt_path = task.task_dir / ".aether2" / "host_receipts" / "receipts" / "0001_action_write_file.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["action"]["permission_decision"]["behavior"] == "allow"
    assert [entry["event"] for entry in receipt["action"]["hook_trace"]] == [
        "permission_request",
        "pre_tool_use",
        "post_tool_use",
    ]

    trace = json.loads(Path(result.reasoning_trace_ref).read_text(encoding="utf-8"))
    assert trace["steps"][0]["tool_calls"][0]["permission_decision"]["behavior"] == "allow"
    assert [entry["event"] for entry in trace["steps"][0]["tool_calls"][0]["hook_trace"]] == [
        "permission_request",
        "pre_tool_use",
        "post_tool_use",
    ]
