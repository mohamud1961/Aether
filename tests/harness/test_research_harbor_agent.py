from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from aether.model_profile import GLM_RESEARCH_PROFILES, PRODUCTION_PROFILE
from aether.research_glm_harbor_agent import (
    GLMResearchHarborAgent,
    G4_KH_RUN_TASK_CONFIG,
    G4_PROFILE_SELECTOR,
    G4_REASONING_EFFORT,
    G4_SOLVER_MAX_OUTPUT_TOKENS,
    g4_kh_profile,
    g4_runtime_config,
)
from aether.research_runtime import (
    PROVIDER_LIMITER_PATH_ENV,
    PROVIDER_RPM_ENV,
    PROVIDER_TPM_ENV,
    PROVIDER_WINDOW_ENV,
)


def _bind_route(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = g4_kh_profile()
    monkeypatch.setenv(profile.endpoint_env, "https://example.openai.azure.com/")
    monkeypatch.setenv(profile.deployment_env, profile.model_id)


def test_g4_glm_profile_is_not_production_frontier() -> None:
    profile = g4_kh_profile()
    assert G4_PROFILE_SELECTOR == "glm-research-par-v1"
    assert profile.model_id == "FW-GLM-5.3-Flash-par"
    assert profile.expected_returned_model == "FW-GLM-5.3-Flash"
    assert profile.model_id != PRODUCTION_PROFILE.model_id
    assert profile.solver_reasoning_effort == G4_REASONING_EFFORT == "high"
    assert profile.solver_max_output_tokens == G4_SOLVER_MAX_OUTPUT_TOKENS == 32768


def test_g4_kh_config_is_exact_current_reference() -> None:
    assert G4_KH_RUN_TASK_CONFIG == {
        "solver_reanchor_mode": "current_full",
        "solver_context_mode": "full",
        "context_cleanup_mode": "off",
        "completion_record_mode": "off",
        "solver_loop": "thin",
        "thin_failed_observation_disposition_mode": "control",
        "solver_reasoning_mode": "control",
        "solver_async_mode": "control",
        "solver_task_contract_mode": "raw_task_control",
        "solver_model_view_mode": "hygiene_lean_v1",
        "solver_tool_surface_mode": "static_kernel_v1",
        "solver_prefix_renderer": "incumbent_context",
        "solver_reality_transport_mode": "observation_history_v1",
        "solver_working_context_mode": "off",
        "solver_hosted_tool_search_mode": "control",
        "verifier_activation_continuity_mode": "fresh_compact_control",
        "boundary_verification_mode": "control",
        "completion_disposition_mode": "control",
        "provider_frontier_recovery_mode": "control",
        "refresh_runtime_operation_status": False,
        "probe_runtime_capabilities": False,
        "oracle_finish_response_mode": "control",
        "delivery_hygiene_mode": "control",
    }


def test_g4_runtime_defaults_match_live_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _bind_route(monkeypatch)
    for name in (PROVIDER_TPM_ENV, PROVIDER_RPM_ENV, PROVIDER_WINDOW_ENV, PROVIDER_LIMITER_PATH_ENV):
        monkeypatch.delenv(name, raising=False)
    runtime = g4_runtime_config(state_root=tmp_path)
    assert runtime.profile_selector == G4_PROFILE_SELECTOR
    assert runtime.profile.solver_reasoning_effort == "high"
    assert runtime.provider_tpm == 420000
    assert runtime.provider_rpm == 420
    assert runtime.provider_window_s == 62.0
    assert runtime.observed_route_tpm == 450000
    assert runtime.observed_route_rpm == 450
    assert runtime.observed_route_window_s == 60.0
    assert runtime.solver_model_view_mode == "hygiene_lean_v1"
    assert runtime.solver_reality_transport_mode == "observation_history_v1"
    assert runtime.solver_tool_surface_mode == "static_kernel_v1"
    assert runtime.solver_context_policy == "control"
    assert runtime.solver_max_output_tokens == 32768
    assert runtime.shared_limiter_path == str((tmp_path / "shared_glm_par_limiter.json").resolve())


def test_completion_signal_control_is_identity_neutral_but_treatment_is_bound(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _bind_route(monkeypatch)
    for name in (PROVIDER_TPM_ENV, PROVIDER_RPM_ENV, PROVIDER_WINDOW_ENV, PROVIDER_LIMITER_PATH_ENV):
        monkeypatch.delenv(name, raising=False)
    runtime = g4_runtime_config(state_root=tmp_path)
    control_manifest = runtime.manifest()
    assert runtime.solver_completion_signal_mode == "control"
    assert "solver_completion_signal_mode" not in control_manifest
    treated = replace(runtime, solver_completion_signal_mode="verification_v1")
    assert treated.manifest()["solver_completion_signal_mode"] == "verification_v1"
    assert treated.sha256 != runtime.sha256


def test_g4_runtime_honors_sealed_pacing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _bind_route(monkeypatch)
    limiter = tmp_path / "route.json"
    monkeypatch.setenv(PROVIDER_TPM_ENV, "200000")
    monkeypatch.setenv(PROVIDER_RPM_ENV, "200")
    monkeypatch.setenv(PROVIDER_WINDOW_ENV, "63")
    monkeypatch.setenv(PROVIDER_LIMITER_PATH_ENV, str(limiter))
    runtime = g4_runtime_config(state_root=tmp_path)
    assert (runtime.provider_tpm, runtime.provider_rpm, runtime.provider_window_s) == (200000, 200, 63.0)
    assert runtime.shared_limiter_path == str(limiter)


def test_g4_runtime_rejects_wrong_deployment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    profile = g4_kh_profile()
    monkeypatch.setenv(profile.endpoint_env, "https://example.openai.azure.com/")
    monkeypatch.setenv(profile.deployment_env, "wrong")
    with pytest.raises(RuntimeError, match="must equal"):
        g4_runtime_config(state_root=tmp_path)


def test_m_tree_selector_fails_capacity_without_reanchoring_or_changing_control_wire(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import json
    from types import SimpleNamespace

    from aether.context_tree.config import CONTROL, M_TREE_V1
    from aether.model_hooks import ModelHooks
    from aether.model_profile import PROVIDER_CALLS_ALLOWED_ENV, PROVIDER_PROFILE_SHA256_ENV
    from aether.persistent_flat_advanced import PROVIDER_TOOL_SHAPE_FLAT
    from aether.persistent_provider_protocol import persistent_chat_provider_tools
    from aether.providers.chat_model import (
        ChatContextCapacityError,
        make_chat_callable,
    )
    from aether.research_glm_harbor_agent import (
        G4_PROFILE_SELECTOR_ENV,
        G4_REASONING_EFFORT_ENV,
        G4_REALITY_TRANSPORT_CONTROL,
    )
    from aether.runtime_ir import ACTION_SCHEMA

    class CaptureTransport:
        def __init__(self, *responses):
            self.responses = list(responses)
            self.requests: list[dict] = []

        def create(self, **request):
            self.requests.append(request)
            return self.responses.pop(0)

    def tool_response(call_id: str, *, reasoning: str = "") -> dict:
        return {
            "model": "FW-GLM-5.3-Flash",
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": reasoning,
                    "tool_calls": [{
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"arguments": {"path": "/tmp/input"}}),
                        },
                    }],
                },
            }],
            "usage": {"prompt_tokens": 41, "completion_tokens": 12, "total_tokens": 53},
        }

    monkeypatch.setenv(G4_PROFILE_SELECTOR_ENV, G4_PROFILE_SELECTOR)
    monkeypatch.setenv(G4_REASONING_EFFORT_ENV, G4_REASONING_EFFORT)
    _bind_route(monkeypatch)
    profile = g4_kh_profile()
    monkeypatch.setenv(profile.key_env, "offline-test-key")
    monkeypatch.setenv(PROVIDER_CALLS_ALLOWED_ENV, "1")
    monkeypatch.delenv(PROVIDER_TPM_ENV, raising=False)
    monkeypatch.delenv(PROVIDER_RPM_ENV, raising=False)
    monkeypatch.delenv(PROVIDER_LIMITER_PATH_ENV, raising=False)
    monkeypatch.delenv("AETHER_PROVIDER_WINDOW_ANCHOR", raising=False)
    monkeypatch.setenv("AETHER_PROVIDER_TPM_WINDOW_S", "1")

    # Pin the unmodified control selector's historical route and wire identity.
    control = g4_runtime_config(
        state_root=tmp_path / "control",
        reality_transport_mode=G4_REALITY_TRANSPORT_CONTROL,
        capacity_recovery_mode="control",
        context_mode=CONTROL,
    )
    assert control.profile.sha256() == (
        "403fa47b34bbece32e87f51fccd989fdc8329b6beadbb1642c0db12291b71b1d"
    )
    monkeypatch.setenv(PROVIDER_PROFILE_SHA256_ENV, control.profile.sha256())
    control_transport = CaptureTransport(tool_response("control-call"))
    control_model = make_chat_callable(
        control.profile,
        role="solver",
        capture_rate_headers=True,
        tool_surface_mode="static_kernel_v1",
        tools=persistent_chat_provider_tools(
            advanced_tool_shape=PROVIDER_TOOL_SHAPE_FLAT,
            include_m_tree_zoom=False,
        ),
        client_factory=lambda **_kwargs: SimpleNamespace(
            chat=SimpleNamespace(completions=control_transport),
        ),
    )
    control_model(
        [{"role": "user", "content": "control wire identity fixture"}],
        max_output_tokens=32,
    )
    assert control_model.drain_telemetry()[0]["request_sha256"] == (
        "5f4c12861fc21b500e984e2cfc8354b474cd9110ffe8595f5893a490d89a6108"
    )

    # The selected M-TREE profile reaches the actual provider factory and model.
    runtime = g4_runtime_config(
        state_root=tmp_path / "m-tree",
        reality_transport_mode=G4_REALITY_TRANSPORT_CONTROL,
        capacity_recovery_mode="control",
        context_mode=M_TREE_V1,
    )
    assert runtime.profile.chat_capacity_reanchor_recovery_mode == "off"
    assert runtime.profile.chat_capacity_overflow_action == "m_tree_epoch_overflow"
    assert runtime.profile.manifest()["chat_capacity_overflow_action"] == "m_tree_epoch_overflow"
    assert runtime.profile.sha256() != control.profile.sha256()
    monkeypatch.setenv(PROVIDER_PROFILE_SHA256_ENV, runtime.profile.sha256())
    monkeypatch.setenv(PROVIDER_TPM_ENV, "100000")
    transport = CaptureTransport(
        tool_response("m-tree-call-1", reasoning="r" * 450_000),
        tool_response("unexpected-reanchor-call"),
    )
    solver = make_chat_callable(
        runtime.profile,
        role="solver",
        capture_rate_headers=True,
        tool_surface_mode="static_kernel_v1",
        tools=persistent_chat_provider_tools(
            advanced_tool_shape=PROVIDER_TOOL_SHAPE_FLAT,
            include_m_tree_zoom=True,
        ),
        client_factory=lambda **_kwargs: SimpleNamespace(
            chat=SimpleNamespace(completions=transport),
        ),
    )
    first_messages = [
        {"role": "system", "content": "[context_packet]\ninitial state"},
        {"role": "user", "content": "task"},
    ]
    hooks = ModelHooks(
        solver,
        lambda _messages, **_kwargs: "{}",
        run_id="m-tree-run",
        task_id="m-tree-task",
        solver_max_output_tokens=runtime.solver_max_output_tokens,
    )
    compiled = SimpleNamespace(
        action_schema=ACTION_SCHEMA,
        config_realization={},
        selected_capability_ids=lambda: set(),
    )
    hooks.solve(first_messages, compiled)
    assert any(
        tool["function"]["name"] == "zoom"
        for tool in transport.requests[0]["tools"]
    )
    before = solver.export_continuity_scope(run_id="m-tree-run", task_id="m-tree-task")
    assert before is not None

    with pytest.raises(ChatContextCapacityError, match="m_tree_epoch_overflow"):
        solver.call_with_telemetry_scope(
            [{"role": "system", "content": "[context_packet]\nnext state"}],
            max_output_tokens=runtime.solver_max_output_tokens,
            run_id="m-tree-run",
            task_id="m-tree-task",
            call_generation=2,
        )

    after = solver.export_continuity_scope(run_id="m-tree-run", task_id="m-tree-task")
    assert after == before
    assert len(transport.requests) == 1
    events = solver.drain_telemetry()
    assert len(events) == 2
    assert events[1]["status"] == "failed"
    assert events[1]["throughput_single_request_admission"] == "rejected_local_capacity"
    assert events[1].get("throughput_capacity_reanchor") is not True
    assert not any(
        event.get("event_kind") == "chat_continuity_capacity_reanchor"
        for event in solver.drain_continuity_admission_telemetry()
    )


def test_agent_selector_is_explicit_research_surface() -> None:
    assert GLMResearchHarborAgent.name() == "aether-glm-research"
    assert GLMResearchHarborAgent.version(object.__new__(GLMResearchHarborAgent)) == "revision-kh-glm-harbor-v1"


def test_run_kh_sync_passes_uncapped_exact_kh_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    captured: dict[str, object] = {}

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-1"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs):
            del args, kwargs
            self.closed = False
        def set_verifier_world_roots(self, roots):
            captured["verifier_roots"] = roots
        def close(self):
            self.closed = True
            captured["closed"] = True

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    class DummySolver:
        def bind_run_cancellation(self, event):
            captured["bound_cancel"] = event

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", lambda *args, **kwargs: DummySolver())
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: captured.setdefault("updated", record))
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(
        mod,
        "run_task",
        lambda **kwargs: captured.setdefault("run_task_kwargs", kwargs) or {"status": "submitted"},
    )

    logs = tmp_path / "logs"
    logs.mkdir()
    record = mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="repair the task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    kwargs = captured["run_task_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["max_steps"] is None
    assert kwargs["max_solver_turns"] is None
    assert kwargs["max_accepted_task_actions"] is None
    assert kwargs["solver_max_output_tokens"] == 32768
    assert kwargs["run_timeout_s"] == 28800.0
    for key, value in G4_KH_RUN_TASK_CONFIG.items():
        assert kwargs[key] == value
    assert kwargs["model_profile"].model_id == "FW-GLM-5.3-Flash-par"
    assert kwargs["model_profile"].solver_reasoning_effort == "high"
    assert record["research_harbor_adapter"]["official_harbor_grader_owned"] is True
    assert record["research_harbor_adapter"]["model_verifier_disabled"] is True
    assert (logs / "aether_run_record.json").is_file()
    assert captured["closed"] is True


def test_research_agent_does_not_change_production_harbor_selector() -> None:
    from aether.harbor_agent import AetherHarborAgent

    assert AetherHarborAgent.name() == "aether"
    assert GLMResearchHarborAgent.name() == "aether-glm-research"


def test_g4_runtime_allows_explicit_jobs_surface(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aether.research_glm_harbor_agent import (
        G4_TOOL_SURFACE_ENV,
        G4_TOOL_SURFACE_JOBS_V1,
        g4_tool_surface_mode,
    )

    _bind_route(monkeypatch)
    monkeypatch.setenv(G4_TOOL_SURFACE_ENV, G4_TOOL_SURFACE_JOBS_V1)
    assert g4_tool_surface_mode() == "static_kernel_jobs_v1"
    runtime = g4_runtime_config(state_root=tmp_path)
    assert runtime.solver_tool_surface_mode == "static_kernel_jobs_v1"


def test_g4_runtime_rejects_unknown_tool_surface(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aether.research_glm_harbor_agent import G4_TOOL_SURFACE_ENV, g4_tool_surface_mode

    _bind_route(monkeypatch)
    monkeypatch.setenv(G4_TOOL_SURFACE_ENV, "mystery")
    with pytest.raises(RuntimeError, match="must be one of"):
        g4_tool_surface_mode()
    with pytest.raises(RuntimeError, match="must be one of"):
        g4_runtime_config(state_root=tmp_path)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("observation_history_v1", "observation_history_v1"),
        ("reasoning_actions_no_results_v1", "reasoning_actions_no_results_v1"),
        ("reasoning_latest_action_no_results_v1", "reasoning_latest_action_no_results_v1"),
    ],
)
def test_g4_runtime_allows_explicit_reality_transport(
    mode: str, expected: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aether.research_glm_harbor_agent import (
        G4_REALITY_TRANSPORT_ENV,
        g4_reality_transport_mode,
    )

    _bind_route(monkeypatch)
    monkeypatch.setenv(G4_REALITY_TRANSPORT_ENV, mode)
    assert g4_reality_transport_mode() == expected
    runtime = g4_runtime_config(state_root=tmp_path)
    assert runtime.solver_reality_transport_mode == expected


def test_g4_runtime_rejects_unknown_reality_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aether.research_glm_harbor_agent import (
        G4_REALITY_TRANSPORT_ENV,
        g4_reality_transport_mode,
    )

    _bind_route(monkeypatch)
    monkeypatch.setenv(G4_REALITY_TRANSPORT_ENV, "mystery")
    with pytest.raises(RuntimeError, match="must be one of"):
        g4_reality_transport_mode()
    with pytest.raises(RuntimeError, match="must be one of"):
        g4_runtime_config(state_root=tmp_path)


def test_run_kh_sync_applies_explicit_pt_ra_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(
        mod.G4_REALITY_TRANSPORT_ENV,
        mod.G4_REALITY_TRANSPORT_PT_RA,
    )
    captured: dict[str, object] = {}

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-pt-ra"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    class DummySolver:
        def bind_run_cancellation(self, event): pass

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", lambda *args, **kwargs: DummySolver())
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(
        mod,
        "run_task",
        lambda **kwargs: captured.setdefault("run_task_kwargs", kwargs) or {"status": "submitted"},
    )

    logs = tmp_path / "logs-pt-ra"
    logs.mkdir()
    mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    kwargs = captured["run_task_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["solver_reality_transport_mode"] == mod.G4_REALITY_TRANSPORT_PT_RA


def test_run_kh_sync_restores_provider_runtime_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    sentinel = str(tmp_path / "sentinel-limiter.json")
    monkeypatch.setenv(PROVIDER_LIMITER_PATH_ENV, sentinel)
    captured = {}

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-env"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    class DummySolver:
        def bind_run_cancellation(self, event): pass

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", lambda *args, **kwargs: DummySolver())
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(mod, "run_task", lambda **kwargs: {"status": "submitted"})

    logs = tmp_path / "logs-env"
    logs.mkdir()
    mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    assert __import__("os").environ[PROVIDER_LIMITER_PATH_ENV] == sentinel

def test_g4_async_selector_is_default_off_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aether.research_glm_harbor_agent as mod

    monkeypatch.delenv(mod.G4_ASYNC_MODE_ENV, raising=False)
    assert mod.g4_async_mode() == mod.G4_ASYNC_CONTROL == "control"
    monkeypatch.setenv(
        mod.G4_ASYNC_MODE_ENV,
        mod.G4_ASYNC_INDEPENDENT_JOBS_V1,
    )
    assert mod.g4_async_mode() == "independent_jobs_v1"
    monkeypatch.setenv(mod.G4_ASYNC_MODE_ENV, "mystery")
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_async_mode()


def test_run_kh_sync_applies_independent_jobs_only_with_jobs_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(mod.G4_TOOL_SURFACE_ENV, mod.G4_TOOL_SURFACE_JOBS_V1)
    monkeypatch.setenv(
        mod.G4_ASYNC_MODE_ENV,
        mod.G4_ASYNC_INDEPENDENT_JOBS_V1,
    )
    captured: dict[str, object] = {}

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-async"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    class DummySolver:
        def bind_run_cancellation(self, event): pass

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", lambda *args, **kwargs: DummySolver())
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(
        mod,
        "run_task",
        lambda **kwargs: captured.setdefault("run_task_kwargs", kwargs) or {"status": "submitted"},
    )

    logs = tmp_path / "logs-async"
    logs.mkdir()
    mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    kwargs = captured["run_task_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["solver_tool_surface_mode"] == mod.G4_TOOL_SURFACE_JOBS_V1
    assert kwargs["solver_async_mode"] == mod.G4_ASYNC_INDEPENDENT_JOBS_V1
    record = __import__("json").loads((logs / "aether_run_record.json").read_text())
    assert record["research_harbor_adapter"]["kh_run_task_config"]["solver_async_mode"] == "independent_jobs_v1"


def test_run_kh_sync_rejects_async_without_jobs_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(
        mod.G4_ASYNC_MODE_ENV,
        mod.G4_ASYNC_INDEPENDENT_JOBS_V1,
    )

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-async-invalid"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())

    logs = tmp_path / "logs-async-invalid"
    logs.mkdir()
    with pytest.raises(RuntimeError, match="requires static_kernel_jobs_v1"):
        mod._run_kh_sync(
            environment=object(),
            event_loop=object(),
            context=DummyContext(),
            instruction="task",
            logs_dir=logs,
            mcp_servers=(),
            cancellation_event=__import__("threading").Event(),
            agent_timeout_sec=28800.0,
            run_started_monotonic=1.0,
        )

def test_run_kh_sync_defaults_to_disabled_verifier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.delenv("AETHER_RESEARCH_JUDGE_VERIFIER_ARM", raising=False)
    captured: dict[str, object] = {}

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-judge-control"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    class DummySolver:
        def bind_run_cancellation(self, event): pass

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", lambda *args, **kwargs: DummySolver())
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(
        mod, "run_task",
        lambda **kwargs: captured.setdefault("run_task_kwargs", kwargs) or {"status": "submitted"},
    )

    logs = tmp_path / "logs"
    logs.mkdir()
    record = mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="repair the task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    kwargs = captured["run_task_kwargs"]
    assert isinstance(kwargs, dict)
    assert isinstance(kwargs["verifier_model"], mod.DisabledVerifier)
    assert record["research_harbor_adapter"]["model_verifier_disabled"] is True
    assert record["research_harbor_adapter"]["research_judge_verifier_arm"] == "control"


def test_run_kh_sync_can_select_typed_judge_v3_verifier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv("AETHER_RESEARCH_JUDGE_VERIFIER_ARM", "v3_typed")
    captured: dict[str, object] = {}
    sentinel = object()

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-judge-v3"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    class DummySolver:
        def bind_run_cancellation(self, event): pass

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", lambda *args, **kwargs: DummySolver())
    monkeypatch.setattr(mod, "build_selected_judge_v3_verifier", lambda: sentinel)
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(
        mod, "run_task",
        lambda **kwargs: captured.setdefault("run_task_kwargs", kwargs) or {"status": "submitted"},
    )

    logs = tmp_path / "logs"
    logs.mkdir()
    record = mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="repair the task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    kwargs = captured["run_task_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["verifier_model"] is sentinel
    assert kwargs["thin_terminal_verifier_mode"] == "terminal_verifier_v1"
    assert record["research_harbor_adapter"]["model_verifier_disabled"] is False
    assert record["research_harbor_adapter"]["research_judge_verifier_arm"] == "v3_typed"

def test_g4_runtime_operation_refresh_selector_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aether.research_glm_harbor_agent as mod

    monkeypatch.delenv(mod.G4_RUNTIME_OPERATION_REFRESH_ENV, raising=False)
    assert (
        mod.g4_runtime_operation_refresh_mode()
        == mod.G4_RUNTIME_OPERATION_REFRESH_CONTROL
        == "control"
    )
    monkeypatch.setenv(
        mod.G4_RUNTIME_OPERATION_REFRESH_ENV,
        mod.G4_RUNTIME_OPERATION_REFRESH_V1,
    )
    assert mod.g4_runtime_operation_refresh_mode() == "runtime_operation_refresh_v1"
    monkeypatch.setenv(mod.G4_RUNTIME_OPERATION_REFRESH_ENV, "mystery")
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_runtime_operation_refresh_mode()


def test_g4_refresh_treatment_requires_jobs_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(
        mod.G4_RUNTIME_OPERATION_REFRESH_ENV,
        mod.G4_RUNTIME_OPERATION_REFRESH_V1,
    )
    monkeypatch.delenv(mod.G4_TOOL_SURFACE_ENV, raising=False)

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-refresh-guard"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())

    logs = tmp_path / "logs-refresh-guard"
    logs.mkdir()
    with pytest.raises(RuntimeError, match="refresh treatment requires static_kernel_jobs_v1"):
        mod._run_kh_sync(
            environment=object(),
            event_loop=object(),
            context=DummyContext(),
            instruction="repair the task",
            logs_dir=logs,
            mcp_servers=(),
            cancellation_event=__import__("threading").Event(),
            agent_timeout_sec=28800.0,
            run_started_monotonic=1.0,
        )


def test_g4_refresh_treatment_is_one_factor_over_jobs_control(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(mod.G4_TOOL_SURFACE_ENV, mod.G4_TOOL_SURFACE_JOBS_V1)
    monkeypatch.setenv(mod.G4_ASYNC_MODE_ENV, mod.G4_ASYNC_CONTROL)
    monkeypatch.setenv(
        mod.G4_RUNTIME_OPERATION_REFRESH_ENV,
        mod.G4_RUNTIME_OPERATION_REFRESH_V1,
    )
    captured: dict[str, object] = {}

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-refresh"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    class DummySolver:
        def bind_run_cancellation(self, event): pass

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", lambda *args, **kwargs: DummySolver())
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(
        mod,
        "run_task",
        lambda **kwargs: captured.setdefault("run_task_kwargs", kwargs) or {"status": "submitted"},
    )

    logs = tmp_path / "logs-refresh"
    logs.mkdir()
    record = mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="repair the task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    kwargs = captured["run_task_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["solver_tool_surface_mode"] == "static_kernel_jobs_v1"
    assert kwargs["solver_async_mode"] == "control"
    assert kwargs["refresh_runtime_operation_status"] is True
    assert record["research_harbor_adapter"]["runtime_operation_refresh_mode"] == (
        "runtime_operation_refresh_v1"
    )

def test_g4_completion_signal_selector_defaults_control_and_allows_authority_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aether.research_glm_harbor_agent as mod

    monkeypatch.delenv(mod.G4_COMPLETION_SIGNAL_ENV, raising=False)
    assert mod.g4_completion_signal_mode() == mod.G4_COMPLETION_SIGNAL_CONTROL == "control"
    monkeypatch.setenv(
        mod.G4_COMPLETION_SIGNAL_ENV,
        mod.G4_COMPLETION_SIGNAL_VERIFICATION_AUTHORITY_V2,
    )
    assert mod.g4_completion_signal_mode() == "verification_authority_v2"
    monkeypatch.setenv(mod.G4_COMPLETION_SIGNAL_ENV, "mystery")
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_completion_signal_mode()


def test_g4_runtime_manifest_binds_authority_v2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(
        mod.G4_COMPLETION_SIGNAL_ENV,
        mod.G4_COMPLETION_SIGNAL_VERIFICATION_AUTHORITY_V2,
    )
    runtime = mod.g4_runtime_config(state_root=tmp_path)
    assert runtime.solver_completion_signal_mode == "verification_authority_v2"
    assert runtime.manifest()["solver_completion_signal_mode"] == "verification_authority_v2"


def test_g4_authority_v2_is_one_factor_over_completion_control(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(
        mod.G4_COMPLETION_SIGNAL_ENV,
        mod.G4_COMPLETION_SIGNAL_VERIFICATION_AUTHORITY_V2,
    )
    captured: dict[str, object] = {}

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-authority-v2"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    class DummySolver:
        def bind_run_cancellation(self, event): pass

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", lambda *args, **kwargs: DummySolver())
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(
        mod,
        "run_task",
        lambda **kwargs: captured.setdefault("run_task_kwargs", kwargs) or {"status": "submitted"},
    )

    logs = tmp_path / "logs-authority-v2"
    logs.mkdir()
    record = mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="repair the task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    kwargs = captured["run_task_kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["solver_completion_signal_mode"] == "verification_authority_v2"
    for key, value in mod.G4_KH_RUN_TASK_CONFIG.items():
        assert kwargs[key] == value
    assert record["research_harbor_adapter"]["completion_signal_mode"] == (
        "verification_authority_v2"
    )
    assert record["research_harbor_adapter"]["runtime"]["solver_completion_signal_mode"] == (
        "verification_authority_v2"
    )



def test_vf1_builds_same_route_same_effort_verifier_and_enables_finish_hook(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(
        mod.G4_SAME_MODEL_VERIFIER_ENV,
        mod.G4_SAME_MODEL_VERIFIER_VF1,
    )
    monkeypatch.delenv("AETHER_RESEARCH_JUDGE_VERIFIER_ARM", raising=False)
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_ENV, mod.G4_JUDGE_ADVICE_CONTROL)
    captured: dict[str, object] = {}
    built: list[tuple[str, str | None, object]] = []

    class DummyModel:
        def __init__(self, role: str):
            self.role = role
        def bind_run_cancellation(self, event): pass

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-vf1"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    def build(profile, *args, **kwargs):
        role = kwargs.get("role", "solver")
        built.append((role, kwargs.get("effort"), profile))
        return DummyModel(role)

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "make_chat_callable", build)
    monkeypatch.setattr(mod, "_update_agent_context", lambda context, record: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())
    monkeypatch.setattr(
        mod, "run_task",
        lambda **kwargs: captured.setdefault("run_task_kwargs", kwargs) or {"status": "submitted"},
    )

    logs = tmp_path / "logs-vf1"
    logs.mkdir()
    record = mod._run_kh_sync(
        environment=object(),
        event_loop=object(),
        context=DummyContext(),
        instruction="repair the task",
        logs_dir=logs,
        mcp_servers=(),
        cancellation_event=__import__("threading").Event(),
        agent_timeout_sec=28800.0,
        run_started_monotonic=1.0,
    )
    kwargs = captured["run_task_kwargs"]
    assert isinstance(kwargs, dict)
    assert [role for role, _effort, _profile in built] == ["solver", "verifier"]
    solver_profile = built[0][2]
    verifier_profile = built[1][2]
    assert solver_profile is verifier_profile
    assert built[1][1] == solver_profile.solver_reasoning_effort == "high"
    assert getattr(kwargs["verifier_model"], "role") == "verifier"
    assert kwargs["thin_terminal_verifier_mode"] == "terminal_verifier_v1"
    assert record["research_harbor_adapter"]["model_verifier_disabled"] is False
    assert (
        record["research_harbor_adapter"]["same_model_verifier_mode"]
        == mod.G4_SAME_MODEL_VERIFIER_VF1
    )


def test_vf1_rejects_mixed_judge_arm_before_model_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import aether.research_glm_harbor_agent as mod

    _bind_route(monkeypatch)
    monkeypatch.setenv(
        mod.G4_SAME_MODEL_VERIFIER_ENV,
        mod.G4_SAME_MODEL_VERIFIER_VF1,
    )
    monkeypatch.setenv("AETHER_RESEARCH_JUDGE_VERIFIER_ARM", "v3_typed")

    class DummyContext:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-vf1-mixed"

    class DummyExecutor:
        workspace_root = "/app/workspace"
        def __init__(self, *args, **kwargs): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    class DummyEnvMap:
        workspace_root = "/app/workspace"

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", DummyExecutor)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **kwargs: DummyEnvMap())
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda instruction: ())

    logs = tmp_path / "logs-vf1-mixed"
    logs.mkdir()
    with pytest.raises(RuntimeError, match="cannot be combined with JUDGE"):
        mod._run_kh_sync(
            environment=object(),
            event_loop=object(),
            context=DummyContext(),
            instruction="repair the task",
            logs_dir=logs,
            mcp_servers=(),
            cancellation_event=__import__("threading").Event(),
            agent_timeout_sec=28800.0,
            run_started_monotonic=1.0,
        )


def test_rev93_glm_route_profiles_have_exact_identity_and_capacity() -> None:
    import aether.research_glm_harbor_agent as mod

    expected = {
        "glm-research-v1": ("FW-GLM-5.3-Flash", "FW-GLM-5.3-Flash", 9_000, 9),
        "glm-research-par-v1": ("FW-GLM-5.3-Flash-par", "FW-GLM-5.3-Flash", 420_000, 420),
        "glm-research-par2-v1": ("FW-GLM-5.3-Flash-par-2", "FW-GLM-5.3-Flash", 36_000, 36),
    }
    assert mod.G4_PROFILE_SELECTORS == frozenset(expected)
    limiter_names = set()
    for selector, (deployment, returned, client_tpm, client_rpm) in expected.items():
        profile = GLM_RESEARCH_PROFILES[selector]
        limits = mod.G4_ROUTE_LIMITS[selector]
        assert profile.model_id == deployment
        assert (profile.expected_returned_model or profile.model_id) == returned
        assert limits["client_tpm"] == client_tpm
        assert limits["client_rpm"] == client_rpm
        limiter_names.add(limits["limiter_name"])
    assert len(limiter_names) == 3


@pytest.mark.parametrize(
    ("selector", "deployment", "client_tpm", "observed_tpm"),
    [
        ("glm-research-v1", "FW-GLM-5.3-Flash", 9_000, 10_000),
        ("glm-research-par-v1", "FW-GLM-5.3-Flash-par", 420_000, 450_000),
        ("glm-research-par2-v1", "FW-GLM-5.3-Flash-par-2", 36_000, 40_000),
    ],
)
def test_rev93_glm_route_selector_reaches_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    selector: str,
    deployment: str,
    client_tpm: int,
    observed_tpm: int,
) -> None:
    import aether.research_glm_harbor_agent as mod

    profile = GLM_RESEARCH_PROFILES[selector]
    monkeypatch.setenv(mod.G4_PROFILE_SELECTOR_ENV, selector)
    monkeypatch.setenv(profile.endpoint_env, "https://example.openai.azure.com/")
    monkeypatch.setenv(profile.deployment_env, deployment)
    for name in (
        PROVIDER_TPM_ENV,
        PROVIDER_RPM_ENV,
        PROVIDER_WINDOW_ENV,
        PROVIDER_LIMITER_PATH_ENV,
    ):
        monkeypatch.delenv(name, raising=False)

    runtime = mod.g4_runtime_config(state_root=tmp_path)
    assert runtime.profile_selector == selector
    assert runtime.deployment == deployment
    assert runtime.provider_tpm == client_tpm
    assert runtime.observed_route_tpm == observed_tpm


def test_rev93_glm_route_selector_rejects_unknown_route(monkeypatch: pytest.MonkeyPatch) -> None:
    import aether.research_glm_harbor_agent as mod

    monkeypatch.setenv(mod.G4_PROFILE_SELECTOR_ENV, "made-up-route")
    with pytest.raises(RuntimeError, match=mod.G4_PROFILE_SELECTOR_ENV):
        mod.g4_profile_selector()
