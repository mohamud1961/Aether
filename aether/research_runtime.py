"""Canonical route and runtime binding for trace-first research rows.

This is launcher configuration, not a second runtime. Batch and direct research
rows resolve the same immutable contract and hand it to the existing GLM path.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
import os
import posixpath
from pathlib import Path
from typing import Any, Mapping

from .model_profile import GLM_RESEARCH_LOCAL_ADMISSION_DEFAULTS, GLM_RESEARCH_PROFILES, ModelProfile
from .persistent_runtime import (
    SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1,
    SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1,
    SOLVER_WORKING_CONTEXT_MODES,
    SOLVER_WORKING_CONTEXT_OFF,
)
from .managed_context_checkpoint import (
    MANAGED_CONTEXT_DEFAULT_KEEP_EXCHANGES,
    MANAGED_CONTEXT_DEFAULT_TRIGGER_TOKENS,
    MANAGED_CONTEXT_CHECKPOINT_POLICIES,
    MANAGED_CONTEXT_POLICIES,
    MANAGED_CONTEXT_POLICY_CONTROL,
)
from .persistent_provider_protocol import PERSISTENT_TOOL_SURFACE_CONTROL, PERSISTENT_TOOL_SURFACE_MODES
from .selective_judge_advice import MODE_OFF as JUDGE_MODE_OFF, MODES as SELECTIVE_JUDGE_MODES
from .trace_aware_judge_advice import MODE_HARD_STUCK_TRACE_V1
from .long_command_mode import selected_long_command_mode

JUDGE_MODES = frozenset(set(SELECTIVE_JUDGE_MODES) | {MODE_HARD_STUCK_TRACE_V1})


PROVIDER_TPM_ENV = "AETHER_PROVIDER_TPM_LIMIT"
PROVIDER_RPM_ENV = "AETHER_PROVIDER_RPM_LIMIT"
PROVIDER_WINDOW_ENV = "AETHER_PROVIDER_TPM_WINDOW_S"
PROVIDER_WINDOW_ANCHOR_ENV = "AETHER_PROVIDER_WINDOW_ANCHOR"
PROVIDER_LIMITER_PATH_ENV = "AETHER_PROVIDER_SHARED_LIMITER_PATH"
JUDGE_TRANSPORT_DIRECT = "direct"
JUDGE_TRANSPORT_FILE_BROKER = "file_broker_v1"
JUDGE_TRANSPORT_MODES = frozenset({JUDGE_TRANSPORT_DIRECT, JUDGE_TRANSPORT_FILE_BROKER})
RUNTIME_CONFIG_SHA256_ENV = "AETHER_RESEARCH_RUNTIME_CONFIG_SHA256"


def _same_endpoint(left: str, right: str) -> bool:
    return left.strip().rstrip("/") == right.strip().rstrip("/")


def _stable_absolute_path(value: str | Path) -> str:
    """Normalize paths without resolving host-specific symlinks.

    Research manifests are prepared on macOS and executed on Linux. Resolving a
    remote absolute path such as ``/home/<user>/...`` locally can rewrite it
    through a host mount alias and make the config hash differ at execution.
    """
    raw = os.fspath(value)
    if raw.startswith("/"):
        return posixpath.normpath(raw)
    return os.path.abspath(os.path.normpath(raw))


@dataclass(frozen=True)
class ResearchRuntimeConfig:
    profile_selector: str
    profile: ModelProfile
    endpoint: str
    deployment: str
    provider_tpm: int
    provider_rpm: int
    provider_window_s: float
    provider_max_retries: int
    provider_sdk_max_retries: int
    provider_window_anchor: str
    shared_limiter_path: str
    observed_route_tpm: int | None
    observed_route_rpm: int | None
    observed_route_window_s: float | None
    solver_model_view_mode: str
    solver_reality_transport_mode: str
    solver_working_context_mode: str
    solver_tool_surface_mode: str
    solver_completion_signal_mode: str
    solver_context_policy: str
    managed_context_trigger_tokens: int
    managed_context_keep_exchanges: int
    solver_judge_advice_mode: str
    judge_model: str | None
    judge_transport_mode: str
    judge_max_calls: int
    judge_cap_gbp: str
    solver_max_output_tokens: int
    # Provider-visible shape of run_command_advanced; the G4 research adapter
    # sets "flat_v1". Default keeps every other runtime identity unchanged.
    solver_provider_tool_shape: str = "nested_v1"
    # Research-only capacity-boundary recovery selector. "control" leaves the
    # profile's own recovery mode untouched and stays out of the identity hash.
    solver_capacity_recovery_mode: str = "control"
    solver_long_command_mode: str = "control"

    @property
    def expected_returned_model(self) -> str:
        return self.profile.expected_returned_model or self.profile.model_id

    @property
    def route_identity_sha256(self) -> str:
        return self.profile.route_identity_sha256(
            selector=self.profile_selector,
            endpoint=self.endpoint,
            deployment=self.deployment,
        )

    def _identity(self) -> dict[str, Any]:
        return {
            "schema": "aether.research_runtime_config.v1",
            "profile_selector": self.profile_selector,
            "profile_id": self.profile.profile_id,
            "requested_model": self.profile.model_id,
            "expected_returned_model": self.expected_returned_model,
            "endpoint": self.endpoint,
            "deployment": self.deployment,
            "route_identity_sha256": self.route_identity_sha256,
            "provider_tpm": self.provider_tpm,
            "provider_rpm": self.provider_rpm,
            "provider_window_s": self.provider_window_s,
            "provider_max_retries": self.provider_max_retries,
            "provider_sdk_max_retries": self.provider_sdk_max_retries,
            "provider_window_anchor": self.provider_window_anchor,
            "shared_limiter_path": self.shared_limiter_path,
            "observed_route_tpm": self.observed_route_tpm,
            "observed_route_rpm": self.observed_route_rpm,
            "observed_route_window_s": self.observed_route_window_s,
            "solver_model_view_mode": self.solver_model_view_mode,
            "solver_reality_transport_mode": self.solver_reality_transport_mode,
            "solver_working_context_mode": self.solver_working_context_mode,
            "solver_tool_surface_mode": self.solver_tool_surface_mode,
            **({"solver_long_command_mode": self.solver_long_command_mode}
               if self.solver_long_command_mode != "control" else {}),
            **(
                {"solver_completion_signal_mode": self.solver_completion_signal_mode}
                if self.solver_completion_signal_mode != "control" else {}
            ),
            **(
                {"solver_provider_tool_shape": self.solver_provider_tool_shape}
                if self.solver_provider_tool_shape != "nested_v1" else {}
            ),
            "solver_context_policy": self.solver_context_policy,
            "managed_context_trigger_tokens": self.managed_context_trigger_tokens,
            "managed_context_keep_exchanges": self.managed_context_keep_exchanges,
            "solver_judge_advice_mode": self.solver_judge_advice_mode,
            "judge_model": self.judge_model,
            "judge_transport_mode": self.judge_transport_mode,
            "judge_max_calls": self.judge_max_calls,
            "judge_cap_gbp": self.judge_cap_gbp,
            "solver_max_output_tokens": self.solver_max_output_tokens,
            **(
                {"solver_capacity_recovery_mode": self.solver_capacity_recovery_mode}
                if self.solver_capacity_recovery_mode != "control" else {}
            ),
            "reasoning_effort": self.profile.solver_reasoning_effort,
            "model_profile_treatment_sha256": self.profile.sha256(),
        }

    @property
    def sha256(self) -> str:
        encoded = json.dumps(
            self._identity(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def manifest(self) -> dict[str, Any]:
        return {**self._identity(), "research_runtime_config_sha256": self.sha256}

    def provider_environment(self) -> dict[str, str]:
        """The complete provider-side contract bound before callable creation."""
        return {
            self.profile.endpoint_env: self.endpoint,
            self.profile.deployment_env: self.deployment,
            PROVIDER_TPM_ENV: str(self.provider_tpm),
            PROVIDER_RPM_ENV: str(self.provider_rpm),
            PROVIDER_WINDOW_ENV: str(self.provider_window_s),
            PROVIDER_WINDOW_ANCHOR_ENV: self.provider_window_anchor,
            PROVIDER_LIMITER_PATH_ENV: self.shared_limiter_path,
            RUNTIME_CONFIG_SHA256_ENV: self.sha256,
        }

    def cli_args(self) -> list[str]:
        """Canonical explicit CLI projection used by both launch paths."""
        return [
            "--model-profile", self.profile_selector,
            "--endpoint", self.endpoint,
            "--deployment", self.deployment,
            "--provider-tpm", str(self.provider_tpm),
            "--provider-rpm", str(self.provider_rpm),
            "--provider-window-s", str(self.provider_window_s),
            "--provider-max-retries", str(self.provider_max_retries),
            "--provider-window-anchor", self.provider_window_anchor,
            "--provider-shared-limiter-path", self.shared_limiter_path,
            "--solver-model-view-mode", self.solver_model_view_mode,
            "--solver-reality-transport-mode", self.solver_reality_transport_mode,
            "--solver-working-context-mode", self.solver_working_context_mode,
            "--solver-tool-surface-mode", self.solver_tool_surface_mode,
            *(
                ["--solver-completion-signal-mode", self.solver_completion_signal_mode]
                if self.solver_completion_signal_mode != "control" else []
            ),
            "--solver-context-policy", self.solver_context_policy,
            "--managed_context-trigger-tokens", str(self.managed_context_trigger_tokens),
            "--managed_context-keep-exchanges", str(self.managed_context_keep_exchanges),
            "--solver-judge-advice-mode", self.solver_judge_advice_mode,
            *(
                [
                    "--judge-model", str(self.judge_model),
                    "--judge-transport-mode", self.judge_transport_mode,
                    "--judge-max-calls", str(self.judge_max_calls),
                    "--judge-cap-gbp", str(self.judge_cap_gbp),
                ]
                if self.solver_judge_advice_mode != JUDGE_MODE_OFF
                else []
            ),
            "--solver-max-output-tokens", str(self.solver_max_output_tokens),
            "--reasoning-effort", self.profile.solver_reasoning_effort,
            *(
                [
                    "--observed-provider-tpm", str(self.observed_route_tpm),
                    "--observed-provider-rpm", str(self.observed_route_rpm),
                    "--observed-provider-window-s", str(self.observed_route_window_s),
                ]
                if self.observed_route_tpm is not None
                and self.observed_route_rpm is not None
                and self.observed_route_window_s is not None
                else []
            ),
        ]


def build_research_runtime_config(
    args: Any,
    *,
    output_root: Path,
    default_endpoint: str,
    inherited_env: Mapping[str, str] | None = None,
) -> ResearchRuntimeConfig:
    """Resolve route, pacing and model-facing settings once for every launcher.

    Explicit sealed CLI values must agree with any inherited batch contract.
    An omitted direct-row pacing contract resolves to the profile's conservative
    cap and a row-local shared limiter, so a standalone live row is never
    unpaced.
    """
    env = os.environ if inherited_env is None else inherited_env
    selector = str(getattr(args, "model_profile", "") or "").strip()
    try:
        base_profile = GLM_RESEARCH_PROFILES[selector]
    except KeyError as exc:
        raise RuntimeError(f"unknown research model profile: {selector!r}") from exc

    retry_override = getattr(args, "provider_max_retries", None)
    provider_max_retries = (
        base_profile.provider_max_retries
        if retry_override is None
        else int(retry_override)
    )
    if provider_max_retries not in {0, 1, 2}:
        raise RuntimeError("provider max retries must be 0, 1, or 2")
    provider_sdk_max_retries = int(base_profile.provider_sdk_max_retries)
    if provider_sdk_max_retries != 0:
        raise RuntimeError("research Chat Completions SDK retries must remain zero")

    run_timeout_s = float(getattr(args, "run_timeout_s", 0.0) or 0.0)
    if run_timeout_s > 0 and float(base_profile.provider_poll_timeout_s) < run_timeout_s:
        raise RuntimeError(
            "research provider timeout is shorter than the declared run timeout"
        )

    inherited_endpoint = str(env.get(base_profile.endpoint_env, "") or "").strip()
    expected_endpoint = inherited_endpoint or str(default_endpoint or "").strip()
    endpoint = str(getattr(args, "endpoint", None) or expected_endpoint).strip()
    if not endpoint:
        raise RuntimeError("endpoint is not configured for the selected model profile")
    if not expected_endpoint or not _same_endpoint(endpoint, expected_endpoint):
        raise RuntimeError("endpoint does not match selected model profile route")

    deployment = str(getattr(args, "deployment", None) or base_profile.model_id).strip()
    if deployment != base_profile.model_id:
        raise RuntimeError("deployment does not match selected model profile")

    raw_tpm = str(env.get(PROVIDER_TPM_ENV, "") or "").strip()
    raw_rpm = str(env.get(PROVIDER_RPM_ENV, "") or "").strip()
    raw_window = str(env.get(PROVIDER_WINDOW_ENV, "") or "").strip()
    raw_path = str(env.get(PROVIDER_LIMITER_PATH_ENV, "") or "").strip()
    inherited_present = any((raw_tpm, raw_rpm, raw_window, raw_path))
    if inherited_present and not all((raw_tpm, raw_rpm, raw_window, raw_path)):
        raise RuntimeError("inherited provider pacing contract is incomplete")

    cli_tpm = getattr(args, "provider_tpm", None)
    cli_rpm = getattr(args, "provider_rpm", None)
    cli_window = getattr(args, "provider_window_s", None)
    cli_path = str(getattr(args, "provider_shared_limiter_path", None) or "").strip()
    cli_limits_present = any((cli_tpm is not None, cli_rpm is not None, cli_window is not None))
    if cli_limits_present and (cli_tpm is None or cli_rpm is None):
        raise RuntimeError("provider pacing requires --provider-tpm and --provider-rpm together")

    if inherited_present:
        inherited_values = (int(raw_tpm), int(raw_rpm), float(raw_window))
        inherited_path = _stable_absolute_path(raw_path)
        if (
            (cli_limits_present and (
                int(cli_tpm) != inherited_values[0]
                or int(cli_rpm) != inherited_values[1]
            ))
            or (cli_window is not None and float(cli_window) != inherited_values[2])
            or (cli_path and _stable_absolute_path(cli_path) != inherited_path)
        ):
            raise RuntimeError("row pacing arguments conflict with inherited shared limiter contract")
        tpm, rpm, window_s, shared_path = (*inherited_values, inherited_path)
    elif cli_limits_present:
        tpm, rpm = int(cli_tpm), int(cli_rpm)
        window_s = float(cli_window) if cli_window is not None else 62.0
        shared_path = _stable_absolute_path(cli_path or (output_root / "shared_provider_limiter.json"))
    else:
        tpm, rpm = GLM_RESEARCH_LOCAL_ADMISSION_DEFAULTS[selector]
        window_s = float(cli_window) if cli_window is not None else 62.0
        shared_path = _stable_absolute_path(cli_path or (output_root / "shared_provider_limiter.json"))

    if tpm <= 0 or rpm <= 0 or window_s <= 0:
        raise RuntimeError("provider pacing limits and window must be positive")
    if not math.isfinite(window_s):
        raise RuntimeError("provider pacing window must be finite")
    window_anchor = str(getattr(args, "provider_window_anchor", "settlement") or "settlement")
    if window_anchor not in {"settlement", "dispatch"}:
        raise RuntimeError("provider pacing window anchor must be settlement or dispatch")
    observed_values = (
        getattr(args, "observed_provider_tpm", None),
        getattr(args, "observed_provider_rpm", None),
        getattr(args, "observed_provider_window_s", None),
    )
    observed_present = any(value is not None for value in observed_values)
    if observed_present and not all(value is not None for value in observed_values):
        raise RuntimeError("observed provider route requires TPM, RPM, and window together")
    observed_tpm = int(observed_values[0]) if observed_values[0] is not None else None
    observed_rpm = int(observed_values[1]) if observed_values[1] is not None else None
    observed_window_s = (
        float(observed_values[2]) if observed_values[2] is not None else None
    )
    if observed_present and (
        observed_tpm <= 0
        or observed_rpm <= 0
        or observed_window_s <= 0
        or not math.isfinite(observed_window_s)
    ):
        raise RuntimeError("observed provider route limits must be positive with a finite window")
    default_tpm, default_rpm = GLM_RESEARCH_LOCAL_ADMISSION_DEFAULTS[selector]
    if observed_present:
        # The shared pacer enforces a rolling window of this duration. A
        # shorter local window could admit a burst above the provider's
        # observed rolling quota even when the average rate is lower.
        if (
            tpm > observed_tpm
            or rpm > observed_rpm
            or window_s < observed_window_s
        ):
            raise RuntimeError(
                "client pacing exceeds observed provider route limits or uses a shorter rolling window"
            )
    elif (
        tpm > default_tpm
        or rpm > default_rpm
        or window_s < 62.0
    ):
        raise RuntimeError(
            "client pacing exceeds conservative defaults or uses a shorter rolling window; sealed observed provider route limits are required"
        )
    model_view = str(getattr(args, "solver_model_view_mode", "control") or "control")
    transport = str(
        getattr(args, "solver_reality_transport_mode", "full_snapshot_control")
        or "full_snapshot_control"
    )
    working_context_mode = str(
        getattr(args, "solver_working_context_mode", SOLVER_WORKING_CONTEXT_OFF)
        or SOLVER_WORKING_CONTEXT_OFF
    ).strip().lower()
    if working_context_mode not in SOLVER_WORKING_CONTEXT_MODES:
        raise RuntimeError(f"unsupported Solver working-context mode: {working_context_mode!r}")
    tool_surface_mode = str(
        getattr(args, "solver_tool_surface_mode", PERSISTENT_TOOL_SURFACE_CONTROL)
        or PERSISTENT_TOOL_SURFACE_CONTROL
    ).strip()
    if tool_surface_mode not in PERSISTENT_TOOL_SURFACE_MODES:
        raise RuntimeError(f"unsupported Solver tool surface mode: {tool_surface_mode!r}")
    completion_signal_mode = str(
        getattr(args, "solver_completion_signal_mode", "control") or "control"
    ).strip().lower()
    if completion_signal_mode not in {
        "control", "verification_v1", "verification_authority_v2",
        "verification_oracle_guard_v1",
    }:
        raise RuntimeError(
            f"unsupported Solver completion signal mode: {completion_signal_mode!r}"
        )
    if working_context_mode != SOLVER_WORKING_CONTEXT_OFF and (
        str(getattr(args, "solver_loop", "thin") or "thin").strip().lower() != "thin"
        or transport != SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1
    ):
        raise RuntimeError(
            "non-off Solver working context requires the thin loop with latest_exchange_v1 reality transport"
        )
    context_policy = str(
        getattr(args, "solver_context_policy", MANAGED_CONTEXT_POLICY_CONTROL) or MANAGED_CONTEXT_POLICY_CONTROL
    ).strip()
    managed_context_trigger = int(getattr(args, "managed_context_trigger_tokens", None) or MANAGED_CONTEXT_DEFAULT_TRIGGER_TOKENS)
    keep_raw = getattr(args, "managed_context_keep_exchanges", None)
    managed_context_keep = MANAGED_CONTEXT_DEFAULT_KEEP_EXCHANGES if keep_raw is None else int(keep_raw)
    if context_policy not in MANAGED_CONTEXT_POLICIES:
        raise RuntimeError(f"unsupported Solver context policy: {context_policy!r}")
    if managed_context_trigger <= 0 or managed_context_keep < 0:
        raise RuntimeError("managed_context trigger tokens must be positive and keep exchanges non-negative")
    if context_policy in MANAGED_CONTEXT_CHECKPOINT_POLICIES and (
        str(getattr(args, "solver_loop", "thin") or "thin").strip().lower() != "thin"
        or transport != "observation_history_v1"
    ):
        raise RuntimeError(
            "checkpoint context policy requires the thin loop with observation_history_v1 reality transport"
        )
    judge_mode = str(
        getattr(args, "solver_judge_advice_mode", JUDGE_MODE_OFF) or JUDGE_MODE_OFF
    ).strip()
    if judge_mode not in JUDGE_MODES:
        raise RuntimeError(f"unsupported selective JUDGE mode: {judge_mode!r}")
    judge_model_raw = str(getattr(args, "judge_model", "") or "").strip()
    judge_transport_mode = str(
        getattr(args, "judge_transport_mode", JUDGE_TRANSPORT_DIRECT) or JUDGE_TRANSPORT_DIRECT
    ).strip()
    if judge_transport_mode not in JUDGE_TRANSPORT_MODES:
        raise RuntimeError(f"unsupported selective JUDGE transport: {judge_transport_mode!r}")
    judge_max_calls_raw = getattr(args, "judge_max_calls", None)
    judge_cap_raw = str(getattr(args, "judge_cap_gbp", "0.01") or "0.01").strip()
    if judge_mode == JUDGE_MODE_OFF:
        judge_model = None
        judge_transport_mode = JUDGE_TRANSPORT_DIRECT
        judge_max_calls = 0
        judge_cap = "0"
    else:
        judge_model = judge_model_raw or "judge-1.13.0"
        judge_max_calls = 1 if judge_max_calls_raw is None else int(judge_max_calls_raw)
        if judge_max_calls != 1:
            raise RuntimeError("selective JUDGE treatments are one-shot and require exactly one call")
        try:
            from decimal import Decimal
            cap = Decimal(judge_cap_raw)
        except Exception as exc:
            raise RuntimeError("invalid selective JUDGE cap") from exc
        if not cap.is_finite() or cap <= 0:
            raise RuntimeError("selective JUDGE cap must be positive and finite")
        judge_cap = str(cap)
    max_output = int(getattr(args, "solver_max_output_tokens", 0) or 0)
    if max_output <= 0:
        raise RuntimeError("solver max output tokens must be positive")
    effort = str(getattr(args, "reasoning_effort", None) or base_profile.solver_reasoning_effort)
    # Clone the frozen route profile so provider authorization and the profile
    # treatment hash bind the row's retry policy without mutating the selector.
    profile = replace(
        base_profile,
        solver_reasoning_effort=effort,
        solver_max_output_tokens=max_output,
        provider_max_retries=provider_max_retries,
    )
    return ResearchRuntimeConfig(
        profile_selector=selector,
        profile=profile,
        endpoint=endpoint,
        deployment=deployment,
        provider_tpm=int(tpm),
        provider_rpm=int(rpm),
        provider_window_s=float(window_s),
        provider_max_retries=provider_max_retries,
        provider_sdk_max_retries=provider_sdk_max_retries,
        provider_window_anchor=window_anchor,
        shared_limiter_path=shared_path,
        observed_route_tpm=observed_tpm,
        observed_route_rpm=observed_rpm,
        observed_route_window_s=observed_window_s,
        solver_model_view_mode=model_view,
        solver_reality_transport_mode=transport,
        solver_working_context_mode=working_context_mode,
        solver_tool_surface_mode=tool_surface_mode,
        solver_completion_signal_mode=completion_signal_mode,
        solver_context_policy=context_policy,
        managed_context_trigger_tokens=managed_context_trigger,
        managed_context_keep_exchanges=managed_context_keep,
        solver_judge_advice_mode=judge_mode,
        judge_model=judge_model,
        judge_transport_mode=judge_transport_mode,
        judge_max_calls=judge_max_calls,
        judge_cap_gbp=judge_cap,
        solver_max_output_tokens=max_output,
        solver_long_command_mode=selected_long_command_mode(),
    )
