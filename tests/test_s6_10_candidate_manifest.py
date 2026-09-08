from __future__ import annotations

from pathlib import Path

from evals.performance.s6_10_candidate_manifest import SCHEMA, collect_identity
from aether.launch import package_closure, production_tool_schema_sha256
from aether.model_profile import PRODUCTION_PROFILE


def test_s6_10_identity_is_derived_from_installed_runtime(tmp_path: Path) -> None:
    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"candidate")
    row = collect_identity(wheel_path=wheel, harbor_version="0.20.0")
    assert row["schema_version"] == SCHEMA
    assert row["package"]["closure_sha256"] == package_closure().sha256
    assert row["tool_schema_sha256"] == production_tool_schema_sha256()
    assert row["model_profile_sha256"] == PRODUCTION_PROFILE.sha256()
    assert row["wheel_sha256"]
    assert row["tool_count"] == 25


def test_s6_10_identity_binds_actual_execution_controls() -> None:
    row = collect_identity(harbor_version="0.20.0")
    t = row["treatment"]
    assert t["solver_reasoning_effort"] == PRODUCTION_PROFILE.solver_reasoning_effort
    assert t["verifier_reasoning_effort"] == PRODUCTION_PROFILE.verifier_reasoning_effort
    assert t["responses_websocket"] == PRODUCTION_PROFILE.responses_websocket
    assert t["provider_max_retries"] == PRODUCTION_PROFILE.provider_max_retries
    assert t["provider_sdk_max_retries"] == PRODUCTION_PROFILE.provider_sdk_max_retries
    assert t["solver_max_output_tokens"] is PRODUCTION_PROFILE.solver_max_output_tokens
    assert t["verifier_max_output_tokens"] is PRODUCTION_PROFILE.verifier_max_output_tokens
    assert t["solver_turn_budget"] is PRODUCTION_PROFILE.solver_turn_budget


def test_s6_10_prompt_protocol_hashes_are_complete_and_stable_shape() -> None:
    hashes = collect_identity(harbor_version="0.20.0")["prompt_protocol_hashes"]
    assert set(hashes) == {
        "primary_response_instruction", "primary_turn_schema", "primary_provider_schema",
        "direct_provider_tools", "verifier_identity_prompt", "verifier_falsification_doctrine",
        "verifier_runtime_contract", "verifier_protocol_profile", "verifier_semantic_guide",
    }
    assert all(len(v) == 64 and int(v, 16) >= 0 for v in hashes.values())


def test_s6_10_identity_fails_closed_without_harbor_metadata(monkeypatch) -> None:
    import importlib.metadata
    from evals.performance import s6_10_candidate_manifest as mod

    def missing(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError("harbor")

    monkeypatch.setattr(mod.importlib.metadata, "version", missing)
    import pytest
    with pytest.raises(RuntimeError, match="installed candidate environment"):
        collect_identity()
