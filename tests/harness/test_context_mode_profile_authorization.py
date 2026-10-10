"""Launchers must authorize the exact profile a context arm runs with.

Regression: live M-TREE/context-file rows crashed with "provider authorization
profile hash does not match production profile" because the runtime replaced
the profile (reanchor off, explicit overflow) while the launcher authorized the
unmodified one.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aether.research_glm_harbor_agent import (
    context_mode_profile,
    g4_kh_profile,
    g4_runtime_config,
)


def _bind_route(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = g4_kh_profile()
    monkeypatch.setenv(profile.endpoint_env, "https://example.openai.azure.com/")
    monkeypatch.setenv(profile.deployment_env, profile.model_id)


@pytest.mark.parametrize("mode", ["control", "m_tree_v1", "context_file_v1"])
def test_launcher_authorized_hash_matches_runtime_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str,
) -> None:
    _bind_route(monkeypatch)
    runtime = g4_runtime_config(state_root=tmp_path, context_mode=mode)
    authorized = context_mode_profile(g4_kh_profile(), mode)
    assert authorized.sha256() == runtime.profile.sha256()


@pytest.mark.parametrize("mode", ["m_tree_v1", "context_file_v1"])
def test_context_arms_change_the_profile(mode: str) -> None:
    base = g4_kh_profile()
    # Falsifiable: authorizing the unmodified profile is exactly the old bug.
    assert context_mode_profile(base, mode).sha256() != base.sha256()
