from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .hashing import hash_canonical_json
from .policy_config import PolicyConfig


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    provider: str
    context_window_tokens: int
    max_output_tokens: int
    supports_tool_use: bool
    supports_structured_output: bool
    cost_per_1k_input: float
    cost_per_1k_output: float
    tool_surface: List[str]
    phase_affinity: Dict[str, float]


def default_model_profiles() -> Dict[str, ModelProfile]:
    base = ModelProfile(
        model_id="default_model_v1",
        provider="unknown",
        context_window_tokens=200_000,
        max_output_tokens=8_192,
        supports_tool_use=True,
        supports_structured_output=True,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        tool_surface=["run", "run_command", "read_file", "write_file", "list_paths", "stat"],
        phase_affinity={
            "Orient": 0.5,
            "Explore": 0.7,
            "Plan": 0.8,
            "Implement": 1.0,
            "Verify": 0.9,
            "Review": 0.7,
        },
    )
    return {base.model_id: base}


def route_model(
    *,
    phase: str,
    task_complexity: str,
    policy: PolicyConfig,
    profiles: Optional[Dict[str, ModelProfile]] = None,
) -> Tuple[str, str, Dict[str, object]]:
    active_profiles = profiles or default_model_profiles()
    from_model_id = policy.model_profile_id

    complexity = str(task_complexity or "normal").lower()
    normalized_phase = str(phase or "Implement")

    preferred = policy.phase_model_map.get(normalized_phase)
    if isinstance(preferred, str) and preferred in active_profiles:
        to_model_id = preferred
        reason_codes = ["PHASE_MODEL_MAP"]
    elif from_model_id in active_profiles:
        to_model_id = from_model_id
        reason_codes = ["POLICY_MODEL_PROFILE"]
    else:
        to_model_id = sorted(active_profiles.keys())[0]
        reason_codes = ["FALLBACK_DEFAULT_PROFILE"]

    if complexity in {"high", "complex"}:
        reason_codes.append("TASK_COMPLEXITY_HIGH")
    elif complexity in {"low", "simple"}:
        reason_codes.append("TASK_COMPLEXITY_LOW")
    else:
        reason_codes.append("TASK_COMPLEXITY_NORMAL")

    signal_payload = {
        "phase": normalized_phase,
        "task_complexity": complexity,
        "policy_profile": policy.policy_profile,
        "model_profile_id": policy.model_profile_id,
        "phase_model_map": policy.phase_model_map,
    }
    signals_hash = hash_canonical_json(signal_payload)

    details = {
        "from_model_id": from_model_id,
        "to_model_id": to_model_id,
        "signals_hash": signals_hash,
        "reason_codes": sorted(set(reason_codes)),
        "phase_model_map_used": bool(isinstance(preferred, str) and preferred in active_profiles),
    }
    return to_model_id, signals_hash, details
