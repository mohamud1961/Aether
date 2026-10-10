"""Research-only Harbor adapter for revision-9.2 Aether+GLM diagnostics.

This module is never selected by production launch authority. It exists so exposed
Terminal-Bench development diagnostics can use Harbor's native task lifecycle,
official task image and official grader while running the exact current KH/full
GLM research configuration.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping

from .challenger_runtime.config import (
    ACTIVE_CLAIM_LEDGER_MODES, CHALLENGER_EVIDENCE_ROOT_ENV, FINISH_CARD_MODES, CHALLENGER_RUN_ID_ENV, CLAIM_LEDGER_ENV, CONTROL as CLAIM_LEDGER_CONTROL,
    resolve_claim_ledger_mode, runtime_identity as claim_ledger_runtime_identity,
)
from .managed_context_checkpoint import MANAGED_CONTEXT_DEFAULT_KEEP_EXCHANGES, MANAGED_CONTEXT_DEFAULT_TRIGGER_TOKENS
from .context_file.adapter import ContextFileAdapter
from .context_file.config import CTX_BUDGET_ENV, is_context_file_mode, resolve_budget
from .context_tree.config import (
    CONTEXT_MODE_ENV, CONTROL as CONTEXT_MODE_CONTROL,
    COMPACTOR_DEPLOYMENT, COMPACTOR_ROUTE_KEY,
    M_TREE_V1 as CONTEXT_MODE_M_TREE_V1, M_TREE_EVIDENCE_ROOT_ENV,
    COMPACTOR_LIMITER_PATH_ENV, resolve_context_mode,
    runtime_identity as context_runtime_identity, validate_context_launch,
)
from .harbor_agent import AetherHarborAgent
from .harbor_executor import HarborEnvironmentExecutor
from .harbor_runtime import (
    DisabledVerifier,
    JUDGE_VERIFIER_CONTROL_ARM,
    JUDGE_VERIFIER_V3_TYPED_ARM,
    _build_structural_envmap,
    _update_agent_context,
    build_selected_judge_v3_verifier,
    discover_harbor_workspace,
    literal_task_absolute_paths,
    selected_judge_verifier_arm,
)
from .model_profile import GLM_RESEARCH_PAR2_PROFILE, GLM_RESEARCH_PROFILES, ModelProfile
from .persistent_flat_advanced import PROVIDER_TOOL_SHAPE_FLAT
from .persistent_provider_protocol import persistent_chat_provider_tools
from .providers.chat_model import ChatCompletionsModelCallable, make_chat_callable
from .providers.judge_broker import FileBrokerEvaluator
from .trace_aware_judge_advice import MODE_HARD_STUCK_TRACE_V1, TraceAwareJudgeAdvice
from .research_runtime import (
    PROVIDER_LIMITER_PATH_ENV,
    PROVIDER_RPM_ENV,
    PROVIDER_TPM_ENV,
    PROVIDER_WINDOW_ANCHOR_ENV,
    PROVIDER_WINDOW_ENV,
    RUNTIME_CONFIG_SHA256_ENV,
    ResearchRuntimeConfig,
)
from .run_adapter import run_task
from .packet_lean import PacketModeError, resolve_packet_mode
from .env_lean import EnvModeError, resolve_env_mode
from .history_lean import HistoryModeError, resolve_history_mode
from .sampling import SamplingModeError, resolve_sampling_mode, sampling_kwargs
from .progress_checkpoints import (
    PROGRESS_CHECKPOINTS_ENV, STATE_SNAPSHOT_ENV, SUCCESS_CONTRACT_ENV, FINISH_REVIEW_ENV, ProgressCheckpointsError,
    progress_checkpoints_runtime_identity, resolve_progress_checkpoint_config,
    resolve_state_snapshot_mode, resolve_success_contract_mode, resolve_finish_review_mode,
)
from .criteria_mode import criteria_mode_runtime_identity
from .session_affinity import SessionAffinityError, check_selector_matches_key, resolve_session_affinity_mode
from .protocol_resilience import (
    OUTPUT_CAP_MODES, TOLERANT_ARGUMENT_MODES, ProtocolResilienceError,
    resolve_protocol_resilience,
)
from .deadline_visibility import (
    VISIBLE_V1 as DEADLINE_VISIBLE_V1, DeadlineVisibilityError, agent_deadline_from_env,
    resolve_deadline_visibility_mode,
)
from .run_deadline import KernelRunTimeout, remaining_run_s, run_deadline
from .thin_loop import ContextTreeAdapter


G4_PROFILE_SELECTOR = "glm-research-par-v1"
G4_PROFILE_SELECTOR_ENV = "AETHER_G4_PROFILE_SELECTOR"
G4_PROFILE_SELECTORS = frozenset({
    "glm-research-v1",
    "glm-research-par-v1",
    "glm-research-par2-v1",
})
# Provisioned capacity consolidated onto -par on 2026-10-10 (principal-approved):
# -par 450k TPM, -par-2 40k (M-TREE compactor), base 10k. Client limits keep ~7% headroom.
G4_ROUTE_LIMITS = {
    "glm-research-v1": {
        "client_tpm": 9_000,
        "client_rpm": 9,
        "window_s": 62.0,
        "observed_tpm": 10_000,
        "observed_rpm": 10,
        "observed_window_s": 60.0,
        "limiter_name": "shared_glm_base_limiter.json",
    },
    "glm-research-par-v1": {
        "client_tpm": 420_000,
        "client_rpm": 420,
        "window_s": 62.0,
        "observed_tpm": 450_000,
        "observed_rpm": 450,
        "observed_window_s": 60.0,
        "limiter_name": "shared_glm_par_limiter.json",
    },
    "glm-research-par2-v1": {
        "client_tpm": 36_000,
        "client_rpm": 36,
        "window_s": 62.0,
        "observed_tpm": 40_000,
        "observed_rpm": 40,
        "observed_window_s": 60.0,
        "limiter_name": "shared_glm_par2_limiter.json",
    },
}
G4_REASONING_EFFORT = "high"
G4_REASONING_EFFORT_ENV = "AETHER_G4_REASONING_EFFORT"
G4_REASONING_EFFORT_MODES = frozenset({G4_REASONING_EFFORT, "max"})
G4_SOLVER_MAX_OUTPUT_TOKENS = 32768
G4_TOOL_SURFACE_ENV = "AETHER_G4_TOOL_SURFACE_MODE"
G4_TOOL_SURFACE_CONTROL = "static_kernel_v1"
G4_TOOL_SURFACE_JOBS_V1 = "static_kernel_jobs_v1"
G4_TOOL_SURFACE_EDIT_V1 = "static_kernel_edit_v1"
G4_TOOL_SURFACE_EDIT_FLAT_V1 = "static_kernel_edit_flat_v1"
G4_TOOL_SURFACE_MODES = frozenset({
    G4_TOOL_SURFACE_CONTROL,
    G4_TOOL_SURFACE_JOBS_V1,
    G4_TOOL_SURFACE_EDIT_V1,
    G4_TOOL_SURFACE_EDIT_FLAT_V1,
})
G4_ASYNC_MODE_ENV = "AETHER_G4_ASYNC_MODE"
G4_ASYNC_CONTROL = "control"
G4_ASYNC_INDEPENDENT_JOBS_V1 = "independent_jobs_v1"
G4_ASYNC_MODES = frozenset({
    G4_ASYNC_CONTROL,
    G4_ASYNC_INDEPENDENT_JOBS_V1,
})
G4_RUNTIME_OPERATION_REFRESH_ENV = "AETHER_G4_RUNTIME_OPERATION_REFRESH"
G4_RUNTIME_OPERATION_REFRESH_CONTROL = "control"
G4_RUNTIME_OPERATION_REFRESH_V1 = "runtime_operation_refresh_v1"
G4_RUNTIME_OPERATION_REFRESH_MODES = frozenset({
    G4_RUNTIME_OPERATION_REFRESH_CONTROL,
    G4_RUNTIME_OPERATION_REFRESH_V1,
})
G4_JUDGE_ADVICE_ENV = "AETHER_G4_JUDGE_ADVICE_MODE"
G4_JUDGE_ADVICE_CONTROL = "control"
G4_JUDGE_ADVICE_HARD_STUCK_TRACE_V1 = MODE_HARD_STUCK_TRACE_V1
G4_JUDGE_ADVICE_MODES = frozenset({
    G4_JUDGE_ADVICE_CONTROL,
    G4_JUDGE_ADVICE_HARD_STUCK_TRACE_V1,
})
G4_JUDGE_ADVICE_MODEL_ENV = "AETHER_G4_JUDGE_ADVICE_MODEL"
G4_JUDGE_ADVICE_BROKER_DIR_ENV = "AETHER_G4_JUDGE_ADVICE_BROKER_DIR"
G4_JUDGE_ADVICE_JOURNAL_ENV = "AETHER_G4_JUDGE_ADVICE_JOURNAL"
G4_JUDGE_ADVICE_CAP_GBP_ENV = "AETHER_G4_JUDGE_ADVICE_CAP_GBP"
G4_JUDGE_ADVICE_FROZEN_MODEL = "judge-1.13.0"
G4_COMPLETION_SIGNAL_ENV = "AETHER_G4_COMPLETION_SIGNAL_MODE"
G4_COMPLETION_SIGNAL_CONTROL = "control"
G4_COMPLETION_SIGNAL_VERIFICATION_AUTHORITY_V2 = "verification_authority_v2"
G4_COMPLETION_SIGNAL_VERIFICATION_ORACLE_GUARD_V1 = "verification_oracle_guard_v1"
G4_COMPLETION_SIGNAL_MODES = frozenset({
    G4_COMPLETION_SIGNAL_CONTROL,
    G4_COMPLETION_SIGNAL_VERIFICATION_AUTHORITY_V2,
    G4_COMPLETION_SIGNAL_VERIFICATION_ORACLE_GUARD_V1,
})
G4_REALITY_TRANSPORT_ENV = "AETHER_G4_REALITY_TRANSPORT_MODE"
G4_REALITY_TRANSPORT_CONTROL = "observation_history_v1"
G4_REALITY_TRANSPORT_PT_RA = "reasoning_actions_no_results_v1"
G4_REALITY_TRANSPORT_PT_R1 = "reasoning_latest_action_no_results_v1"
G4_REALITY_TRANSPORT_PT_NR = "actions_results_no_reasoning_v1"
G4_REALITY_TRANSPORT_MODES = frozenset({
    G4_REALITY_TRANSPORT_CONTROL,
    G4_REALITY_TRANSPORT_PT_RA,
    G4_REALITY_TRANSPORT_PT_R1,
    G4_REALITY_TRANSPORT_PT_NR,
})
G4_CAPACITY_RECOVERY_ENV = "AETHER_G4_CAPACITY_RECOVERY_MODE"
G4_CAPACITY_RECOVERY_CONTROL = "control"
G4_CAPACITY_RECOVERY_CHECKPOINT_AT_CAPACITY_V1 = "checkpoint_at_capacity_v1"
G4_CAPACITY_RECOVERY_MODES = frozenset({
    G4_CAPACITY_RECOVERY_CONTROL,
    G4_CAPACITY_RECOVERY_CHECKPOINT_AT_CAPACITY_V1,
})
G4_SAME_MODEL_VERIFIER_ENV = "AETHER_G4_SAME_MODEL_VERIFIER_MODE"
G4_SAME_MODEL_VERIFIER_CONTROL = "control"
G4_SAME_MODEL_VERIFIER_VF1 = "vf1_same_model_terminal_v1"
G4_SAME_MODEL_VERIFIER_MODES = frozenset({
    G4_SAME_MODEL_VERIFIER_CONTROL,
    G4_SAME_MODEL_VERIFIER_VF1,
})
G4_ORACLE_RESPONSE_ENV = "AETHER_G4_ORACLE_RESPONSE_MODE"
G4_ORACLE_RESPONSE_CONTROL = "control"
G4_ORACLE_RESPONSE_V1B = "oracle_hold_once_v1"
G4_ORACLE_RESPONSE_MODES = frozenset({
    G4_ORACLE_RESPONSE_CONTROL,
    G4_ORACLE_RESPONSE_V1B,
})
G4_DELIVERY_HYGIENE_ENV = "AETHER_G4_DELIVERY_HYGIENE_MODE"
G4_DELIVERY_HYGIENE_CONTROL = "control"
G4_DELIVERY_HYGIENE_HY1 = "delivery_hygiene_v1"
G4_DELIVERY_HYGIENE_MODES = frozenset({
    G4_DELIVERY_HYGIENE_CONTROL,
    G4_DELIVERY_HYGIENE_HY1,
})
G4_SOLVER_REASONING_ENV = "AETHER_G4_SOLVER_REASONING_MODE"
G4_SOLVER_REASONING_CONTROL = "control"
G4_SOLVER_REASONING_DISCRIMINATING = "discriminating_experiment_v1"
G4_SOLVER_REASONING_MODES = frozenset({
    G4_SOLVER_REASONING_CONTROL,
    G4_SOLVER_REASONING_DISCRIMINATING,
})
G4_PROVIDER_TPM = 250000
G4_PROVIDER_RPM = 250
G4_PROVIDER_WINDOW_S = 62.0
G4_OBSERVED_PROVIDER_TPM = 300000
G4_OBSERVED_PROVIDER_RPM = 300
G4_OBSERVED_PROVIDER_WINDOW_S = 60.0

# Exact current KH/full treatment. Keep this tuple small and mechanically testable.
G4_KH_RUN_TASK_CONFIG = {
    "solver_reanchor_mode": "current_full",
    "solver_context_mode": "full",
    "context_cleanup_mode": "off",
    "completion_record_mode": "off",
    "solver_loop": "thin",
    "thin_failed_observation_disposition_mode": "control",
    "solver_reasoning_mode": "control",
    "solver_async_mode": "control",
    "solver_task_contract_mode": "raw_task_control",
    "solver_model_view_mode": "hygiene_lean_v1",
    "solver_tool_surface_mode": "static_kernel_v1",
    "solver_prefix_renderer": "incumbent_context",
    "solver_reality_transport_mode": "observation_history_v1",
    "solver_working_context_mode": "off",
    "solver_hosted_tool_search_mode": "control",
    "verifier_activation_continuity_mode": "fresh_compact_control",
    "boundary_verification_mode": "control",
    "completion_disposition_mode": "control",
    "provider_frontier_recovery_mode": "control",
    "refresh_runtime_operation_status": False,
    "probe_runtime_capabilities": False,
    "oracle_finish_response_mode": "control",
    "delivery_hygiene_mode": "control",
}


def g4_tool_surface_mode() -> str:
    """Return the explicit research-only tool-surface treatment."""
    mode = str(
        os.environ.get(G4_TOOL_SURFACE_ENV, G4_TOOL_SURFACE_CONTROL)
        or G4_TOOL_SURFACE_CONTROL
    ).strip().lower()
    if mode not in G4_TOOL_SURFACE_MODES:
        raise RuntimeError(
            f"{G4_TOOL_SURFACE_ENV} must be one of {sorted(G4_TOOL_SURFACE_MODES)!r}, "
            f"got {mode!r}"
        )
    return mode


def g4_async_mode() -> str:
    """Return the explicit research-only async scheduling treatment."""
    mode = str(
        os.environ.get(G4_ASYNC_MODE_ENV, G4_ASYNC_CONTROL)
        or G4_ASYNC_CONTROL
    ).strip().lower()
    if mode not in G4_ASYNC_MODES:
        raise RuntimeError(
            f"{G4_ASYNC_MODE_ENV} must be one of {sorted(G4_ASYNC_MODES)!r}, "
            f"got {mode!r}"
        )
    return mode


def g4_runtime_operation_refresh_mode() -> str:
    """Return the explicit one-factor automatic lifecycle-refresh treatment."""
    mode = str(
        os.environ.get(
            G4_RUNTIME_OPERATION_REFRESH_ENV,
            G4_RUNTIME_OPERATION_REFRESH_CONTROL,
        )
        or G4_RUNTIME_OPERATION_REFRESH_CONTROL
    ).strip().lower()
    if mode not in G4_RUNTIME_OPERATION_REFRESH_MODES:
        raise RuntimeError(
            f"{G4_RUNTIME_OPERATION_REFRESH_ENV} must be one of " 
            f"{sorted(G4_RUNTIME_OPERATION_REFRESH_MODES)!r}, got {mode!r}"
        )
    return mode


def g4_judge_advice_mode() -> str:
    """Return the explicit default-off hard-trace JUDGE advice treatment."""
    mode = str(
        os.environ.get(G4_JUDGE_ADVICE_ENV, G4_JUDGE_ADVICE_CONTROL)
        or G4_JUDGE_ADVICE_CONTROL
    ).strip().lower()
    if mode not in G4_JUDGE_ADVICE_MODES:
        raise RuntimeError(
            f"{G4_JUDGE_ADVICE_ENV} must be one of {sorted(G4_JUDGE_ADVICE_MODES)!r}, "
            f"got {mode!r}"
        )
    return mode


def _required_g4_judge_env(name: str) -> str:
    value = str(os.environ.get(name, "") or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for G4 trace-aware JUDGE advice")
    return value


def build_g4_trace_aware_judge_assistance(*, cancellation_event: Any) -> Any | None:
    """Build credential-free one-shot J-S assistance; default control is None."""
    mode = g4_judge_advice_mode()
    if mode == G4_JUDGE_ADVICE_CONTROL:
        return None
    model = _required_g4_judge_env(G4_JUDGE_ADVICE_MODEL_ENV)
    if model != G4_JUDGE_ADVICE_FROZEN_MODEL:
        raise RuntimeError(
            f"{G4_JUDGE_ADVICE_MODEL_ENV} must equal {G4_JUDGE_ADVICE_FROZEN_MODEL!r}, "
            f"got {model!r}"
        )
    chat_journal = Path(
        str(os.environ.get("AETHER_CHAT_TELEMETRY_JOURNAL", "") or "").strip()
    )
    if not str(chat_journal) or str(chat_journal) == ".":
        raise RuntimeError("AETHER_CHAT_TELEMETRY_JOURNAL is required for G4 J-S")
    broker_dir = Path(_required_g4_judge_env(G4_JUDGE_ADVICE_BROKER_DIR_ENV))
    journal = Path(_required_g4_judge_env(G4_JUDGE_ADVICE_JOURNAL_ENV))
    cap_gbp = _required_g4_judge_env(G4_JUDGE_ADVICE_CAP_GBP_ENV)
    evaluator = FileBrokerEvaluator(
        broker_dir=broker_dir,
        journal=journal,
        expected_result_model=model,
        max_calls=1,
        cap_gbp=cap_gbp,
    )
    assistance = TraceAwareJudgeAdvice(
        evaluator,
        model=model,
        telemetry_journal=chat_journal,
    )
    assistance.bind_run_cancellation(cancellation_event)
    return assistance


def g4_completion_signal_mode() -> str:
    """Return the explicit task-authority completion-signal treatment."""
    mode = str(
        os.environ.get(G4_COMPLETION_SIGNAL_ENV, G4_COMPLETION_SIGNAL_CONTROL)
        or G4_COMPLETION_SIGNAL_CONTROL
    ).strip().lower()
    if mode not in G4_COMPLETION_SIGNAL_MODES:
        raise RuntimeError(
            f"{G4_COMPLETION_SIGNAL_ENV} must be one of " 
            f"{sorted(G4_COMPLETION_SIGNAL_MODES)!r}, got {mode!r}"
        )
    return mode


def g4_reality_transport_mode() -> str:
    """Return the explicit research-only continuity transport treatment."""
    mode = str(
        os.environ.get(G4_REALITY_TRANSPORT_ENV, G4_REALITY_TRANSPORT_CONTROL)
        or G4_REALITY_TRANSPORT_CONTROL
    ).strip().lower()
    if mode not in G4_REALITY_TRANSPORT_MODES:
        raise RuntimeError(
            f"{G4_REALITY_TRANSPORT_ENV} must be one of {sorted(G4_REALITY_TRANSPORT_MODES)!r}, "
            f"got {mode!r}"
        )
    return mode


def g4_capacity_recovery_mode() -> str:
    """Return the explicit research-only capacity-boundary recovery treatment."""
    mode = str(
        os.environ.get(G4_CAPACITY_RECOVERY_ENV, G4_CAPACITY_RECOVERY_CONTROL)
        or G4_CAPACITY_RECOVERY_CONTROL
    ).strip().lower()
    if mode not in G4_CAPACITY_RECOVERY_MODES:
        raise RuntimeError(
            f"{G4_CAPACITY_RECOVERY_ENV} must be one of "
            f"{sorted(G4_CAPACITY_RECOVERY_MODES)!r}, got {mode!r}"
        )
    return mode


def g4_context_mode() -> str:
    """Read the registered selector; never let an unknown value fall through."""
    raw = str(os.environ.get(CONTEXT_MODE_ENV, CONTEXT_MODE_CONTROL) or CONTEXT_MODE_CONTROL).strip()
    try:
        return resolve_context_mode(raw)
    except ValueError as exc:
        raise RuntimeError(f"{CONTEXT_MODE_ENV} is invalid: {exc}") from exc


def g4_claim_ledger_mode() -> str:
    """Read the registered CHALLENGER selector; an unknown value is a hard error, never control."""
    raw = str(os.environ.get(CLAIM_LEDGER_ENV, CLAIM_LEDGER_CONTROL) or CLAIM_LEDGER_CONTROL).strip()
    try:
        return resolve_claim_ledger_mode(raw)
    except ValueError as exc:
        raise RuntimeError(f"{CLAIM_LEDGER_ENV} is invalid: {exc}") from exc


def g4_deadline_visibility_mode() -> str:
    """Read the registered deadline-visibility selector; an unknown value is a hard error."""
    try:
        return resolve_deadline_visibility_mode(environ=os.environ)
    except DeadlineVisibilityError as exc:
        raise RuntimeError(f"AETHER_G4_DEADLINE_VISIBILITY is invalid: {exc}") from exc


def g4_packet_mode() -> str:
    """Read the registered packet-mode selector; an unknown value is a hard error."""
    try:
        return resolve_packet_mode(environ=os.environ)
    except PacketModeError as exc:
        raise RuntimeError(f"AETHER_G4_PACKET_MODE is invalid: {exc}") from exc


def g4_env_mode() -> str:
    """Read the registered env-mode selector; an unknown value is a hard error."""
    try:
        return resolve_env_mode(environ=os.environ)
    except EnvModeError as exc:
        raise RuntimeError(f"AETHER_G4_ENV_MODE is invalid: {exc}") from exc


def g4_history_mode() -> str:
    """Read the registered history-mode selector; an unknown value is a hard error."""
    try:
        return resolve_history_mode(environ=os.environ)
    except HistoryModeError as exc:
        raise RuntimeError(f"AETHER_G4_HISTORY_MODE is invalid: {exc}") from exc


def g4_session_affinity_mode() -> str:
    """Read the registered session-affinity selector; unknown value or selector/key mismatch is a hard error."""
    try:
        mode = resolve_session_affinity_mode(environ=os.environ)
        check_selector_matches_key(mode, os.environ)
        return mode
    except SessionAffinityError as exc:
        raise RuntimeError(f"AETHER_G4_SESSION_AFFINITY is invalid: {exc}") from exc


def g4_sampling_mode() -> str:
    """Read the registered sampling selector; an unknown value is a hard error."""
    try:
        return resolve_sampling_mode(environ=os.environ)
    except SamplingModeError as exc:
        raise RuntimeError(f"AETHER_G4_SAMPLING is invalid: {exc}") from exc


def g4_progress_checkpoints(claim_ledger: str, deadline_visibility: str) -> tuple[str, tuple[int, ...]]:
    """Read the checkpoint selector and enforce its CHALLENGER/deadline dependencies."""
    try:
        mode, fractions = resolve_progress_checkpoint_config(environ=os.environ)
    except ProgressCheckpointsError as exc:
        raise RuntimeError(f"{PROGRESS_CHECKPOINTS_ENV} is invalid: {exc}") from exc
    if fractions and claim_ledger not in ("challenger_v4", "challenger_v5"):
        raise RuntimeError(f"{PROGRESS_CHECKPOINTS_ENV} requires claim-ledger challenger_v4 or challenger_v5")
    if fractions and deadline_visibility != DEADLINE_VISIBLE_V1:
        raise RuntimeError(f"{PROGRESS_CHECKPOINTS_ENV} requires visible deadline")
    return mode, fractions


def g4_state_snapshot(progress_mode: str, claim_ledger: str = "challenger_v5") -> str:
    try:
        selected = resolve_state_snapshot_mode(environ=os.environ)
    except ProgressCheckpointsError as exc:
        raise RuntimeError(f"{STATE_SNAPSHOT_ENV} is invalid: {exc}") from exc
    if progress_mode == "v2" and selected != "v1":
        raise RuntimeError("progress-checkpoints-mode v2 requires state-snapshot v1")
    return selected


def g4_success_contract(progress_mode: str) -> str:
    try:
        selected = resolve_success_contract_mode(environ=os.environ)
    except ProgressCheckpointsError as exc:
        raise RuntimeError(f"{SUCCESS_CONTRACT_ENV} is invalid: {exc}") from exc
    if selected == "v1" and progress_mode != "v2":
        raise RuntimeError("success-contract v1 requires progress-checkpoints-mode v2")
    return selected


def g4_finish_review(claim_ledger: str, state_snapshot: str) -> str:
    try:
        selected = resolve_finish_review_mode(environ=os.environ)
    except ProgressCheckpointsError as exc:
        raise RuntimeError(f"{FINISH_REVIEW_ENV} is invalid: {exc}") from exc
    if selected != "control" and (claim_ledger != "challenger_v5" or state_snapshot != "v1"):
        raise RuntimeError(f"{FINISH_REVIEW_ENV} requires claim-ledger challenger_v5 and state-snapshot v1")
    return selected


def g4_protocol_resilience() -> str:
    """Read the registered protocol-resilience selector; an unknown value is a hard error."""
    try:
        return resolve_protocol_resilience(environ=os.environ)
    except ProtocolResilienceError as exc:
        raise RuntimeError(f"AETHER_G4_PROTOCOL_RESILIENCE is invalid: {exc}") from exc


def g4_visible_deadline_sec(mode: str) -> float | None:
    """Launcher-supplied agent timeout, only under visible_v1 (never inferred or defaulted)."""
    if mode != DEADLINE_VISIBLE_V1:
        return None
    try:
        return agent_deadline_from_env(os.environ)
    except DeadlineVisibilityError as exc:
        raise RuntimeError(f"AETHER_AGENT_DEADLINE_SEC is invalid: {exc}") from exc


def g4_delivery_hygiene_mode() -> str:
    """Return the explicit default-off HY1 delivery/state-safety arm."""
    mode = str(
        os.environ.get(G4_DELIVERY_HYGIENE_ENV, G4_DELIVERY_HYGIENE_CONTROL)
        or G4_DELIVERY_HYGIENE_CONTROL
    ).strip().lower()
    if mode not in G4_DELIVERY_HYGIENE_MODES:
        raise RuntimeError(
            f"{G4_DELIVERY_HYGIENE_ENV} must be one of "
            f"{sorted(G4_DELIVERY_HYGIENE_MODES)!r}, got {mode!r}"
        )
    return mode


def g4_solver_reasoning_mode() -> str:
    """Return the explicit default-off generic discriminating-experiment arm."""
    mode = str(
        os.environ.get(G4_SOLVER_REASONING_ENV, G4_SOLVER_REASONING_CONTROL)
        or G4_SOLVER_REASONING_CONTROL
    ).strip().lower()
    if mode not in G4_SOLVER_REASONING_MODES:
        raise RuntimeError(
            f"{G4_SOLVER_REASONING_ENV} must be one of "
            f"{sorted(G4_SOLVER_REASONING_MODES)!r}, got {mode!r}"
        )
    return mode


def g4_oracle_response_mode() -> str:
    """Return the explicit default-off V1b active oracle-response arm."""
    mode = str(
        os.environ.get(G4_ORACLE_RESPONSE_ENV, G4_ORACLE_RESPONSE_CONTROL)
        or G4_ORACLE_RESPONSE_CONTROL
    ).strip().lower()
    if mode not in G4_ORACLE_RESPONSE_MODES:
        raise RuntimeError(
            f"{G4_ORACLE_RESPONSE_ENV} must be one of "
            f"{sorted(G4_ORACLE_RESPONSE_MODES)!r}, got {mode!r}"
        )
    return mode


def g4_same_model_verifier_mode() -> str:
    """Return the explicit default-off VF1 same-model terminal-review arm."""
    mode = str(
        os.environ.get(
            G4_SAME_MODEL_VERIFIER_ENV, G4_SAME_MODEL_VERIFIER_CONTROL
        )
        or G4_SAME_MODEL_VERIFIER_CONTROL
    ).strip().lower()
    if mode not in G4_SAME_MODEL_VERIFIER_MODES:
        raise RuntimeError(
            f"{G4_SAME_MODEL_VERIFIER_ENV} must be one of "
            f"{sorted(G4_SAME_MODEL_VERIFIER_MODES)!r}, got {mode!r}"
        )
    return mode


def g4_profile_selector() -> str:
    """Return the exact launcher-sealed GLM route selector."""
    selector = str(
        os.environ.get(G4_PROFILE_SELECTOR_ENV, G4_PROFILE_SELECTOR)
        or G4_PROFILE_SELECTOR
    ).strip()
    if selector not in G4_PROFILE_SELECTORS:
        raise RuntimeError(
            f"{G4_PROFILE_SELECTOR_ENV} must be one of "
            f"{sorted(G4_PROFILE_SELECTORS)!r}, got {selector!r}"
        )
    return selector


def g4_reasoning_effort() -> str:
    """Return the solver reasoning effort selected by env (default ``high``)."""
    mode = str(
        os.environ.get(G4_REASONING_EFFORT_ENV, G4_REASONING_EFFORT)
        or G4_REASONING_EFFORT
    ).strip().lower()
    if mode not in G4_REASONING_EFFORT_MODES:
        raise RuntimeError(
            f"{G4_REASONING_EFFORT_ENV} must be one of "
            f"{sorted(G4_REASONING_EFFORT_MODES)!r}, got {mode!r}"
        )
    return mode


def g4_kh_profile(reasoning_effort: str | None = None) -> ModelProfile:
    """Return the GLM profile used by KH research rows (effort from env unless given)."""
    base = GLM_RESEARCH_PROFILES[g4_profile_selector()]
    effort = g4_reasoning_effort() if reasoning_effort is None else reasoning_effort
    if effort not in G4_REASONING_EFFORT_MODES:
        raise RuntimeError(f"unsupported G4 reasoning effort: {effort!r}")
    return replace(
        base,
        solver_reasoning_effort=effort,
        solver_max_output_tokens=G4_SOLVER_MAX_OUTPUT_TOKENS,
    )


def _positive_int_env(name: str, default: int) -> int:
    raw = str(os.environ.get(name, "") or "").strip()
    value = default if not raw else int(raw)
    if value <= 0:
        raise RuntimeError(f"{name} must be positive")
    return value


def _positive_float_env(name: str, default: float) -> float:
    raw = str(os.environ.get(name, "") or "").strip()
    value = default if not raw else float(raw)
    if value <= 0:
        raise RuntimeError(f"{name} must be positive")
    return value



def context_mode_profile(profile: ModelProfile, context_mode: str | None) -> ModelProfile:
    """The provider profile a context arm actually runs with.

    M-TREE and the context file replace capacity reanchoring with an explicit
    overflow failure, which changes the profile (and its hash). Launchers must
    authorize this exact profile, so both the runtime and the launchers use
    this one function.
    """
    if context_mode == CONTEXT_MODE_M_TREE_V1:
        # Recovery mode controls what prior observations are added after a
        # capacity reanchor; "off" does not disable the reset itself. M-TREE
        # replaces that behavior with an explicit epoch-overflow failure.
        return replace(
            profile,
            chat_capacity_reanchor_recovery_mode="off",
            chat_capacity_overflow_action="m_tree_epoch_overflow",
        )
    if context_mode is not None and is_context_file_mode(context_mode):
        return replace(
            profile,
            chat_capacity_reanchor_recovery_mode="off",
            chat_capacity_overflow_action="managed_context_context_overflow",
        )
    return profile

def g4_runtime_config(
    *,
    state_root: Path,
    tool_surface_mode: str | None = None,
    reality_transport_mode: str | None = None,
    completion_signal_mode: str | None = None,
    capacity_recovery_mode: str | None = None,
    context_mode: str | None = None,
) -> ResearchRuntimeConfig:
    """Resolve one explicit research runtime from the launcher's sealed env."""
    selector = g4_profile_selector()
    profile = g4_kh_profile()
    route_limits = G4_ROUTE_LIMITS[selector]
    selected_capacity_recovery = (
        g4_capacity_recovery_mode()
        if capacity_recovery_mode is None
        else str(capacity_recovery_mode).strip().lower()
    )
    if selected_capacity_recovery not in G4_CAPACITY_RECOVERY_MODES:
        raise RuntimeError(
            f"unsupported G4 capacity recovery mode: {selected_capacity_recovery!r}"
        )
    selected_tool_surface = (
        g4_tool_surface_mode()
        if tool_surface_mode is None
        else str(tool_surface_mode).strip().lower()
    )
    if selected_tool_surface not in G4_TOOL_SURFACE_MODES:
        raise RuntimeError(f"unsupported G4 tool surface: {selected_tool_surface!r}")
    selected_reality_transport = (
        g4_reality_transport_mode()
        if reality_transport_mode is None
        else str(reality_transport_mode).strip().lower()
    )
    if selected_reality_transport not in G4_REALITY_TRANSPORT_MODES:
        raise RuntimeError(f"unsupported G4 reality transport: {selected_reality_transport!r}")
    selected_context_mode = (
        resolve_context_mode(context_mode) if context_mode is not None else None
    )
    if selected_context_mode is not None:
        selected_context_mode = validate_context_launch(
            selected_context_mode,
            capacity_recovery=selected_capacity_recovery,
            transport=selected_reality_transport,
        )
    if selected_context_mode == CONTEXT_MODE_M_TREE_V1 or is_context_file_mode(selected_context_mode):
        selected_capacity_recovery = G4_CAPACITY_RECOVERY_CONTROL
        profile = context_mode_profile(profile, selected_context_mode)
    elif selected_capacity_recovery != G4_CAPACITY_RECOVERY_CONTROL:
        profile = replace(
            profile, chat_capacity_reanchor_recovery_mode=selected_capacity_recovery,
        )
    selected_completion_signal = (
        g4_completion_signal_mode()
        if completion_signal_mode is None
        else str(completion_signal_mode).strip().lower()
    )
    if selected_completion_signal not in G4_COMPLETION_SIGNAL_MODES:
        raise RuntimeError(f"unsupported G4 completion signal: {selected_completion_signal!r}")
    endpoint = str(os.environ.get(profile.endpoint_env, "") or "").strip()
    deployment = str(os.environ.get(profile.deployment_env, "") or "").strip()
    if not endpoint:
        raise RuntimeError(f"missing {profile.endpoint_env}")
    if deployment != profile.model_id:
        raise RuntimeError(
            f"{profile.deployment_env} must equal {profile.model_id!r}, got {deployment!r}"
        )
    limiter = str(os.environ.get(PROVIDER_LIMITER_PATH_ENV, "") or "").strip()
    if not limiter:
        limiter = str((state_root / str(route_limits["limiter_name"])).resolve())
    window_anchor = str(os.environ.get(PROVIDER_WINDOW_ANCHOR_ENV, "settlement") or "settlement")
    if window_anchor not in {"settlement", "dispatch"}:
        raise RuntimeError("provider window anchor must be settlement or dispatch")
    return ResearchRuntimeConfig(
        profile_selector=selector,
        profile=profile,
        endpoint=endpoint,
        deployment=deployment,
        provider_tpm=_positive_int_env(
            PROVIDER_TPM_ENV, int(route_limits["client_tpm"])
        ),
        provider_rpm=_positive_int_env(
            PROVIDER_RPM_ENV, int(route_limits["client_rpm"])
        ),
        provider_window_s=_positive_float_env(
            PROVIDER_WINDOW_ENV, float(route_limits["window_s"])
        ),
        provider_max_retries=int(profile.provider_max_retries),
        provider_sdk_max_retries=int(profile.provider_sdk_max_retries),
        provider_window_anchor=window_anchor,
        shared_limiter_path=limiter,
        observed_route_tpm=int(route_limits["observed_tpm"]),
        observed_route_rpm=int(route_limits["observed_rpm"]),
        observed_route_window_s=float(route_limits["observed_window_s"]),
        solver_model_view_mode="hygiene_lean_v1",
        solver_reality_transport_mode=selected_reality_transport,
        solver_working_context_mode="off",
        solver_tool_surface_mode=selected_tool_surface,
        solver_context_policy="control",
        solver_completion_signal_mode=selected_completion_signal,
        managed_context_trigger_tokens=MANAGED_CONTEXT_DEFAULT_TRIGGER_TOKENS,
        managed_context_keep_exchanges=MANAGED_CONTEXT_DEFAULT_KEEP_EXCHANGES,
        solver_judge_advice_mode="off",
        judge_model=None,
        judge_transport_mode="direct",
        judge_max_calls=0,
        judge_cap_gbp="0",
        solver_max_output_tokens=G4_SOLVER_MAX_OUTPUT_TOKENS,
        solver_provider_tool_shape=PROVIDER_TOOL_SHAPE_FLAT,
        solver_capacity_recovery_mode=selected_capacity_recovery,
    )


def _write_run_record(logs_dir: Path, record: dict[str, Any]) -> Path:
    path = logs_dir / "aether_run_record.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def _build_m_tree_compactor_provider(
    runtime: ResearchRuntimeConfig,
    *,
    limiter_path: str | Path,
    run_id: str,
    task_id: str,
    callable_factory: Callable[..., Any] = make_chat_callable,
) -> Callable[..., Mapping[str, Any]]:
    """Build an isolated same-model compactor callable without dispatching."""
    from .context_tree.compactor import MAX_OUTPUT_TOKENS

    profile = GLM_RESEARCH_PAR2_PROFILE
    if (
        runtime.profile.endpoint_env != profile.endpoint_env
        or runtime.profile.key_env != profile.key_env
    ):
        raise RuntimeError("M-TREE compactor route must use the solver endpoint and credential")
    route_limits = G4_ROUTE_LIMITS["glm-research-par2-v1"]
    normalized_limiter = str(Path(limiter_path).resolve())
    route_identity = {
        "deployment": COMPACTOR_DEPLOYMENT,
        "endpoint": runtime.endpoint,
        "limiter_path": normalized_limiter,
        "provider_tpm": int(route_limits["client_tpm"]),
        "provider_rpm": int(route_limits["client_rpm"]),
        "provider_window_s": float(route_limits["window_s"]),
        "profile_sha256": profile.sha256(),
    }
    runtime_sha = sha256(json.dumps(
        route_identity, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    overrides = {
        profile.endpoint_env: runtime.endpoint,
        profile.deployment_env: COMPACTOR_DEPLOYMENT,
        PROVIDER_LIMITER_PATH_ENV: normalized_limiter,
        PROVIDER_TPM_ENV: str(int(route_limits["client_tpm"])),
        PROVIDER_RPM_ENV: str(int(route_limits["client_rpm"])),
        PROVIDER_WINDOW_ENV: str(float(route_limits["window_s"])),
        PROVIDER_WINDOW_ANCHOR_ENV: "settlement",
        "AETHER_PROVIDER_PROFILE_SHA256": profile.sha256(),
        RUNTIME_CONFIG_SHA256_ENV: runtime_sha,
    }
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        os.environ.update(overrides)
        model = callable_factory(
            profile,
            role="solver",
            effort="medium",
            tools=(),
            native_persistent_tools=False,
            capture_rate_headers=True,
            capture_provider_request_id=True,
            disable_output_cap_escalation=True,
            charge_shared_pacer_wait_to_run_deadline=True,
            session_affinity_suffix="compactor",
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if not isinstance(model, ChatCompletionsModelCallable):
        raise TypeError("M-TREE compactor requires the bounded Chat Completions callable")
    provider_timeout = getattr(model, "_provider_timeout_s", None)
    if (
        not isinstance(provider_timeout, (int, float))
        or not math.isfinite(float(provider_timeout))
        or float(provider_timeout) <= 0
    ):
        raise TypeError("M-TREE compactor requires a finite Chat SDK request timeout")

    def call(
        request: Mapping[str, Any], *, route: str, limiter: Any,
        deadline_monotonic: float,
    ) -> Mapping[str, Any]:
        if str(route) != COMPACTOR_DEPLOYMENT or str(limiter) != normalized_limiter:
            raise RuntimeError("M-TREE compactor route or limiter identity mismatch")
        if str(request.get("model") or "") != COMPACTOR_DEPLOYMENT:
            raise RuntimeError("M-TREE compactor request deployment mismatch")
        if str(request.get("effort") or "") != "medium":
            raise RuntimeError("M-TREE compactor request effort mismatch")
        messages = request.get("messages")
        if not isinstance(messages, (list, tuple)):
            raise TypeError("M-TREE compactor request messages must be a sequence")
        deadline = float(deadline_monotonic)
        if not math.isfinite(deadline) or deadline <= time.monotonic():
            raise KernelRunTimeout("M-TREE compactor request deadline is invalid or expired")

        def invoke_model() -> str:
            scoped_call = getattr(model, "call_with_telemetry_scope", None)
            if callable(scoped_call):
                return scoped_call(
                    list(messages), max_output_tokens=MAX_OUTPUT_TOKENS,
                    run_id=str(run_id), task_id=str(task_id),
                )
            return model(list(messages), max_output_tokens=MAX_OUTPUT_TOKENS)

        # Compactor already binds this request deadline. Preserve any shift
        # applied by run_deadline_excluded_wait during shared-pacer admission;
        # rebinding the original scalar here would charge that wait to the run.
        active_remaining = remaining_run_s()
        if active_remaining is None:
            with run_deadline(deadline):
                text = invoke_model()
        elif active_remaining <= 0.0:
            raise KernelRunTimeout("M-TREE compactor request deadline expired before dispatch")
        else:
            text = invoke_model()
        telemetry = getattr(model, "last_call_telemetry", {})
        telemetry = telemetry if isinstance(telemetry, Mapping) else {}
        usage = {
            key: telemetry[key]
            for key in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens")
            if isinstance(telemetry.get(key), (int, float))
        }
        return {"text": text, "usage": usage}

    def bind_run_cancellation(event: Any | None) -> None:
        bind = getattr(model, "bind_run_cancellation", None)
        if callable(bind):
            bind(event)

    setattr(call, "bind_run_cancellation", bind_run_cancellation)
    setattr(call, "supports_finite_deadline", True)
    return call


def _run_kh_sync(
    *,
    environment: Any,
    event_loop: asyncio.AbstractEventLoop,
    context: Any,
    instruction: str,
    logs_dir: Path,
    mcp_servers: tuple[dict[str, Any], ...],
    cancellation_event: threading.Event,
    agent_timeout_sec: float | None,
    run_started_monotonic: float,
) -> dict[str, Any]:
    workspace_root = str(
        getattr(context, "metadata", {}).get("aether_workspace_root", "") or ""
    ).strip()
    if not workspace_root:
        raise RuntimeError("Harbor workspace root missing from adapter metadata")

    local_state = logs_dir / "aether_harbor_glm_research"
    local_state.mkdir(parents=True, exist_ok=True)
    executor = HarborEnvironmentExecutor(
        environment,
        event_loop=event_loop,
        workspace_root=workspace_root,
        local_state_dir=local_state / "executor_state",
        mcp_servers=mcp_servers,
    )
    executor.set_verifier_world_roots(literal_task_absolute_paths(instruction))

    try:
        context_mode = g4_context_mode()
        claim_ledger_mode = g4_claim_ledger_mode()
        deadline_visibility_mode = g4_deadline_visibility_mode()
        progress_mode, progress_fractions = g4_progress_checkpoints(claim_ledger_mode, deadline_visibility_mode)
        state_snapshot_mode = g4_state_snapshot(progress_mode, claim_ledger_mode)
        success_contract_mode = g4_success_contract(progress_mode)
        finish_review_mode = g4_finish_review(claim_ledger_mode, state_snapshot_mode)
        visible_deadline_sec = g4_visible_deadline_sec(deadline_visibility_mode)
        packet_mode = g4_packet_mode()
        env_mode = g4_env_mode()
        history_mode = g4_history_mode()
        protocol_resilience = g4_protocol_resilience()
        session_affinity_mode = g4_session_affinity_mode()
        sampling_mode = g4_sampling_mode()
        envmap = _build_structural_envmap(
            executor=executor,
            instruction=instruction,
            local_state_dir=local_state,
            mcp_servers=mcp_servers,
            agent_timeout_sec=agent_timeout_sec,
        )
        effective_run_task_config = dict(G4_KH_RUN_TASK_CONFIG)
        if state_snapshot_mode == "v1" and claim_ledger_mode not in ACTIVE_CLAIM_LEDGER_MODES:
            # Host-owned Aether evidence stays under Harbor logs, outside /app.
            evidence_key = sha256(str(getattr(context, "context_id", "") or "terminal-bench").encode()).hexdigest()[:20]
            effective_run_task_config["state_snapshot_evidence_path"] = str(
                local_state / "run_evidence" / f"{evidence_key}.json"
            )
        effective_run_task_config["solver_reasoning_mode"] = g4_solver_reasoning_mode()
        effective_run_task_config["solver_tool_surface_mode"] = g4_tool_surface_mode()
        effective_run_task_config["solver_async_mode"] = g4_async_mode()
        runtime_operation_refresh_mode = g4_runtime_operation_refresh_mode()
        effective_run_task_config["refresh_runtime_operation_status"] = (
            runtime_operation_refresh_mode == G4_RUNTIME_OPERATION_REFRESH_V1
        )
        effective_run_task_config["solver_reality_transport_mode"] = g4_reality_transport_mode()
        completion_signal_mode = g4_completion_signal_mode()
        effective_run_task_config["solver_completion_signal_mode"] = completion_signal_mode
        oracle_response_mode = g4_oracle_response_mode()
        effective_run_task_config["oracle_finish_response_mode"] = oracle_response_mode
        delivery_hygiene_mode = g4_delivery_hygiene_mode()
        effective_run_task_config["delivery_hygiene_mode"] = delivery_hygiene_mode
        capacity_recovery_mode = g4_capacity_recovery_mode()
        same_model_verifier_mode = g4_same_model_verifier_mode()
        judge_verifier_arm = selected_judge_verifier_arm()
        judge_advice_mode = g4_judge_advice_mode()
        if (
            same_model_verifier_mode != G4_SAME_MODEL_VERIFIER_CONTROL
            and (
                judge_verifier_arm != JUDGE_VERIFIER_CONTROL_ARM
                or judge_advice_mode != G4_JUDGE_ADVICE_CONTROL
            )
        ):
            raise RuntimeError(
                "VF1 same-model verifier cannot be combined with JUDGE verifier/advice"
            )
        effective_run_task_config["thin_terminal_verifier_mode"] = (
            "terminal_verifier_v1"
            if (
                same_model_verifier_mode == G4_SAME_MODEL_VERIFIER_VF1
                or judge_verifier_arm == JUDGE_VERIFIER_V3_TYPED_ARM
            )
            else "control"
        )
        if (
            effective_run_task_config["solver_async_mode"] != G4_ASYNC_CONTROL
            and effective_run_task_config["solver_tool_surface_mode"] != G4_TOOL_SURFACE_JOBS_V1
        ):
            raise RuntimeError(
                "non-control G4 async mode requires static_kernel_jobs_v1 tool surface"
            )
        if (
            effective_run_task_config["refresh_runtime_operation_status"]
            and effective_run_task_config["solver_tool_surface_mode"] != G4_TOOL_SURFACE_JOBS_V1
        ):
            raise RuntimeError(
                "G4 runtime-operation refresh treatment requires static_kernel_jobs_v1 tool surface"
            )
        runtime = g4_runtime_config(
            state_root=local_state,
            tool_surface_mode=effective_run_task_config["solver_tool_surface_mode"],
            reality_transport_mode=effective_run_task_config["solver_reality_transport_mode"],
            completion_signal_mode=completion_signal_mode,
            capacity_recovery_mode=capacity_recovery_mode,
            context_mode=context_mode,
        )
        effective_run_task_config["solver_long_command_mode"] = runtime.solver_long_command_mode
        provider_env = runtime.provider_environment()
        previous_provider_env = {key: os.environ.get(key) for key in provider_env}
        context_tree_adapter = None
        claim_ledger_controller = None
        claim_ledger_components: tuple[Any, ...] = ()
        m_tree_limiter_path = ""
        m_tree_evidence_root = ""
        context_file_budget: int | None = None
        try:
            for key, value in provider_env.items():
                existing = str(os.environ.get(key, "") or "").strip()
                if existing and existing != value:
                    raise RuntimeError(f"provider runtime env conflict for {key}")
            os.environ.update(provider_env)
            solver = make_chat_callable(
                runtime.profile,
                role="solver",
                capture_rate_headers=True,
                tool_surface_mode=runtime.solver_tool_surface_mode,
                tools=persistent_chat_provider_tools(
                    advanced_tool_shape=runtime.solver_provider_tool_shape,
                    include_m_tree_zoom=context_mode == CONTEXT_MODE_M_TREE_V1,
                    finish_completion_card=claim_ledger_mode in FINISH_CARD_MODES,
                    include_background_jobs=runtime.solver_long_command_mode == "background_v1",
                ),
                context_policy=runtime.solver_context_policy,
                managed_context_trigger_tokens=runtime.managed_context_trigger_tokens,
                managed_context_keep_exchanges=runtime.managed_context_keep_exchanges,
                **(
                    {"disable_output_cap_escalation": True}
                    if protocol_resilience in OUTPUT_CAP_MODES else {}
                ),
                **({"tolerant_argument_parsing": True} if protocol_resilience in TOLERANT_ARGUMENT_MODES else {}),
                **sampling_kwargs(sampling_mode),
            )
            if context_mode == CONTEXT_MODE_M_TREE_V1:
                m_tree_limiter_path = str(
                    os.environ.get(COMPACTOR_LIMITER_PATH_ENV, "") or ""
                ).strip()
                m_tree_evidence_root = str(
                    os.environ.get(M_TREE_EVIDENCE_ROOT_ENV, "") or ""
                ).strip()
                compactor_deployment = str(
                    os.environ.get("AETHER_M_TREE_COMPACTOR_DEPLOYMENT", "") or ""
                ).strip()
                if not m_tree_limiter_path or not m_tree_evidence_root:
                    raise RuntimeError("M-TREE launcher evidence and limiter paths are required")
                if compactor_deployment != COMPACTOR_DEPLOYMENT:
                    raise RuntimeError("M-TREE compactor deployment identity mismatch")
                compactor_provider = _build_m_tree_compactor_provider(
                    runtime,
                    limiter_path=m_tree_limiter_path,
                    run_id=f"g4:{getattr(context, 'context_id', '') or 'unknown'}",
                    task_id=str(getattr(context, "context_id", "") or "terminal-bench"),
                )
                context_tree_adapter = ContextTreeAdapter(
                    raw_task=instruction,
                    evidence_root=m_tree_evidence_root,
                    run_id=f"g4:{getattr(context, 'context_id', '') or 'unknown'}",
                    compactor_provider=compactor_provider,
                    compactor_route=COMPACTOR_DEPLOYMENT,
                    compactor_limiter_path=m_tree_limiter_path,
                )
            elif is_context_file_mode(context_mode):
                m_tree_evidence_root = str(
                    os.environ.get(M_TREE_EVIDENCE_ROOT_ENV, "") or ""
                ).strip()
                if not m_tree_evidence_root:
                    raise RuntimeError("context-file launcher evidence path is required")
                context_file_budget = resolve_budget(context_mode, environ=os.environ)
                context_tree_adapter = ContextFileAdapter(
                    evidence_root=m_tree_evidence_root,
                    run_id=f"g4:{getattr(context, 'context_id', '') or 'unknown'}",
                    budget_bytes=context_file_budget,
                )
            if claim_ledger_mode in ACTIVE_CLAIM_LEDGER_MODES:
                if (
                    same_model_verifier_mode != G4_SAME_MODEL_VERIFIER_CONTROL
                    or judge_verifier_arm != JUDGE_VERIFIER_CONTROL_ARM
                    or judge_advice_mode != G4_JUDGE_ADVICE_CONTROL
                ):
                    raise RuntimeError("CHALLENGER claim ledger conflicts with a verifier/JUDGE arm")
                from .challenger_runtime.production import build_challenger_controller
                claim_ledger_controller, claim_ledger_components = build_challenger_controller(
                    runtime.profile, make_chat_callable=make_chat_callable,
                    instruction=instruction,
                    run_id=str(os.environ.get(CHALLENGER_RUN_ID_ENV, "") or "").strip()
                    or f"g4:{getattr(context, 'context_id', '') or 'unknown'}",
                    evidence_root=os.environ[CHALLENGER_EVIDENCE_ROOT_ENV],
                    mode=claim_ledger_mode,
                    progress_fractions=progress_fractions,
                    progress_mode=progress_mode,
                    state_snapshot_mode=state_snapshot_mode,
                    success_contract_mode=success_contract_mode,
                    finish_review_mode=finish_review_mode,
                )
            same_model_verifier = (
                make_chat_callable(
                    runtime.profile,
                    role="verifier",
                    effort=runtime.profile.solver_reasoning_effort,
                    capture_rate_headers=True,
                )
                if same_model_verifier_mode == G4_SAME_MODEL_VERIFIER_VF1
                else None
            )
        finally:
            for key, value in previous_provider_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        verifier = (
            same_model_verifier
            if same_model_verifier is not None
            else build_selected_judge_v3_verifier()
            if judge_verifier_arm == JUDGE_VERIFIER_V3_TYPED_ARM
            else DisabledVerifier()
        )
        semantic_assistance = build_g4_trace_aware_judge_assistance(
            cancellation_event=cancellation_event,
        )
        for model in (solver, verifier, semantic_assistance, *claim_ledger_components):
            bind_cancel = getattr(model, "bind_run_cancellation", None)
            if callable(bind_cancel):
                bind_cancel(cancellation_event)

        task_surface = local_state / "task_surface"
        task_surface.mkdir(parents=True, exist_ok=True)
        identity = {
            "task_id": str(getattr(context, "context_id", "") or "terminal-bench"),
            "run_id": f"g4:{getattr(context, 'context_id', '') or 'unknown'}",
            "source_commit": str(os.environ.get("AETHER_SOURCE_COMMIT", "") or ""),
            "campaign_id": str(os.environ.get("AETHER_CAMPAIGN_ID", "") or ""),
            "research_runtime": runtime.manifest(),
            "research_harbor_adapter": "kh_glm_v1",
            "context_mode": context_mode,
            "solver_reasoning_effort": runtime.profile.solver_reasoning_effort,
        }
        identity.update(context_runtime_identity(
            context_mode,
            compactor_limiter_path=m_tree_limiter_path or None,
            ctx_budget_bytes=context_file_budget,
        ))
        identity.update(claim_ledger_runtime_identity(claim_ledger_mode))
        identity.update(progress_checkpoints_runtime_identity(
            ",".join(map(str, progress_fractions)) if progress_fractions else None,
            progress_mode, state_snapshot_mode, success_contract_mode,
            finish_review_mode,
        ))
        identity.update(criteria_mode_runtime_identity())
        if context_tree_adapter is not None:
            identity["m_tree_evidence_root"] = m_tree_evidence_root
        record = run_task(
            task_dir=str(task_surface),
            instruction_text=instruction,
            solver_model=solver,
            verifier_model=verifier,
            vision_model=None,
            workspace_root=workspace_root,
            max_steps=None,
            max_solver_turns=None,
            max_accepted_task_actions=None,
            solver_max_output_tokens=runtime.solver_max_output_tokens,
            verifier_max_output_tokens=int(runtime.profile.verifier_max_output_tokens or 12000),
            model_profile=runtime.profile,
            runtime_identity=identity,
            executor=executor,
            envmap_override=envmap,
            close_executor=False,
            context_tree_adapter=context_tree_adapter,
            claim_ledger_controller=claim_ledger_controller,
            semantic_assistance=semantic_assistance,
            cancellation_event=cancellation_event,
            run_timeout_s=agent_timeout_sec,
            run_started_monotonic=run_started_monotonic,
            visible_deadline_sec=visible_deadline_sec,
            packet_mode=packet_mode,
            env_mode=env_mode,
            protocol_resilience=protocol_resilience,
            **effective_run_task_config,
        )
    finally:
        executor.close()

    record["research_harbor_adapter"] = {
        "schema": "aether.g4_glm_research_adapter.v1",
        "profile_selector": runtime.profile_selector,
        "solver_reasoning_effort": runtime.profile.solver_reasoning_effort,
        "runtime": runtime.manifest(),
        "kh_run_task_config": dict(effective_run_task_config),
        "official_harbor_grader_owned": True,
        "model_verifier_disabled": (
            judge_verifier_arm == JUDGE_VERIFIER_CONTROL_ARM
            and same_model_verifier_mode == G4_SAME_MODEL_VERIFIER_CONTROL
        ),
        "research_judge_verifier_arm": judge_verifier_arm,
        "same_model_verifier_mode": same_model_verifier_mode,
        "research_judge_advice_mode": judge_advice_mode,
        "runtime_operation_refresh_mode": runtime_operation_refresh_mode,
        "completion_signal_mode": completion_signal_mode,
        "oracle_response_mode": oracle_response_mode,
        "delivery_hygiene_mode": delivery_hygiene_mode,
        "capacity_recovery_mode": capacity_recovery_mode,
        "context_mode": context_mode,
        "claim_ledger": claim_ledger_mode,
        "deadline_visibility": deadline_visibility_mode,
        "packet_mode": packet_mode,
        "env_mode": env_mode,
        "history_mode": history_mode,
        "protocol_resilience": protocol_resilience,
        "session_affinity": session_affinity_mode,
        "sampling": sampling_mode,
        "progress_checkpoints": ",".join(map(str, progress_fractions)) if progress_fractions else "control",
        **({"progress_checkpoints_mode": progress_mode} if progress_mode != "control" else {}),
        **criteria_mode_runtime_identity(),
        **(
            {
                COMPACTOR_ROUTE_KEY: {
                    "deployment": COMPACTOR_DEPLOYMENT,
                    "limiter_path": m_tree_limiter_path,
                },
                "m_tree_evidence_root": m_tree_evidence_root,
            }
            if context_mode == CONTEXT_MODE_M_TREE_V1 else {}
        ),
        **(
            {"m_tree_evidence_root": m_tree_evidence_root, CTX_BUDGET_ENV: context_file_budget}
            if context_file_budget is not None else {}
        ),
    }
    path = _write_run_record(logs_dir, record)
    record["aether_run_record_path"] = str(path)
    _update_agent_context(context, record)
    return record


class GLMResearchHarborAgent(AetherHarborAgent):
    """Explicit TB diagnostic adapter for current KH/full/high Aether+GLM."""

    @staticmethod
    def name() -> str:
        return "aether-glm-research"

    def version(self) -> str:
        return "revision-kh-glm-harbor-v1"

    async def run(self, instruction: str, environment: Any, context: Any) -> None:
        started = time.monotonic()
        facts = await discover_harbor_workspace(environment)
        metadata = dict(getattr(context, "metadata", None) or {})
        metadata["aether_workspace_root"] = facts.workspace_root
        metadata["aether_harbor_workspace_probe"] = {
            "pwd": facts.pwd,
            "git_root": facts.git_root,
            "workspace_root": facts.workspace_root,
            "existing_candidates": list(facts.existing_candidates),
        }
        effective_run_task_config = dict(G4_KH_RUN_TASK_CONFIG)
        effective_run_task_config["solver_reasoning_mode"] = g4_solver_reasoning_mode()
        effective_run_task_config["solver_tool_surface_mode"] = g4_tool_surface_mode()
        effective_run_task_config["solver_async_mode"] = g4_async_mode()
        runtime_operation_refresh_mode = g4_runtime_operation_refresh_mode()
        effective_run_task_config["refresh_runtime_operation_status"] = (
            runtime_operation_refresh_mode == G4_RUNTIME_OPERATION_REFRESH_V1
        )
        effective_run_task_config["solver_reality_transport_mode"] = g4_reality_transport_mode()
        completion_signal_mode = g4_completion_signal_mode()
        effective_run_task_config["solver_completion_signal_mode"] = completion_signal_mode
        oracle_response_mode = g4_oracle_response_mode()
        effective_run_task_config["oracle_finish_response_mode"] = oracle_response_mode
        delivery_hygiene_mode = g4_delivery_hygiene_mode()
        effective_run_task_config["delivery_hygiene_mode"] = delivery_hygiene_mode
        capacity_recovery_mode = g4_capacity_recovery_mode()
        context_mode = g4_context_mode()
        same_model_verifier_mode = g4_same_model_verifier_mode()
        effective_run_task_config["thin_terminal_verifier_mode"] = (
            "terminal_verifier_v1"
            if same_model_verifier_mode == G4_SAME_MODEL_VERIFIER_VF1
            else "control"
        )
        if (
            effective_run_task_config["refresh_runtime_operation_status"]
            and effective_run_task_config["solver_tool_surface_mode"] != G4_TOOL_SURFACE_JOBS_V1
        ):
            raise RuntimeError(
                "G4 runtime-operation refresh treatment requires static_kernel_jobs_v1 tool surface"
            )
        metadata["aether_glm_research_adapter"] = {
            "profile_selector": g4_profile_selector(),
            "reasoning_effort": g4_reasoning_effort(),
            "solver_max_output_tokens": G4_SOLVER_MAX_OUTPUT_TOKENS,
            "kh_run_task_config": effective_run_task_config,
            "runtime_operation_refresh_mode": runtime_operation_refresh_mode,
            "completion_signal_mode": completion_signal_mode,
            "oracle_response_mode": oracle_response_mode,
            "delivery_hygiene_mode": delivery_hygiene_mode,
            "capacity_recovery_mode": capacity_recovery_mode,
            "context_mode": context_mode,
            "claim_ledger": g4_claim_ledger_mode(),
            "deadline_visibility": g4_deadline_visibility_mode(),
            "packet_mode": g4_packet_mode(),
            "env_mode": g4_env_mode(),
            "history_mode": g4_history_mode(),
            "protocol_resilience": g4_protocol_resilience(),
            "session_affinity": g4_session_affinity_mode(),
            "sampling": g4_sampling_mode(),
            "same_model_verifier_mode": same_model_verifier_mode,
        }
        context.metadata = metadata

        loop = asyncio.get_running_loop()
        cancellation_event = threading.Event()
        worker = asyncio.create_task(
            asyncio.to_thread(
                _run_kh_sync,
                environment=environment,
                event_loop=loop,
                context=context,
                instruction=instruction,
                logs_dir=Path(self.logs_dir),
                mcp_servers=tuple(dict(row) for row in self._mcp_servers),
                cancellation_event=cancellation_event,
                agent_timeout_sec=self._agent_timeout_sec,
                run_started_monotonic=started,
            )
        )
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            cancellation_event.set()
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if worker.done():
                try:
                    worker.result()
                except BaseException:
                    pass
            raise


__all__ = [
    "GLMResearchHarborAgent",
    "G4_KH_RUN_TASK_CONFIG",
    "g4_async_mode",
    "g4_capacity_recovery_mode",
    "g4_completion_signal_mode",
    "g4_kh_profile",
    "g4_reality_transport_mode",
    "g4_runtime_operation_refresh_mode",
    "g4_runtime_config",
    "g4_tool_surface_mode",
    "G4_ASYNC_MODE_ENV",
    "G4_COMPLETION_SIGNAL_ENV",
    "G4_COMPLETION_SIGNAL_VERIFICATION_ORACLE_GUARD_V1",
    "G4_ASYNC_CONTROL",
    "G4_ASYNC_INDEPENDENT_JOBS_V1",
    "G4_REALITY_TRANSPORT_ENV",
    "G4_REALITY_TRANSPORT_CONTROL",
    "G4_REALITY_TRANSPORT_PT_RA",
    "G4_REALITY_TRANSPORT_PT_R1",
    "G4_REALITY_TRANSPORT_PT_NR",
    "G4_REASONING_EFFORT_ENV",
    "G4_REASONING_EFFORT_MODES",
    "g4_reasoning_effort",
    "G4_CAPACITY_RECOVERY_ENV",
    "G4_CAPACITY_RECOVERY_MODES",
    "G4_COMPLETION_SIGNAL_MODES",
    "G4_CAPACITY_RECOVERY_CONTROL",
    "G4_CAPACITY_RECOVERY_CHECKPOINT_AT_CAPACITY_V1",
    "G4_TOOL_SURFACE_ENV",
    "G4_TOOL_SURFACE_CONTROL",
    "G4_TOOL_SURFACE_JOBS_V1",
    "G4_TOOL_SURFACE_EDIT_V1",
]
