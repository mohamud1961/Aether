import json
import time
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from runner.aether2 import bridge_harbor as bridge_module
from runner.aether2.bridge_harbor import TaskSpec, run_task_via_harbor
from runner.aether2.loop import run_aether2_loop
from runner.aether2.metrics import build_scorecard
from runner.aether2.model_client import ModelResponse


def test_run_task_via_harbor_syncs_workspace_artifacts_and_writes_result(tmp_path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "instruction.txt").write_text("do the task\n", encoding="utf-8")

    class LoopRecorder:
        def __init__(self) -> None:
            self.calls = []

        def __call__(self, task, model_client, executor, *, deadline_ts):
            self.calls.append((task, model_client, executor, deadline_ts))
            artifact_path = Path(task.workspace_root) / "answer.txt"
            artifact_path.write_text("done\n", encoding="utf-8")
            return {"status": "complete", "deadline_ts": deadline_ts, "artifact": artifact_path.name}

    loop_fn = LoopRecorder()
    result = run_task_via_harbor(task_dir, loop_fn, deadline_ts=123.0)

    assert result["status"] == "complete"
    assert loop_fn.calls[0][3] == 123.0
    assert loop_fn.calls[0][0].instruction == "do the task\n"
    assert Path(loop_fn.calls[0][0].workspace_root) == task_dir / "workspace"
    assert Path(loop_fn.calls[0][0].artifacts_dir) == task_dir / "artifacts"
    assert (task_dir / "artifacts" / "result.json").exists()
    assert (task_dir / "artifacts" / "answer.txt").read_text(encoding="utf-8") == "done\n"


def test_run_task_via_harbor_raises_on_incomplete_sync_back(tmp_path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "instruction.txt").write_text("do the task\n", encoding="utf-8")

    def loop_fn(task, model_client, executor, *, deadline_ts):
        return {"status": "complete", "deadline_ts": deadline_ts}

    with pytest.raises(RuntimeError, match="incomplete artifact sync-back"):
        run_task_via_harbor(task_dir, loop_fn, deadline_ts=123.0)


def test_run_task_via_harbor_preserves_preexisting_workspace_fixture(tmp_path) -> None:
    """C8: bridge_harbor must never delete pre-existing workspace fixture files."""
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "instruction.txt").write_text("do the task\n", encoding="utf-8")
    workspace = task_dir / "workspace"
    workspace.mkdir()
    (workspace / "fixture.txt").write_text("pre-seeded fixture\n", encoding="utf-8")

    def loop_fn(task, model_client, executor, *, deadline_ts):
        (Path(task.workspace_root) / "answer.txt").write_text("done\n", encoding="utf-8")
        return {"status": "complete", "deadline_ts": deadline_ts}

    run_task_via_harbor(task_dir, loop_fn, deadline_ts=123.0)

    assert (workspace / "fixture.txt").read_text(encoding="utf-8") == "pre-seeded fixture\n"
    assert (task_dir / "artifacts" / "fixture.txt").read_text(encoding="utf-8") == "pre-seeded fixture\n"
    assert (task_dir / "artifacts" / "answer.txt").exists()


def test_run_task_via_harbor_ignores_hidden_workspace_files_when_validating_sync_back(tmp_path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "instruction.txt").write_text("do the task\n", encoding="utf-8")

    def loop_fn(task, model_client, executor, *, deadline_ts):
        hidden_artifact = Path(task.workspace_root) / ".scratch.txt"
        hidden_artifact.write_text("noise\n", encoding="utf-8")
        return {"status": "complete", "deadline_ts": deadline_ts, "artifact": hidden_artifact.name}

    with pytest.raises(RuntimeError, match="no visible synced task artifacts"):
        run_task_via_harbor(task_dir, loop_fn, deadline_ts=123.0)


def test_run_task_via_harbor_requires_an_instruction_file(tmp_path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    def loop_fn(task, model_client, executor, *, deadline_ts):
        raise AssertionError("should not run")

    with pytest.raises(FileNotFoundError, match="no instruction file found"):
        run_task_via_harbor(task_dir, loop_fn, deadline_ts=123.0)


def test_load_tomllib_falls_back_to_minimal_loader_without_tomllib_or_tomli(monkeypatch) -> None:
    """Simulate a pre-3.11 interpreter lacking both ``tomllib`` and ``tomli``.

    ``bridge_harbor._load_tomllib`` must still return a module exposing a
    working ``loads``/``load`` pair so the core remains importable and
    ``_task_container_image`` keeps working regardless of interpreter/entrypoint.
    """
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name in {"tomllib", "tomli"}:
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    fallback = bridge_module._load_tomllib()

    assert hasattr(fallback, "loads")
    assert hasattr(fallback, "load")

    parsed = fallback.loads(
        "\n".join(
            [
                "[environment]",
                'docker_image = "example/image:latest"',
                "max_steps = 5",
                "enabled = true",
            ]
        )
    )
    assert parsed == {
        "environment": {
            "docker_image": "example/image:latest",
            "max_steps": 5,
            "enabled": True,
        }
    }


def test_task_container_image_reads_toml_via_fallback_loader(tmp_path: Path, monkeypatch) -> None:
    """``_task_container_image`` works using the minimal fallback ``tomllib``."""

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text(
        "\n".join(
            [
                "[environment]",
                'docker_image = "example/fallback-image:1.0"',
            ]
        ),
        encoding="utf-8",
    )

    fallback_module = bridge_module._load_tomllib()
    # Force the module-level binding used by _task_container_image to the
    # fallback loader, mirroring a pre-3.11 interpreter with no tomli.
    monkeypatch.setattr(bridge_module, "tomllib", fallback_module)

    image = bridge_module._task_container_image(task_dir)
    assert image == "example/fallback-image:1.0"


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


def _verify_response(satisfied: bool = True) -> ModelResponse:
    payload = {
        "requirements": [
            {
                "requirement": "task complete",
                "verdict": "satisfied" if satisfied else "unsatisfied",
                "evidence": "checked",
                "evidence_refs": ["checks_results[0]"],
            }
        ],
        "reason_codes": [],
        "summary": "ok" if satisfied else "missing evidence",
    }
    return _response(text=json.dumps(payload))


class _ScriptedModelClient:
    """Replays a fixed sequence of tool-call turns; non-tool calls (verify/compaction) get a side queue."""

    def __init__(self, turns, side_responses=None):
        self.turns = list(turns)
        self.side_responses = list(side_responses or [])
        self.calls: list[tuple[list[dict], list[dict], int]] = []

    def call(self, messages, tools, *, cache_prefix_len):
        self.calls.append((list(messages), list(tools), cache_prefix_len))
        tool_names = {
            tool.get("function", {}).get("name")
            for tool in tools
            if isinstance(tool, dict)
        }
        if tool_names and tool_names.issubset({"run_command", "read_file", "job_status", "session_read"}):
            if self.side_responses:
                return self.side_responses.pop(0)
            return _verify_response(True)
        if not tools:
            if self.side_responses:
                return self.side_responses.pop(0)
            return _verify_response(True)
        if self.turns:
            return self.turns.pop(0)
        return _response(text="done")


def test_run_task_via_harbor_end_to_end_with_aether2_loop(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "instruction.txt").write_text("write hello.txt containing hello\n", encoding="utf-8")

    turns = [
        _response(
            text="writing the file",
            tool_calls=(_tool_call("write_file", {"path": "hello.txt", "content": "hello"}),),
        ),
        _response(
            text="done",
            tool_calls=(
                _tool_call(
                    "task_done",
                    {"summary": "wrote hello.txt", "checks": ["cat hello.txt"]},
                    call_id="call-2",
                ),
            ),
        ),
    ]
    client = _ScriptedModelClient(turns)

    def loop_fn(task, model_client, executor, *, deadline_ts):
        return run_aether2_loop(task, client, executor, deadline_ts=deadline_ts)

    result = run_task_via_harbor(task_dir, loop_fn, deadline_ts=time.time() + 60)

    assert result.finalize_reason == "task_done"
    assert result.pass_ is True

    artifacts_dir = task_dir / "artifacts"
    assert (artifacts_dir / "hello.txt").read_text(encoding="utf-8") == "hello"
    assert (artifacts_dir / "result.json").exists()

    receipts_root = task_dir / ".aether2" / "host_receipts"
    receipt_files = list(receipts_root.rglob("*.json")) if receipts_root.exists() else []
    assert receipt_files, "expected receipt files to be written under task_dir/.aether2/receipts"

    scorecard = build_scorecard(result)
    assert scorecard.pass_ is True
    assert scorecard.steps >= 1


def test_build_runtime_mounts_task_container_and_model_factory(tmp_path: Path, monkeypatch) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    workspace_root = task_dir / "workspace"
    workspace_root.mkdir()
    artifacts_dir = task_dir / "artifacts"
    artifacts_dir.mkdir()
    (task_dir / "task.toml").write_text(
        '\n'.join(
            [
                "[environment]",
                'docker_image = "example/task-image:latest"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task = TaskSpec(
        task_id="task",
        instruction="do it",
        task_dir=task_dir,
        workspace_root=workspace_root,
        artifacts_dir=artifacts_dir,
    )

    sentinel_client = object()
    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, text, check=False):
        calls.append(list(cmd))
        if cmd[:3] == ["docker", "run", "-d"]:
            return CompletedProcess(cmd, 0, stdout="cid-123\n", stderr="")
        raise AssertionError(f"unexpected subprocess.run call: {cmd}")

    monkeypatch.setattr(bridge_module.subprocess, "run", fake_run)
    monkeypatch.setattr(bridge_module, "_build_model_client", lambda: sentinel_client)

    handle = bridge_module._build_runtime(task)
    runtime = handle.__enter__()
    try:
        assert runtime.model_client is sentinel_client
        assert runtime.executor.execution_boundary == "docker"
        assert runtime.executor.backend.container_id == "cid-123"
        assert runtime.executor.to_container_path(workspace_root) == "/app"
    finally:
        handle.__exit__(None, None, None)

    assert calls[0][:3] == ["docker", "run", "-d"]
    # C2: exiting the runtime handle must NOT stop the container or kill
    # in-container process trees (Harbor grades after the agent exits, so
    # declared services must remain running). Only the docker-run call is
    # expected.
    assert all(call[:3] != ["docker", "rm", "-f"] for call in calls)


def test_build_runtime_builds_local_image_when_declared_image_is_missing(tmp_path: Path, monkeypatch) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    workspace_root = task_dir / "workspace"
    workspace_root.mkdir()
    artifacts_dir = task_dir / "artifacts"
    artifacts_dir.mkdir()
    (task_dir / "task.toml").write_text('[environment]\ndocker_image = "example/task-image:latest"\n', encoding="utf-8")
    (task_dir / "Dockerfile").write_text("FROM busybox\n", encoding="utf-8")
    task = TaskSpec(
        task_id="task",
        instruction="do it",
        task_dir=task_dir,
        workspace_root=workspace_root,
        artifacts_dir=artifacts_dir,
    )

    sentinel_client = object()
    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, text, check=False):
        calls.append(list(cmd))
        if cmd[:3] == ["docker", "run", "-d"] and len([c for c in calls if c[:3] == ["docker", "run", "-d"]]) == 1:
            return CompletedProcess(cmd, 125, stdout="", stderr="Unable to find image")
        if cmd[:2] == ["docker", "build"]:
            return CompletedProcess(cmd, 0, stdout="built\n", stderr="")
        if cmd[:3] == ["docker", "run", "-d"]:
            return CompletedProcess(cmd, 0, stdout="cid-456\n", stderr="")
        raise AssertionError(f"unexpected subprocess.run call: {cmd}")

    monkeypatch.setattr(bridge_module.subprocess, "run", fake_run)
    monkeypatch.setattr(bridge_module, "_build_model_client", lambda: sentinel_client)

    handle = bridge_module._build_runtime(task)
    runtime = handle.__enter__()
    try:
        assert runtime.model_client is sentinel_client
        assert runtime.executor.backend.container_id == "cid-456"
    finally:
        handle.__exit__(None, None, None)

    assert calls[0][:3] == ["docker", "run", "-d"]
    assert calls[1][:2] == ["docker", "build"]
    assert calls[2][:3] == ["docker", "run", "-d"]
