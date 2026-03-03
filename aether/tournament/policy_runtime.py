"""
Policy Runtime — Signal normalization and decision application layer.

This module is the bridge between HarnessPolicy hooks and the live harness.
It converts raw harness state/events into the typed signal containers that
policy hooks consume, and translates policy decisions back into harness actions.

Design constraint: this module NEVER modifies aether/* directly.
It operates purely through the public interfaces of harness components.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type

from ..event_log import EventLog
from ..policy_config import PolicyConfig

from .harness_policy import (
    DefaultPolicy,
    HarnessPolicy,
    L0Decision,
    L1Decision,
    L2Decision,
    L3Decision,
    L4Decision,
    L5Decision,
    LoopSignals,
    ModelRouteSignals,
    StepContext,
    ToolSignals,
    VerifierSignals,
)
from .variant_spec import VariantSpec, load_variant_spec


# ---------------------------------------------------------------------------
# Signal Construction — convert harness state → typed signal containers
# ---------------------------------------------------------------------------

def build_step_context(
    *,
    step_id: int,
    current_phase: str,
    tool_calls_executed: int,
    model_calls_made: int,
    prompt_total: int,
    section_bytes: Dict[str, int],
    workspace_fingerprint_hash: Optional[str],
    workspace_fingerprint_delta: int,
    plan_status: Optional[str],
    plan_artifact_present: bool,
    cache_read: int = 0,
    uncached_input: int = 0,
    stable_prefix_bytes: int = 0,
) -> StepContext:
    """Build a StepContext from explicit harness state values."""
    return StepContext(
        step_id=step_id,
        current_phase=current_phase,
        tool_calls_executed=tool_calls_executed,
        model_calls_made=model_calls_made,
        prompt_total=prompt_total,
        section_bytes=section_bytes,
        workspace_fingerprint_hash=workspace_fingerprint_hash,
        workspace_fingerprint_delta=workspace_fingerprint_delta,
        plan_status=plan_status,
        plan_artifact_present=plan_artifact_present,
        cache_read=cache_read,
        uncached_input=uncached_input,
        stable_prefix_bytes=stable_prefix_bytes,
    )


def build_tool_signals(
    *,
    tool_name: str,
    exit_code: Optional[int] = None,
    deny_reason_code: Optional[str] = None,
    truncation_flags: Any = None,
    duration_ms: Optional[int] = None,
    files_read: Optional[List[str]] = None,
    files_written: Optional[List[str]] = None,
    risk_class: str = "LOW",
    attempted_action_fingerprint: Optional[str] = None,
    tool_call_blocked: bool = False,
) -> ToolSignals:
    """
    Build ToolSignals from aether tool result / deny event.

    Performs normalization of truncation_flags:
      - If string (e.g. "UNKNOWN"), converts to dict form
      - If None, sets empty dict
      - If already dict, passes through
    """
    normalized_trunc = _normalize_truncation_flags(truncation_flags)
    return ToolSignals(
        tool_name=tool_name,
        exit_code=exit_code,
        deny_reason_code=deny_reason_code,
        truncation_flags=normalized_trunc,
        duration_ms=duration_ms,
        files_read=files_read or [],
        files_written=files_written or [],
        risk_class=risk_class,
        attempted_action_fingerprint=attempted_action_fingerprint,
        tool_call_blocked=tool_call_blocked,
    )


def build_tool_signals_from_result(tool_result: Any) -> ToolSignals:
    """Build ToolSignals from a ToolResult dataclass (from tool_gateway)."""
    return build_tool_signals(
        tool_name=tool_result.event.get("tool_name", "unknown"),
        exit_code=tool_result.exit_code if isinstance(tool_result.exit_code, int) else None,
        truncation_flags=tool_result.truncation,
        duration_ms=tool_result.duration_ms,
        files_read=tool_result.files_read,
        files_written=tool_result.files_written,
        risk_class=tool_result.risk_class,
        attempted_action_fingerprint=None,
        tool_call_blocked=False,
    )


def build_tool_signals_from_deny(
    *,
    tool_name: str,
    deny_reason_code: str,
    tool_args: Dict[str, Any],
    attempted_action_fingerprint: Optional[str] = None,
) -> ToolSignals:
    """Build ToolSignals from a tool denial event."""
    return build_tool_signals(
        tool_name=tool_name,
        deny_reason_code=deny_reason_code,
        tool_call_blocked=True,
        attempted_action_fingerprint=attempted_action_fingerprint,
    )


def build_verifier_signals(
    *,
    verifier_id: str,
    exit_code: Optional[int],
    result: str,
    workspace_fingerprint_hash: Optional[str] = None,
    artifact_refs: Optional[List[str]] = None,
) -> VerifierSignals:
    """Build VerifierSignals from a VerifierrunResult."""
    return VerifierSignals(
        verifier_id=verifier_id,
        exit_code=exit_code,
        result=result,
        workspace_fingerprint_hash=workspace_fingerprint_hash,
        artifact_refs=artifact_refs or [],
    )


def build_loop_signals(
    *,
    loop_breaker_triggered: bool = False,
    triggers_fired: Optional[List[str]] = None,
    consecutive_no_delta_count: int = 0,
    transition_only_turns: int = 0,
    reanchor_repeat_count: int = 0,
    no_progress_turn_count: int = 0,
    tool_call_blocked_count: int = 0,
    tool_call_blocked_reasons: Optional[Dict[str, int]] = None,
) -> LoopSignals:
    """Build LoopSignals from loop breaker state."""
    return LoopSignals(
        loop_breaker_triggered=loop_breaker_triggered,
        triggers_fired=triggers_fired or [],
        consecutive_no_delta_count=consecutive_no_delta_count,
        transition_only_turns=transition_only_turns,
        reanchor_repeat_count=reanchor_repeat_count,
        no_progress_turn_count=no_progress_turn_count,
        tool_call_blocked_count=tool_call_blocked_count,
        tool_call_blocked_reasons=tool_call_blocked_reasons or {},
    )


def build_model_route_signals(
    *,
    current_phase: str,
    model_profile_id: str,
    usage_prompt_total: int = 0,
    usage_cache_read: int = 0,
    usage_output_total: int = 0,
    step_count: int = 0,
    loop_signals: Optional[LoopSignals] = None,
) -> ModelRouteSignals:
    """Build ModelRouteSignals for L4 hooks."""
    return ModelRouteSignals(
        current_phase=current_phase,
        model_profile_id=model_profile_id,
        usage_prompt_total=usage_prompt_total,
        usage_cache_read=usage_cache_read,
        usage_output_total=usage_output_total,
        step_count=step_count,
        loop_signals=loop_signals,
    )


# ---------------------------------------------------------------------------
# Signal Normalization Helpers
# ---------------------------------------------------------------------------

def _normalize_truncation_flags(raw: Any) -> Dict[str, Dict[str, Any]]:
    """
    Normalize truncation_flags from whatever the harness emits into the
    canonical dict form that policy hooks expect.

    Handles:
      - None → {}
      - str "UNKNOWN" → {"stdout": {"state": "UNKNOWN"}, "stderr": {"state": "UNKNOWN"}}
      - dict with nested dicts → passthrough
      - dict with non-dict values → wrap into {"state": value}
    """
    if raw is None:
        return {}
    if isinstance(raw, str):
        state = {"state": raw}
        return {"stdout": state, "stderr": state}
    if not isinstance(raw, dict):
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            result[key] = value
        else:
            result[key] = {"state": str(value)}
    return result


def count_blocked_tools_from_events(events: Sequence[Dict[str, Any]]) -> Tuple[int, Dict[str, int]]:
    """
    Count tool_call_blocked events and their reason codes from an event log.

    Returns (total_count, {reason_code: count}).
    """
    total = 0
    reasons: Dict[str, int] = {}
    for event in events:
        if event.get("event_type") == "tool_call_blocked":
            total += 1
            code = event.get("deny_reason_code", "UNKNOWN")
            reasons[code] = reasons.get(code, 0) + 1
    return total, reasons


# ---------------------------------------------------------------------------
# Decision Application — translate decisions into harness actions
# ---------------------------------------------------------------------------

def apply_l0_decision(
    decision: L0Decision,
    *,
    context_pack: Any,
    section_state: str = "STATE",
) -> None:
    """
    Apply an L0Decision to the harness context pack.

    - inject_state_items: adds items to STATE section
    - suppress_denial_publishing: handled by the runner (checked externally)
    - skip_model_call / force_phase: handled by the runner (checked externally)
    """
    for item in decision.inject_state_items:
        # Spread item first, then override with required fields
        raw_source = item.get("source", "l0_inject")
        enriched = {
            "tier": "WORKSPACE",
            "section": section_state,
            "authority_tier": "runtime",
            **item,
            "source": f"policy:{raw_source}",
        }
        context_pack.add_item(enriched)


def apply_l1_decision_to_compiler_kwargs(
    decision: L1Decision,
    compiler_kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply an L1Decision to the compiler keyword arguments.

    Returns the modified kwargs dict.
    """
    if decision.section_budget_overrides:
        existing = compiler_kwargs.get("section_budgets") or {}
        existing.update(decision.section_budget_overrides)
        compiler_kwargs["section_budgets"] = existing

    return compiler_kwargs


def apply_l2_decision_to_tool_args(
    decision: L2Decision,
    tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply an L2Decision to tool arguments before execution.

    Returns the (possibly modified) tool_args dict.
    """
    if decision.rewrite_command is not None:
        tool_args = dict(tool_args)  # Defensive copy
        tool_args["command"] = decision.rewrite_command

    if decision.canonicalize_cwd and "cwd" in tool_args:
        from pathlib import Path as _Path
        raw_cwd = tool_args["cwd"]
        try:
            tool_args = dict(tool_args)
            tool_args["cwd"] = str(_Path(raw_cwd).resolve())
        except Exception:
            pass  # Keep original if resolution fails

    return tool_args


def apply_l4_decision(
    decision: L4Decision,
    *,
    default_model_id: str,
) -> str:
    """
    Apply an L4Decision to model selection.

    Returns the model_id to use.
    """
    if decision.override_model_id is not None:
        return decision.override_model_id
    return default_model_id


def apply_l5_decision(
    decision: L5Decision,
    *,
    context_pack: Any,
) -> Dict[str, Any]:
    """
    Apply an L5Decision and return a summary of actions taken.

    Most L5 actions (force_reanchor, force_plan_revision) require runner-level
    methods and are handled by PolicyRunner._apply_l5_recovery(). This function
    handles the remaining decisions that operate on the context pack directly:
      - drop_scratch_fraction: evicts a fraction of SCRATCH items
      - inject_diagnostic_prompt: adds a capped diagnostic into STATE

    Returns a dict summarizing what was applied.
    """
    actions: Dict[str, Any] = {
        "force_reanchor": decision.force_reanchor,
        "force_plan_revision": decision.force_plan_revision,
        "scratch_dropped": 0,
        "diagnostic_injected": False,
    }

    # Drop SCRATCH items if requested
    if decision.drop_scratch_fraction > 0.0:
        items = getattr(context_pack, "_items", None)
        if items and isinstance(items, list):
            scratch_indices = [
                i for i, item in enumerate(items)
                if isinstance(item, dict) and item.get("section") == "SCRATCH"
            ]
            n_drop = int(len(scratch_indices) * min(decision.drop_scratch_fraction, 1.0))
            # Drop oldest SCRATCH items
            for idx in scratch_indices[:n_drop]:
                # Mark as None and compact later
                items[idx] = None
            items[:] = [item for item in items if item is not None]
            actions["scratch_dropped"] = n_drop

    # Inject diagnostic prompt
    if decision.inject_diagnostic_prompt:
        diag = str(decision.inject_diagnostic_prompt)[:200]
        context_pack.add_item({
            "tier": "WORKSPACE",
            "section": "STATE",
            "content": f"[DIAGNOSTIC] {diag}",
            "source": "policy:l5_diagnostic",
            "authority_tier": "runtime",
        })
        actions["diagnostic_injected"] = True

    return actions


def apply_l3_decision(
    decision: L3Decision,
) -> Dict[str, Any]:
    """
    Apply an L3Decision and return a summary of actions needed.

    L3 decisions are mostly signals to the runner (run_verifier_now,
    require_verifier_for_completion). This function normalizes the
    decision into a dict that the runner can consume.
    """
    return {
        "run_verifier_now": decision.run_verifier_now,
        "verifier_stage": decision.verifier_stage,
        "require_verifier_for_completion": decision.require_verifier_for_completion,
        "false_success_override": decision.false_success_override,
    }


# ---------------------------------------------------------------------------
# Variant Loading — load spec + instantiate policy
# ---------------------------------------------------------------------------

def load_and_instantiate(spec_path: str) -> HarnessPolicy:
    """
    Load a VariantSpec YAML and instantiate the declared HarnessPolicy subclass.

    The policy_module field in the YAML must be a dotted Python import path
    to a module that contains a class subclassing HarnessPolicy named
    after the variant (e.g., class L3_01_Policy(HarnessPolicy): ...).

    Convention: the module must expose a `create_policy()` factory function
    that returns a HarnessPolicy instance.
    """
    spec = load_variant_spec(Path(spec_path))
    return instantiate_policy(spec)


def instantiate_policy(spec: VariantSpec) -> HarnessPolicy:
    """
    Import the policy module declared in a VariantSpec and instantiate it.

    The module must expose a `create_policy() -> HarnessPolicy` function.
    If no policy_module is specified, returns DefaultPolicy.
    """
    if not spec.policy_module:
        return DefaultPolicy()

    try:
        module = importlib.import_module(spec.policy_module)
    except ImportError as e:
        raise ImportError(
            f"Could not import policy module '{spec.policy_module}' "
            f"for variant {spec.variant_id}: {e}"
        ) from e

    factory = getattr(module, "create_policy", None)
    if factory is None:
        raise AttributeError(
            f"Policy module '{spec.policy_module}' for variant {spec.variant_id} "
            f"must expose a 'create_policy() -> HarnessPolicy' function."
        )

    policy = factory()
    if not isinstance(policy, HarnessPolicy):
        raise TypeError(
            f"create_policy() in '{spec.policy_module}' returned {type(policy).__name__}, "
            f"expected HarnessPolicy subclass."
        )

    return policy


def load_all_variants(specs_dir: str) -> List[Tuple[VariantSpec, HarnessPolicy]]:
    """
    Load all VariantSpec YAMLs from a directory and instantiate their policies.

    Returns a list of (spec, policy) tuples.
    Skips specs that fail to load with a warning.
    """
    import logging
    logger = logging.getLogger(__name__)

    specs_path = Path(specs_dir)
    if not specs_path.is_dir():
        return []

    results: List[Tuple[VariantSpec, HarnessPolicy]] = []
    for yaml_path in sorted(specs_path.glob("*.yaml")):
        try:
            spec = load_variant_spec(yaml_path)
            policy = instantiate_policy(spec)
            results.append((spec, policy))
        except Exception as e:
            logger.warning("Failed to load variant spec %s: %s", yaml_path, e)

    return results
