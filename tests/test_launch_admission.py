from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import os

import pytest

from aether import harbor_runtime
from aether import launch
from aether.model_profile import (
    PRODUCTION_PROFILE,
    PROVIDER_CALLS_ALLOWED_ENV,
    PROVIDER_PROFILE_SHA256_ENV,
)


def _fake_harbor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        launch,
        "_harbor_identity",
        lambda: {"version": "0.20.0", "agent_selector": "aether.harbor_agent:AetherHarborAgent"},
    )


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, provider: bool = False):
    _fake_harbor(monkeypatch)
    package = tmp_path / "installed" / "aether"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# package\n")
    (package / "core.py").write_text("VALUE=1\n")
    task = tmp_path / "task"
    task.mkdir()
    (task / "task.toml").write_text("instruction='test'\n")
    (task / "data.txt").write_text("input\n")
    evidence = tmp_path / "evidence"
    spec = launch.build_spec(
        task,
        run_id="run-001",
        evidence_root=evidence,
        provider_calls_allowed=provider,
        package_root_override=package,
    )
    return package, task, evidence, spec


def test_launch_spec_is_exact_and_retry_policy_is_fixed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, evidence, spec = _fixture(tmp_path, monkeypatch)
    launch.validate_spec(spec)
    assert spec["schema_version"] == "aether.launch.v1"
    assert spec["retry"] == {"max_attempts": 1, "max_retries": 0}
    assert spec["runtime"]["profile_sha256"] == PRODUCTION_PROFILE.sha256()
    assert spec["task"]["path"] == str(task.resolve())
    assert spec["evidence"]["root"] == str(evidence.resolve())
    assert spec["package"]["closure_sha256"] == launch.package_closure(package).sha256


def test_unknown_policy_looking_field_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, _, spec = _fixture(tmp_path, monkeypatch)
    spec["retry"]["retry_on_timeout"] = True
    with pytest.raises(launch.LaunchError, match="retry keys invalid"):
        launch.validate_spec(spec)


def test_unknown_top_level_field_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, _, spec = _fixture(tmp_path, monkeypatch)
    spec["verifier"] = {"command": "trust me"}
    with pytest.raises(launch.LaunchError, match="launch spec keys invalid"):
        launch.validate_spec(spec)


def test_task_tamper_blocks_before_dispatch_and_writes_terminal_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, evidence, spec = _fixture(tmp_path, monkeypatch)
    (task / "data.txt").write_text("tampered\n")
    called = []
    with pytest.raises(launch.LaunchError, match="task closure changed"):
        launch.launch(spec, runner=lambda *a, **k: called.append((a, k)), package_root_override=package)
    assert called == []
    receipt = json.loads((evidence / "run-001" / "terminal_launch_receipt.json").read_text())
    assert receipt["status"] == "launch_blocked"
    assert receipt["provider_credentials_read"] is False


def test_package_tamper_blocks_before_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, _, evidence, spec = _fixture(tmp_path, monkeypatch)
    (package / "core.py").write_text("VALUE=2\n")
    with pytest.raises(launch.LaunchError, match="package closure changed"):
        launch.launch(spec, package_root_override=package)
    receipt = json.loads((evidence / "run-001" / "terminal_launch_receipt.json").read_text())
    assert receipt["status"] == "launch_blocked"


def test_symlink_task_component_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_harbor(monkeypatch)
    real = tmp_path / "real-task"
    real.mkdir()
    (real / "x").write_text("x")
    alias = tmp_path / "task-link"
    alias.symlink_to(real, target_is_directory=True)
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    with pytest.raises(launch.LaunchError, match="symlink"):
        launch.build_spec(alias, run_id="r1", evidence_root=tmp_path / "evidence", package_root_override=package)


def test_symlink_inside_task_closure_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, task, _, _ = _fixture(tmp_path, monkeypatch)
    target = tmp_path / "outside"
    target.write_text("secret")
    (task / "alias").symlink_to(target)
    with pytest.raises(launch.LaunchError, match="symlink in closure"):
        launch.build_spec(task, run_id="r2", evidence_root=tmp_path / "e2", package_root_override=package)


def test_evidence_overlap_with_task_or_package_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_harbor(monkeypatch)
    package = tmp_path / "pkg"; package.mkdir(); (package / "__init__.py").write_text("")
    task = tmp_path / "task"; task.mkdir(); (task / "x").write_text("x")
    with pytest.raises(launch.LaunchError, match="evidence root overlaps task"):
        launch.build_spec(task, run_id="r", evidence_root=task / "logs", package_root_override=package)
    with pytest.raises(launch.LaunchError, match="evidence root overlaps installed package"):
        launch.build_spec(task, run_id="r", evidence_root=package / "logs", package_root_override=package)


def test_run_id_collision_is_refused_without_overwriting_existing_namespace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, _, evidence, spec = _fixture(tmp_path, monkeypatch)
    existing = evidence / "run-001"; existing.mkdir(parents=True)
    marker = existing / "keep"; marker.write_text("original")
    with pytest.raises(launch.LaunchError, match="run-id collision"):
        launch.launch(spec, package_root_override=package)
    assert marker.read_text() == "original"


def test_no_provider_authorization_blocks_without_runner_or_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, _, evidence, spec = _fixture(tmp_path, monkeypatch, provider=False)
    called = []
    terminal = launch.launch(spec, runner=lambda *a, **k: called.append((a, k)), package_root_override=package)
    assert terminal["status"] == "blocked_provider_not_authorized"
    assert terminal["provider_credentials_read"] is False
    assert called == []
    assert (evidence / "run-001" / "preflight_receipt.json").is_file()


def test_dry_run_never_dispatches_or_reads_provider_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, _, evidence, spec = _fixture(tmp_path, monkeypatch, provider=True)
    called = []
    terminal = launch.launch(spec, dry_run=True, runner=lambda *a, **k: called.append((a, k)), package_root_override=package)
    assert terminal["status"] == "dry_run_valid"
    assert terminal["provider_credentials_read"] is False
    assert called == []
    assert terminal["argv"][0] == os.sys.executable
    assert "--max-retries" in terminal["argv"]
    assert terminal["argv"][terminal["argv"].index("--max-retries") + 1] == "0"


def test_provider_free_smoke_uses_harbor_install_only_no_shell_and_no_secret_inheritance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, _, evidence, spec = _fixture(tmp_path, monkeypatch, provider=False)
    monkeypatch.setenv(PRODUCTION_PROFILE.key_env, "MUST_NOT_LEAK")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "MUST_NOT_LEAK")
    calls = []
    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="harbor smoke ok\n", stderr="")
    terminal = launch.launch(spec, smoke=True, runner=runner, package_root_override=package)
    assert terminal["status"] == "smoke_completed"
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert "--install-only" in argv
    assert kwargs["shell"] is False
    assert kwargs["env"][PROVIDER_CALLS_ALLOWED_ENV] == "0"
    assert PRODUCTION_PROFILE.key_env not in kwargs["env"]
    assert "AWS_SECRET_ACCESS_KEY" not in kwargs["env"]
    assert terminal["provider_credentials_read"] is False
    assert (evidence / "run-001" / "launcher.stdout").read_text() == "harbor smoke ok\n"


def test_authorized_provider_env_is_narrow_and_profile_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, _, evidence, spec = _fixture(tmp_path, monkeypatch, provider=True)
    monkeypatch.setenv(PRODUCTION_PROFILE.endpoint_env, "https://example.invalid")
    monkeypatch.setenv(PRODUCTION_PROFILE.deployment_env, "deployment")
    monkeypatch.setenv(PRODUCTION_PROFILE.key_env, "secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "other-secret")
    calls = []
    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="warn")
    terminal = launch.launch(spec, runner=runner, package_root_override=package)
    env = calls[0][1]["env"]
    assert env[PROVIDER_CALLS_ALLOWED_ENV] == "1"
    assert env[PROVIDER_PROFILE_SHA256_ENV] == PRODUCTION_PROFILE.sha256()
    assert env[PRODUCTION_PROFILE.endpoint_env] == "https://example.invalid"
    assert env[PRODUCTION_PROFILE.deployment_env] == "deployment"
    assert env[PRODUCTION_PROFILE.key_env] == "secret"
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert terminal["provider_credentials_read"] is True
    assert terminal["stdout"]["sha256"] == launch.file_sha256(evidence / "run-001" / "launcher.stdout")
    assert terminal["stderr"]["sha256"] == launch.file_sha256(evidence / "run-001" / "launcher.stderr")


def test_authorized_launch_requires_all_profile_owned_provider_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package, _, _, spec = _fixture(tmp_path, monkeypatch, provider=True)
    for name in (PRODUCTION_PROFILE.endpoint_env, PRODUCTION_PROFILE.deployment_env, PRODUCTION_PROFILE.key_env):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(launch.LaunchError, match="missing required environment variable"):
        launch.launch(spec, runner=lambda *a, **k: None, package_root_override=package)


def test_harbor_argv_is_exact_custom_agent_and_one_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, task, evidence, spec = _fixture(tmp_path, monkeypatch)
    argv = launch.harbor_argv(spec, evidence / "run-001")
    assert argv[:4] == [os.sys.executable, "-m", "harbor.cli.main", "run"]
    assert argv[argv.index("--path") + 1] == str(task.resolve())
    assert argv[argv.index("--agent") + 1] == "aether.harbor_agent:AetherHarborAgent"
    assert argv[argv.index("--n-attempts") + 1] == "1"
    assert argv[argv.index("--max-retries") + 1] == "0"
    assert argv[argv.index("--n-concurrent") + 1] == "1"


def test_provider_model_construction_refuses_before_factory_when_not_authorized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PROVIDER_CALLS_ALLOWED_ENV, raising=False)
    monkeypatch.delenv(PROVIDER_PROFILE_SHA256_ENV, raising=False)
    calls = []
    monkeypatch.setattr(harbor_runtime, "make_azure_callable", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(RuntimeError, match="not authorized"):
        harbor_runtime.build_selected_luna_models()
    assert calls == []


def test_provider_model_construction_refuses_wrong_profile_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PROVIDER_CALLS_ALLOWED_ENV, "1")
    monkeypatch.setenv(PROVIDER_PROFILE_SHA256_ENV, "0" * 64)
    calls = []
    monkeypatch.setattr(harbor_runtime, "make_azure_callable", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(RuntimeError, match="profile hash"):
        harbor_runtime.build_selected_luna_models()
    assert calls == []


def test_launch_schema_file_is_strict() -> None:
    schema_path = Path(launch.__file__).with_name("launch_schema.json")
    schema = json.loads(schema_path.read_text())
    assert schema["additionalProperties"] is False
    assert schema["properties"]["retry"]["additionalProperties"] is False
    assert schema["properties"]["provider"]["additionalProperties"] is False
    assert schema["properties"]["metadata"]["type"] == "object"


def test_child_environment_carries_nonsecret_custody_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _package, _task, _evidence, spec = _fixture(tmp_path, monkeypatch, provider=False)
    monkeypatch.setenv("AETHER_SOURCE_COMMIT", "c" * 40)
    monkeypatch.setenv("AETHER_RUNTIME_MANIFEST_SHA256", "d" * 64)
    child = launch._child_environment(spec)
    assert child["AETHER_SOURCE_COMMIT"] == "c" * 40
    assert child["AETHER_RUNTIME_MANIFEST_SHA256"] == "d" * 64
    assert child["AETHER_CAMPAIGN_ID"] == spec["runtime"]["profile_id"]
    assert child["AETHER_TASK_CLOSURE_SHA256"] == spec["task"]["closure_sha256"]
    assert child["AETHER_PACKAGE_CLOSURE_SHA256"] == spec["package"]["closure_sha256"]
