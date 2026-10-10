from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import os
import sys

import pytest

from aether import launch
from aether import provider_runtime_canary as canary
from aether.model_profile import PRODUCTION_PROFILE


def _fake_harbor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        launch,
        "_harbor_identity",
        lambda: {"version": "0.20.0", "agent_selector": "aether.harbor_agent:AetherHarborAgent"},
    )


def _runtime_identity() -> dict[str, object]:
    return {
        "transport": "responses_websocket",
        "websocket_client_required": True,
        "websocket_client_version": "1.9.2",
        "create_connection_available": True,
        "network_calls_performed": 0,
        "provider_credentials_read": False,
    }


def _provider_budget() -> dict[str, object]:
    role = {
        "max_input_tokens": 120000,
        "max_output_tokens": 16000,
        "input_gbp_per_million": "0.20",
        "output_gbp_per_million": "1.20",
    }
    return {
        "schema_version": "aether.provider_budget.v1",
        "budget_id": "provider-canary-test-budget",
        "model_id": "gpt-5.6-luna",
        "currency": "GBP",
        "budget_constrained": True,
        "total_cap_gbp": "1",
        "provider_max_retries": 0,
        "provider_sdk_max_retries": 0,
        "solver_turn_budget": 4,
        "agent_timeout_sec": 120.0,
        "vm_incremental_cap_gbp": "0",
        "roles": {
            "solver": {**role, "max_provider_creates": 2},
            "verifier": {**role, "max_provider_creates": 1},
            "vision": {**role, "max_provider_creates": 0, "max_output_tokens": 8000},
        },
    }


def _world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _fake_harbor(monkeypatch)
    # Keep hermetic provider-admission records out of the user's durable
    # official-launch namespace.
    monkeypatch.setenv("AETHER_OFFICIAL_LAUNCH_STATE_DIR", str(tmp_path / "official-launch-admission"))
    monkeypatch.setattr(launch, "_provider_runtime_identity", _runtime_identity)
    monkeypatch.setenv(PRODUCTION_PROFILE.endpoint_env, "https://unit.invalid")
    monkeypatch.setenv(PRODUCTION_PROFILE.deployment_env, "unit-deployment")
    monkeypatch.setenv(PRODUCTION_PROFILE.key_env, "unit-secret")
    package = tmp_path / "installed" / "aether"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# package\n")
    (package / "core.py").write_text("VALUE=1\n")
    task = tmp_path / "task"
    task.mkdir()
    (task / "task.toml").write_text("instruction='test'\n")
    (task / "data.txt").write_text("input\n")
    evidence = tmp_path / "evidence"
    return package, task, evidence


def _receipt(package: Path, *, now: float = 2_000_000_000.0) -> dict[str, object]:
    closure = launch.package_closure(package)
    return {
        "schema_version": "aether.provider_runtime_canary.v1",
        "passed": True,
        "label": "unit",
        "created_at_unix_s": now - 2.0,
        "finished_at_unix_s": now - 1.0,
        "elapsed_s": 1.0,
        "requested_width": 1,
        "completed_provider_calls": 1,
        "python_executable": str(Path(sys.executable).resolve()),
        "package_root": str(package.resolve()),
        "candidate": {
            "package_closure_sha256": closure.sha256,
            "package_file_count": closure.file_count,
            "model_profile_sha256": PRODUCTION_PROFILE.sha256(),
            "tool_schema_sha256": launch.production_tool_schema_sha256(),
            "model_id": PRODUCTION_PROFILE.model_id,
            "solver_reasoning_effort": PRODUCTION_PROFILE.solver_reasoning_effort,
        },
        "provider_route_sha256": launch._provider_route_sha256(),
        "provider_runtime": _runtime_identity(),
        "provider_policy": {
            "responses_websocket": True,
            "responses_background": False,
            "provider_max_retries": 0,
            "sdk_max_retries": 0,
            "poll_timeout_s": 180,
            "max_output_tokens": 2000,
            "budget_constrained": True,
        },
        "provider_budget": {
            "budget_id": "canary-unit-budget",
            "model_id": PRODUCTION_PROFILE.model_id,
            "contract_sha256": "e" * 64,
            "total_cap_gbp": "0.1",
            "max_total_provider_creates": 1,
            "snapshot": {
                "aggregate_create_count": 1,
                "role_create_counts": {"solver": 1, "verifier": 0, "vision": 0},
            },
        },
        "worker": {
            "passed": True,
            "error": None,
            "transport_mode": "websocket",
            "native_tool_name": "read_file",
            "native_tool_call_count": 1,
            "attempt_ordinal": 1,
            "provider_terminal_failure": None,
            "raw_sha256": "b" * 64,
        },
        "raw_model_output_persisted": False,
        "credential_values_persisted": False,
    }


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


def test_paid_dispatch_without_canary_is_blocked_before_harbor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, evidence = _world(tmp_path, monkeypatch)
    spec = launch.build_spec(
        task, run_id="no-canary", evidence_root=evidence,
        provider_calls_allowed=True, provider_budget_contract=_provider_budget(), package_root_override=package,
    )
    called = []
    with pytest.raises(launch.LaunchError, match="requires a bound successful provider canary"):
        launch.launch(spec, runner=lambda *a, **k: called.append((a, k)), package_root_override=package)
    assert called == []
    terminal = json.loads((evidence / "no-canary" / "terminal_launch_receipt.json").read_text())
    assert terminal["status"] == "launch_blocked"
    assert terminal["provider_credentials_read"] is False


def test_exact_fresh_canary_admits_same_runtime_and_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, evidence = _world(tmp_path, monkeypatch)
    now = 2_000_000_000.0
    canary = tmp_path / "canary.json"
    _write_receipt(canary, _receipt(package, now=now))
    spec = launch.build_spec(
        task, run_id="with-canary", evidence_root=evidence,
        provider_calls_allowed=True, provider_canary_receipt=canary,
        provider_budget_contract=_provider_budget(), package_root_override=package,
    )
    proof = launch._verify_provider_canary_receipt(
        spec, package_root_override=package, now_unix_s=now,
    )
    assert proof["status"] == "valid"
    assert proof["transport_mode"] == "websocket"
    assert proof["native_tool_name"] == "read_file"
    assert proof["completed_provider_calls"] == 1


def test_stale_canary_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, evidence = _world(tmp_path, monkeypatch)
    now = 2_000_000_000.0
    receipt = _receipt(package, now=now)
    receipt["created_at_unix_s"] = now - 1002.0
    receipt["finished_at_unix_s"] = now - 1001.0
    canary = tmp_path / "stale.json"
    _write_receipt(canary, receipt)
    spec = launch.build_spec(
        task, run_id="stale", evidence_root=evidence,
        provider_calls_allowed=True, provider_canary_receipt=canary,
        provider_budget_contract=_provider_budget(), package_root_override=package,
    )
    with pytest.raises(launch.LaunchError, match="canary is stale"):
        launch._verify_provider_canary_receipt(spec, package_root_override=package, now_unix_s=now)


def test_canary_tamper_after_spec_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, evidence = _world(tmp_path, monkeypatch)
    now = 2_000_000_000.0
    canary = tmp_path / "canary.json"
    receipt = _receipt(package, now=now)
    _write_receipt(canary, receipt)
    spec = launch.build_spec(
        task, run_id="tamper", evidence_root=evidence,
        provider_calls_allowed=True, provider_canary_receipt=canary,
        provider_budget_contract=_provider_budget(), package_root_override=package,
    )
    receipt["label"] = "tampered"
    _write_receipt(canary, receipt)
    with pytest.raises(launch.LaunchError, match="receipt hash changed"):
        launch._verify_provider_canary_receipt(spec, package_root_override=package, now_unix_s=now)


def test_canary_from_different_provider_route_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, evidence = _world(tmp_path, monkeypatch)
    now = 2_000_000_000.0
    canary = tmp_path / "canary.json"
    _write_receipt(canary, _receipt(package, now=now))
    spec = launch.build_spec(
        task, run_id="route-drift", evidence_root=evidence,
        provider_calls_allowed=True, provider_canary_receipt=canary,
        provider_budget_contract=_provider_budget(), package_root_override=package,
    )
    monkeypatch.setenv(PRODUCTION_PROFILE.deployment_env, "different-deployment")
    with pytest.raises(launch.LaunchError, match="route differs"):
        launch._verify_provider_canary_receipt(spec, package_root_override=package, now_unix_s=now)


def test_admitted_launch_binds_lifecycle_journal_before_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, evidence = _world(tmp_path, monkeypatch)
    now = 2_000_000_000.0
    canary = tmp_path / "canary.json"
    _write_receipt(canary, _receipt(package, now=now))
    spec = launch.build_spec(
        task, run_id="admitted", evidence_root=evidence,
        provider_calls_allowed=True, provider_canary_receipt=canary,
        provider_budget_contract=_provider_budget(), package_root_override=package,
    )
    monkeypatch.setattr(launch.time, "time", lambda: now)
    calls = []
    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        assert kwargs["env"]["AETHER_PROVIDER_LIFECYCLE_JOURNAL"] == str(
            evidence / "admitted" / "provider_lifecycle.jsonl"
        )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")
    terminal = launch.launch(spec, runner=runner, package_root_override=package)
    assert terminal["status"] == "completed"
    assert len(calls) == 1
    admission = json.loads((evidence / "admitted" / "provider_canary_admission.json").read_text())
    assert admission["status"] == "valid"
    assert terminal["provider_canary"]["receipt_sha256"] == launch.file_sha256(canary)


def test_canary_generator_uses_one_zero_retry_native_websocket_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aether import provider_runtime_canary as canary

    monkeypatch.setattr(canary, "require_provider_authorization", lambda profile: None)
    monkeypatch.setenv(PRODUCTION_PROFILE.endpoint_env, "https://unit.invalid")
    monkeypatch.setenv(PRODUCTION_PROFILE.deployment_env, "unit-deployment")
    fake_root = tmp_path / "installed" / "aether"
    fake_root.mkdir(parents=True)
    monkeypatch.setattr(canary, "package_root", lambda: fake_root)
    monkeypatch.setattr(
        canary, "package_closure",
        lambda: SimpleNamespace(sha256="c" * 64, file_count=7),
    )
    monkeypatch.setattr(canary, "production_tool_schema_sha256", lambda: "d" * 64)
    monkeypatch.setattr(canary, "_provider_runtime_identity", _runtime_identity)
    fake_guard = SimpleNamespace(
        contract=SimpleNamespace(
            model_id=PRODUCTION_PROFILE.model_id,
            roles={
                "solver": SimpleNamespace(max_provider_creates=1, max_output_tokens=2000),
                "verifier": SimpleNamespace(max_provider_creates=0, max_output_tokens=2000),
                "vision": SimpleNamespace(max_provider_creates=0, max_output_tokens=8000),
            },
        ),
        snapshot=lambda: {
            "aggregate_create_count": 1,
            "role_create_counts": {"solver": 1, "verifier": 0, "vision": 0},
        },
    )
    monkeypatch.setattr(canary, "provider_budget_guard_from_env", lambda: fake_guard)
    monkeypatch.setattr(canary, "budget_runtime_limits_from_env", lambda: {
        "budget_id": "canary-unit-budget",
        "model_id": PRODUCTION_PROFILE.model_id,
        "budget_contract_sha256": "e" * 64,
        "total_cap_gbp": "0.1",
        "max_total_provider_creates": 1,
    })

    class FakeModel:
        def __init__(self) -> None:
            self.calls = []
            self.closed = False
        def call_with_telemetry_scope(self, messages, *, run_id, task_id, max_output_tokens):
            self.calls.append((messages, run_id, task_id, max_output_tokens))
            return '{"kind":"act","action":{"kind":"read_file","arguments":{"path":"/tmp/x"}}}'
        def drain_telemetry(self):
            return ({
                "status": "completed",
                "provider_transport_mode": "websocket",
                "native_tool_name": "read_file",
                "native_tool_call_count": 1,
                "attempt_ordinal": 1,
            },)
        def close_run_transport(self):
            self.closed = True

    fake = FakeModel()
    kwargs_seen = {}
    def make_fake(**kwargs):
        kwargs_seen.update(kwargs)
        return fake
    monkeypatch.setattr(canary, "make_azure_callable", make_fake)
    receipt = canary.run_canary(label="unit")
    assert receipt["passed"] is True
    assert receipt["requested_width"] == 1
    assert receipt["completed_provider_calls"] == 1
    assert receipt["worker"]["native_tool_name"] == "read_file"
    assert receipt["raw_model_output_persisted"] is False
    assert receipt["credential_values_persisted"] is False
    assert kwargs_seen["responses_websocket"] is True
    assert kwargs_seen["responses_background"] is False
    assert kwargs_seen["max_retries"] == 0
    assert kwargs_seen["sdk_max_retries"] == 0
    assert kwargs_seen["poll_timeout_s"] == 180
    assert len(fake.calls) == 1
    assert fake.calls[0][3] == 2000
    assert receipt["provider_policy"]["budget_constrained"] is True
    assert receipt["provider_budget"]["max_total_provider_creates"] == 1
    assert fake.closed is True


def test_canary_generator_refuses_without_finite_budget_before_model_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    monkeypatch.setattr(canary, "require_provider_authorization", lambda _profile: None)
    monkeypatch.setattr(canary, "budget_runtime_limits_from_env", lambda: None)
    monkeypatch.setattr(canary, "provider_budget_guard_from_env", lambda: None)
    monkeypatch.setattr(canary, "make_azure_callable", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(RuntimeError, match="requires a finite provider budget"):
        canary.run_canary(label="missing-budget")
    assert calls == []


def test_canary_generator_refuses_budget_that_authorizes_extra_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    guard = SimpleNamespace(
        contract=SimpleNamespace(
            model_id=PRODUCTION_PROFILE.model_id,
            roles={
                "solver": SimpleNamespace(max_provider_creates=1, max_output_tokens=2000),
                "verifier": SimpleNamespace(max_provider_creates=1, max_output_tokens=2000),
                "vision": SimpleNamespace(max_provider_creates=0, max_output_tokens=8000),
            },
        )
    )
    monkeypatch.setattr(canary, "require_provider_authorization", lambda _profile: None)
    monkeypatch.setattr(canary, "budget_runtime_limits_from_env", lambda: {"budget_id": "x"})
    monkeypatch.setattr(canary, "provider_budget_guard_from_env", lambda: guard)
    monkeypatch.setattr(canary, "make_azure_callable", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(RuntimeError, match="may authorize only the one solver create"):
        canary.run_canary(label="extra-role")
    assert calls == []
