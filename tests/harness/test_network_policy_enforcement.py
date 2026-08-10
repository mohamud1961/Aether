"""Mechanical task-container network policy tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.envmap_builder import build_envmap_from_task
from aether.monitors import LocalOnlySafetyGuard
from aether.network_policy import (
    EXTERNAL_UNRESTRICTED,
    LOOPBACK_ONLY,
    resolve_network_policy,
)
from aether.runners import docker_runner
from aether.runners.docker_runner import (
    _GRADER_PREPARE_DIRS_CMD,
    _build_task_container_command,
    _prepare_grader_network,
)
from aether.runtime_ir import ActionRequest, CapabilityDescriptor, EnvMap, RuntimeConfigIR


def test_default_policy_matches_harbor_public_network_default() -> None:
    policy = resolve_network_policy({}, environ={})
    assert policy.scope == EXTERNAL_UNRESTRICTED
    assert policy.source == "harbor_default_public"
    assert policy.docker_args == ()


def test_harbor_network_mode_aliases_are_honored() -> None:
    public = resolve_network_policy({"environment": {"network_mode": "public"}}, environ={})
    isolated = resolve_network_policy({"environment": {"network_mode": "no-network"}}, environ={})
    assert public.scope == EXTERNAL_UNRESTRICTED
    assert public.source == "task_environment.network_mode"
    assert isolated.scope == LOOPBACK_ONLY
    assert isolated.source == "task_environment.network_mode"
    assert isolated.docker_args == ("--network", "none")


def test_legacy_allow_internet_false_maps_to_no_network() -> None:
    policy = resolve_network_policy({"environment": {"allow_internet": False}}, environ={})
    assert policy.scope == LOOPBACK_ONLY
    assert policy.source == "task_environment.allow_internet"


def test_explicit_external_scope_is_supported_not_universally_blocked() -> None:
    policy = resolve_network_policy({}, explicit_scope="external_unrestricted", environ={})
    assert policy.scope == EXTERNAL_UNRESTRICTED
    assert policy.source == "runner_argument"
    assert policy.docker_args == ()


def test_public_environment_and_operator_scopes_have_deterministic_precedence() -> None:
    metadata = {"environment": {"network_scope": "external_unrestricted"}}
    assert resolve_network_policy(metadata, environ={}).source == "task_environment.network_scope"
    assert resolve_network_policy(
        metadata,
        explicit_scope="loopback_only",
        environ={"AETHER_TASK_NETWORK_SCOPE": "external_unrestricted"},
    ).scope == LOOPBACK_ONLY
    assert resolve_network_policy(
        {}, environ={"AETHER_TASK_NETWORK_SCOPE": "external_unrestricted"},
    ).scope == EXTERNAL_UNRESTRICTED


def test_unknown_or_endpoint_claim_scope_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported network scope"):
        resolve_network_policy({}, explicit_scope="declared_endpoints")


def test_production_container_command_contains_real_docker_boundary() -> None:
    isolated = resolve_network_policy({}, explicit_scope="loopback_only")
    open_policy = resolve_network_policy({}, explicit_scope="external_unrestricted")
    isolated_cmd = _build_task_container_command(
        image="task-image", workspace_dir="/tmp/work", network_policy=isolated,
    )
    open_cmd = _build_task_container_command(
        image="task-image", workspace_dir="/tmp/work", network_policy=open_policy,
    )
    assert isolated_cmd[:6] == ["docker", "run", "-d", "--init", "--network", "none"]
    assert "--init" in isolated_cmd and "--init" in open_cmd
    assert "--network" not in open_cmd
    assert isolated_cmd[-3:] == ["task-image", "sleep", "infinity"]


def test_envmap_reports_enforced_policy_not_post_start_probe(tmp_path: Path) -> None:
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Complete the task.",
        network_scope=LOOPBACK_ONLY,
        task_metadata={
            "network_policy": resolve_network_policy({}, explicit_scope=LOOPBACK_ONLY).as_dict(),
            "environment_probe": {"network": {"status": "probed_true"}},
        },
    )
    assert envmap.network_scope == LOOPBACK_ONLY
    request = __import__("aether.kernel_messages", fromlist=["build_architect_request"]).build_architect_request(
        envmap,
        ConfigCompiler(CapabilityRegistry.from_envmap(envmap)),
    )
    assert request["environment"]["network_scope"] == LOOPBACK_ONLY
    assert request["environment"]["enforced_network_policy"]["mechanical_boundary"] == "docker_network_none"


def _compiled():
    return SimpleNamespace()


def test_structured_external_target_blocked_in_loopback_scope() -> None:
    action = ActionRequest(
        action_id="probe",
        kind="probe_service",
        capability_id="service_probe",
        arguments={"target": "example.com:443"},
        intent="probe",
        expected_observation="status",
        if_fail_next="stop",
    )
    guard = LocalOnlySafetyGuard()
    assert guard.violation(_compiled(), action, network_scope=LOOPBACK_ONLY)
    assert guard.violation(_compiled(), action, network_scope=EXTERNAL_UNRESTRICTED) is None


def test_shell_text_is_not_misrepresented_as_network_enforcement() -> None:
    action = ActionRequest(
        action_id="command",
        kind="run_command",
        capability_id="shell",
        arguments={"command": "python3 -c 'import socket; socket.create_connection((\"example.com\",443))'"},
        intent="attempt egress",
        expected_observation="network namespace decides",
        if_fail_next="stop",
    )
    assert LocalOnlySafetyGuard().violation(
        _compiled(), action, network_scope=LOOPBACK_ONLY,
    ) is None


def test_grader_preparation_creates_reward_output_directory() -> None:
    assert "/logs/verifier" in _GRADER_PREPARE_DIRS_CMD
    assert "mkdir -p" in _GRADER_PREPARE_DIRS_CMD


def test_loopback_agent_gets_bridge_only_at_grader_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_checked(args, *, label, timeout):
        calls.append(list(args))
        return SimpleNamespace(returncode=0, stdout="", stderr=""), None

    monkeypatch.setattr(docker_runner, "_checked_process", fake_checked)
    policy = resolve_network_policy({}, explicit_scope="loopback_only")
    result = _prepare_grader_network("container-123", policy)
    assert result["transition_required"] is True
    assert result["transition_succeeded"] is True
    assert calls == [
        ["docker", "network", "disconnect", "none", "container-123"],
        ["docker", "network", "connect", "bridge", "container-123"],
    ]



def test_failed_none_disconnect_blocks_bridge_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_checked(args, *, label, timeout):
        calls.append(list(args))
        return SimpleNamespace(returncode=1, stdout="", stderr="detach failed"), "detach failed"

    monkeypatch.setattr(docker_runner, "_checked_process", fake_checked)
    policy = resolve_network_policy({}, explicit_scope="loopback_only")
    result = _prepare_grader_network("container-123", policy)
    assert result["transition_succeeded"] is False
    assert result["error"] == "detach failed"
    assert calls == [["docker", "network", "disconnect", "none", "container-123"]]

def test_external_agent_network_needs_no_grader_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network connect must not run for already-external container")

    monkeypatch.setattr(docker_runner, "_checked_process", forbidden)
    policy = resolve_network_policy({}, explicit_scope="external_unrestricted")
    result = _prepare_grader_network("container-123", policy)
    assert result["transition_required"] is False
    assert result["transition_succeeded"] is True
