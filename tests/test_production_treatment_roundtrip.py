from __future__ import annotations

from dataclasses import fields, replace
import json
from types import SimpleNamespace

import pytest

from aether import harbor_runtime
from aether.launch import production_tool_schema_sha256
from aether.model_hooks import ModelHooks
from aether.model_profile import PRODUCTION_PROFILE
from aether.providers.azure_model import AzureModelCallable
from aether.verifier_budget import (
    PRODUCTION_VERIFIER_CALL_TIMEOUT_S,
    PRODUCTION_VERIFIER_PHASE_BUDGET,
    PRODUCTION_VERIFIER_TIMEOUT_RESERVE_S,
    PRODUCTION_VERIFIER_WALL_CLOCK_BUDGET_S,
)


FIXED_IMPLEMENTATION_FIELDS = {
    "provider_transport",
    "solver_continuity_mode",
    "verifier_continuity_mode",
    "reasoning_context",
    "solver_compact_threshold",
    "context_projection_mode",
    "attention_projection_mode",
    "native_compaction_mode",
    "tool_surface_id",
    "tool_schema_sha256",
    "provider_call_timeout_s",
    "verifier_timeout_reserve_s",
    "verifier_generation_wall_clock_budget_s",
    "verifier_phase_budget",
}

POSITIVE_TREATMENT_FIELDS = {
    "deployment_env",
    "endpoint_env",
    "solver_reasoning_effort",
    "verifier_reasoning_effort",
    "solver_reanchor_mode",
    "responses_background",
    "responses_websocket",
    "prompt_cache_mode",
    "provider_poll_interval_s",
    "provider_poll_timeout_s",
    "provider_max_retries",
    "provider_sdk_max_retries",
}


class _RecordingModel:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[int | None] = []

    def __call__(self, messages, *, max_output_tokens=None):
        del messages
        self.calls.append(None if max_output_tokens is None else int(max_output_tokens))
        return self.output


def _provider(role: str) -> AzureModelCallable:
    return AzureModelCallable(
        client=SimpleNamespace(responses=SimpleNamespace()),  # no call is made
        deployment="unit-luna",
        effort="low",
        role=role,
        prompt_cache_mode="off",
        prompt_cache_namespace="unit",
        responses_background=PRODUCTION_PROFILE.responses_background,
        poll_interval_s=10,
        poll_timeout_s=1200,
        max_retries=0,
    )


def test_model_profile_contains_only_positive_controls_plus_public_metadata() -> None:
    names = {field.name for field in fields(type(PRODUCTION_PROFILE))}
    assert FIXED_IMPLEMENTATION_FIELDS.isdisjoint(names)
    assert set(PRODUCTION_PROFILE.treatment_manifest()) == POSITIVE_TREATMENT_FIELDS
    assert "key_env" not in PRODUCTION_PROFILE.manifest()


def test_treatment_hash_changes_with_positive_execution_control_not_metadata() -> None:
    baseline = PRODUCTION_PROFILE.sha256()
    relabelled = replace(
        PRODUCTION_PROFILE,
        schema_version="descriptive-schema-label",
        profile_id="descriptive-profile-label",
        model_id="descriptive-model-label",
    )
    assert relabelled.sha256() == baseline
    changed = replace(
        PRODUCTION_PROFILE,
        solver_max_output_tokens=16000,
    )
    assert changed.sha256() != baseline


def test_selected_model_factory_forwards_profile_execution_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    def fake_make(**kwargs):
        calls.append(dict(kwargs))
        return object()

    monkeypatch.setattr(harbor_runtime, "make_azure_callable", fake_make)
    monkeypatch.setattr(harbor_runtime, "require_provider_authorization", lambda _profile: None)
    profile = replace(
        PRODUCTION_PROFILE,
        solver_reasoning_effort="medium",
        verifier_reasoning_effort="high",
        responses_background=False,
        prompt_cache_mode="off",
        provider_poll_interval_s=7,
        provider_poll_timeout_s=777,
        provider_max_retries=2,
        provider_sdk_max_retries=3,
    )
    harbor_runtime.build_selected_luna_models(profile)
    assert len(calls) == 2
    solver, verifier = calls
    assert solver["effort"] == profile.solver_reasoning_effort
    assert verifier["effort"] == profile.verifier_reasoning_effort
    assert solver["responses_background"] == verifier["responses_background"] == profile.responses_background
    assert solver["prompt_cache_mode"] == verifier["prompt_cache_mode"] == profile.prompt_cache_mode
    for row in calls:
        assert row["poll_interval_s"] == profile.provider_poll_interval_s
        assert row["poll_timeout_s"] == profile.provider_poll_timeout_s
        assert row["max_retries"] == profile.provider_max_retries
        assert row["sdk_max_retries"] == profile.provider_sdk_max_retries


def test_model_hooks_production_output_budget_is_unbounded() -> None:
    solver = _RecordingModel(json.dumps({"kind": "submit", "claim": "candidate ready", "evidence_refs": ["receipt:1"]}))
    verifier = _RecordingModel("{}")
    hooks = ModelHooks(
        solver,
        verifier,
        solver_max_output_tokens=PRODUCTION_PROFILE.solver_max_output_tokens,
        verifier_max_output_tokens=PRODUCTION_PROFILE.verifier_max_output_tokens,
    )
    compiled = SimpleNamespace(action_schema={})
    hooks.solve([], compiled)  # type: ignore[arg-type]
    hooks.call_verifier([], max_output_tokens=hooks.verifier_max_output_tokens)
    assert solver.calls == [PRODUCTION_PROFILE.solver_max_output_tokens]
    assert verifier.calls == [PRODUCTION_PROFILE.verifier_max_output_tokens]


def test_production_harbor_budget_defaults_are_profile_owned() -> None:
    import inspect

    sync_default = inspect.signature(harbor_runtime.run_harbor_aether_sync).parameters["max_steps"].default
    async_default = inspect.signature(harbor_runtime.run_harbor_aether).parameters["max_steps"].default
    assert sync_default is None
    assert async_default is None
    assert PRODUCTION_PROFILE.solver_turn_budget is None
    assert PRODUCTION_PROFILE.solver_max_output_tokens is None
    assert PRODUCTION_PROFILE.verifier_max_output_tokens is None


def test_fixed_provider_identity_is_derived_from_executable_native_route() -> None:
    solver = _provider("solver").preflight_request(max_output_tokens=None, logical_role="solver")
    verifier = _provider("verifier").preflight_request(max_output_tokens=None, logical_role="verifier")
    assert solver["transport"] == verifier["transport"] == "responses_tools"
    assert solver["structured_output_mode"] == "pcr_v0_direct_native_tools"
    assert verifier["structured_output_mode"] == "verifier_direct_turn_native_tool"
    assert solver["pcr_continuity_mode"] == "previous_response"
    assert verifier["pcr_continuity_mode"] == "fresh"
    assert solver["reasoning_context"] == "all_turns"
    assert verifier["reasoning_context"] is None
    assert solver["max_output_tokens"] is None
    assert verifier["max_output_tokens"] is None
    assert solver["background"] is verifier["background"] is False
    assert solver["prompt_cache_mode"] == verifier["prompt_cache_mode"] == "off"
    assert solver["max_retries"] == verifier["max_retries"] == 0


def test_fixed_verifier_budget_is_single_implementation_authority() -> None:
    budget = PRODUCTION_VERIFIER_PHASE_BUDGET
    assert budget.max_direct_requests_per_batch == 12
    assert budget.max_model_calls == 4
    assert budget.max_investigation_batches is None
    assert budget.max_derived_execution_batches is None
    assert budget.max_protocol_corrections is None
    assert budget.max_provider_corrections is None
    assert budget.max_budget_corrections is None
    assert budget.max_tool_execution_s_per_batch is None
    assert budget.max_tool_lifecycle_s_per_batch is None
    assert PRODUCTION_VERIFIER_CALL_TIMEOUT_S == 180.0
    assert PRODUCTION_VERIFIER_TIMEOUT_RESERVE_S == 10.0
    assert PRODUCTION_VERIFIER_WALL_CLOCK_BUDGET_S is None


def test_launch_tool_identity_is_hash_of_actual_action_contract() -> None:
    digest = production_tool_schema_sha256()
    assert len(digest) == 64
    assert int(digest, 16) >= 0
