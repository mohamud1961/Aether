"""Vertical proof: G4 adapter env -> runtime config -> real callable -> model-visible request.

Past defects were "CLI accepted, runtime ignored", so each new mode is driven through
the adapter's own `_run_kh_sync`, the real chat-callable factory and the real thin loop.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import _capacity_scenarios as sc  # noqa: E402
import aether.providers.chat_model as chat_model  # noqa: E402
import aether.research_glm_harbor_agent as mod  # noqa: E402
from aether.execution import MemoryExecutor  # noqa: E402
from aether.model_hooks import ModelHooks  # noqa: E402
from aether.runtime_ir import CapabilityDescriptor, EnvMap  # noqa: E402
from aether.thin_loop import ThinLoopConfig, run_thin_loop  # noqa: E402

LIMIT = 32_768 + 24_000
FILES = ("a", "b", "c", "d", "e", "f", "g", "h")


def _drive_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transport: sc.Transport, *, token_limit: int):
    profile = mod.g4_kh_profile()
    monkeypatch.setenv(profile.endpoint_env, "https://example.openai.azure.com/")
    monkeypatch.setenv(profile.deployment_env, profile.model_id)
    monkeypatch.setenv(profile.key_env, "test-key-not-real")
    monkeypatch.setattr(chat_model, "require_provider_authorization", lambda _p: None)
    seen: dict[str, Any] = {}

    def factory(profile_arg, **kwargs):
        client = SimpleNamespace(chat=SimpleNamespace(completions=transport))
        model = chat_model.make_chat_completions_callable(
            profile=profile_arg, client_factory=lambda **_k: client, **kwargs,
        )
        model._throughput_pacer = sc.CapacityPacer(token_limit)  # only the limit is test-sized
        seen["solver"] = model
        return model

    def fake_run_task(**kwargs):
        seen["kwargs"] = kwargs
        hooks = ModelHooks(kwargs["solver_model"], lambda *_a, **_k: "{}", run_id="vert-run", task_id="vert-task")
        executor = MemoryExecutor(
            workspace_root="/app/workspace",
            files={f"/app/workspace/{n}.txt": f"CONTENT-OF-{n.upper()}" for n in FILES},
        )
        env = EnvMap(
            task_prompt="Inspect the files.", workspace_root="/app/workspace",
            visible_files=tuple(f"/app/workspace/{n}.txt" for n in FILES),
            capabilities={"filesystem": CapabilityDescriptor("filesystem", "files", tool_names=("read_file",))},
        )
        seen['result'] = run_thin_loop(env, executor, hooks, config=ThinLoopConfig(
            max_steps=seen["steps"], max_solver_turns=60,
            solver_reality_transport_mode=kwargs["solver_reality_transport_mode"],
            probe_runtime_capabilities=False,
        ))
        return {"status": "submitted"}

    class Ctx:
        metadata = {"aether_workspace_root": "/app/workspace"}
        context_id = "ctx-vert"

    class Exec:
        workspace_root = "/app/workspace"
        def __init__(self, *a, **k): pass
        def set_verifier_world_roots(self, roots): pass
        def close(self): pass

    monkeypatch.setattr(mod, "HarborEnvironmentExecutor", Exec)
    monkeypatch.setattr(mod, "_build_structural_envmap", lambda **k: SimpleNamespace(workspace_root="/app/workspace"))
    monkeypatch.setattr(mod, "make_chat_callable", factory)
    monkeypatch.setattr(mod, "_update_agent_context", lambda c, r: None)
    monkeypatch.setattr(mod, "literal_task_absolute_paths", lambda i: ())
    monkeypatch.setattr(mod, "run_task", fake_run_task)
    logs = tmp_path / "logs"
    logs.mkdir()
    seen["steps"] = 12
    record = mod._run_kh_sync(
        environment=object(), event_loop=object(), context=Ctx(), instruction="task",
        logs_dir=logs, mcp_servers=(), cancellation_event=threading.Event(),
        agent_timeout_sec=28800.0, run_started_monotonic=1.0,
    )
    return record, seen


def _routed(response: dict[str, Any]) -> dict[str, Any]:
    return {**response, "model": mod.g4_kh_profile().expected_returned_model}


def _checkpoints(count: int) -> list[dict[str, Any]]:
    return [_routed(sc.checkpoint_response()) for _ in range(count)]


def _reads(count: int) -> list[dict[str, Any]]:
    return [
        _routed(sc.tool_response(
            f"call-{i}", reasoning=f"reasoning-{i}-" + "r" * 12_000,
            args={"arguments": {"path": f"/app/workspace/{FILES[i % 8]}.txt"}},
        ))
        for i in range(count)
    ]


def test_capacity_selector_env_reaches_callable_request_and_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(mod.G4_CAPACITY_RECOVERY_ENV, mod.G4_CAPACITY_RECOVERY_CHECKPOINT_AT_CAPACITY_V1)
    transport = sc.Transport(*_reads(30), checkpoints=_checkpoints(4))
    record, seen = _drive_adapter(monkeypatch, tmp_path, transport, token_limit=LIMIT)
    assert seen["solver"]._capacity_reanchor_recovery_mode == "checkpoint_at_capacity_v1"
    forced = [i for i, r in enumerate(transport.requests) if sc.is_checkpoint_request(r)]
    assert forced, "capacity boundary never reached; the mode was not exercised"
    follow = transport.requests[forced[0] + 1]
    assert any(str(m.get("content", "")).startswith("[your_checkpoint 1,") for m in follow["messages"])
    adapter = record["research_harbor_adapter"]
    assert adapter["capacity_recovery_mode"] == "checkpoint_at_capacity_v1"
    assert adapter["runtime"]["solver_capacity_recovery_mode"] == "checkpoint_at_capacity_v1"
    assert "checkpoint_at_capacity" not in json.dumps(transport.requests)


def test_capacity_selector_default_keeps_profile_recovery_and_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(mod.G4_CAPACITY_RECOVERY_ENV, raising=False)
    transport = sc.Transport(*_reads(30), checkpoints=[])
    record, seen = _drive_adapter(monkeypatch, tmp_path, transport, token_limit=LIMIT)
    assert seen["solver"]._capacity_reanchor_recovery_mode == "recent_exchanges_v1"
    assert not any(sc.is_checkpoint_request(r) for r in transport.requests)
    assert "solver_capacity_recovery_mode" not in record["research_harbor_adapter"]["runtime"]


def test_capacity_selector_changes_runtime_hash_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile = mod.g4_kh_profile()
    monkeypatch.setenv(profile.endpoint_env, "https://example.openai.azure.com/")
    monkeypatch.setenv(profile.deployment_env, profile.model_id)
    monkeypatch.delenv(mod.G4_CAPACITY_RECOVERY_ENV, raising=False)
    control = mod.g4_runtime_config(state_root=tmp_path)
    monkeypatch.setenv(mod.G4_CAPACITY_RECOVERY_ENV, "checkpoint_at_capacity_v1")
    treated = mod.g4_runtime_config(state_root=tmp_path)
    assert treated.sha256 != control.sha256
    assert treated.profile.chat_capacity_reanchor_recovery_mode == "checkpoint_at_capacity_v1"
    monkeypatch.setenv(mod.G4_CAPACITY_RECOVERY_ENV, "recent_exchanges_v1")
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_capacity_recovery_mode()
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_runtime_config(state_root=tmp_path)


@pytest.mark.parametrize("mode", ["observation_history_v1", mod.G4_REALITY_TRANSPORT_PT_NR])
def test_ptnr_selector_env_reaches_model_visible_request(
    mode: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(mod.G4_REALITY_TRANSPORT_ENV, mode)
    transport = sc.Transport(*_reads(30))
    record, seen = _drive_adapter(monkeypatch, tmp_path, transport, token_limit=10**9)
    assert seen["kwargs"]["solver_reality_transport_mode"] == mode
    assert record["research_harbor_adapter"]["runtime"]["solver_reality_transport_mode"] == mode
    last = transport.requests[-1]
    assistants = [m for m in last["messages"] if m["role"] == "assistant"]
    assert len(assistants) >= 5
    historical_with_reasoning = sum("reasoning_content" in a for a in assistants[:-1])
    if mode == mod.G4_REALITY_TRANSPORT_PT_NR:
        assert historical_with_reasoning == 0
        assert "reasoning_content" in assistants[-1]
    else:
        assert historical_with_reasoning == len(assistants) - 1
    assert all(a["tool_calls"] for a in assistants)


def test_ptnr_selector_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod.G4_REALITY_TRANSPORT_ENV, "no_reasoning")
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_reality_transport_mode()



@pytest.mark.parametrize("env_value,expected", [(None, "high"), ("max", "max")])
def test_reasoning_effort_selector_reaches_model_request_and_identity(
    env_value: str | None, expected: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if env_value is None:
        monkeypatch.delenv(mod.G4_REASONING_EFFORT_ENV, raising=False)
    else:
        monkeypatch.setenv(mod.G4_REASONING_EFFORT_ENV, env_value)
    transport = sc.Transport(*_reads(6))
    record, seen = _drive_adapter(monkeypatch, tmp_path, transport, token_limit=10**9)
    assert transport.requests
    assert {r["reasoning_effort"] for r in transport.requests} == {expected}
    assert seen["kwargs"]["model_profile"].solver_reasoning_effort == expected
    assert seen["kwargs"]["runtime_identity"]["solver_reasoning_effort"] == expected
    assert record["research_harbor_adapter"]["solver_reasoning_effort"] == expected


def test_reasoning_effort_selector_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod.G4_REASONING_EFFORT_ENV, "xhigh")
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_reasoning_effort()
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_kh_profile()
