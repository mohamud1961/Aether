"""
HarnessPolicy — the abstract interface that tournament variants implement.

Each layer (L0-L5) has a defined set of hook methods. A variant overrides
ONLY the hooks for its target layer. The default implementation is a no-op
passthrough, meaning the harness behaves exactly as the current baseline.

Design grounding (from actual harness code):
  - L0 hooks plug into Agentrunner.run_task() loop decisions
  - L1 hooks plug into ContextCompiler and ContextPackProjection
  - L2 hooks plug into ToolGateway.execute() pre/post processing
  - L3 hooks plug into VerifierRegistry and completion enforcement
  - L4 hooks plug into model_profile.route_model()
  - L5 hooks plug into LoopBreaker and recovery logic

All hooks receive and return STRUCTURAL signals only (dicts, enums, ints).
No hook may consume stdout/stderr text content for decisions.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Structural signal containers passed to hooks
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StepContext:
    """Snapshot of harness state at a given step, passed to all hooks."""
    step_id: int
    current_phase: str
    tool_calls_executed: int
    model_calls_made: int
    prompt_total: int
    section_bytes: Dict[str, int]
    workspace_fingerprint_hash: Optional[str]
    workspace_fingerprint_delta: int
    plan_status: Optional[str]
    plan_artifact_present: bool
    cache_read: int
    uncached_input: int
    stable_prefix_bytes: int


@dataclass(frozen=True)
class ToolSignals:
    """Structural signals from a tool call, passed to L2 and L5 hooks."""
    tool_name: str
    exit_code: Optional[int]
    deny_reason_code: Optional[str]
    truncation_flags: Dict[str, Dict[str, Any]]
    duration_ms: Optional[int]
    files_read: List[str]
    files_written: List[str]
    risk_class: str
    attempted_action_fingerprint: Optional[str]
    tool_call_blocked: bool


@dataclass(frozen=True)
class VerifierSignals:
    """Structural signals from a verifier run, passed to L3 hooks."""
    verifier_id: str
    exit_code: Optional[int]
    result: str                   # "pass" | "fail" | "unknown"
    workspace_fingerprint_hash: Optional[str]
    artifact_refs: List[str]


@dataclass(frozen=True)
class LoopSignals:
    """Structural signals from loop detection, passed to L5 hooks."""
    loop_breaker_triggered: bool
    triggers_fired: List[str]
    consecutive_no_delta_count: int
    transition_only_turns: int
    reanchor_repeat_count: int
    no_progress_turn_count: int
    tool_call_blocked_count: int
    tool_call_blocked_reasons: Dict[str, int]   # reason_code -> count


@dataclass(frozen=True)
class ModelRouteSignals:
    """Structural signals for model routing, passed to L4 hooks."""
    current_phase: str
    model_profile_id: str
    usage_prompt_total: int
    usage_cache_read: int
    usage_output_total: int
    step_count: int
    loop_signals: Optional[LoopSignals]


# ---------------------------------------------------------------------------
# Hook return types
# ---------------------------------------------------------------------------

@dataclass
class L0Decision:
    """L0 orchestration decision."""
    skip_model_call: bool = False           # True = suppress next model call
    force_phase: Optional[str] = None       # Force a specific phase
    inject_state_items: List[Dict[str, Any]] = None  # Extra STATE items to inject
    suppress_denial_publishing: bool = False  # Suppress denial spam

    def __post_init__(self):
        if self.inject_state_items is None:
            self.inject_state_items = []


@dataclass
class L1Decision:
    """L1 context engineering decision."""
    section_budget_overrides: Dict[str, int] = None   # Override section budgets
    scratch_retain_count: Optional[int] = None         # LRU limit for SCRATCH items
    deduplicate_by_content_hash: bool = False           # De-dup SCRATCH by content_hash
    tool_text_in_state: bool = True                     # Allow tool text in STATE (False = purge)
    denial_cap: Optional[int] = None                    # Max denial items in STATE

    def __post_init__(self):
        if self.section_budget_overrides is None:
            self.section_budget_overrides = {}


@dataclass
class L2Decision:
    """L2 tool gateway decision."""
    rewrite_command: Optional[str] = None     # Rewritten command (for shell-op rewrites)
    canonicalize_cwd: bool = False             # Force cwd canonicalization
    override_truncation_unknown: Optional[bool] = None  # Set truncation.unknown explicitly
    additional_event_fields: Dict[str, Any] = None   # Extra fields for tool events

    def __post_init__(self):
        if self.additional_event_fields is None:
            self.additional_event_fields = {}


@dataclass
class L3Decision:
    """L3 verification decision."""
    run_verifier_now: bool = False            # Force immediate verifier run
    verifier_stage: str = "B"                 # "A" = fast smoke, "B" = full
    require_verifier_for_completion: bool = True  # Block completion without verifier pass
    false_success_override: Optional[bool] = None  # Override false success detection


@dataclass
class L4Decision:
    """L4 model routing decision."""
    override_model_id: Optional[str] = None   # Force a specific model
    override_reasoning_effort: Optional[str] = None  # "low" | "medium" | "high"
    reason_codes: List[str] = None

    def __post_init__(self):
        if self.reason_codes is None:
            self.reason_codes = []


@dataclass
class L5Decision:
    """L5 recovery decision."""
    force_reanchor: bool = False              # Force context reanchor
    drop_scratch_fraction: float = 0.0        # Fraction of SCRATCH to evict (0-1)
    swap_cwd_strategy: Optional[str] = None   # "relative" | "workspace_root"
    force_plan_revision: bool = False          # Force a new plan
    inject_diagnostic_prompt: Optional[str] = None  # Short diagnostic nudge (max 200 chars)


# ---------------------------------------------------------------------------
# HarnessPolicy — the abstract base class
# ---------------------------------------------------------------------------

class HarnessPolicy(ABC):
    """
    Abstract base for tournament variant policies.

    Override ONLY the hooks for your target layer. Leave all others as default.
    Every method receives structural signals and returns a decision dataclass.

    Rules:
      1. No reading stdout/stderr text content.
      2. No importing forbidden modules (see variant_spec.FORBIDDEN_IMPORTS).
      3. No referencing forbidden symbols (see variant_spec.FORBIDDEN_SYMBOLS).
      4. No task-identity routing (no keying on task names, paths, or markers).
      5. All decisions must be deterministic given the same inputs.
    """

    # --- Identity ---

    @property
    def variant_id(self) -> str:
        """Return the variant ID, e.g. 'L1-01'."""
        return "baseline"

    @property
    def variant_name(self) -> str:
        """Return human-readable name, e.g. 'Trusted-State Purge'."""
        return "DefaultPolicy"

    # --- L0: Orchestration ---

    def on_step_start(self, ctx: StepContext) -> L0Decision:
        """Called at the start of each harness step, before the model call."""
        return L0Decision()

    def on_phase_transition_denied(
        self,
        ctx: StepContext,
        *,
        from_phase: str,
        to_phase: str,
        deny_reason_code: str,
        missing_conditions: List[str],
    ) -> L0Decision:
        """Called when a phase transition is denied by ControlPlane."""
        return L0Decision()

    # --- L1: Context Engineering ---

    def on_context_compile(self, ctx: StepContext) -> L1Decision:
        """Called before context compilation. Returns overrides for the compiler."""
        return L1Decision()

    def on_context_projection(
        self,
        ctx: StepContext,
        *,
        projection_section_bytes: Dict[str, int],
    ) -> L1Decision:
        """Called after projection is built, before rendering to model."""
        return L1Decision()

    # --- L2: Tool Gateway ---

    def on_tool_pre_execute(
        self,
        ctx: StepContext,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> L2Decision:
        """Called before a tool is executed. Can rewrite or canonicalize."""
        return L2Decision()

    def on_tool_post_execute(
        self,
        ctx: StepContext,
        *,
        tool_signals: ToolSignals,
    ) -> L2Decision:
        """Called after a tool executes. Can override truncation metadata."""
        return L2Decision()

    def on_tool_blocked(
        self,
        ctx: StepContext,
        *,
        tool_signals: ToolSignals,
    ) -> L2Decision:
        """Called when a tool call is blocked (denied)."""
        return L2Decision()

    # --- L3: Verification ---

    def on_workspace_mutated(
        self,
        ctx: StepContext,
        *,
        fingerprint_delta: int,
    ) -> L3Decision:
        """Called when workspace fingerprint changes after a tool call."""
        return L3Decision()

    def on_completion_claimed(
        self,
        ctx: StepContext,
        *,
        completion_signals: List[str],
    ) -> L3Decision:
        """Called when the model signals it believes the task is done."""
        return L3Decision()

    def on_verifier_result(
        self,
        ctx: StepContext,
        *,
        verifier_signals: VerifierSignals,
    ) -> L3Decision:
        """Called after a verifier runs. Can trigger follow-up actions."""
        return L3Decision()

    # --- L4: Model Strategy ---

    def on_model_route(
        self,
        *,
        route_signals: ModelRouteSignals,
    ) -> L4Decision:
        """Called before each model call to decide which model/profile to use."""
        return L4Decision()

    # --- L5: Recovery ---

    def on_loop_detected(
        self,
        ctx: StepContext,
        *,
        loop_signals: LoopSignals,
    ) -> L5Decision:
        """Called when the loop breaker detects a stuck pattern."""
        return L5Decision()

    def on_context_bloat(
        self,
        ctx: StepContext,
        *,
        prompt_total: int,
        section_bytes: Dict[str, int],
    ) -> L5Decision:
        """Called when prompt_total exceeds a threshold (e.g. 10k tokens)."""
        return L5Decision()

    def on_deny_loop(
        self,
        ctx: StepContext,
        *,
        loop_signals: LoopSignals,
    ) -> L5Decision:
        """Called when repeated tool denials are detected."""
        return L5Decision()


# ---------------------------------------------------------------------------
# DefaultPolicy — the baseline (no-op passthrough)
# ---------------------------------------------------------------------------

class DefaultPolicy(HarnessPolicy):
    """
    The baseline policy. All hooks return default decisions.
    This represents the current harness behavior with no modifications.
    Used as the control variant in Season 1.
    """

    @property
    def variant_id(self) -> str:
        return "baseline-v1"

    @property
    def variant_name(self) -> str:
        return "DefaultPolicy (Baseline)"
