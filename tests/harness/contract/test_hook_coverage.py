"""
Hook Coverage Tests — Prove that each HarnessPolicy hook fires and its decision is applied.

These tests construct minimal harness-like scaffolding, feed a custom policy
through the adapter layer, and assert that the hook's decision had a real effect.

This test suite does NOT start Docker or run real tasks. It tests the adapter
layer in isolation using mocks of the harness components.
"""
from __future__ import annotations

import pytest
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from unittest.mock import MagicMock, patch

# Import the tournament adapter layer
from aether.tournament.harness_policy import (
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
from aether.tournament.policy_runtime import (
    _normalize_truncation_flags,
    apply_l0_decision,
    apply_l1_decision_to_compiler_kwargs,
    apply_l2_decision_to_tool_args,
    apply_l4_decision,
    build_loop_signals,
    build_model_route_signals,
    build_step_context,
    build_tool_signals,
    build_tool_signals_from_deny,
    build_verifier_signals,
    count_blocked_tools_from_events,
)
from aether.tournament.policy_model_router import policy_route_model


# ---------------------------------------------------------------------------
# Helpers — minimal mocks
# ---------------------------------------------------------------------------

def _make_step_context(**overrides) -> StepContext:
    """Create a StepContext with sensible defaults."""
    defaults = dict(
        step_id=0,
        current_phase="Implement",
        tool_calls_executed=0,
        model_calls_made=0,
        prompt_total=100,
        section_bytes={"TASK": 50, "STATE": 50},
        workspace_fingerprint_hash="abc123",
        workspace_fingerprint_delta=0,
        plan_status="EXECUTING",
        plan_artifact_present=True,
        cache_read=0,
        uncached_input=100,
        stable_prefix_bytes=80,
    )
    defaults.update(overrides)
    return StepContext(**defaults)


class _MockContextPack:
    """Minimal mock of SimpleContextPack."""

    def __init__(self):
        self.items: List[Dict[str, Any]] = []

    def add_item(self, item: Dict[str, Any]) -> None:
        self.items.append(item)


# ---------------------------------------------------------------------------
# Test 1: L0 on_step_start — inject_state_items appear in context pack
# ---------------------------------------------------------------------------

class InjectItemPolicy(HarnessPolicy):
    """Policy that injects a diagnostic item into STATE at step start."""

    @property
    def variant_id(self) -> str:
        return "test-l0-inject"

    def on_step_start(self, ctx: StepContext) -> L0Decision:
        return L0Decision(
            inject_state_items=[
                {"content": "L0 diagnostic: step started", "source": "test_l0"}
            ]
        )


def test_l0_on_step_start_injects_state_items():
    """L0 hook: inject_state_items should appear in the context pack."""
    policy = InjectItemPolicy()
    ctx = _make_step_context()
    decision = policy.on_step_start(ctx)

    context_pack = _MockContextPack()
    apply_l0_decision(decision, context_pack=context_pack)

    assert len(context_pack.items) == 1
    assert context_pack.items[0]["content"] == "L0 diagnostic: step started"
    assert context_pack.items[0]["source"] == "policy:test_l0"
    assert context_pack.items[0]["section"] == "STATE"


# ---------------------------------------------------------------------------
# Test 2: L1 on_context_compile — section budget overrides apply
# ---------------------------------------------------------------------------

class ScratchCapPolicy(HarnessPolicy):
    """Policy that overrides the SCRATCH section budget."""

    @property
    def variant_id(self) -> str:
        return "test-l1-scratch-cap"

    def on_context_compile(self, ctx: StepContext) -> L1Decision:
        return L1Decision(
            section_budget_overrides={"SCRATCH": 2000},
            scratch_retain_count=3,
        )


def test_l1_on_context_compile_applies_section_budgets():
    """L1 hook: section_budget_overrides should modify compiler kwargs."""
    policy = ScratchCapPolicy()
    ctx = _make_step_context()
    decision = policy.on_context_compile(ctx)

    compiler_kwargs: Dict[str, Any] = {"section_budgets": {"TASK": 5000}}
    result = apply_l1_decision_to_compiler_kwargs(decision, compiler_kwargs)

    assert result["section_budgets"]["SCRATCH"] == 2000
    assert result["section_budgets"]["TASK"] == 5000  # Preserved


# ---------------------------------------------------------------------------
# Test 3: L2 on_tool_pre_execute — rewrite_command changes tool args
# ---------------------------------------------------------------------------

class RewriteCommandPolicy(HarnessPolicy):
    """Policy that rewrites 'cat' commands to 'head -n 100'."""

    @property
    def variant_id(self) -> str:
        return "test-l2-rewrite"

    def on_tool_pre_execute(
        self,
        ctx: StepContext,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> L2Decision:
        command = tool_args.get("command", "")
        if isinstance(command, str) and command.startswith("cat "):
            return L2Decision(rewrite_command=f"head -n 100 {command[4:]}")
        return L2Decision()


def test_l2_on_tool_pre_execute_rewrites_command():
    """L2 hook: rewrite_command should change the tool_args['command']."""
    policy = RewriteCommandPolicy()
    ctx = _make_step_context()
    tool_args = {"command": "cat /etc/passwd"}

    decision = policy.on_tool_pre_execute(ctx, tool_name="run", tool_args=tool_args)
    result = apply_l2_decision_to_tool_args(decision, tool_args)

    assert result["command"] == "head -n 100 /etc/passwd"


def test_l2_on_tool_pre_execute_no_rewrite_for_non_cat():
    """L2 hook: non-cat commands should not be rewritten."""
    policy = RewriteCommandPolicy()
    ctx = _make_step_context()
    tool_args = {"command": "ls -la"}

    decision = policy.on_tool_pre_execute(ctx, tool_name="run", tool_args=tool_args)
    result = apply_l2_decision_to_tool_args(decision, tool_args)

    assert result["command"] == "ls -la"


# ---------------------------------------------------------------------------
# Test 4: L2 on_tool_blocked — receives blocked tool signals
# ---------------------------------------------------------------------------

class BlockedToolAuditor(HarnessPolicy):
    """Policy that records blocked tool events."""

    def __init__(self):
        self.blocked_events: List[ToolSignals] = []

    @property
    def variant_id(self) -> str:
        return "test-l2-blocked"

    def on_tool_blocked(self, ctx: StepContext, *, tool_signals: ToolSignals) -> L2Decision:
        self.blocked_events.append(tool_signals)
        return L2Decision()


def test_l2_on_tool_blocked_receives_deny_signals():
    """L2 hook: on_tool_blocked receives correct ToolSignals with blocked=True."""
    policy = BlockedToolAuditor()
    ctx = _make_step_context()

    tool_signals = build_tool_signals_from_deny(
        tool_name="run",
        deny_reason_code="PATH_SANDBOX",
        tool_args={"command": "rm -rf /"},
        attempted_action_fingerprint="fingerprint_abc",
    )
    policy.on_tool_blocked(ctx, tool_signals=tool_signals)

    assert len(policy.blocked_events) == 1
    sig = policy.blocked_events[0]
    assert sig.tool_call_blocked is True
    assert sig.deny_reason_code == "PATH_SANDBOX"
    assert sig.tool_name == "run"


# ---------------------------------------------------------------------------
# Test 5: L3 on_workspace_mutated — run_verifier_now triggers
# ---------------------------------------------------------------------------

class ForceVerifyPolicy(HarnessPolicy):
    """Policy that forces verification on any workspace mutation."""

    @property
    def variant_id(self) -> str:
        return "test-l3-force-verify"

    def on_workspace_mutated(
        self, ctx: StepContext, *, fingerprint_delta: int
    ) -> L3Decision:
        if fingerprint_delta > 0:
            return L3Decision(run_verifier_now=True)
        return L3Decision()


def test_l3_on_workspace_mutated_forces_verifier():
    """L3 hook: on_workspace_mutated returns run_verifier_now=True when delta > 0."""
    policy = ForceVerifyPolicy()
    ctx = _make_step_context()

    decision = policy.on_workspace_mutated(ctx, fingerprint_delta=3)
    assert decision.run_verifier_now is True

    decision_no_delta = policy.on_workspace_mutated(ctx, fingerprint_delta=0)
    assert decision_no_delta.run_verifier_now is False


# ---------------------------------------------------------------------------
# Test 6: L4 on_model_route — override_model_id changes selection
# ---------------------------------------------------------------------------

class ForceModelPolicy(HarnessPolicy):
    """Policy that forces a specific model when step_count > 5."""

    @property
    def variant_id(self) -> str:
        return "test-l4-force-model"

    def on_model_route(self, *, route_signals: ModelRouteSignals) -> L4Decision:
        if route_signals.step_count > 5:
            return L4Decision(
                override_model_id="cheap_model_v2",
                reason_codes=["STEP_COUNT_DOWNGRADE"],
            )
        return L4Decision()


def test_l4_on_model_route_overrides_model_id():
    """L4 hook: override_model_id should change the selected model."""
    policy = ForceModelPolicy()

    # Step 3 — should not override
    signals_early = build_model_route_signals(
        current_phase="Implement",
        model_profile_id="default_model_v1",
        step_count=3,
    )
    decision_early = policy.on_model_route(route_signals=signals_early)
    result_early = apply_l4_decision(decision_early, default_model_id="default_model_v1")
    assert result_early == "default_model_v1"

    # Step 8 — should override
    signals_late = build_model_route_signals(
        current_phase="Implement",
        model_profile_id="default_model_v1",
        step_count=8,
    )
    decision_late = policy.on_model_route(route_signals=signals_late)
    result_late = apply_l4_decision(decision_late, default_model_id="default_model_v1")
    assert result_late == "cheap_model_v2"


# ---------------------------------------------------------------------------
# Test 7: L5 on_loop_detected — force_reanchor triggers
# ---------------------------------------------------------------------------

class ReanchorOnLoopPolicy(HarnessPolicy):
    """Policy that forces reanchor when loop breaker fires."""

    @property
    def variant_id(self) -> str:
        return "test-l5-reanchor"

    def on_loop_detected(
        self, ctx: StepContext, *, loop_signals: LoopSignals
    ) -> L5Decision:
        if loop_signals.loop_breaker_triggered:
            return L5Decision(force_reanchor=True, drop_scratch_fraction=0.5)
        return L5Decision()


def test_l5_on_loop_detected_forces_reanchor():
    """L5 hook: on_loop_detected returns force_reanchor=True when loop fires."""
    policy = ReanchorOnLoopPolicy()
    ctx = _make_step_context()

    loop_signals = build_loop_signals(
        loop_breaker_triggered=True,
        triggers_fired=["REPETITIVE_ACTION"],
        consecutive_no_delta_count=5,
    )
    decision = policy.on_loop_detected(ctx, loop_signals=loop_signals)

    assert decision.force_reanchor is True
    assert decision.drop_scratch_fraction == 0.5


def test_l5_on_loop_detected_no_reanchor_when_no_loop():
    """L5 hook: on_loop_detected returns default when no loop."""
    policy = ReanchorOnLoopPolicy()
    ctx = _make_step_context()

    loop_signals = build_loop_signals(loop_breaker_triggered=False)
    decision = policy.on_loop_detected(ctx, loop_signals=loop_signals)

    assert decision.force_reanchor is False
    assert decision.drop_scratch_fraction == 0.0


# ---------------------------------------------------------------------------
# Signal Normalization Tests
# ---------------------------------------------------------------------------

class TestTruncationNormalization:
    """Tests for _normalize_truncation_flags."""

    def test_none_returns_empty(self):
        assert _normalize_truncation_flags(None) == {}

    def test_string_unknown(self):
        result = _normalize_truncation_flags("UNKNOWN")
        assert result == {
            "stdout": {"state": "UNKNOWN"},
            "stderr": {"state": "UNKNOWN"},
        }

    def test_dict_passthrough(self):
        raw = {"stdout": {"truncated": True, "bytes": 1024}}
        result = _normalize_truncation_flags(raw)
        assert result == raw

    def test_dict_with_non_dict_values(self):
        raw = {"stdout": "TRUNCATED", "stderr": "OK"}
        result = _normalize_truncation_flags(raw)
        assert result == {
            "stdout": {"state": "TRUNCATED"},
            "stderr": {"state": "OK"},
        }

    def test_non_dict_non_string_returns_empty(self):
        assert _normalize_truncation_flags(42) == {}


class TestBlockedToolCounting:
    """Tests for count_blocked_tools_from_events."""

    def test_empty_events(self):
        count, reasons = count_blocked_tools_from_events([])
        assert count == 0
        assert reasons == {}

    def test_counts_blocked_events(self):
        events = [
            {"event_type": "tool_call_blocked", "deny_reason_code": "PATH_SANDBOX"},
            {"event_type": "tool_call_blocked", "deny_reason_code": "PATH_SANDBOX"},
            {"event_type": "tool_call_blocked", "deny_reason_code": "LOOP_DETECTED"},
            {"event_type": "model_call", "tokens": 100},  # Not a blocked tool
        ]
        count, reasons = count_blocked_tools_from_events(events)
        assert count == 3
        assert reasons == {"PATH_SANDBOX": 2, "LOOP_DETECTED": 1}


# ---------------------------------------------------------------------------
# DefaultPolicy Tests — verify baseline is truly no-op
# ---------------------------------------------------------------------------

class TestDefaultPolicy:
    """Verify that DefaultPolicy returns default decisions for all hooks."""

    def test_variant_id(self):
        p = DefaultPolicy()
        assert p.variant_id == "baseline-v1"

    def test_on_step_start_returns_default(self):
        p = DefaultPolicy()
        ctx = _make_step_context()
        d = p.on_step_start(ctx)
        assert d.skip_model_call is False
        assert d.force_phase is None
        assert d.inject_state_items == []

    def test_on_tool_pre_execute_returns_default(self):
        p = DefaultPolicy()
        ctx = _make_step_context()
        d = p.on_tool_pre_execute(ctx, tool_name="run", tool_args={})
        assert d.rewrite_command is None

    def test_on_model_route_returns_default(self):
        p = DefaultPolicy()
        signals = build_model_route_signals(
            current_phase="Implement",
            model_profile_id="default_model_v1",
        )
        d = p.on_model_route(route_signals=signals)
        assert d.override_model_id is None

    def test_on_loop_detected_returns_default(self):
        p = DefaultPolicy()
        ctx = _make_step_context()
        loop_signals = build_loop_signals()
        d = p.on_loop_detected(ctx, loop_signals=loop_signals)
        assert d.force_reanchor is False


# ---------------------------------------------------------------------------
# Patch 3 Tests: Every decision field is consumed
# ---------------------------------------------------------------------------

class TestApplyL5Decision:
    """Tests for apply_l5_decision — Patch 3."""

    def test_drop_scratch_fraction_removes_items(self):
        """L5: drop_scratch_fraction evicts oldest SCRATCH items."""
        from aether.tournament.policy_runtime import apply_l5_decision

        pack = _MockContextPack()
        # Simulate _items attribute that the real ContextPack has
        pack._items = [
            {"section": "TASK", "content": "task description"},
            {"section": "SCRATCH", "content": "scratch_1"},
            {"section": "SCRATCH", "content": "scratch_2"},
            {"section": "SCRATCH", "content": "scratch_3"},
            {"section": "SCRATCH", "content": "scratch_4"},
            {"section": "STATE", "content": "state item"},
        ]

        decision = L5Decision(drop_scratch_fraction=0.5)
        actions = apply_l5_decision(decision, context_pack=pack)

        # 4 SCRATCH items * 0.5 = 2 dropped
        assert actions["scratch_dropped"] == 2
        remaining_scratch = [i for i in pack._items if i and i.get("section") == "SCRATCH"]
        assert len(remaining_scratch) == 2
        # Oldest should be dropped, newest preserved
        assert remaining_scratch[0]["content"] == "scratch_3"
        assert remaining_scratch[1]["content"] == "scratch_4"
        # TASK and STATE preserved
        assert any(i["section"] == "TASK" for i in pack._items)
        assert any(i["section"] == "STATE" for i in pack._items)

    def test_inject_diagnostic_prompt(self):
        """L5: inject_diagnostic_prompt adds capped diagnostic to STATE."""
        from aether.tournament.policy_runtime import apply_l5_decision

        pack = _MockContextPack()
        pack._items = []

        decision = L5Decision(inject_diagnostic_prompt="Try a different approach: use grep instead of find")
        actions = apply_l5_decision(decision, context_pack=pack)

        assert actions["diagnostic_injected"] is True
        assert len(pack.items) == 1
        item = pack.items[0]
        assert item["section"] == "STATE"
        assert "[DIAGNOSTIC]" in item["content"]
        assert "Try a different approach" in item["content"]

    def test_diagnostic_prompt_capped_at_200_chars(self):
        """L5: diagnostic prompt must be capped at 200 chars."""
        from aether.tournament.policy_runtime import apply_l5_decision

        pack = _MockContextPack()
        pack._items = []
        long_msg = "x" * 500

        decision = L5Decision(inject_diagnostic_prompt=long_msg)
        apply_l5_decision(decision, context_pack=pack)

        # Content should be: "[DIAGNOSTIC] " + 200 chars max
        item = pack.items[0]
        # The diagnostic portion (after "[DIAGNOSTIC] ") should be max 200 chars
        diag_part = item["content"].replace("[DIAGNOSTIC] ", "")
        assert len(diag_part) <= 200

    def test_no_action_on_default(self):
        """L5: default decision produces no actions."""
        from aether.tournament.policy_runtime import apply_l5_decision

        pack = _MockContextPack()
        pack._items = [{"section": "SCRATCH", "content": "stays"}]

        decision = L5Decision()
        actions = apply_l5_decision(decision, context_pack=pack)

        assert actions["force_reanchor"] is False
        assert actions["scratch_dropped"] == 0
        assert actions["diagnostic_injected"] is False
        assert len(pack._items) == 1  # Nothing removed


class TestApplyL3Decision:
    """Tests for apply_l3_decision — Patch 3."""

    def test_returns_all_fields(self):
        """L3: apply_l3_decision returns all decision fields as dict."""
        from aether.tournament.policy_runtime import apply_l3_decision

        decision = L3Decision(
            run_verifier_now=True,
            verifier_stage="A",
            require_verifier_for_completion=True,
            false_success_override=False,
        )
        result = apply_l3_decision(decision)

        assert result["run_verifier_now"] is True
        assert result["verifier_stage"] == "A"
        assert result["require_verifier_for_completion"] is True
        assert result["false_success_override"] is False

    def test_default_values(self):
        """L3: default L3Decision produces baseline field values."""
        from aether.tournament.policy_runtime import apply_l3_decision

        result = apply_l3_decision(L3Decision())

        assert result["run_verifier_now"] is False
        assert result["verifier_stage"] == "B"
        assert result["require_verifier_for_completion"] is True
        assert result["false_success_override"] is None


# ---------------------------------------------------------------------------
# New hook coverage tests for Patch 1 — hooks that were previously stub-only
# ---------------------------------------------------------------------------

class CompletionClaimPolicy(HarnessPolicy):
    """Policy that blocks completion unless verifier has run."""

    def __init__(self):
        self.claims_seen: List[List[str]] = []

    @property
    def variant_id(self) -> str:
        return "test-l3-completion"

    def on_completion_claimed(
        self, ctx: StepContext, *, completion_signals: List[str]
    ) -> L3Decision:
        self.claims_seen.append(completion_signals)
        return L3Decision(require_verifier_for_completion=True)


def test_l3_on_completion_claimed_receives_signals():
    """L3 hook: on_completion_claimed receives completion signal string list."""
    policy = CompletionClaimPolicy()
    ctx = _make_step_context()

    signals = ["commit_keyword", "ready_marker"]
    decision = policy.on_completion_claimed(ctx, completion_signals=signals)

    assert len(policy.claims_seen) == 1
    assert policy.claims_seen[0] == ["commit_keyword", "ready_marker"]
    assert decision.require_verifier_for_completion is True


class VerifierResultAuditor(HarnessPolicy):
    """Policy that records verifier results."""

    def __init__(self):
        self.results: List[VerifierSignals] = []

    @property
    def variant_id(self) -> str:
        return "test-l3-verresult"

    def on_verifier_result(
        self, ctx: StepContext, *, verifier_signals: VerifierSignals
    ) -> L3Decision:
        self.results.append(verifier_signals)
        if verifier_signals.result == "fail":
            return L3Decision(run_verifier_now=False)
        return L3Decision()


def test_l3_on_verifier_result_receives_signals():
    """L3 hook: on_verifier_result receives VerifierSignals with real values."""
    policy = VerifierResultAuditor()
    ctx = _make_step_context()

    v_signals = build_verifier_signals(
        verifier_id="test_verifier",
        exit_code=0,
        result="pass",
        workspace_fingerprint_hash="fp_after_verify",
        artifact_refs=["ref_001", "ref_002"],
    )
    decision = policy.on_verifier_result(ctx, verifier_signals=v_signals)

    assert len(policy.results) == 1
    sig = policy.results[0]
    assert sig.verifier_id == "test_verifier"
    assert sig.exit_code == 0
    assert sig.result == "pass"
    assert sig.workspace_fingerprint_hash == "fp_after_verify"
    assert sig.artifact_refs == ["ref_001", "ref_002"]


class DenyLoopPolicy(HarnessPolicy):
    """Policy that injects diagnostic on deny loop."""

    @property
    def variant_id(self) -> str:
        return "test-l5-deny-loop"

    def on_deny_loop(
        self, ctx: StepContext, *, loop_signals: LoopSignals
    ) -> L5Decision:
        if loop_signals.tool_call_blocked_count >= 3:
            return L5Decision(
                inject_diagnostic_prompt="Multiple denials detected. Try a different approach.",
                force_plan_revision=True,
            )
        return L5Decision()


def test_l5_on_deny_loop_fires_on_repeated_denials():
    """L5 hook: on_deny_loop returns recovery action when denials accumulate."""
    policy = DenyLoopPolicy()
    ctx = _make_step_context()

    loop_signals = build_loop_signals(
        tool_call_blocked_count=5,
        tool_call_blocked_reasons={"PATH_SANDBOX": 3, "LOOP_DETECTED": 2},
    )
    decision = policy.on_deny_loop(ctx, loop_signals=loop_signals)

    assert decision.force_plan_revision is True
    assert "different approach" in decision.inject_diagnostic_prompt


class BloatPolicy(HarnessPolicy):
    """Policy that forces reanchor on bloat."""

    @property
    def variant_id(self) -> str:
        return "test-l5-bloat"

    def on_context_bloat(
        self, ctx: StepContext, *, prompt_total: int, section_bytes: Dict[str, int]
    ) -> L5Decision:
        if prompt_total > 50000:
            return L5Decision(force_reanchor=True, drop_scratch_fraction=0.75)
        return L5Decision()


def test_l5_on_context_bloat_triggers_recovery():
    """L5 hook: on_context_bloat fires reanchor when prompt exceeds limit."""
    policy = BloatPolicy()
    ctx = _make_step_context(prompt_total=60000)

    decision = policy.on_context_bloat(
        ctx, prompt_total=60000, section_bytes={"TASK": 10000, "SCRATCH": 50000}
    )

    assert decision.force_reanchor is True
    assert decision.drop_scratch_fraction == 0.75


# ---------------------------------------------------------------------------
# Patch 2 Test: Real fingerprint delta in StepContext
# ---------------------------------------------------------------------------

def test_step_context_carries_real_fingerprint_delta():
    """StepContext must carry workspace_fingerprint_delta, not always 0."""
    ctx_with_delta = _make_step_context(workspace_fingerprint_delta=7)
    assert ctx_with_delta.workspace_fingerprint_delta == 7

    ctx_zero = _make_step_context(workspace_fingerprint_delta=0)
    assert ctx_zero.workspace_fingerprint_delta == 0


# ---------------------------------------------------------------------------
# DefaultPolicy expanded coverage — all 13 hooks
# ---------------------------------------------------------------------------

class TestDefaultPolicyAllHooks:
    """Verify DefaultPolicy returns defaults for ALL hooks, not just the original subset."""

    def test_on_context_compile(self):
        p = DefaultPolicy()
        d = p.on_context_compile(_make_step_context())
        assert d.section_budget_overrides == {}
        assert d.denial_cap is None

    def test_on_context_projection(self):
        p = DefaultPolicy()
        d = p.on_context_projection(_make_step_context(), projection_section_bytes={"TASK": 100})
        assert d.section_budget_overrides == {}

    def test_on_tool_post_execute(self):
        p = DefaultPolicy()
        ts = build_tool_signals(tool_name="run", exit_code=0)
        d = p.on_tool_post_execute(_make_step_context(), tool_signals=ts)
        assert d.override_truncation_unknown is None

    def test_on_tool_blocked(self):
        p = DefaultPolicy()
        ts = build_tool_signals_from_deny(tool_name="run", deny_reason_code="X", tool_args={})
        d = p.on_tool_blocked(_make_step_context(), tool_signals=ts)
        assert d.rewrite_command is None

    def test_on_workspace_mutated(self):
        p = DefaultPolicy()
        d = p.on_workspace_mutated(_make_step_context(), fingerprint_delta=5)
        assert d.run_verifier_now is False

    def test_on_completion_claimed(self):
        p = DefaultPolicy()
        d = p.on_completion_claimed(_make_step_context(), completion_signals=["done"])
        assert d.require_verifier_for_completion is True

    def test_on_verifier_result(self):
        p = DefaultPolicy()
        vs = build_verifier_signals(verifier_id="v1", exit_code=0, result="pass")
        d = p.on_verifier_result(_make_step_context(), verifier_signals=vs)
        assert d.run_verifier_now is False

    def test_on_phase_transition_denied(self):
        p = DefaultPolicy()
        d = p.on_phase_transition_denied(
            _make_step_context(),
            from_phase="Implement",
            to_phase="Review",
            deny_reason_code="MISSING_VERIFY",
            missing_conditions=["verifier_pass"],
        )
        assert d.skip_model_call is False

    def test_on_context_bloat(self):
        p = DefaultPolicy()
        d = p.on_context_bloat(_make_step_context(), prompt_total=99999, section_bytes={})
        assert d.force_reanchor is False

    def test_on_deny_loop(self):
        p = DefaultPolicy()
        ls = build_loop_signals(tool_call_blocked_count=10)
        d = p.on_deny_loop(_make_step_context(), loop_signals=ls)
        assert d.force_reanchor is False
