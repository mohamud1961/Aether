from dataclasses import FrozenInstanceError
import pytest

from aether.model_profile import GLM_RESEARCH_PROFILE, PRODUCTION_PROFILE


def test_production_profile_is_frozen_hashed_and_contains_only_positive_controls() -> None:
    manifest = PRODUCTION_PROFILE.manifest()
    assert manifest["profile_id"] == "production-persistent-v1"
    assert manifest["solver_reasoning_effort"] == "max"
    assert manifest["verifier_reasoning_effort"] == "max"
    assert manifest["solver_reanchor_mode"] == "continuity_fresh_delta_v1"
    assert manifest["solver_max_output_tokens"] is None
    assert manifest["verifier_max_output_tokens"] is None
    assert manifest["solver_turn_budget"] is None
    assert manifest["provider_max_retries"] == 1
    assert manifest["provider_sdk_max_retries"] == 0
    assert manifest["responses_background"] is False
    assert manifest["responses_websocket"] is True
    assert manifest["prompt_cache_mode"] == "off"
    assert "key_env" not in manifest
    for fixed_identity in (
        "provider_transport",
        "solver_continuity_mode",
        "verifier_continuity_mode",
        "reasoning_context",
        "solver_compact_threshold",
        "context_projection_mode",
        "attention_projection_mode",
        "native_compaction_mode",
        "tool_surface_id",
        "verifier_phase_budget",
    ):
        assert fixed_identity not in manifest
    assert len(PRODUCTION_PROFILE.sha256()) == 64
    with pytest.raises(FrozenInstanceError):
        PRODUCTION_PROFILE.profile_id = "task-selected"  # type: ignore[misc]

def test_glm_research_profile_uses_trace_first_failsafe_ceiling() -> None:
    manifest = GLM_RESEARCH_PROFILE.manifest()
    assert manifest["profile_id"] == "glm-chat-judge-research-v1"
    assert manifest["solver_reasoning_effort"] == "max"
    assert manifest["solver_max_output_tokens"] == 32768
    assert manifest["provider_poll_timeout_s"] == 1800
    assert manifest["provider_max_retries"] == 2


def test_glm_research_route_profiles_keep_treatment_and_route_identity_separate() -> None:
    from aether.model_profile import GLM_RESEARCH_PAR_PROFILE, GLM_RESEARCH_PROFILES

    base = GLM_RESEARCH_PROFILES["glm-research-v1"]
    parallel = GLM_RESEARCH_PROFILES["glm-research-par-v1"]
    assert base is GLM_RESEARCH_PROFILE
    assert parallel is GLM_RESEARCH_PAR_PROFILE
    assert parallel.model_id == "FW-GLM-5.3-Flash-par"
    assert parallel.sha256() == base.sha256()
    endpoint = "https://resource.cognitiveservices.azure.com/"
    assert base.route_identity_sha256(
        selector="glm-research-v1", endpoint=endpoint, deployment=base.model_id
    ) != parallel.route_identity_sha256(
        selector="glm-research-par-v1", endpoint=endpoint, deployment=parallel.model_id
    )
