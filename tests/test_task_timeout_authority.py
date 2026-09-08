from __future__ import annotations

from types import SimpleNamespace

from aether.kernel_dispatch import _action_timeout_s
from aether.kernel_verifier import _verifier_command_budget_s


def test_solver_command_timeout_does_not_cap_explicit_task_authority():
    action = SimpleNamespace(arguments={"timeout_s": 20_000})
    envmap = SimpleNamespace(task_metadata={"resource_budget": {"agent_timeout_sec": 20_000}})
    effective, note = _action_timeout_s(action, envmap)
    assert effective == 20_000
    assert "max_available=20000" in note


def test_solver_command_timeout_metadata_poor_fallback_remains_mechanical():
    action = SimpleNamespace(arguments={"timeout_s": 600})
    envmap = SimpleNamespace(task_metadata={})
    effective, note = _action_timeout_s(action, envmap)
    assert effective == 300
    assert "max_available=300" in note


def test_verifier_overlay_timeout_does_not_cap_explicit_task_authority():
    envmap = SimpleNamespace(task_metadata={"resource_budget": {"verifier_timeout_sec": 20_000}})
    assert _verifier_command_budget_s(envmap) == 20_000


def test_verifier_overlay_metadata_poor_fallback_remains_mechanical():
    envmap = SimpleNamespace(task_metadata={})
    assert _verifier_command_budget_s(envmap) == 300
