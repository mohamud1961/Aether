"""
VariantSpec — the strict contract between the Variant Architect and the Tournament Runner.

Every tournament variant is declared as a YAML file that conforms to this schema.
The tournament runner loads a VariantSpec, validates it, and injects the declared
policy overrides into the harness before execution.

Design constraints (from V3.3 Blueprint + review feedback):
  - Lane A only: no new evidence objects, no spine changes, no infra dependencies.
  - No task-identity routing: variants may NOT key on task names, paths, or markers.
  - Structural signals only: variants may only consume signals enumerated below.
  - Deterministic: all policy functions must be pure functions of their inputs.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VariantLane(str, Enum):
    """Lane classification per V3.3 Blueprint §5."""
    A = "A"   # Safe: no spine changes, no new evidence objects
    B = "B"   # Experimental: may alter spine/evidence/replay semantics


class VariantLayer(str, Enum):
    """Layer targeted by the variant (from TOURNAMENT_CHARTER)."""
    L0 = "L0"   # Phase Orchestrator
    L1 = "L1"   # Context Engineering
    L2 = "L2"   # Tool Gateway & Normalization
    L3 = "L3"   # Verification & Completion Enforcement
    L4 = "L4"   # Model Strategy & MCP Routing
    L5 = "L5"   # Recovery & Robustness


class OutcomeClass(str, Enum):
    """V3.3 3-bucket outcome classification."""
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    DQ = "DQ"
    VOID = "VOID"


# ---------------------------------------------------------------------------
# Allowed Signals — the ONLY inputs a variant policy may consume
# ---------------------------------------------------------------------------

ALLOWED_SIGNALS = frozenset({
    # L0 orchestration signals
    "step_count",
    "current_phase",
    "phase_transition_denied_events",
    "exploration_floor_eval",
    "plan_artifact_present",
    "plan_status",

    # L1 context signals
    "section_bytes",
    "prompt_total",
    "cache_read",
    "cache_create",
    "uncached_input",
    "content_hash",
    "stable_prefix_bytes",
    "compiler_mode",
    "overdrive_count",

    # L2 tool signals
    "tool_call_blocked_count",
    "tool_call_blocked_reasons",
    "deny_reason_code",
    "exit_code",
    "truncation_flags",
    "duration_ms",
    "files_read",
    "files_written",
    "attempted_action_fingerprint",
    "risk_class",

    # L3 verification signals
    "verifier_result",
    "verifier_result_pass",
    "workspace_fingerprint_hash",
    "workspace_fingerprint_delta",
    "completion_signals_detected",
    "evidence_bundle_present",
    "false_success_count",

    # L4 model signals
    "model_profile_id",
    "usage_prompt_total",
    "usage_cache_read",
    "usage_output_total",
    "phase_model_map",
    "model_route_reason_codes",

    # L5 recovery signals
    "loop_breaker_triggered",
    "loop_breaker_triggers_fired",
    "reanchor_repeat_count",
    "transition_only_turns",
    "no_progress_turn_count",
    "consecutive_no_delta_count",
})


# ---------------------------------------------------------------------------
# Forbidden Imports — the variant MUST NOT import these
# ---------------------------------------------------------------------------

FORBIDDEN_IMPORTS = frozenset({
    "os.environ",           # No env-var routing
    "subprocess",           # No direct execution (use tool gateway)
    "socket",               # No network access
    "urllib",               # No network access
    "requests",             # No network access
    "httpx",                # No network access
    "openai",               # No direct model calls
    "anthropic",            # No direct model calls
    "google.generativeai",  # No direct model calls
})


# ---------------------------------------------------------------------------
# Forbidden Symbols — the variant MUST NOT reference these harness internals
# ---------------------------------------------------------------------------

FORBIDDEN_SYMBOLS = frozenset({
    # Verifier internals (V3.3 §5 Constraint 1)
    "VerifierRegistry.run_plan",
    "_derive_verifier_result",
    "completion_evidence_bundle",

    # Evidence bundle creation
    "_create_completion_bundle",
    "CompletionEvidenceBundle",

    # Scorer / DQ / Leak linter internals
    "benchifying_linter",
    "hardcoding_linter",

    # Direct model calls
    "ModelAdapter.call",
    "ClaudeAdapter",
    "GeminiAdapter",
    "OpenAIAdapter",
})


# ---------------------------------------------------------------------------
# VariantSpec — the YAML-serializable declaration
# ---------------------------------------------------------------------------

@dataclass
class PolicyOverride:
    """A single knob override within the harness PolicyConfig."""
    field_path: str          # Dot-notation path, e.g. "loop_breaker.max_repair_cycles"
    value: Any               # The override value
    rationale: str = ""      # Why this override improves performance


@dataclass
class EvalSlice:
    """Minimal eval plan for a variant (not task-identity routing)."""
    bucket_filter: str               # Generic structural filter, e.g. "tool_call_blocked_count > 0"
    perturbation: str                # What to inject, e.g. "inject one PATH_SANDBOX denial early"
    pass_criterion: str              # e.g. "FS2 rate < baseline"
    min_trials: int = 3              # Minimum trials for stability


@dataclass
class VariantSpec:
    """
    Complete variant declaration.

    This is the contract a Variant Architect agent must produce.
    The Tournament Runner validates this spec before loading it.
    """

    # --- Identity ---
    variant_id: str              # e.g. "L1-01"
    name: str                    # e.g. "Trusted-State Purge of Tool Text"
    layer: VariantLayer          # Which layer this targets
    lane: VariantLane            # Must be Lane.A for tournament entry
    version: str = "1.0.0"      # Semver for tracking

    # --- Hypothesis ---
    hypothesis: str = ""         # What this variant tests
    expected_win_buckets: str = ""  # Which failure signatures improve
    failure_signatures_reduced: List[str] = field(default_factory=list)

    # --- Evidence ---
    motivating_evidence: List[str] = field(default_factory=list)  # Audit refs
    findings_referenced: List[str] = field(default_factory=list)   # M1-F1, etc.

    # --- Mechanism ---
    signals_consumed: List[str] = field(default_factory=list)      # From ALLOWED_SIGNALS
    mechanism_description: str = ""   # Human-readable description
    policy_module: str = ""           # Python module path, e.g. "aether.tournament.variants.l1_01"

    # --- Policy Overrides (knobs on existing PolicyConfig) ---
    policy_overrides: List[PolicyOverride] = field(default_factory=list)

    # --- Feature Flag Overrides ---
    feature_flag_overrides: Dict[str, bool] = field(default_factory=dict)

    # --- Complexity ---
    lines_added: int = 0             # For complexity tax calculation
    lines_modified: int = 0
    new_imports: List[str] = field(default_factory=list)  # Must not overlap FORBIDDEN_IMPORTS

    # --- Eval Plan ---
    eval_slices: List[EvalSlice] = field(default_factory=list)

    # --- Computed ---
    spec_hash: str = field(init=False, default="")

    def __post_init__(self) -> None:
        # Validate lane
        if self.lane != VariantLane.A:
            raise ValueError(
                f"Only Lane A variants can enter the tournament. "
                f"Variant {self.variant_id} declared Lane {self.lane.value}."
            )

        # Validate signals
        invalid = set(self.signals_consumed) - ALLOWED_SIGNALS
        if invalid:
            raise ValueError(
                f"Variant {self.variant_id} consumes forbidden signals: {invalid}. "
                f"Only ALLOWED_SIGNALS are permitted."
            )

        # Validate imports
        forbidden = set(self.new_imports) & FORBIDDEN_IMPORTS
        if forbidden:
            raise ValueError(
                f"Variant {self.variant_id} uses forbidden imports: {forbidden}."
            )

        # Compute spec hash
        payload = {
            "variant_id": self.variant_id,
            "name": self.name,
            "layer": self.layer.value,
            "lane": self.lane.value,
            "version": self.version,
            "hypothesis": self.hypothesis,
            "signals_consumed": sorted(self.signals_consumed),
            "policy_module": self.policy_module,
            "policy_overrides": [asdict(o) for o in self.policy_overrides],
            "feature_flag_overrides": self.feature_flag_overrides,
            "lines_added": self.lines_added,
            "lines_modified": self.lines_modified,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        object.__setattr__(self, "spec_hash", hashlib.sha256(raw.encode()).hexdigest()[:16])


# ---------------------------------------------------------------------------
# Loading / Serialization
# ---------------------------------------------------------------------------

def load_variant_spec(path: Path) -> VariantSpec:
    """Load a VariantSpec from a YAML file."""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required: pip install pyyaml")

    with open(path) as f:
        data = yaml.safe_load(f)

    # Convert nested dicts to dataclasses
    overrides = [
        PolicyOverride(**o) for o in data.pop("policy_overrides", [])
    ]
    eval_slices = [
        EvalSlice(**e) for e in data.pop("eval_slices", [])
    ]

    # Convert string enums
    data["layer"] = VariantLayer(data["layer"])
    data["lane"] = VariantLane(data["lane"])

    return VariantSpec(
        **data,
        policy_overrides=overrides,
        eval_slices=eval_slices,
    )


def variant_spec_to_dict(spec: VariantSpec) -> Dict[str, Any]:
    """Serialize a VariantSpec to a dict (for YAML/JSON output)."""
    d = asdict(spec)
    d["layer"] = spec.layer.value
    d["lane"] = spec.lane.value
    return d
