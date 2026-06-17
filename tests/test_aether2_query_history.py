"""Tests for the query_history tool added to the executor's tool surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.aether2.loop import ExecutionContext, ToolInvocationRecord
from runner.aether2.jobs import JobRegistry
from runner.aether2.sessions import SessionRegistry
from runner.aether2.executor import ContainerExecutor
from runner.aether2.tools import TOOL_NAMES, TOOL_SCHEMAS, dispatch
from runner.aether2.envelope import ObservationEnvelope, ProcessDelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(tmp_path: Path) -> ExecutionContext:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    state_dir = workspace / ".aether2" / "state"
    return ExecutionContext(
        executor=ContainerExecutor(workspace_root=workspace),
        job_registry=JobRegistry(state_dir),
        session_registry=SessionRegistry(state_dir),
        raw_log_dir=workspace / ".aether2" / "raw_logs",
    )


def _fake_envelope(tool: str, stdout: str = "", stderr: str = "", exit_code: int = 0) -> ObservationEnvelope:
    return ObservationEnvelope(
        tool=tool,
        exit_code=exit_code,
        duration_sec=0.01,
        cwd="/workspace",
        stdout_head=stdout[:500],
        stdout_tail="",
        stderr_head=stderr[:500],
        stderr_tail="",
        truncated=False,
        raw_log_path=None,
        files_changed=[],
        process_delta=ProcessDelta(),
        blind_retry_blocked=False,
        error=None,
        truncation_digest=None,
    )


def _inject_records(ctx: ExecutionContext, records: list[dict]) -> None:
    """Populate ctx._run_tool_invocations with fake ToolInvocationRecord entries."""
    for i, r in enumerate(records):
        env = _fake_envelope(
            r["tool_name"],
            stdout=r.get("stdout", ""),
            stderr=r.get("stderr", ""),
            exit_code=r.get("exit_code", 0),
        )
        ctx._run_tool_invocations.append(
            ToolInvocationRecord(
                step=i,
                tool_name=r["tool_name"],
                arguments=r.get("arguments", {}),
                envelope=env,
            )
        )


# ---------------------------------------------------------------------------
# Registration & schema tests
# ---------------------------------------------------------------------------

def test_query_history_in_tool_names() -> None:
    assert "query_history" in TOOL_NAMES


def test_query_history_schema_present_and_well_formed() -> None:
    schema = next((s for s in TOOL_SCHEMAS if s["function"]["name"] == "query_history"), None)
    assert schema is not None, "query_history schema missing from TOOL_SCHEMAS"
    assert schema["type"] == "function"
    params = schema["function"]["parameters"]
    assert params["type"] == "object"
    assert params["additionalProperties"] is False
    props = params["properties"]
    assert "query" in props
    assert props["query"]["type"] == "string"
    assert "limit" in props
    assert props["limit"]["minimum"] == 1
    assert props["limit"]["maximum"] == 50
    assert params["required"] == ["query"]


def test_tool_names_and_schemas_stay_in_sync() -> None:
    schema_names = [s["function"]["name"] for s in TOOL_SCHEMAS]
    assert schema_names == TOOL_NAMES


# ---------------------------------------------------------------------------
# dispatch routing test
# ---------------------------------------------------------------------------

class _FakeCtxWithQueryHistory:
    def query_history(self, query: str, tool: str | None = None, limit: int = 10) -> str:
        return f"qh:{query}:{tool}:{limit}"


def test_dispatch_routes_query_history() -> None:
    ctx = _FakeCtxWithQueryHistory()
    result = dispatch("query_history", {"query": "echo"}, ctx)
    assert result == "qh:echo:None:10"


def test_dispatch_query_history_strips_null_tool() -> None:
    """Dispatch must not pass None for optional args when model omits them."""
    ctx = _FakeCtxWithQueryHistory()
    result = dispatch("query_history", {"query": "x", "tool": None, "limit": None}, ctx)
    # None values are stripped; defaults apply
    assert result == "qh:x:None:10"


def test_dispatch_query_history_passes_tool_filter() -> None:
    ctx = _FakeCtxWithQueryHistory()
    result = dispatch("query_history", {"query": "x", "tool": "run_command", "limit": 3}, ctx)
    assert result == "qh:x:run_command:3"


# ---------------------------------------------------------------------------
# Behavioural tests via ExecutionContext
# ---------------------------------------------------------------------------

def test_query_history_returns_observation_envelope(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _inject_records(ctx, [{"tool_name": "run_command", "arguments": {"cmd": "ls"}, "stdout": "file1.txt"}])
    result = ctx.query_history(query="ls")
    assert isinstance(result, ObservationEnvelope)
    assert result.exit_code == 0
    assert result.tool == "query_history"


def test_query_history_matches_prior_steps_most_recent_first(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _inject_records(ctx, [
        {"tool_name": "run_command", "arguments": {"cmd": "echo hello"}, "stdout": "hello"},
        {"tool_name": "run_command", "arguments": {"cmd": "echo world"}, "stdout": "world"},
        {"tool_name": "write_file", "arguments": {"path": "out.txt", "content": "x"}, "stdout": "wrote 1 bytes"},
    ])
    result = ctx.query_history(query="echo")
    text = result.stdout_head
    # Should match both run_command steps containing "echo", most-recent first (step 1 before step 0).
    idx_step1 = text.find('"step":1')
    idx_step0 = text.find('"step":0')
    assert idx_step1 != -1, "step 1 not in result"
    assert idx_step0 != -1, "step 0 not in result"
    assert idx_step1 < idx_step0, "most-recent-first ordering violated"
    # write_file step should not match
    assert "out.txt" not in text


def test_query_history_limit_caps_results(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _inject_records(ctx, [
        {"tool_name": "run_command", "arguments": {"cmd": f"echo step{i}"}, "stdout": f"step{i}"}
        for i in range(10)
    ])
    result = ctx.query_history(query="echo", limit=3)
    # Parse lines; first line is header, then one JSON per match.
    lines = [l for l in result.stdout_head.splitlines() if l.startswith("{")]
    assert len(lines) == 3


def test_query_history_tool_filter(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _inject_records(ctx, [
        {"tool_name": "run_command", "arguments": {"cmd": "echo hi"}, "stdout": "hi"},
        {"tool_name": "write_file", "arguments": {"path": "x.txt", "content": "data"}, "stdout": "wrote"},
        {"tool_name": "run_command", "arguments": {"cmd": "ls /tmp"}, "stdout": "/tmp"},
    ])
    result = ctx.query_history(query="", tool="write_file")
    text = result.stdout_head
    assert "write_file" in text
    assert "run_command" not in text


def test_query_history_no_match_returns_clean_envelope(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _inject_records(ctx, [
        {"tool_name": "run_command", "arguments": {"cmd": "ls"}, "stdout": "ok"},
    ])
    result = ctx.query_history(query="zzz_no_such_keyword")
    assert result.exit_code == 0
    assert result.error is None
    assert "no matching history" in result.stdout_head


def test_query_history_empty_history_no_error(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = ctx.query_history(query="anything")
    assert result.exit_code == 0
    assert result.error is None
    assert "no matching history" in result.stdout_head


def test_query_history_excludes_own_calls(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    # Inject a query_history record (as would happen after a real call).
    _inject_records(ctx, [
        {"tool_name": "query_history", "arguments": {"query": "prior"}, "stdout": "1 result for 'prior'"},
        {"tool_name": "run_command", "arguments": {"cmd": "echo hi"}, "stdout": "hi"},
    ])
    result = ctx.query_history(query="prior")
    # The query_history record's output "1 result for 'prior'" should not appear.
    # The run_command record does not match "prior" either.
    assert "no matching history" in result.stdout_head or '"tool":"query_history"' not in result.stdout_head


def test_query_history_redacts_secrets_in_output(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _inject_records(ctx, [
        {
            "tool_name": "run_command",
            "arguments": {"cmd": "export API_KEY=sk-secret123"},
            "stdout": "Bearer sk-secret123TOKEN",
        }
    ])
    result = ctx.query_history(query="Bearer")
    text = result.stdout_head
    # The raw secret token should be redacted.
    assert "sk-secret123TOKEN" not in text
    assert "[REDACTED]" in text


def test_query_history_matches_in_args(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    _inject_records(ctx, [
        {"tool_name": "read_file", "arguments": {"path": "/app/special_file.txt"}, "stdout": "contents"},
        {"tool_name": "run_command", "arguments": {"cmd": "ls"}, "stdout": "ok"},
    ])
    result = ctx.query_history(query="special_file")
    text = result.stdout_head
    assert "read_file" in text
    assert "run_command" not in text


def test_query_history_total_output_budget_not_blown(tmp_path: Path) -> None:
    """A huge history with large outputs should not produce an unbounded response."""
    ctx = _make_ctx(tmp_path)
    _inject_records(ctx, [
        {"tool_name": "run_command", "arguments": {"cmd": "echo x"}, "stdout": "x" * 500}
        for _ in range(50)
    ])
    result = ctx.query_history(query="echo", limit=50)
    total_len = len(result.stdout_head) + len(result.stdout_tail)
    # The tool truncates at _TOTAL_OUTPUT_BUDGET (8000) plus header overhead.
    assert total_len < 12000, f"output too large: {total_len}"
