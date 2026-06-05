from __future__ import annotations

import pytest

import runner.aether2.tools as tools_module
from runner.aether2.tools import TOOL_NAMES, TOOL_SCHEMAS, dispatch


def test_tool_schema_names_are_exact_and_stable() -> None:
    assert TOOL_NAMES == [
        "run_command",
        "start_job",
        "job_status",
        "session_start",
        "session_send",
        "session_read",
        "read_file",
        "write_file",
        "wait",
        "task_done",
        "task_blocked",
    ]
    assert [schema["function"]["name"] for schema in TOOL_SCHEMAS] == TOOL_NAMES
    assert len(TOOL_SCHEMAS) == 11
    assert tools_module.__doc__ == "Generic provider tool schemas and dispatch helpers."
    assert tools_module.__doc__.count(".") == 1
    assert "run_command" not in tools_module.__doc__
    assert "task_done" not in tools_module.__doc__
    assert "receipts.py" not in tools_module.__doc__


def test_tool_schemas_are_native_function_calling_shapes() -> None:
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        assert schema["function"]["parameters"]["type"] == "object"
        assert schema["function"]["parameters"]["additionalProperties"] is False
        assert schema["function"]["description"]

    wait_schema = next(schema for schema in TOOL_SCHEMAS if schema["function"]["name"] == "wait")
    assert wait_schema["function"]["parameters"]["properties"]["seconds"]["maximum"] == 300
    assert wait_schema["function"]["parameters"]["properties"]["seconds"]["minimum"] == 0
    assert wait_schema["function"]["parameters"]["properties"]["reason"]["type"] == "string"

    task_done_schema = next(schema for schema in TOOL_SCHEMAS if schema["function"]["name"] == "task_done")
    checks_schema = task_done_schema["function"]["parameters"]["properties"]["checks"]
    assert checks_schema["type"] == "array"
    assert checks_schema["minItems"] == 1
    assert checks_schema["items"]["type"] == "string"

    read_file_schema = next(schema for schema in TOOL_SCHEMAS if schema["function"]["name"] == "read_file")
    assert "task workspace" in read_file_schema["function"]["description"]
    assert read_file_schema["function"]["parameters"]["properties"]["path"]["type"] == "string"

    start_job_schema = next(schema for schema in TOOL_SCHEMAS if schema["function"]["name"] == "start_job")
    assert "detached job" in start_job_schema["function"]["description"]
    assert start_job_schema["function"]["parameters"]["properties"]["job_id"]["type"] == ["string", "null"]


class FakeCtx:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def _record(self, name: str, **kwargs: object) -> str:
        self.calls.append((name, kwargs))
        return name

    def run_command(self, **kwargs: object) -> str:
        return self._record("run_command", **kwargs)

    def start_job(self, **kwargs: object) -> str:
        return self._record("start_job", **kwargs)

    def job_status(self, **kwargs: object) -> str:
        return self._record("job_status", **kwargs)

    def session_start(self, **kwargs: object) -> str:
        return self._record("session_start", **kwargs)

    def session_send(self, **kwargs: object) -> str:
        return self._record("session_send", **kwargs)

    def session_read(self, **kwargs: object) -> str:
        return self._record("session_read", **kwargs)

    def read_file(self, **kwargs: object) -> str:
        return self._record("read_file", **kwargs)

    def write_file(self, **kwargs: object) -> str:
        return self._record("write_file", **kwargs)

    def wait(self, **kwargs: object) -> str:
        return self._record("wait", **kwargs)

    def task_done(self, **kwargs: object) -> str:
        return self._record("task_done", **kwargs)

    def task_blocked(self, **kwargs: object) -> str:
        return self._record("task_blocked", **kwargs)


@pytest.mark.parametrize(
    "tool_name,args",
    [
        ("run_command", {"cmd": "echo hi", "timeout_sec": 3, "cwd": "/tmp"}),
        ("start_job", {"cmd": "sleep 1", "job_id": "job-1", "cwd": "/tmp"}),
        ("job_status", {"job_id": "job-1"}),
        ("session_start", {"session_id": "s1", "command": "bash"}),
        ("session_send", {"session_id": "s1", "keys": "Enter"}),
        ("session_read", {"session_id": "s1"}),
        ("read_file", {"path": "/tmp/x", "offset": 0, "limit": 10}),
        ("write_file", {"path": "/tmp/x", "content": "ok"}),
        ("wait", {"seconds": 1, "reason": "pause"}),
        ("task_done", {"summary": "done", "checks": ["true"]}),
        (
            "task_blocked",
            {
                "blocker": "missing dependency",
                "evidence": ["which foo -> not found"],
                "attempts": ["apt-get install foo"],
                "missing_external_state": ["network access"],
                "recommended_next_evidence": ["foo --version after install"],
            },
        ),
    ],
)
def test_dispatch_routes_each_tool(tool_name: str, args: dict[str, object]) -> None:
    ctx = FakeCtx()
    result = dispatch(tool_name, args, ctx)
    assert result == tool_name
    assert ctx.calls == [(tool_name, args)]


def test_dispatch_rejects_unknown_tools() -> None:
    with pytest.raises(KeyError):
        dispatch("search_receipts", {}, FakeCtx())
