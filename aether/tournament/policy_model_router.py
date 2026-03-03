"""
PolicyModelRouter — Wraps model routing to fire L4 HarnessPolicy hooks.

Intercepts the model routing decision to allow L4 variants to override
the model selection based on structural signals (loop detection, phase, etc).

Design constraint: does NOT modify aether/model_profile.py.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..model_profile import ModelProfile, route_model
from ..policy_config import PolicyConfig

from .harness_policy import HarnessPolicy, LoopSignals, ModelRouteSignals
from .policy_runtime import apply_l4_decision, build_model_route_signals


def policy_route_model(
    *,
    phase: str,
    task_complexity: str,
    policy: PolicyConfig,
    harness_policy: Optional[HarnessPolicy] = None,
    step_count: int = 0,
    usage_prompt_total: int = 0,
    usage_cache_read: int = 0,
    usage_output_total: int = 0,
    loop_signals: Optional[LoopSignals] = None,
    profiles: Optional[Dict[str, ModelProfile]] = None,
) -> Tuple[str, str, Dict[str, object]]:
    """
    Route model selection with optional L4 policy hook.

    If a HarnessPolicy is provided and its on_model_route() returns an
    override_model_id, that model is used instead of the standard routing.

    Returns the same (model_id, signals_hash, details) tuple as route_model().
    """
    # Standard routing first
    model_id, signals_hash, details = route_model(
        phase=phase,
        task_complexity=task_complexity,
        policy=policy,
        profiles=profiles,
    )

    if harness_policy is None:
        return model_id, signals_hash, details

    # Build signals for the L4 hook
    route_signals = build_model_route_signals(
        current_phase=phase,
        model_profile_id=model_id,
        usage_prompt_total=usage_prompt_total,
        usage_cache_read=usage_cache_read,
        usage_output_total=usage_output_total,
        step_count=step_count,
        loop_signals=loop_signals,
    )

    try:
        decision = harness_policy.on_model_route(route_signals=route_signals)
        overridden_id = apply_l4_decision(decision, default_model_id=model_id)

        if overridden_id != model_id:
            details = dict(details)
            details["from_model_id"] = model_id
            details["to_model_id"] = overridden_id
            details["reason_codes"] = list(details.get("reason_codes", [])) + (
                decision.reason_codes or ["POLICY_L4_OVERRIDE"]
            )
            details["policy_override"] = True
            model_id = overridden_id

    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "L4 on_model_route hook failed, using standard routing"
        )

    return model_id, signals_hash, details
