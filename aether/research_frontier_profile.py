"""revision Frontier research-route identity.

This module is provider-free configuration only.  It does not make a provider
request and it does not alter the frozen production default.  LQ1 exists to
bind the later Frontier comparison lane to one explicit Responses-API profile and
route identity while reusing the already-qualified native previous-response
continuation implementation.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from .harbor_runtime import build_selected_frontier_models
from .model_profile import (
    ModelProfile,
    PRODUCTION_PROFILE,
    SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE,
)

FRONTIER_RESEARCH_SELECTOR = "frontier-research-v1"

# Reuse the qualified Responses transport and native-continuity topology while
# setting the research model, effort, cache mode, and keyless auth explicitly.
# Keep the qualified persistent WebSocket and native previous_response_id chain;
# Managed Identity supplies the bearer token when the connection is opened.
FRONTIER_RESEARCH_PROFILE = replace(
    PRODUCTION_PROFILE,
    profile_id=FRONTIER_RESEARCH_SELECTOR,
    model_id="GPT-6-Luna",
    key_env="",
    credential_mode=SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE,
    solver_reasoning_effort="high",
    verifier_reasoning_effort="high",
    prompt_cache_mode="stable_prefix",
    expected_returned_model="GPT-6-Luna",
)

FRONTIER_RESEARCH_PROFILES: dict[str, ModelProfile] = {
    FRONTIER_RESEARCH_SELECTOR: FRONTIER_RESEARCH_PROFILE,
}


def frontier_research_profile(selector: str = FRONTIER_RESEARCH_SELECTOR) -> ModelProfile:
    """Resolve the one admitted revision Frontier research profile or fail closed."""
    key = str(selector or "").strip()
    try:
        return FRONTIER_RESEARCH_PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"unsupported Frontier research profile selector: {selector!r}") from exc


def build_frontier_research_models(
    selector: str = FRONTIER_RESEARCH_SELECTOR,
) -> tuple[Any, Any]:
    """Build Solver/Verifier callables through the canonical Responses path."""
    return build_selected_frontier_models(frontier_research_profile(selector))


__all__ = [
    "FRONTIER_RESEARCH_PROFILE",
    "FRONTIER_RESEARCH_PROFILES",
    "FRONTIER_RESEARCH_SELECTOR",
    "build_frontier_research_models",
    "frontier_research_profile",
]
