from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether import harbor_runtime as hr
from aether.kernel import AetherNextKernel
from aether.model_hooks import ModelHooks
from aether.persistent_runtime import (
    SOLVER_REALITY_TRANSPORT_CONTROL,
    SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1,
    build_persistent_runtime,
)
from aether.runtime_ir import CapabilityDescriptor, EnvMap


def _envmap() -> EnvMap:
    return EnvMap(
        task_prompt="Inspect /app/input.txt and produce the requested artifact.",
        workspace_root="/app",
        visible_files=("/app/input.txt",),
        visible_dirs=("/app",),
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "filesystem", True, ("read_file", "write_file")
            ),
            "shell": CapabilityDescriptor("shell", "shell", True, ("run_command",)),
        },
        task_metadata={
            "environment_probe": {
                "schema_version": "environment_probe.v1",
                "workspace_root": "/app",
                "command_names": {},
                "python": {},
                "network": {"status": "unavailable", "value": "unavailable"},
                "task_hints": {},
            }
        },
        network_scope="unavailable",
        file_tree="/app\n- input.txt",
        file_map_summary={"extension_counts": {".txt": 1}},
    )


def test_control_transport_is_exact_runtime_compile_default() -> None:
    env = _envmap()
    implicit = build_persistent_runtime(env)
    explicit = build_persistent_runtime(
        env, solver_reality_transport_mode=SOLVER_REALITY_TRANSPORT_CONTROL
    )
    assert implicit.compiled is not None and explicit.compiled is not None
    assert implicit.compiled == explicit.compiled
    assert "solver_reality_transport_mode" not in implicit.compiled.config_realization


def test_delta_transport_changes_only_runtime_realization_not_solver_projection() -> None:
    env = _envmap()
    control = build_persistent_runtime(env)
    treated = build_persistent_runtime(
        env, solver_reality_transport_mode=SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1
    )
    assert control.compiled is not None and treated.compiled is not None
    c = control.compiled
    t = treated.compiled

    assert c.prefix_messages() == t.prefix_messages()
    assert c.stable_prefix_sections == t.stable_prefix_sections
    assert c.task_prompt == t.task_prompt
    assert c.task_contract_identity == t.task_contract_identity
    assert c.task_contract_payload_sha256 == t.task_contract_payload_sha256
    assert c.env_digest == t.env_digest
    assert c.action_schema == t.action_schema
    assert c.selected_capabilities == t.selected_capabilities
    assert c.context_policy == t.context_policy
    assert c.process_policy == t.process_policy
    assert c.completion_policy == t.completion_policy

    c_realization = dict(c.config_realization)
    t_realization = dict(t.config_realization)
    assert t_realization.pop("solver_reality_transport_mode") == SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1
    assert t_realization == c_realization


def test_invalid_runtime_transport_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported Solver reality transport mode"):
        build_persistent_runtime(_envmap(), solver_reality_transport_mode="invented")
    with pytest.raises(ValueError, match="unsupported Solver reality transport mode"):
        AetherNextKernel(solver_reality_transport_mode="invented")


class _ModeCapturingSolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def set_reality_transport_mode(self, mode: str, *, run_id: str, task_id: str) -> None:
        self.calls.append((mode, run_id, task_id))

    def __call__(self, _messages, *, max_output_tokens=None) -> str:  # pragma: no cover
        raise AssertionError("provider call is not part of this wiring test")


def test_model_hooks_bind_compiled_transport_mode_without_provider_call() -> None:
    solver = _ModeCapturingSolver()
    hooks = ModelHooks(
        solver, solver, run_id="run-a", task_id="task-a",
        solver_max_output_tokens=16, verifier_max_output_tokens=16,
    )
    control = build_persistent_runtime(_envmap()).compiled
    treated = build_persistent_runtime(
        _envmap(), solver_reality_transport_mode=SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1
    ).compiled
    assert control is not None and treated is not None

    hooks._configure_solver_reality_transport_mode(control)
    hooks._configure_solver_reality_transport_mode(treated)
    assert solver.calls == [
        (SOLVER_REALITY_TRANSPORT_CONTROL, "run-a", "task-a"),
        (SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1, "run-a", "task-a"),
    ]


class _SolveModeRecordingModel(_ModeCapturingSolver):
    def __init__(self) -> None:
        super().__init__()
        self.model_calls = 0

    def __call__(self, _messages, *, max_output_tokens=None) -> str:
        self.model_calls += 1
        return '{"kind":"act","action":{"kind":"read_file","arguments":{"path":"/app/input.txt"}}}'


def test_actual_model_hooks_solve_configures_transport_before_model_call() -> None:
    solver = _SolveModeRecordingModel()
    verifier = _SolveModeRecordingModel()
    hooks = ModelHooks(
        solver, verifier, run_id="run-a", task_id="task-a",
        solver_max_output_tokens=16, verifier_max_output_tokens=16,
    )
    treated = build_persistent_runtime(
        _envmap(), solver_reality_transport_mode=SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1
    ).compiled
    assert treated is not None
    turn = hooks.solve([], treated)
    assert turn.kind == "act"
    assert solver.model_calls == 1
    assert solver.calls == [
        (SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1, "run-a", "task-a")
    ]


def test_harbor_transport_selector_is_default_off_and_production_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(hr.SOLVER_REALITY_TRANSPORT_ENV, raising=False)
    assert (
        hr.selected_solver_reality_transport_mode(hr.build_selected_frontier_models)
        == hr.SOLVER_REALITY_TRANSPORT_CONTROL
    )

    monkeypatch.setenv(
        hr.SOLVER_REALITY_TRANSPORT_ENV, hr.SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1
    )
    assert (
        hr.selected_solver_reality_transport_mode(hr.build_selected_frontier_models)
        == hr.SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1
    )

    def offline_factory():
        raise AssertionError("factory should not be invoked")

    assert (
        hr.selected_solver_reality_transport_mode(offline_factory)
        == hr.SOLVER_REALITY_TRANSPORT_CONTROL
    )


def test_harbor_transport_selector_invalid_value_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(hr.SOLVER_REALITY_TRANSPORT_ENV, "invented")
    with pytest.raises(RuntimeError, match=hr.SOLVER_REALITY_TRANSPORT_ENV):
        hr.selected_solver_reality_transport_mode(hr.build_selected_frontier_models)


def test_runtime_identity_records_transport_only_when_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Env:
        task_metadata = {}

        def digest(self) -> str:
            return "env-digest"

    class Context:
        metadata = {}
        context_id = "ctx"

    monkeypatch.delenv(hr.SOLVER_REALITY_TRANSPORT_ENV, raising=False)
    baseline = hr._runtime_identity(
        Context(), Env(), model_factory=hr.build_selected_frontier_models
    )
    assert "research_solver_reality_transport" not in baseline
    assert "research_solver_reality_transport_authority" not in baseline

    monkeypatch.setenv(
        hr.SOLVER_REALITY_TRANSPORT_ENV, hr.SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1
    )
    treated = hr._runtime_identity(
        Context(), Env(), model_factory=hr.build_selected_frontier_models
    )
    assert (
        treated["research_solver_reality_transport"]
        == hr.SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1
    )
    assert (
        treated["research_solver_reality_transport_authority"]
        == hr.SOLVER_REALITY_TRANSPORT_ENV
    )
