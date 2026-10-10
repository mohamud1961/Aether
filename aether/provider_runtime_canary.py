"""One-call production provider admission canary.

This is deliberately not a benchmark task. It proves that the exact installed
Aether runtime can reach the configured production Responses WebSocket route
and receive one native ``read_file`` tool call before a paid Harbor dispatch.
No raw model output or credential value is persisted.
"""
from __future__ import annotations

import argparse
from contextvars import ContextVar
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlsplit

from .launch import (
    canonical_json,
    package_closure,
    package_root,
    production_tool_schema_sha256,
    _provider_runtime_identity,
)
from .model_profile import PRODUCTION_PROFILE, require_provider_authorization
from .provider_budget import budget_runtime_limits_from_env, provider_budget_guard_from_env
from .providers.azure_model import make_azure_callable
from .run_deadline import (
    raise_if_run_deadline_exceeded,
    remaining_run_s,
    run_deadline,
)

SCHEMA_VERSION = "aether.provider_runtime_canary.v1"
PRODUCTION_SELECTOR = "production"
FRONTIER_RESEARCH_SELECTOR = "frontier-research-v1"
FRONTIER_CANARY_SMOKE_MODE = "bounded-canary-smoke"
FRONTIER_REQUEST_DEADLINE_S = 180
FRONTIER_OVERALL_DEADLINE_S = 360
FRONTIER_MAX_INPUT_TOKENS = 30_000
FRONTIER_MAX_OUTPUT_TOKENS = 2_000
FRONTIER_MAX_TOTAL_CAP_GBP = "0.02"
FRONTIER_EXPECTED_RETURNED_MODELS = frozenset({
    "gpt-6-luna",
    "gpt-6-luna-2026-09-22",
})
FRONTIER_PRICING_REFERENCE = (
    "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/"
)
_monotonic = time.monotonic
_active_access_token_capture: ContextVar[list[str] | None] = ContextVar(
    "aether_canary_access_token_capture", default=None,
)


@contextmanager
def _capture_access_tokens():
    captured: list[str] = []
    token = _active_access_token_capture.set(captured)
    try:
        yield captured
    finally:
        _active_access_token_capture.reset(token)


def _token_spellings(access_tokens: list[str] | tuple[str, ...]) -> dict[str, str]:
    """Return only in-memory secret spellings and their nonreversible IDs."""
    spellings: dict[str, str] = {}
    for access_token in access_tokens:
        if not isinstance(access_token, str) or not access_token:
            continue
        token_id = sha256(access_token.encode("utf-8", errors="replace")).hexdigest()
        encoded = access_token.encode("utf-8")
        candidates = {
            access_token,
            repr(access_token),
            repr(encoded),
            str(encoded),
            json.dumps(access_token, ensure_ascii=True),
            json.dumps(access_token, ensure_ascii=False),
            json.dumps(access_token, ensure_ascii=True)[1:-1],
            json.dumps(access_token, ensure_ascii=False)[1:-1],
        }
        for value in candidates:
            if value:
                spellings[value] = token_id
    return spellings


def _secret_matches(value: str | bytes, spellings: dict[str, str]) -> list[str]:
    observed = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return [spelling for spelling in spellings if spelling in observed]


def _secret_echo_findings(
    value: Any,
    access_tokens: list[str] | tuple[str, ...],
    *,
    path: str = "$",
) -> list[dict[str, str]]:
    spellings = _token_spellings(access_tokens)
    findings: list[dict[str, str]] = []

    def visit(current: Any, current_path: str) -> None:
        if isinstance(current, (str, bytes)):
            matches = _secret_matches(current, spellings)
            if matches:
                token_ids = sorted({spellings[match] for match in matches})
                rendered = current if isinstance(current, bytes) else current.encode("utf-8", errors="replace")
                findings.append({
                    "path": current_path,
                    "value_sha256": sha256(rendered).hexdigest(),
                    "token_sha256": ",".join(token_ids),
                })
            return
        if isinstance(current, dict):
            for index, (key, child) in enumerate(current.items()):
                key_text = key if isinstance(key, str) else str(key)
                key_matches = _secret_matches(key_text, spellings)
                if key_matches:
                    token_ids = sorted({spellings[match] for match in key_matches})
                    findings.append({
                        "path": f"{current_path}.<key:{index}>",
                        "value_sha256": sha256(key_text.encode("utf-8", errors="replace")).hexdigest(),
                        "token_sha256": ",".join(token_ids),
                    })
                safe_key = key_text if not key_matches else f"<redacted-key:{index}>"
                visit(child, f"{current_path}.{safe_key}")
            return
        if isinstance(current, (list, tuple)):
            for index, child in enumerate(current):
                visit(child, f"{current_path}[{index}]")

    visit(value, path)
    return findings


def _sanitize_secret_values(
    value: Any,
    access_tokens: list[str] | tuple[str, ...],
    *,
    path: str = "$",
) -> tuple[Any, list[dict[str, str]]]:
    """Preserve evidence shape while replacing only token-bearing values."""
    spellings = _token_spellings(access_tokens)
    findings: list[dict[str, str]] = []

    def visit(current: Any, current_path: str) -> Any:
        if isinstance(current, (str, bytes)):
            matches = _secret_matches(current, spellings)
            if not matches:
                return current.decode("utf-8", errors="replace") if isinstance(current, bytes) else current
            token_ids = sorted({spellings[match] for match in matches})
            rendered = current if isinstance(current, bytes) else current.encode("utf-8", errors="replace")
            value_hash = sha256(rendered).hexdigest()
            findings.append({
                "path": current_path,
                "value_sha256": value_hash,
                "token_sha256": ",".join(token_ids),
            })
            return f"[REDACTED_TOKEN_BEARING_VALUE sha256={value_hash}]"
        if isinstance(current, dict):
            cleaned: dict[str, Any] = {}
            for index, (key, child) in enumerate(current.items()):
                key_text = key if isinstance(key, str) else str(key)
                key_matches = _secret_matches(key_text, spellings)
                if key_matches:
                    token_ids = sorted({spellings[match] for match in key_matches})
                    key_hash = sha256(key_text.encode("utf-8", errors="replace")).hexdigest()
                    findings.append({
                        "path": f"{current_path}.<key:{index}>",
                        "value_sha256": key_hash,
                        "token_sha256": ",".join(token_ids),
                    })
                    safe_key = f"[REDACTED_TOKEN_BEARING_KEY_{index}]"
                else:
                    safe_key = key_text
                cleaned[safe_key] = visit(child, f"{current_path}.{safe_key}")
            return cleaned
        if isinstance(current, (list, tuple)):
            return [visit(child, f"{current_path}[{index}]") for index, child in enumerate(current)]
        return current

    return visit(value, path), findings


def _assert_serialized_artifact_secret_free(
    serialized: str,
    access_tokens: list[str] | tuple[str, ...],
) -> None:
    if _secret_echo_findings(serialized, access_tokens, path="$.serialized_artifact"):
        raise _CanaryCheckFailure("artifact_access_token_containment_failed")


def _containment_failure_receipt(
    receipt: dict[str, Any],
    access_tokens: list[str] | tuple[str, ...],
    *,
    rejected_artifact_sha256: str,
) -> dict[str, Any]:
    sanitized, findings = _sanitize_secret_values(
        receipt, access_tokens, path="$.receipt",
    )
    result = dict(sanitized)
    result["passed"] = False
    worker = dict(result.get("worker") or {})
    worker["passed"] = False
    worker["error"] = {
        "stage": "artifact_write_boundary",
        "type": "_CanaryCheckFailure",
        "code": "artifact_access_token_containment_failed",
        "message": "raw error detail omitted",
        "rejected_artifact_sha256": rejected_artifact_sha256,
    }
    result["worker"] = worker
    containment = dict(result.get("provider_value_containment") or {})
    prior_findings = list(containment.get("rejected_fields") or [])
    containment["token_bearing_provider_values_rejected"] = bool(findings or prior_findings)
    containment["rejected_field_count"] = len(prior_findings) + len(findings)
    containment["rejected_fields"] = prior_findings + findings
    containment["serialized_artifact_rejected"] = True
    containment["rejected_artifact_sha256"] = rejected_artifact_sha256
    result["provider_value_containment"] = containment
    result["raw_native_actions_persisted"] = False
    result["access_token_values_persisted"] = False
    result["credential_values_persisted"] = False
    return result


def _record_mi_token(remaining_s: float, token_provider: Any) -> str:
    capture = _active_access_token_capture.get()
    if capture is None:
        raise _CanaryCheckFailure("access_token_capture_not_bound")
    access_token = token_provider(remaining_s)
    if not isinstance(access_token, str) or not access_token:
        raise _CanaryCheckFailure("managed_identity_token_missing")
    capture.append(access_token)
    return access_token


def _ensure_frontier_deadline(deadline_at: float) -> float:
    remaining = deadline_at - _monotonic()
    runtime_remaining = remaining_run_s()
    if remaining <= 0 or (runtime_remaining is not None and runtime_remaining <= 0):
        raise _CanaryCheckFailure("overall_canary_deadline_exceeded")
    raise_if_run_deadline_exceeded()
    return remaining if runtime_remaining is None else min(remaining, runtime_remaining)


def _route_fingerprint() -> str:
    endpoint = str(os.environ.get(PRODUCTION_PROFILE.endpoint_env, "") or "").strip()
    deployment = str(os.environ.get(PRODUCTION_PROFILE.deployment_env, "") or "").strip()
    if not endpoint or not deployment:
        raise RuntimeError("provider canary missing endpoint/deployment environment")
    return sha256(canonical_json({"endpoint": endpoint, "deployment": deployment}).encode("utf-8")).hexdigest()


def _run_production_canary(*, label: str) -> dict[str, Any]:
    require_provider_authorization(PRODUCTION_PROFILE)
    budget_limits = budget_runtime_limits_from_env()
    budget_guard = provider_budget_guard_from_env()
    if budget_limits is None or budget_guard is None:
        raise RuntimeError("provider canary requires a finite provider budget contract")
    if budget_guard.contract.model_id != PRODUCTION_PROFILE.model_id:
        raise RuntimeError("provider canary budget model identity mismatch")
    if budget_guard.contract.roles["solver"].max_provider_creates != 1:
        raise RuntimeError("provider canary budget must authorize exactly one solver create")
    if any(budget_guard.contract.roles[role].max_provider_creates != 0 for role in ("verifier", "vision")):
        raise RuntimeError("provider canary budget may authorize only the one solver create")
    canary_max_output_tokens = 2000
    if budget_guard.contract.roles["solver"].max_output_tokens < canary_max_output_tokens:
        raise RuntimeError("provider canary budget solver output ceiling must be at least 2000 tokens")
    closure = package_closure()
    runtime_identity = _provider_runtime_identity()
    started = time.time()
    model = make_azure_callable(
        deployment_env=PRODUCTION_PROFILE.deployment_env,
        key_env=PRODUCTION_PROFILE.key_env,
        endpoint_env=PRODUCTION_PROFILE.endpoint_env,
        effort=PRODUCTION_PROFILE.solver_reasoning_effort,
        role="solver",
        responses_background=False,
        responses_websocket=True,
        prompt_cache_mode="off",
        poll_interval_s=2,
        poll_timeout_s=180,
        max_retries=0,
        sdk_max_retries=0,
    )
    raw: str | None = None
    error: dict[str, str] | None = None
    try:
        raw = model.call_with_telemetry_scope(
            [
                {
                    "role": "system",
                    "content": "Synthetic Aether provider admission canary. Make exactly one native read_file call and do not submit.",
                },
                {
                    "role": "user",
                    "content": f"Call read_file for /tmp/aether-provider-canary-{label}.txt.",
                },
            ],
            run_id=f"provider-canary-{label}",
            task_id=f"synthetic-provider-canary-{label}",
            max_output_tokens=canary_max_output_tokens,
        )
    except Exception as exc:  # evidence, no retry
        error = {"type": type(exc).__name__, "message": str(exc)[:2000]}
    finally:
        telemetry = list(model.drain_telemetry())
        model.close_run_transport()
    finished = time.time()
    completed = [row for row in telemetry if row.get("status") == "completed"]
    row = completed[-1] if completed else {}
    budget_snapshot = budget_guard.snapshot()
    passed = bool(
        error is None
        and int(budget_snapshot.get("aggregate_create_count") or 0) == 1
        and int(dict(budget_snapshot.get("role_create_counts") or {}).get("solver") or 0) == 1
        and len(completed) == 1
        and row.get("provider_transport_mode") == "websocket"
        and row.get("native_tool_name") == "read_file"
        and int(row.get("native_tool_call_count") or 0) == 1
        and int(row.get("attempt_ordinal") or 0) == 1
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": passed,
        "label": str(label),
        "created_at_unix_s": started,
        "finished_at_unix_s": finished,
        "elapsed_s": round(finished - started, 6),
        "requested_width": 1,
        "completed_provider_calls": len(completed),
        "python_executable": str(Path(sys.executable).resolve()),
        "package_root": str(package_root().resolve()),
        "candidate": {
            "package_closure_sha256": closure.sha256,
            "package_file_count": closure.file_count,
            "model_profile_sha256": PRODUCTION_PROFILE.sha256(),
            "tool_schema_sha256": production_tool_schema_sha256(),
            "model_id": PRODUCTION_PROFILE.model_id,
            "solver_reasoning_effort": PRODUCTION_PROFILE.solver_reasoning_effort,
        },
        "provider_route_sha256": _route_fingerprint(),
        "provider_runtime": runtime_identity,
        "provider_policy": {
            "responses_websocket": True,
            "responses_background": False,
            "provider_max_retries": 0,
            "sdk_max_retries": 0,
            "poll_timeout_s": 180,
            "max_output_tokens": canary_max_output_tokens,
            "budget_constrained": True,
        },
        "provider_budget": {
            "budget_id": budget_limits["budget_id"],
            "model_id": budget_limits["model_id"],
            "contract_sha256": budget_limits["budget_contract_sha256"],
            "total_cap_gbp": budget_limits["total_cap_gbp"],
            "max_total_provider_creates": budget_limits["max_total_provider_creates"],
            "snapshot": budget_snapshot,
        },
        "worker": {
            "passed": passed,
            "error": error,
            "transport_mode": row.get("provider_transport_mode"),
            "native_tool_name": row.get("native_tool_name"),
            "native_tool_call_count": row.get("native_tool_call_count"),
            "attempt_ordinal": row.get("attempt_ordinal"),
            "provider_terminal_failure": row.get("provider_terminal_failure"),
            "raw_sha256": None if raw is None else sha256(raw.encode("utf-8")).hexdigest(),
        },
        "raw_model_output_persisted": False,
        "credential_values_persisted": False,
    }


def _safe_label(label: str) -> str:
    normalized = str(label or "").strip()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", normalized) is None:
        raise RuntimeError("canary label must be 1-64 safe ASCII characters")
    return normalized


def _frontier_route(profile: Any, selector: str) -> dict[str, str]:
    endpoint = str(os.environ.get(profile.endpoint_env, "") or "").strip()
    deployment = str(os.environ.get(profile.deployment_env, "") or "").strip()
    if not endpoint or not deployment:
        raise RuntimeError("canary route is missing endpoint or deployment")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise RuntimeError("canary endpoint must be a credential-free HTTPS base URL")
    host = parsed.hostname.lower()
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    normalized_endpoint = f"https://{netloc}"
    route_sha256 = profile.route_identity_sha256(
        selector=selector,
        endpoint=normalized_endpoint,
        deployment=deployment,
    )
    return {
        "selector": selector,
        "profile_id": str(profile.profile_id),
        "model_id": str(profile.model_id),
        "endpoint": normalized_endpoint,
        "deployment": deployment,
        "route_identity_sha256": route_sha256,
    }


def _safe_error(stage: str, exc: BaseException) -> dict[str, str]:
    # Exception messages can contain request headers or provider event bodies.
    # Preserve a stable class/code and a one-way digest, never raw detail.
    code = str(getattr(exc, "code", "") or "") if isinstance(exc, _CanaryCheckFailure) else ""
    if re.fullmatch(r"[a-zA-Z0-9_.-]{1,96}", code) is None:
        code = "details_omitted"
    return {
        "stage": stage,
        "type": type(exc).__name__[:80],
        "code": code,
        "message": "raw error detail omitted",
        "detail_sha256": sha256(str(exc).encode("utf-8", errors="replace")).hexdigest(),
    }


def _frontier_source_identity() -> dict[str, str]:
    source_commit = str(os.environ.get("AETHER_SOURCE_COMMIT") or "").strip()
    runtime_manifest = str(os.environ.get("AETHER_RUNTIME_MANIFEST_SHA256") or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{40,64}", source_commit) is None:
        raise _CanaryCheckFailure("source_commit_identity_missing_or_invalid")
    if re.fullmatch(r"[0-9a-fA-F]{64}", runtime_manifest) is None:
        raise _CanaryCheckFailure("runtime_manifest_identity_missing_or_invalid")
    return {
        "source_commit": source_commit.casefold(),
        "runtime_manifest_sha256": runtime_manifest.casefold(),
    }


class _CanaryCheckFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _bounded_frontier_budget(guard: Any, limits: dict[str, Any]) -> dict[str, Any]:
    contract = getattr(guard, "contract", None)
    if contract is None:
        raise _CanaryCheckFailure("budget_contract_unavailable")
    budget_model_id = str(contract.model_id or "").casefold()
    if budget_model_id != "gpt-6-luna" or str(limits.get("model_id") or "").casefold() != budget_model_id:
        raise _CanaryCheckFailure("budget_model_identity_mismatch")
    solver = contract.roles.get("solver")
    verifier = contract.roles.get("verifier")
    vision = contract.roles.get("vision")
    if solver is None or verifier is None or vision is None:
        raise _CanaryCheckFailure("budget_role_contract_incomplete")
    if (
        int(solver.max_provider_creates) != 2
        or int(verifier.max_provider_creates) != 0
        or int(vision.max_provider_creates) != 0
        or int(contract.max_total_provider_creates) != 2
    ):
        raise _CanaryCheckFailure("budget_create_scope_mismatch")
    if (
        int(solver.max_input_tokens) != FRONTIER_MAX_INPUT_TOKENS
        or int(solver.max_output_tokens) != FRONTIER_MAX_OUTPUT_TOKENS
    ):
        raise _CanaryCheckFailure("budget_token_ceiling_mismatch")
    if (
        int(contract.provider_max_retries) != 0
        or int(contract.provider_sdk_max_retries) != 0
    ):
        raise _CanaryCheckFailure("budget_retry_policy_mismatch")
    if float(contract.agent_timeout_sec) > FRONTIER_OVERALL_DEADLINE_S:
        raise _CanaryCheckFailure("budget_agent_deadline_exceeds_canary_limit")
    if float(contract.total_cap_gbp) > float(FRONTIER_MAX_TOTAL_CAP_GBP):
        raise _CanaryCheckFailure("budget_cost_cap_exceeds_canary_limit")
    if float(contract.worst_case_total_gbp) > float(contract.total_cap_gbp):
        raise _CanaryCheckFailure("budget_worst_case_exceeds_cost_cap")
    return {
        "budget_id": str(contract.budget_id),
        "model_id": budget_model_id,
        "budget_contract_sha256": str(limits.get("budget_contract_sha256") or ""),
        "budget_schema_version": str(contract.schema_version),
        "total_cap_gbp": str(contract.total_cap_gbp),
        "max_total_provider_creates": int(contract.max_total_provider_creates),
        "solver_max_input_tokens": int(solver.max_input_tokens),
        "solver_max_output_tokens": int(solver.max_output_tokens),
        "worst_case_total_gbp": str(contract.worst_case_total_gbp),
        "provider_max_retries": int(contract.provider_max_retries),
        "provider_sdk_max_retries": int(contract.provider_sdk_max_retries),
        "agent_timeout_sec": float(contract.agent_timeout_sec),
        "roles": {
            "solver": int(solver.max_provider_creates),
            "verifier": int(verifier.max_provider_creates),
            "vision": int(vision.max_provider_creates),
        },
    }


def _parse_native_action(raw: str, *, expected_path: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
        action = value["action"]
        path = action["arguments"]["path"]
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise _CanaryCheckFailure("native_action_shape_invalid") from exc
    if value.get("kind") != "act" or action.get("kind") != "read_file" or path != expected_path:
        raise _CanaryCheckFailure("native_action_identity_mismatch")
    return {"kind": "read_file", "arguments": {"path": expected_path}}


def _raw_provider_action(row: dict[str, Any], *, expected_path: str) -> dict[str, str]:
    raw_items = row.get("raw_provider_output_items")
    if not isinstance(raw_items, (list, tuple)):
        raise _CanaryCheckFailure("raw_native_action_evidence_missing")
    calls = [
        item for item in raw_items
        if isinstance(item, dict) and str(item.get("type") or "") == "function_call"
    ]
    if len(calls) != 1:
        raise _CanaryCheckFailure("raw_native_action_count_invalid")
    item = calls[0]
    name = str(item.get("name") or "")
    call_id = str(item.get("call_id") or "")
    arguments = str(item.get("arguments") or "")
    try:
        parsed = json.loads(arguments)
        path = parsed["arguments"]["path"]
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise _CanaryCheckFailure("raw_native_action_shape_invalid") from exc
    if name != "read_file" or not call_id or path != expected_path:
        raise _CanaryCheckFailure("raw_native_action_identity_mismatch")
    return {
        "type": "function_call",
        "name": name,
        "call_id": call_id,
        "arguments": arguments,
    }


def _request_evidence(row: dict[str, Any]) -> dict[str, Any]:
    raw_request = row.get("raw_provider_request")
    if not isinstance(raw_request, dict):
        raise _CanaryCheckFailure("raw_provider_request_evidence_missing")
    reasoning = raw_request.get("reasoning")
    input_items = raw_request.get("input")
    if not isinstance(input_items, list):
        input_items = [input_items]
    tool_names = [
        str(item.get("name") or "")
        for item in raw_request.get("tools", ())
        if isinstance(item, dict)
    ]
    cache_key = str(raw_request.get("prompt_cache_key") or "")
    evidence = {
        "model": raw_request.get("model"),
        "reasoning_effort": reasoning.get("effort") if isinstance(reasoning, dict) else None,
        "prompt_cache_key": cache_key,
        "prompt_cache_mode": row.get("prompt_cache_key_mode"),
        "input": input_items,
        "tool_names": tool_names,
        "tool_schema_sha256": row.get("persistent_primary_provider_schema_sha256"),
        "request_sha256": row.get("raw_provider_request_sha256"),
    }
    if (
        evidence["reasoning_effort"] != "high"
        or evidence["prompt_cache_mode"] != "stable_prefix"
        or not cache_key
    ):
        raise _CanaryCheckFailure("provider_request_profile_mismatch")
    if "read_file" not in tool_names:
        raise _CanaryCheckFailure("provider_native_read_file_tool_missing")
    return evidence


def _frontier_event_evidence(row: dict[str, Any], *, input_upper_bound: int) -> dict[str, Any]:
    numeric_usage: dict[str, int | None] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"):
        value = row.get(key)
        numeric_usage[key] = int(value) if isinstance(value, int) and not isinstance(value, bool) else None
    if (
        row.get("status") != "completed"
        or row.get("provider_transport_mode") != "websocket"
        or row.get("attempt_ordinal") != 1
        or row.get("returned_model_known") is not True
        or str(row.get("returned_model") or "").casefold() not in FRONTIER_EXPECTED_RETURNED_MODELS
        or row.get("native_tool_name") != "read_file"
        or int(row.get("native_tool_call_count") or 0) != 1
        or row.get("usage_status") != "reported"
        or numeric_usage["input_tokens"] is None
        or numeric_usage["output_tokens"] is None
        or numeric_usage["input_tokens"] > FRONTIER_MAX_INPUT_TOKENS
        or numeric_usage["output_tokens"] > FRONTIER_MAX_OUTPUT_TOKENS
        or input_upper_bound > FRONTIER_MAX_INPUT_TOKENS
    ):
        raise _CanaryCheckFailure("provider_attempt_validation_failed")
    request = _request_evidence(row)
    return {
        "status": row.get("status"),
        "role": row.get("role"),
        "attempt_ordinal": row.get("attempt_ordinal"),
        "transport_mode": row.get("provider_transport_mode"),
        "returned_model": row.get("returned_model"),
        "returned_model_known": row.get("returned_model_known"),
        "response_id": row.get("response_id"),
        "native_tool_name": row.get("native_tool_name"),
        "native_tool_call_id": row.get("native_tool_call_id"),
        "native_tool_call_count": row.get("native_tool_call_count"),
        "request_previous_response_id": row.get("persistent_continuity_request_previous_response_id"),
        "continuity_request_input_item_types": row.get("persistent_continuity_request_input_item_types"),
        "continuity_request_function_call_output_count": row.get("persistent_continuity_request_function_call_output_count"),
        "continuity_request_function_call_output_call_ids": row.get("persistent_continuity_request_function_call_output_call_ids"),
        "continuity_expected_prior_call_id": row.get("persistent_continuity_expected_prior_call_id"),
        "continuity_prior_call_id_match_count": row.get("persistent_continuity_prior_call_id_match_count"),
        "continuity_reanchor_attempted": row.get("persistent_continuity_reanchor_attempted"),
        "prompt_cache_key_mode": row.get("prompt_cache_key_mode"),
        "usage_status": row.get("usage_status"),
        "cache_metrics_status": row.get("cache_metrics_status"),
        "provider_budget_reserved_gbp": row.get("provider_budget_reserved_gbp"),
        "provider_budget_settlement_status": row.get("provider_budget_settlement_status"),
        "token_usage": numeric_usage,
        "serialized_request_token_upper_bound": input_upper_bound,
        "model_visible_request": request,
        "provider_websocket_event_count": row.get("provider_websocket_event_count"),
    }


def _run_frontier_canary_smoke(*, label: str) -> dict[str, Any]:
    wall_started = time.time()
    monotonic_started = _monotonic()
    label = _safe_label(label)
    from .research_frontier_profile import FRONTIER_RESEARCH_PROFILE, frontier_research_profile

    profile = frontier_research_profile(FRONTIER_RESEARCH_SELECTOR)
    if profile is not FRONTIER_RESEARCH_PROFILE:
        raise _CanaryCheckFailure("frontier_profile_selector_mismatch")
    require_provider_authorization(profile)
    budget_limits = budget_runtime_limits_from_env()
    if budget_limits is None:
        raise _CanaryCheckFailure("finite_provider_budget_required")
    budget_model_id = str(profile.model_id).casefold()
    budget_guard = provider_budget_guard_from_env(expected_model_id=budget_model_id)
    if budget_guard is None:
        raise _CanaryCheckFailure("finite_provider_budget_required")
    bounded_budget = _bounded_frontier_budget(budget_guard, budget_limits)
    overall_deadline_s = min(
        float(bounded_budget["agent_timeout_sec"]),
        float(FRONTIER_OVERALL_DEADLINE_S),
    )
    overall_deadline_at = monotonic_started + overall_deadline_s
    if profile.solver_reasoning_effort != "high" or profile.prompt_cache_mode != "stable_prefix":
        raise _CanaryCheckFailure("frontier_profile_effort_or_cache_mismatch")
    if (
        profile.credential_mode != "system_assigned_managed_identity"
        or profile.key_env
        or profile.responses_background
        or not profile.responses_websocket
        or not profile.responses_websocket_persistent
    ):
        raise _CanaryCheckFailure("frontier_profile_transport_or_auth_mismatch")

    route: dict[str, str] = {}
    closure = None
    source_identity: dict[str, str] = {}
    runtime_identity: dict[str, Any] = {}
    model = None
    events: list[dict[str, Any]] = []
    turn_records: list[dict[str, Any]] = []
    event_evidence: list[dict[str, Any]] = []
    error: dict[str, str] | None = None
    stage = "model_build"
    started = wall_started
    telemetry_drained = False
    request_bounds: list[int] = []
    secret_echo_findings: list[dict[str, str]] = []
    expected_paths = [
        f"/tmp/aether-provider-canary-{label}.txt",
        f"/tmp/aether-provider-canary-{label}-continuation.txt",
    ]
    common_instructions = (
        "Synthetic Aether provider admission canary. Make exactly one native "
        "read_file call per turn. Never execute a command or submit work."
    )
    messages_per_turn = [
        [
            {"role": "system", "content": common_instructions},
            {"role": "user", "content": f"Call read_file for {expected_paths[0]}."},
        ],
        [
            {"role": "system", "content": common_instructions},
            {
                "role": "user",
                "content": (
                    "Synthetic tool result for your previous read_file call: "
                    "the file contained 'AETHER_CANARY_SYNTHETIC_OK'. Now call "
                    f"read_file for {expected_paths[1]}."
                ),
            },
        ],
    ]
    old_capture_request = os.environ.get("AETHER_CAPTURE_RAW_PROVIDER_REQUEST")
    old_capture_output = os.environ.get("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT")
    os.environ["AETHER_CAPTURE_RAW_PROVIDER_REQUEST"] = "1"
    os.environ["AETHER_CAPTURE_RAW_PROVIDER_OUTPUT"] = "1"
    deadline_binding = run_deadline(overall_deadline_at)
    deadline_binding.__enter__()
    try:
        stage = "route_identity"
        _ensure_frontier_deadline(overall_deadline_at)
        route = _frontier_route(profile, FRONTIER_RESEARCH_SELECTOR)
        closure = package_closure()
        source_identity = _frontier_source_identity()
        runtime_identity = _provider_runtime_identity()
        stage = "model_build"
        model = make_azure_callable(
            deployment_env=profile.deployment_env,
            key_env=profile.key_env,
            endpoint_env=profile.endpoint_env,
            credential_mode=profile.credential_mode,
            expected_model_id=budget_model_id,
            effort=profile.solver_reasoning_effort,
            role="solver",
            responses_background=False,
            responses_websocket=True,
            responses_websocket_persistent=True,
            prompt_cache_mode=profile.prompt_cache_mode,
            poll_interval_s=1,
            poll_timeout_s=FRONTIER_REQUEST_DEADLINE_S,
            max_retries=0,
            sdk_max_retries=0,
            max_rpm=0,
        )
        if (
            str(getattr(model, "_deployment", "")).casefold() != str(route["deployment"]).casefold()
            or getattr(model, "_effort", None) != "high"
            or getattr(model, "_role", None) != "solver"
            or getattr(model, "_prompt_cache_mode", None) != "stable_prefix"
            or getattr(model, "_responses_background", None) is not False
            or getattr(model, "_responses_websocket", None) is not True
            or getattr(model, "_max_retries", None) != 0
            or getattr(model, "_poll_timeout_s", None) != FRONTIER_REQUEST_DEADLINE_S
            or getattr(model, "_budget_guard", None) is not budget_guard
        ):
            raise _CanaryCheckFailure("built_solver_profile_mismatch")
        transport = getattr(model, "_websocket_transport", None)
        if (
            transport is None
            or getattr(transport, "_persist_completed_connection", None) is not True
            or getattr(transport, "_request_timeout_s", None) != FRONTIER_REQUEST_DEADLINE_S
        ):
            raise _CanaryCheckFailure("built_websocket_transport_mismatch")

        token_provider = getattr(transport, "_deadline_bearer_token_provider", None)
        if (
            not callable(token_provider)
            or getattr(transport, "_bearer_token_provider", None) is not None
        ):
            raise _CanaryCheckFailure("managed_identity_deadline_token_provider_missing")

        def captured_token_provider(remaining_s: float) -> str:
            return _record_mi_token(remaining_s, token_provider)

        transport._deadline_bearer_token_provider = captured_token_provider

        responses_create = getattr(model, "_responses_create", None)
        if not callable(responses_create):
            raise _CanaryCheckFailure("model_transport_dispatch_seam_missing")

        def bounded_secret_checked_create(**kwargs: Any) -> Any:
            request_values = {
                key: value for key, value in kwargs.items()
                if not key.startswith("_aether_")
            }
            # Keep the live capture list even before it has its first value;
            # replacing an empty list here would detach the dispatch guard
            # from the MI token recorded moments later by the transport.
            capture = _active_access_token_capture.get()
            if capture is None:
                capture = []
            findings = _secret_echo_findings(
                request_values, capture, path="$.provider_request",
            )
            if findings:
                secret_echo_findings.extend(findings)
                raise _CanaryCheckFailure("provider_request_contains_access_token")
            remaining_s = _ensure_frontier_deadline(overall_deadline_at)
            requested_timeout = float(
                kwargs.get("_aether_transport_timeout_s") or FRONTIER_REQUEST_DEADLINE_S
            )
            kwargs["_aether_transport_timeout_s"] = min(
                requested_timeout,
                remaining_s,
                float(FRONTIER_REQUEST_DEADLINE_S),
            )
            lifecycle_observer = kwargs.get("_aether_lifecycle_observer")
            if callable(lifecycle_observer):
                def guarded_lifecycle_observer(
                    lifecycle_stage: str,
                    detail: dict[str, Any],
                ) -> Any:
                    lifecycle_findings = _secret_echo_findings(
                        {"stage": lifecycle_stage, "detail": detail},
                        capture,
                        path="$.provider_lifecycle_event",
                    )
                    if lifecycle_findings:
                        secret_echo_findings.extend(lifecycle_findings)
                        raise _CanaryCheckFailure(
                            "provider_lifecycle_contains_access_token"
                        )
                    return lifecycle_observer(lifecycle_stage, detail)

                kwargs["_aether_lifecycle_observer"] = guarded_lifecycle_observer
            response = responses_create(**kwargs)
            # AzureModel persists response.id and response.status immediately
            # after this seam returns. Inspect exactly those lifecycle fields
            # while still inside the canary boundary, before that durable write.
            lifecycle_values = {
                "response_id": getattr(response, "id", None),
                "status": getattr(response, "status", None),
            }
            lifecycle_findings = _secret_echo_findings(
                lifecycle_values,
                capture,
                path="$.provider_returned_lifecycle_fields",
            )
            if lifecycle_findings:
                secret_echo_findings.extend(lifecycle_findings)
                raise _CanaryCheckFailure(
                    "provider_lifecycle_contains_access_token"
                )
            return response

        model._responses_create = bounded_secret_checked_create

        stage = "first_native_action"
        run_id = f"provider-canary-{label}"
        task_id = f"synthetic-provider-canary-{label}"
        for index, messages in enumerate(messages_per_turn):
            _ensure_frontier_deadline(overall_deadline_at)
            if index:
                stage = "synthetic_continuation"
            raw = model.call_with_telemetry_scope(
                messages,
                run_id=run_id,
                task_id=task_id,
                max_output_tokens=FRONTIER_MAX_OUTPUT_TOKENS,
            )
            current_row = dict(getattr(model, "last_call_telemetry", {}) or {})
            capture = _active_access_token_capture.get() or []
            response_findings = _secret_echo_findings(
                {"model_output": raw, "attempt_telemetry": current_row},
                capture,
                path=f"$.provider_turns[{index}]",
            )
            if response_findings:
                secret_echo_findings.extend(response_findings)
                sanitized_response, response_redactions = _sanitize_secret_values(
                    raw, capture, path=f"$.provider_turns[{index}].raw_model_output",
                )
                turn_records.append({
                    "turn": index + 1,
                    "messages": messages,
                    "raw_model_output": sanitized_response,
                    "raw_model_output_sha256": sha256(
                        raw.encode("utf-8", errors="replace")
                    ).hexdigest(),
                    "token_echo_redactions": response_redactions,
                })
                raise _CanaryCheckFailure("provider_response_contains_access_token")
            _ensure_frontier_deadline(overall_deadline_at)
            if str(current_row.get("returned_model") or "").casefold() not in FRONTIER_EXPECTED_RETURNED_MODELS:
                raise _CanaryCheckFailure("returned_model_identity_mismatch")
            canonical_action = _parse_native_action(raw, expected_path=expected_paths[index])
            native_action = _raw_provider_action(current_row, expected_path=expected_paths[index])
            if native_action["call_id"] != str(current_row.get("native_tool_call_id") or ""):
                raise _CanaryCheckFailure("native_action_call_id_mismatch")
            raw_request = current_row.get("raw_provider_request")
            if not isinstance(raw_request, dict):
                raise _CanaryCheckFailure("raw_provider_request_evidence_missing")
            from .provider_budget import serialized_request_token_upper_bound

            input_upper_bound = serialized_request_token_upper_bound(raw_request)
            if index:
                prior_total = events[-1].get("total_tokens")
                if not isinstance(prior_total, int) or prior_total <= 0:
                    raise _CanaryCheckFailure("prior_provider_usage_missing_for_continuation")
                input_upper_bound += prior_total
            request_bounds.append(input_upper_bound)
            _frontier_event_evidence(current_row, input_upper_bound=input_upper_bound)
            turn_records.append({"turn": index + 1, "messages": messages})
            turn_records[-1].update({
                "aether_canonical_action": canonical_action,
                "provider_native_action": native_action,
                "canonical_action_sha256": sha256(raw.encode("utf-8")).hexdigest(),
            })
            _ensure_frontier_deadline(overall_deadline_at)
            model.commit_pending_response(run_id=run_id, task_id=task_id)
            continuity_states = getattr(model, "_persistent_continuity_states", {})
            continuity_state = continuity_states.get((run_id, task_id)) if isinstance(continuity_states, dict) else None
            state_findings = _secret_echo_findings(
                continuity_state, capture, path=f"$.continuity_state[{index}]",
            )
            if state_findings:
                secret_echo_findings.extend(state_findings)
                raise _CanaryCheckFailure("committed_continuity_contains_access_token")
            # The event is copied now because commit_pending_response emits a
            # separate continuity-admission record but leaves this attempt row immutable.
            events.append(current_row)
            if index == 0:
                stage = "synthetic_continuation"
        events = list(model.drain_telemetry())
        telemetry_drained = True
        if len(events) != 2:
            raise _CanaryCheckFailure("provider_attempt_count_mismatch")
        first, second = events
        first_call_id = str(first.get("native_tool_call_id") or "")
        first_response_id = str(first.get("response_id") or "")
        if (
            first.get("persistent_continuity_request_previous_response_id") is not None
            or not first_call_id
            or not first_response_id
            or second.get("persistent_continuity_request_previous_response_id") != first_response_id
            or second.get("persistent_continuity_request_function_call_output_count") != 1
            or second.get("persistent_continuity_request_function_call_output_call_ids") != [first_call_id]
            or second.get("persistent_continuity_expected_prior_call_id") != first_call_id
            or second.get("persistent_continuity_prior_call_id_match_count") != 1
            or second.get("persistent_continuity_request_input_item_types") != ["function_call_output"]
            or second.get("persistent_continuity_reanchor_attempted") is not False
        ):
            raise _CanaryCheckFailure("native_previous_response_continuity_mismatch")
        first_request = _request_evidence(first)
        second_request = _request_evidence(second)
        if (
            first_request["prompt_cache_key"] != second_request["prompt_cache_key"]
            or first_request["tool_names"] != second_request["tool_names"]
            or first_request["tool_schema_sha256"] != second_request["tool_schema_sha256"]
        ):
            raise _CanaryCheckFailure("stable_request_profile_changed_between_calls")
        for row, bound in zip(events, request_bounds):
            event_evidence.append(_frontier_event_evidence(row, input_upper_bound=bound))
        stage = "terminal_budget_check"
    except Exception as exc:  # sanitized receipt, no retry
        error = _safe_error(stage, exc)
    finally:
        if model is not None:
            if not telemetry_drained:
                try:
                    events = list(model.drain_telemetry())
                except Exception as exc:
                    if error is None:
                        error = _safe_error("telemetry_drain", exc)
            try:
                model.close_run_transport()
            except Exception as exc:
                if error is None:
                    error = _safe_error("transport_close", exc)
        if old_capture_request is None:
            os.environ.pop("AETHER_CAPTURE_RAW_PROVIDER_REQUEST", None)
        else:
            os.environ["AETHER_CAPTURE_RAW_PROVIDER_REQUEST"] = old_capture_request
        if old_capture_output is None:
            os.environ.pop("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT", None)
        else:
            os.environ["AETHER_CAPTURE_RAW_PROVIDER_OUTPUT"] = old_capture_output
        deadline_binding.__exit__(None, None, None)

    snapshot = budget_guard.snapshot()
    captured_tokens = _active_access_token_capture.get() or []
    safe_events: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        sanitized_event, findings = _sanitize_secret_values(
            event, captured_tokens, path=f"$.provider_attempts[{index}]",
        )
        safe_events.append(sanitized_event)
        secret_echo_findings.extend(findings)
    if secret_echo_findings:
        error = _safe_error(
            "provider_response",
            _CanaryCheckFailure("provider_response_contains_access_token"),
        )
    # Keep model-visible evidence intact on clean rows. For a contaminated row,
    # retain the same structure with token-bearing leaf values replaced by
    # hash-labelled markers, and list the exact field paths below.
    if secret_echo_findings:
        sanitized_turns, turn_findings = _sanitize_secret_values(
            turn_records, captured_tokens, path="$.model_visible_turns",
        )
        turn_records = sanitized_turns
        secret_echo_findings.extend(turn_findings)
    unique_secret_findings: list[dict[str, str]] = []
    observed_secret_findings: set[tuple[str, str, str]] = set()
    for finding in secret_echo_findings:
        key = (
            str(finding.get("path") or ""),
            str(finding.get("value_sha256") or ""),
            str(finding.get("token_sha256") or ""),
        )
        if key not in observed_secret_findings:
            observed_secret_findings.add(key)
            unique_secret_findings.append(finding)
    secret_echo_findings = unique_secret_findings
    evidence_events = safe_events if secret_echo_findings else events
    completed = [row for row in evidence_events if row.get("status") == "completed"]
    passed = bool(
        error is None
        and len(events) == 2
        and len(completed) == 2
        and int(snapshot.get("aggregate_create_count") or 0) == 2
        and int(dict(snapshot.get("role_create_counts") or {}).get("solver") or 0) == 2
        and all(
            int(dict(snapshot.get("role_create_counts") or {}).get(role) or 0) == 0
            for role in ("verifier", "vision")
        )
        and len(turn_records) == 2
        and len(event_evidence) == 2
        and not secret_echo_findings
        and _monotonic() < overall_deadline_at
    )
    finished = time.time()
    candidate = {
        "package_closure_sha256": closure.sha256 if closure is not None else None,
        "package_file_count": closure.file_count if closure is not None else None,
        **source_identity,
        "model_profile_sha256": profile.sha256(),
        "tool_schema_sha256": production_tool_schema_sha256(),
        "model_id": profile.model_id,
        "expected_returned_models": sorted(FRONTIER_EXPECTED_RETURNED_MODELS),
        "solver_reasoning_effort": profile.solver_reasoning_effort,
        "prompt_cache_mode": profile.prompt_cache_mode,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": passed,
        "label": label,
        "profile_selector": FRONTIER_RESEARCH_SELECTOR,
        "mode": FRONTIER_CANARY_SMOKE_MODE,
        "created_at_unix_s": started,
        "finished_at_unix_s": finished,
        "elapsed_s": round(finished - started, 6),
        "requested_width": 2,
        "completed_provider_calls": len(completed),
        "provider_create_count": int(snapshot.get("aggregate_create_count") or 0),
        "provider_terminal_response_count": sum(
            1 for row in evidence_events
            if row.get("provider_websocket_last_event_type") in {
                "response.completed", "response.failed", "response.incomplete", "error",
            }
        ),
        "python_executable": str(Path(sys.executable).resolve()),
        "package_root": str(package_root().resolve()),
        "candidate": candidate,
        "provider_route_sha256": route.get("route_identity_sha256"),
        "provider_route": route,
        "provider_runtime": runtime_identity,
        "provider_policy": {
            "responses_websocket": True,
            "responses_websocket_persistent": True,
            "responses_background": False,
            "provider_max_retries": 0,
            "sdk_max_retries": 0,
            "request_deadline_s": FRONTIER_REQUEST_DEADLINE_S,
            "overall_deadline_s": overall_deadline_s,
            "max_input_tokens": FRONTIER_MAX_INPUT_TOKENS,
            "max_output_tokens": FRONTIER_MAX_OUTPUT_TOKENS,
            "prompt_cache_mode": "stable_prefix",
            "cache_hit_claimed": False,
            "budget_constrained": True,
        },
        "pricing": {
            "reference": FRONTIER_PRICING_REFERENCE,
            "reference_verified_by": "orchestrator_live_catalog_preflight",
            "official_usd_per_million": {
                "short_input": 0.10,
                "cache_write": 0.125,
                "output": 0.50,
                "long_input": 0.20,
                "long_cache_write": 0.25,
                "long_output": 0.75,
            },
            "provider_budget_gbp_reservation_rates_per_million": {
                "input": "0.20",
                "output": "1.20",
            },
            "reservation_rates_are_conservative_ceilings_not_gpt6_list_prices": True,
        },
        "provider_budget": {
            **bounded_budget,
            "snapshot": snapshot,
        },
        "worker": {
            "passed": passed,
            "error": error,
            "provider_create_count": int(snapshot.get("aggregate_create_count") or 0),
            "provider_terminal_event_types": [
                row.get("provider_websocket_last_event_type") for row in evidence_events
            ],
            "transport_mode": completed[-1].get("provider_transport_mode") if completed else None,
            "native_tool_names": [row.get("native_tool_name") for row in completed],
            "native_tool_call_counts": [row.get("native_tool_call_count") for row in completed],
            "attempt_ordinals": [row.get("attempt_ordinal") for row in evidence_events],
            "returned_models": [row.get("returned_model") for row in evidence_events],
            "provider_terminal_failures": [row.get("provider_terminal_failure") for row in evidence_events],
        },
        "model_visible_turns": turn_records,
        "provider_attempt_telemetry": event_evidence,
        "provider_attempt_raw_evidence": safe_events,
        "provider_value_containment": {
            "token_bearing_provider_values_rejected": bool(secret_echo_findings),
            "rejected_field_count": len(secret_echo_findings),
            "rejected_fields": secret_echo_findings,
        },
        "raw_model_output_persisted": False,
        "raw_native_actions_persisted": bool(turn_records) and not secret_echo_findings,
        "credential_values_persisted": False,
        "access_token_values_persisted": False,
    }


def run_canary(
    *,
    label: str,
    profile_selector: str = PRODUCTION_SELECTOR,
    mode: str = "canary",
) -> dict[str, Any]:
    """Run the historical one-call canary or the explicitly selected Frontier smoke."""
    if profile_selector == PRODUCTION_SELECTOR and mode == "canary":
        return _run_production_canary(label=label)
    if profile_selector == FRONTIER_RESEARCH_SELECTOR and mode == FRONTIER_CANARY_SMOKE_MODE:
        capture = _active_access_token_capture.get()
        if capture is not None:
            return _run_frontier_canary_smoke(label=label)
        with _capture_access_tokens() as captured_tokens:
            receipt = _run_frontier_canary_smoke(label=label)
            serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            try:
                _assert_serialized_artifact_secret_free(serialized, captured_tokens)
            except _CanaryCheckFailure:
                receipt = _containment_failure_receipt(
                    receipt,
                    captured_tokens,
                    rejected_artifact_sha256=sha256(serialized.encode("utf-8")).hexdigest(),
                )
            return receipt
    raise RuntimeError("unsupported provider canary profile/mode combination")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--profile", choices=(PRODUCTION_SELECTOR, FRONTIER_RESEARCH_SELECTOR),
        default=PRODUCTION_SELECTOR,
    )
    parser.add_argument(
        "--mode", choices=("canary", FRONTIER_CANARY_SMOKE_MODE), default="canary",
    )
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with _capture_access_tokens() as captured_tokens:
        try:
            receipt = run_canary(label=args.label, profile_selector=args.profile, mode=args.mode)
        except Exception as exc:
            if args.profile != FRONTIER_RESEARCH_SELECTOR:
                raise
            try:
                label = _safe_label(args.label)
            except Exception:
                label = None
            receipt = {
                "schema_version": SCHEMA_VERSION,
                "passed": False,
                "label": label,
                "profile_selector": FRONTIER_RESEARCH_SELECTOR,
                "mode": args.mode,
                "requested_width": 2,
                "completed_provider_calls": 0,
                "provider_policy": {
                    "provider_max_retries": 0,
                    "sdk_max_retries": 0,
                    "request_deadline_s": FRONTIER_REQUEST_DEADLINE_S,
                    "overall_deadline_s": FRONTIER_OVERALL_DEADLINE_S,
                    "max_input_tokens": FRONTIER_MAX_INPUT_TOKENS,
                    "max_output_tokens": FRONTIER_MAX_OUTPUT_TOKENS,
                    "cache_hit_claimed": False,
                    "budget_constrained": True,
                },
                "worker": {
                    "passed": False,
                    "error": _safe_error("preflight", exc),
                },
                "provider_value_containment": {
                    "token_bearing_provider_values_rejected": False,
                    "rejected_field_count": 0,
                    "rejected_fields": [],
                },
                "credential_values_persisted": False,
                "access_token_values_persisted": False,
                "raw_model_output_persisted": False,
                "raw_native_actions_persisted": False,
            }

        serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        try:
            _assert_serialized_artifact_secret_free(serialized, captured_tokens)
        except _CanaryCheckFailure:
            receipt = _containment_failure_receipt(
                receipt,
                captured_tokens,
                rejected_artifact_sha256=sha256(serialized.encode("utf-8")).hexdigest(),
            )
            serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
            _assert_serialized_artifact_secret_free(serialized, captured_tokens)

        console_summary = {"passed": receipt["passed"], "output": str(output)}
        try:
            _assert_serialized_artifact_secret_free(
                json.dumps(console_summary, sort_keys=True), captured_tokens,
            )
        except _CanaryCheckFailure:
            console_summary = {
                "passed": receipt["passed"],
                "output": "<omitted by access-token containment>",
            }
        _assert_serialized_artifact_secret_free(
            json.dumps(console_summary, sort_keys=True), captured_tokens,
        )

        try:
            # This is the first artifact write. The entire serialized value was
            # checked above, including repr/bytes/JSON spellings of every token.
            output.write_text(serialized, encoding="utf-8")
        except Exception:
            return 2
        print(json.dumps(console_summary, sort_keys=True))
        return 0 if receipt["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
