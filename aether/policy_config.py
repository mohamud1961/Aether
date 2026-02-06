from __future__ import annotations

import os
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from .hashing import hash_canonical_json

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

# Stable ignore policy for workspace hashing and deterministic diffing.
# Amendment 3 list is preserved and expanded with existing harness-specific dirs.
WORKSPACE_IGNORE_PATTERNS = (
    ".git/",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "node_modules/",
    ".DS_Store",
    ".venv/",
    "venv/",
    "*.egg-info/",
    "harness_artifacts/",
    ".harness_deps/",
    "artifacts/",
)


def workspace_ignore_list_hash() -> str:
    return hash_canonical_json(list(WORKSPACE_IGNORE_PATTERNS))


def _read_bool(env_name: str, default: bool) -> bool:
    value = os.getenv(env_name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean for {env_name}: {value}")


def _read_str(env_name: str, default: str) -> str:
    value = os.getenv(env_name)
    if value is None:
        return default
    normalized = value.strip()
    return normalized if normalized else default


@dataclass(frozen=True)
class FeatureFlags:
    ff_safe_file_ops: bool = True
    ff_canonical_workdir: bool = True
    cc_u01: bool = True
    ff_mandatory_verifier_phase: bool = True
    ff_verify_and_repair: bool = True
    ff_semantic_success_detection: bool = True
    ff_proceed_gate: bool = True
    ff_permission_loop_resolver: bool = True
    ff_capability_adapter: bool = True
    ff_retry_after_fix: bool = True
    ff_io_limits_adapter: bool = True
    ff_loop_breaker: bool = True
    ff_session_recovery: bool = True
    ff_evaluation_suite_mode: bool = False  # Relaxes safety checks for isolated Docker evaluation suites

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        return cls(
            ff_safe_file_ops=_read_bool("FF_SAFE_FILE_OPS", True),
            ff_canonical_workdir=_read_bool("FF_CANONICAL_WORKDIR", True),
            cc_u01=_read_bool("CC_U01", True),
            ff_mandatory_verifier_phase=_read_bool("FF_MANDATORY_VERIFIER_PHASE", True),
            ff_verify_and_repair=_read_bool("FF_VERIFY_AND_REPAIR", True),
            ff_semantic_success_detection=_read_bool("FF_SEMANTIC_SUCCESS_DETECTION", True),
            ff_proceed_gate=_read_bool("FF_PROCEED_GATE", True),
            ff_permission_loop_resolver=_read_bool("FF_PERMISSION_LOOP_RESOLVER", True),
            ff_capability_adapter=_read_bool("FF_CAPABILITY_ADAPTER", True),
            ff_retry_after_fix=_read_bool("FF_RETRY_AFTER_FIX", True),
            ff_io_limits_adapter=_read_bool("FF_IO_LIMITS_ADAPTER", True),
            ff_loop_breaker=_read_bool("FF_LOOP_BREAKER", True),
            ff_session_recovery=_read_bool("FF_SESSION_RECOVERY", True),
            ff_evaluation_suite_mode=_read_bool("FF_EVALUATION_SUITE_MODE", False),
        )


def _read_int(env_name: str, default: int) -> int:
    value = os.getenv(env_name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        raise ValueError(f"Invalid integer for {env_name}: {value}")


@dataclass(frozen=True)
class LoopBreakerConfig:
    """Configuration for breaking verify-repair loops with weaker models."""

    max_repair_cycles: int = 5  # Max consecutive VERIFY→REPAIR cycles before forcing ACT
    max_consecutive_malformed_calls: int = 3  # Max model errors before skipping
    force_act_after_repair_exhaustion: bool = True  # Return to ACT instead of FAIL
    max_total_verifications: int = 10  # Absolute cap on verification runs per task
    reanchor_repeat_k: int = 2
    reanchor_repeat_w: int = 6
    transition_only_window_size: int = 3
    repetitive_action_threshold: int = 3
    no_progress_turn_threshold: int = 8
    no_progress_max_force_plan: int = 1

    @classmethod
    def from_env(cls) -> "LoopBreakerConfig":
        return cls(
            max_repair_cycles=_read_int("MAX_REPAIR_CYCLES", 5),
            max_consecutive_malformed_calls=_read_int("MAX_CONSECUTIVE_MALFORMED_CALLS", 3),
            force_act_after_repair_exhaustion=_read_bool("FORCE_ACT_AFTER_REPAIR_EXHAUSTION", True),
            max_total_verifications=_read_int("MAX_TOTAL_VERIFICATIONS", 10),
            reanchor_repeat_k=_read_int("REANCHOR_REPEAT_K", 2),
            reanchor_repeat_w=_read_int("REANCHOR_REPEAT_W", 6),
            transition_only_window_size=_read_int("TRANSITION_ONLY_WINDOW_SIZE", 3),
            repetitive_action_threshold=_read_int("REPETITIVE_ACTION_THRESHOLD", 3),
            no_progress_turn_threshold=_read_int("NO_PROGRESS_TURN_THRESHOLD", 8),
            no_progress_max_force_plan=_read_int("NO_PROGRESS_MAX_FORCE_PLAN", 1),
        )


@dataclass(frozen=True)
class PolicyConfig:
    feature_flags: FeatureFlags = field(default_factory=FeatureFlags)
    loop_breaker: LoopBreakerConfig = field(default_factory=LoopBreakerConfig)
    policy_profile: str = "eval"
    model_profile_id: str = "default_model_v1"
    network_enabled: bool = True
    enforce_script_allowlist: bool = False
    script_allowlist_hashes: tuple[str, ...] = ()
    candidate_learning_enabled: bool = False
    phase_model_map: Dict[str, str] = field(default_factory=dict)

    # Stage 0 budget envelope (V1.1 §6.1 + §6.5).
    max_model_calls: int = 200
    max_tool_calls: int = 500
    max_wall_clock_seconds: int = 1800
    max_input_tokens_total: int = 2_000_000
    max_output_tokens_total: int = 2_000_000
    max_cost_units: int = 1_000_000
    anchor_sink_path: str = "harness_artifacts/log_anchor.txt"
    run_tool_timeout_ms: int = 60_000

    policy_hash: str = field(init=False)
    workspace_ignore_hash: str = field(init=False)

    def __post_init__(self) -> None:
        normalized_profile = self.policy_profile.strip().lower()
        if normalized_profile not in {"eval", "prod"}:
            raise ValueError(f"policy_profile must be 'eval' or 'prod', got: {self.policy_profile}")
        object.__setattr__(self, "policy_profile", normalized_profile)
        if not isinstance(self.run_tool_timeout_ms, int) or self.run_tool_timeout_ms <= 0:
            raise ValueError("run_tool_timeout_ms must be a positive integer")

        ignore_hash = workspace_ignore_list_hash()
        object.__setattr__(self, "workspace_ignore_hash", ignore_hash)

        payload: Dict[str, Any] = {
            "feature_flags": asdict(self.feature_flags),
            "loop_breaker": asdict(self.loop_breaker),
            "policy_profile": self.policy_profile,
            "model_profile_id": self.model_profile_id,
            "network_enabled": self.network_enabled,
            "enforce_script_allowlist": self.enforce_script_allowlist,
            "script_allowlist_hashes": list(self.script_allowlist_hashes),
            "candidate_learning_enabled": self.candidate_learning_enabled,
            "phase_model_map": dict(sorted(self.phase_model_map.items())),
            "max_model_calls": self.max_model_calls,
            "max_tool_calls": self.max_tool_calls,
            "max_wall_clock_seconds": self.max_wall_clock_seconds,
            "max_input_tokens_total": self.max_input_tokens_total,
            "max_output_tokens_total": self.max_output_tokens_total,
            "max_cost_units": self.max_cost_units,
            "anchor_sink_path": self.anchor_sink_path,
            "run_tool_timeout_ms": self.run_tool_timeout_ms,
            "workspace_ignore_patterns": list(WORKSPACE_IGNORE_PATTERNS),
            "workspace_ignore_hash": ignore_hash,
        }
        object.__setattr__(self, "policy_hash", hash_canonical_json(payload))

    @classmethod
    def from_env(cls) -> "PolicyConfig":
        return cls(
            feature_flags=FeatureFlags.from_env(),
            loop_breaker=LoopBreakerConfig.from_env(),
            policy_profile=_read_str("POLICY_PROFILE", "eval"),
            model_profile_id=_read_str("MODEL_PROFILE_ID", "default_model_v1"),
            network_enabled=_read_bool("NETWORK_ENABLED", True),
            enforce_script_allowlist=_read_bool("ENFORCE_SCRIPT_ALLOWLIST", False),
            script_allowlist_hashes=tuple(
                item.strip()
                for item in _read_str("SCRIPT_ALLOWLIST_HASHES", "").split(",")
                if item.strip()
            ),
            candidate_learning_enabled=_read_bool("CANDIDATE_LEARNING_ENABLED", False),
            phase_model_map=_read_phase_model_map("PHASE_MODEL_MAP"),
            max_model_calls=_read_int("MAX_MODEL_CALLS", 200),
            max_tool_calls=_read_int("MAX_TOOL_CALLS", 500),
            max_wall_clock_seconds=_read_int("MAX_WALL_CLOCK_SECONDS", 1800),
            max_input_tokens_total=_read_int("MAX_INPUT_TOKENS_TOTAL", 2_000_000),
            max_output_tokens_total=_read_int("MAX_OUTPUT_TOKENS_TOTAL", 2_000_000),
            max_cost_units=_read_int("MAX_COST_UNITS", 1_000_000),
            anchor_sink_path=_read_str("ANCHOR_SINK_PATH", "harness_artifacts/log_anchor.txt"),
            run_tool_timeout_ms=_read_int("RUN_TOOL_TIMEOUT_MS", 60_000),
        )

    def emit_run_start_event(
        self,
        event_log,
        *,
        run_id: str,
        cwd: str,
        enum_registry_hash: str,
        model_profile_id: str | None = None,
        workspace_fingerprint_hash: str | None = None,
        tool_surface_profile: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        model_id = model_profile_id or self.model_profile_id
        surface_profile = tool_surface_profile or _default_tool_surface_profile(self.policy_profile)
        return event_log.append_event(
            {
                "event_type": "run_START",
                "run_id": run_id,
                "timestamp": _utc_now_iso(),
                "cwd": cwd,
                "policy_profile": self.policy_profile,
                "policy_hash": self.policy_hash,
                "enum_registry_hash": enum_registry_hash,
                "model_profile_id": model_id,
                "workspace_fingerprint_hash": workspace_fingerprint_hash,
                "workspace_fingerprint": workspace_fingerprint_hash,
                "candidate_learning_enabled": self.candidate_learning_enabled,
                "tool_surface_profile": surface_profile,
            }
        )


def _default_tool_surface_profile(policy_profile: str) -> Dict[str, Any]:
    return {
        "tools": ["run", "request_phase_transition"],
        "interpreters": [],
        "policy_profile": policy_profile,
    }


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_phase_model_map(env_name: str) -> Dict[str, str]:
    raw = os.getenv(env_name)
    if raw is None or not raw.strip():
        return {}
    try:
        loaded = json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Invalid JSON object for {env_name}: {raw}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{env_name} must be a JSON object")
    result: Dict[str, str] = {}
    for key, value in loaded.items():
        phase = str(key).strip()
        model_id = str(value).strip()
        if not phase or not model_id:
            continue
        result[phase] = model_id
    return result


def fingerprint_delta_count(diff_summary: Dict[str, Any]) -> int:
    if not isinstance(diff_summary, dict):
        return 0
    explicit = diff_summary.get("fingerprint_delta")
    if isinstance(explicit, int):
        return max(0, explicit)
    added = diff_summary.get("added", [])
    removed = diff_summary.get("removed", [])
    modified = diff_summary.get("modified", [])
    added_count = len(added) if isinstance(added, list) else 0
    removed_count = len(removed) if isinstance(removed, list) else 0
    modified_count = len(modified) if isinstance(modified, list) else 0
    return added_count + removed_count + modified_count
