from dataclasses import FrozenInstanceError
import pytest

from aether.model_profile import PRODUCTION_PROFILE


def test_production_profile_is_frozen_hashed_and_contains_only_positive_controls() -> None:
    manifest = PRODUCTION_PROFILE.manifest()
    assert manifest["profile_id"] == "production-pcr-v1"
    assert manifest["solver_reasoning_effort"] == "high"
    assert manifest["verifier_reasoning_effort"] == "low"
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
