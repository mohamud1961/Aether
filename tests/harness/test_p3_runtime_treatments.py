from __future__ import annotations

from dataclasses import replace

from aether.execution import MemoryExecutor
from aether.persistent_runtime import (
    INDEPENDENT_JOBS_V1_GUIDANCE,
    VERTICAL_SLICE_V1_GUIDANCE,
    build_persistent_runtime,
)
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Run independent work when useful and leave the requested artifact.",
        workspace_root="/app",
        capabilities={
            "managed_process": CapabilityDescriptor(
                "managed_process",
                "managed finite jobs",
                tool_names=("start_job", "probe_job", "stop_process"),
            ),
            "filesystem": CapabilityDescriptor(
                "filesystem",
                "workspace files",
                tool_names=("read_file", "write_file"),
            ),
        },
    )


def _prefix(compiled, label: str) -> str:
    rows = dict(compiled.stable_prefix_sections)
    return str(rows[label])


def test_m2_and_m5_are_orthogonal_runtime_treatments() -> None:
    resolved = build_persistent_runtime(
        _env(),
        solver_async_mode="independent_jobs_v1",
        solver_reasoning_mode="vertical_slice_v1",
    )
    assert resolved.compiled is not None
    compiled = resolved.compiled
    assert _prefix(compiled, "solver_async_execution") == INDEPENDENT_JOBS_V1_GUIDANCE
    assert _prefix(compiled, "solver_reasoning_treatment") == VERTICAL_SLICE_V1_GUIDANCE
    assert compiled.config_realization["solver_async_mode"] == "independent_jobs_v1"
    assert compiled.config_realization["solver_reasoning_mode"] == "vertical_slice_v1"


class _CompletingExecutor(MemoryExecutor):
    def __init__(self) -> None:
        super().__init__(workspace_root="/app", files={"input.txt": "ok"})
        self.probe_calls = 0

    def probe_job(self, target: str):
        self.probe_calls += 1
        handle = self.processes[target]
        self.processes[target] = replace(
            handle, live=False, status="completed", exit_code=0, detail="exited 0"
        )
        return super().probe_job(target)


class _TwoTurnHooks:
    verify = None

    def __init__(self) -> None:
        self.calls = 0
        self.requests = []

    def solve(self, messages, compiled):
        del compiled
        self.requests.append(messages)
        self.calls += 1
        if self.calls == 1:
            action = ActionRequest(
                action_id="job-1",
                kind="start_job",
                capability_id="managed_process",
                arguments={"service_name": "job-one", "command": "do-work"},
                intent="",
                expected_observation="",
                if_fail_next="",
            )
        else:
            action = ActionRequest(
                action_id="read",
                kind="read_file",
                capability_id="filesystem",
                arguments={"path": "input.txt"},
                intent="",
                expected_observation="",
                if_fail_next="",
            )
        return SolverTurn(kind="act", summary="act", actions=(action,))


def _context(messages) -> dict:
    import json

    marker = "[context_packet]\n"
    for message in messages:
        content = str(message.get("content", ""))
        if content.startswith(marker):
            return json.loads(content[len(marker):])
    raise AssertionError("context packet missing")


def test_m2_thin_path_delivers_current_job_status_without_explicit_probe() -> None:
    executor = _CompletingExecutor()
    hooks = _TwoTurnHooks()
    result = run_thin_loop(
        _env(),
        executor,
        hooks,
        config=ThinLoopConfig(
            max_steps=2,
            solver_async_mode="independent_jobs_v1",
        ),
    )
    assert result.step == 2
    assert executor.probe_calls == 1
    second = _context(hooks.requests[1])
    assert second["runtime_operations"][0]["status"] == "completed"
    assert second["runtime_operations"][0]["status_current"] is True
    refreshes = [
        receipt for receipt in result.receipts
        if receipt.kind == "runtime_operation_status_refresh"
    ]
    assert len(refreshes) == 1
    assert refreshes[0].payload["automatic_runtime_refresh"] is True


class _ThreeJobHooks:
    verify = None

    def __init__(self) -> None:
        self.calls = 0

    def solve(self, messages, compiled):
        del messages, compiled
        self.calls += 1
        name = f"job-{self.calls}"
        action = ActionRequest(
            action_id=name,
            kind="start_job",
            capability_id="managed_process",
            arguments={"service_name": name, "command": f"work-{self.calls}"},
            intent="",
            expected_observation="",
            if_fail_next="",
        )
        return SolverTurn(kind="act", summary="act", actions=(action,))


def test_m2_rejects_third_live_background_job() -> None:
    executor = MemoryExecutor(workspace_root="/app")
    result = run_thin_loop(
        _env(),
        executor,
        _ThreeJobHooks(),
        config=ThinLoopConfig(
            max_steps=3,
            solver_async_mode="independent_jobs_v1",
        ),
    )
    launches = [r for r in result.receipts if r.kind == "process_launch"]
    assert sum(1 for r in launches if r.success) == 2
    rejected = [r for r in launches if r.failure_class == "async_concurrency_limit"]
    assert len(rejected) == 1
    assert rejected[0].payload["max_live_background_jobs"] == 2
    assert rejected[0].payload["task_action_dispatched"] is False


def test_m4_source_linked_clauses_are_exact_raw_spans() -> None:
    import hashlib
    from aether.persistent_task_contract import source_linked_task_clauses

    prompt = (
        "Instructions:\n\n"
        "- Create café.txt exactly.\n"
        "- Keep the optional note if useful.\n\n"
        "Use the public interface and leave the final artifact in place."
    )
    rows = source_linked_task_clauses(prompt)
    assert len(rows) == 3
    raw_bytes = prompt.encode("utf-8")
    for row in rows:
        text = str(row["text"])
        char_slice = prompt[
            int(row["source_char_start"]):int(row["source_char_end"])
        ]
        byte_slice = raw_bytes[
            int(row["source_byte_start"]):int(row["source_byte_end"])
        ].decode("utf-8")
        assert char_slice == text
        assert byte_slice == text
        assert row["source_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert rows[0]["text"] == "- Create café.txt exactly."
    assert rows[1]["text"] == "- Keep the optional note if useful."


def test_m4_runtime_adds_navigation_view_without_replacing_raw_authority() -> None:
    import json

    env = _env()
    env = EnvMap(
        task_prompt="Do this:\n\n- Create result.txt.\n- Do not delete input.txt.",
        workspace_root=env.workspace_root,
        capabilities=env.capabilities,
    )
    resolved = build_persistent_runtime(
        env,
        solver_task_contract_mode="source_clauses_v1",
    )
    assert resolved.compiled is not None
    compiled = resolved.compiled
    sections = dict(compiled.stable_prefix_sections)
    assert sections["task_prompt"] == env.task_prompt
    view = json.loads(sections["task_contract_view"])
    assert view["authority"] == "navigation_only_raw_task_remains_authoritative"
    assert view["source"] == "exact_raw_task_substrings"
    assert len(view["clauses"]) == 2
    assert compiled.task_contract is not None
    assert compiled.task_contract.schema_version == "persistent_v11_raw"
    assert compiled.task_contract.raw_task_prompt == env.task_prompt
    assert compiled.config_realization["solver_task_contract_mode"] == "source_clauses_v1"


def test_m2_serial_control_rejects_second_live_background_job() -> None:
    executor = MemoryExecutor(workspace_root="/app")
    result = run_thin_loop(
        _env(),
        executor,
        _ThreeJobHooks(),
        config=ThinLoopConfig(
            max_steps=2,
            solver_async_mode="serial_jobs_v1",
        ),
    )
    launches = [r for r in result.receipts if r.kind == "process_launch"]
    assert sum(1 for r in launches if r.success) == 1
    rejected = [r for r in launches if r.failure_class == "async_concurrency_limit"]
    assert len(rejected) == 1
    assert rejected[0].payload["solver_async_mode"] == "serial_jobs_v1"
    assert rejected[0].payload["max_live_background_jobs"] == 1


def test_thin_loop_can_skip_eager_dynamic_capability_probe(monkeypatch):
    from aether.thin_loop import ThinLoopConfig
    config = ThinLoopConfig(probe_runtime_capabilities=False)
    assert config.probe_runtime_capabilities is False
