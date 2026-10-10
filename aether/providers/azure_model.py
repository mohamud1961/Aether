"""Azure OpenAI model providers with strict structured-output boundaries.

This is the ONLY module allowed to ``import openai``.  It builds a
``ModelCallable`` that the kernel's ``ModelHooks`` layer can consume.

Solver and Architect retain the Responses background route.  Factory-created
Verifier calls use Chat Completions with one choice because the Verifier
protocol requires one authoritative envelope, while Responses exposes an
output array whose cardinality is provider-controlled.
"""
from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import inspect
import hashlib
import json
import math
import os
import random
import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse

from .responses_websocket import ResponsesWebSocketError, ResponsesWebSocketTransport
from ..provider_budget import (
    ProviderBudgetGuard, provider_budget_guard_from_env,
    serialized_request_token_upper_bound,
)

from .model_retry import (
    DEFAULT_BACKOFF_BASE_S,
    DEFAULT_BACKOFF_CAP_S,
    DEFAULT_BACKOFF_MAX_TOTAL_S,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_RPM,
    RateLimiter,
    _retry_call,
    get_rate_limiter_for_deployment,
)
from ..verifier_deadline import remaining_verifier_generation_s
from ..verifier_provider_projection import prune_unreachable_local_defs_for_provider
from ..verifier_budget import (
    PRODUCTION_VERIFIER_CALL_TIMEOUT_S,
    PRODUCTION_VERIFIER_TIMEOUT_RESERVE_S,
    PRODUCTION_VERIFIER_PHASE_BUDGET,
)
from ..request_anatomy import enabled as _anatomy_enabled
from ..request_anatomy import observe_request as _observe_request_anatomy
from ..run_cancellation import (
    RunCancellationRequested,
    cancellation_requested,
    raise_if_run_cancelled,
)
from ..run_deadline import KernelRunTimeout, raise_if_run_deadline_exceeded, remaining_run_s
from ..provider_frontier_recovery import (
    CONTROL as PROVIDER_FRONTIER_RECOVERY_CONTROL,
    NO_TOOL_MAX_OUTPUT_V1 as PROVIDER_FRONTIER_RECOVERY_NO_TOOL_MAX_OUTPUT_V1,
    ProviderFrontierReserveReached,
)
from ..persistent_reality_delta import DELTA_MODE as PERSISTENT_REALITY_DELTA_MODE
from ..persistent_reality_delta_state import (
    PreparedRealityTransport, RealityDeltaTransportState,
)
from ..persistent_hosted_tool_search import (
    CONTROL as PERSISTENT_HOSTED_TOOL_SEARCH_CONTROL,
    HOSTED_V1 as PERSISTENT_HOSTED_TOOL_SEARCH_V1,
    SUPPORTED_MODES as PERSISTENT_HOSTED_TOOL_SEARCH_MODES,
    HostedToolSearchError,
    HostedToolSearchObservation,
    HostedToolSearchState,
    catalogue_identity as hosted_tool_search_catalogue_identity,
    hosted_provider_tools,
    validate_hosted_response,
)
from ..verifier_activation_continuity import (
    FRESH_CONTROL as VERIFIER_ACTIVATION_FRESH_CONTROL,
    PREVIOUS_RESPONSE_V1 as VERIFIER_ACTIVATION_PREVIOUS_RESPONSE_V1,
    SUPPORTED_MODES as VERIFIER_ACTIVATION_CONTINUITY_MODES,
    PreparedVerifierActivationTransport,
    VerifierActivationContinuityState,
)


from ..verifier_recovery import EvidenceClass
from ..verifier_budget import DIRECT_OBSERVATION_KINDS, DERIVED_EXECUTION_KINDS
from ..completion_record import (
    COMPLETION_RECORD_OFF,
    COMPLETION_RECORD_V1,
    SUPPORTED_COMPLETION_RECORD_MODES,
)
from ..model_profile import (
    API_KEY_CREDENTIAL_MODE,
    SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE,
)
from ..persistent_provider_protocol import (
    PERSISTENT_DIRECT_PROVIDER_TOOLS,
    PERSISTENT_DIRECT_PROVIDER_TOOLS_COMMITMENT_V1,
    PERSISTENT_DIRECT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1,
    PERSISTENT_DIRECT_PROVIDER_TOOLS_COMMITMENT_AND_DISPOSITION_V1,
    PERSISTENT_PRIMARY_PROVIDER_SCHEMA,
    PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME,
    PERSISTENT_PRIMARY_TURN_RESPONSE_INSTRUCTION,
    PERSISTENT_PRIMARY_TURN_SCHEMA,
    PCRProviderProtocolError,
    canonicalize_persistent_direct_tool_call,
    canonicalize_persistent_primary_turn,
    persistent_primary_provider_schema,
    persistent_primary_turn_response_instruction,
)

try:
    import openai
except ModuleNotFoundError:  # pragma: no cover - provider construction requires dependency.
    openai = None  # type: ignore[assignment]


class AzureModelError(Exception):
    """Raised when the Azure Responses API returns an unrecoverable error."""


_PROVIDER_LIFECYCLE_JOURNAL_ENV = "AETHER_PROVIDER_LIFECYCLE_JOURNAL"
_PROVIDER_LIFECYCLE_LOCK = threading.Lock()


def _append_provider_lifecycle(
    *,
    stage: str,
    role: str,
    logical_call_id: int,
    attempt_ordinal: int,
    telemetry_scope: dict[str, str | None] | None,
    transport_mode: str,
    response_id: str | None = None,
    status: str | None = None,
    create_ordinal: int = 1,
) -> None:
    """Durably append bounded provider lifecycle evidence when launch custody enables it.

    No prompt, model output, endpoint, deployment, or credential value is written.
    A configured journal is strict: inability to persist a boundary event fails
    before proceeding so a paid run never silently loses the requested custody.
    """
    raw_path = str(os.environ.get(_PROVIDER_LIFECYCLE_JOURNAL_ENV, "") or "").strip()
    if not raw_path:
        return
    payload = {
        "schema_version": "aether.provider_lifecycle_event.v1",
        "event_kind": "provider_lifecycle",
        "stage": str(stage),
        "at_unix_s": time.time(),
        "at_monotonic_s": time.monotonic(),
        "role": str(role),
        "logical_call_id": int(logical_call_id),
        "attempt_ordinal": int(attempt_ordinal),
        "create_ordinal": int(create_ordinal),
        "run_id": str((telemetry_scope or {}).get("run_id") or ""),
        "task_id": str((telemetry_scope or {}).get("task_id") or ""),
        "transport_mode": str(transport_mode),
        "response_id": None if response_id is None else str(response_id),
        "status": None if status is None else str(status),
    }
    line = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    parent = os.path.dirname(os.path.abspath(raw_path))
    try:
        os.makedirs(parent, exist_ok=True)
        with _PROVIDER_LIFECYCLE_LOCK:
            fd = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)
    except Exception as exc:
        raise AzureModelError(f"provider lifecycle journal write failed: {type(exc).__name__}: {exc}") from exc


class AzureProviderOutputError(AzureModelError):
    """A provider response cannot safely authorise one structured model turn."""

    is_provider_output_error = True

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(self.code if not self.detail else f"{self.code}: {self.detail}")


# Background-job error codes (``job.error.code``, an openai
# ``ResponseError``) that represent a transient, Azure-side condition worth
# retrying. Every other code (invalid_prompt, image_*, vector_store_timeout,
# …) is a genuine request problem — retrying it just burns the retry budget
# on a call that will never succeed.
_RETRYABLE_JOB_ERROR_CODES = frozenset({"rate_limit_exceeded", "server_error"})

_JSON_OBJECT_RESPONSE_INSTRUCTION = (
    "Return exactly one valid JSON object. Do not include markdown fences, "
    "prose, or multiple candidate responses."
)

_PERSISTENT_PRIMARY_NATIVE_TOOL_RESPONSE_INSTRUCTION = (
    "Make exactly one provided native tool call for the single current causal PERSISTENT turn. "
    "The host executes or observes that turn before any future decision. Do not emit "
    "or plan future turns in this response."
)
_PERSISTENT_PRIMARY_NATIVE_TOOLS: tuple[dict[str, Any], ...] = PERSISTENT_DIRECT_PROVIDER_TOOLS
_PERSISTENT_PRIMARY_NATIVE_TOOLS_COMMITMENT_V1: tuple[dict[str, Any], ...] = PERSISTENT_DIRECT_PROVIDER_TOOLS_COMMITMENT_V1
_PERSISTENT_PRIMARY_NATIVE_TOOLS_COMPLETION_DISPOSITION_V1: tuple[dict[str, Any], ...] = PERSISTENT_DIRECT_PROVIDER_TOOLS_COMPLETION_DISPOSITION_V1
_PERSISTENT_PRIMARY_NATIVE_TOOLS_COMMITMENT_AND_DISPOSITION_V1: tuple[dict[str, Any], ...] = PERSISTENT_DIRECT_PROVIDER_TOOLS_COMMITMENT_AND_DISPOSITION_V1
_PERSISTENT_PRIMARY_NATIVE_TOOL_NAMES = frozenset(str(tool["name"]) for tool in _PERSISTENT_PRIMARY_NATIVE_TOOLS)

# The S5 baseline has one provider-native continuity treatment: the Solver
# carries the accepted previous response with all-turns reasoning continuity;
# the Verifier remains fresh. Alternate continuity experiments are not shipped.
_PERSISTENT_NATIVE_IMAGE_MEDIA_TYPES = frozenset({
    "image/png", "image/jpeg", "image/gif", "image/webp",
})

PERSISTENT_REALITY_TRANSPORT_CONTROL = "full_snapshot_control"
PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1 = "delta_only_v1"
PERSISTENT_REALITY_TRANSPORT_MODES = frozenset({
    PERSISTENT_REALITY_TRANSPORT_CONTROL, PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1,
})
_PERSISTENT_CONTEXT_PACKET_PREFIX = "[context_packet]\n"
_PERSISTENT_CONTEXT_DELTA_PREFIX = "[context_delta]\n"


def _persistent_continuity_scope_key(
    telemetry_scope: dict[str, str | None] | None,
) -> tuple[str, str]:
    if telemetry_scope is None:
        raise AzureModelError("persistent_native_continuity_requires_run_and_task_scope")
    run_id = str(telemetry_scope.get("run_id") or "").strip()
    task_id = str(telemetry_scope.get("task_id") or "").strip()
    if not run_id or not task_id:
        raise AzureModelError("persistent_native_continuity_requires_run_and_task_scope")
    return run_id, task_id






def _provider_output_item_census(response: Any) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in _usage_field(response, "output", ()) or ():
        item_type = str(_usage_field(item, "type", "") or "unknown")
        counts[item_type] = counts.get(item_type, 0) + 1
    return {
        "provider_output_item_count": sum(counts.values()),
        "provider_output_item_type_counts": dict(sorted(counts.items())),
        "provider_reasoning_item_count": counts.get("reasoning", 0),
        "provider_compaction_item_count": counts.get("compaction", 0),
        "provider_function_call_item_count": counts.get("function_call", 0),
    }

# The Verifier is a state machine: one provider turn is either an inspection
# request or a verdict.  Azure Structured Outputs forbids a root ``anyOf``,
# so the strict root is a required ``turn`` wrapper with a nested union.  The
# full V3 request shape is represented directly; no JSON-inside-a-string
# envelope is used on the production Verifier route.
def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    """Encode nullable fields in Azure's strict Structured Outputs subset."""
    return {"anyOf": [schema, {"type": "null"}]}


_NULLABLE_STRING = _nullable({"type": "string"})
_NULLABLE_INTEGER = _nullable({"type": "integer"})
_NULLABLE_STRING_ARRAY = _nullable({"type": "array", "items": {"type": "string"}})
_VERIFIER_EVIDENCE_CLASS_VALUES = tuple(item.value for item in EvidenceClass)


def _verifier_inspection_request_schema(
    kind_values: tuple[str, ...], *,
    allow_legacy_command: bool = True,
    allow_clause_ids: bool = True,
) -> dict[str, Any]:
    """One strict inspection request restricted to a single causal phase.

    V3 derived execution has exactly one executable-command authority:
    ``execution.command``.  Keeping the historical top-level ``command`` as a
    second writable surface lets a strict provider populate two conflicting
    commands, so derived provider turns mechanically force that legacy field
    to null while direct/legacy projections remain schema-compatible.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "request_id", "kind", "path", "handle", "check_id", "receipt_kind",
            "limit", "command", "content", "target", "offset", "span",
            "clause_ids", "proof_ids", "verification_plan", "execution",
        ],
        "properties": {
            "request_id": _NULLABLE_STRING,
            "kind": {"type": "string", "enum": list(kind_values)},
            "path": _NULLABLE_STRING,
            "handle": _NULLABLE_STRING,
            "check_id": _NULLABLE_STRING,
            "receipt_kind": _NULLABLE_STRING,
            "limit": _NULLABLE_INTEGER,
            "command": _NULLABLE_STRING if allow_legacy_command else {"type": "null"},
            "content": _NULLABLE_STRING,
            "target": _NULLABLE_STRING,
            "offset": _NULLABLE_INTEGER,
            "span": _NULLABLE_INTEGER,
            "clause_ids": _NULLABLE_STRING_ARRAY if allow_clause_ids else {"type": "null"},
            "proof_ids": _NULLABLE_STRING_ARRAY,
            "verification_plan": {"anyOf": [{"$ref": "#/$defs/verification_plan"}, {"type": "null"}]},
            "execution": {"anyOf": [{"$ref": "#/$defs/execution"}, {"type": "null"}]},
        },
    }


_VERIFIER_DIRECT_TURN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["turn"],
    "properties": {
        "turn": {
            "anyOf": [
                {"$ref": "#/$defs/direct_inspect_turn"},
                {"$ref": "#/$defs/derived_inspect_turn"},
                {"$ref": "#/$defs/verdict_turn"},
            ],
        },
    },
    "$defs": {
        "basis": {
            "type": "object",
            "additionalProperties": False,
            "required": ["ref", "supported_fact"],
            "properties": {"ref": _NULLABLE_STRING, "supported_fact": _NULLABLE_STRING},
        },
        "execution": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "command"],
            # ``execution`` is only non-null for the derived execution phase.
            # Keep the provider contract closed over the one executable route;
            # accepting arbitrary strings here lets Structured Outputs return
            # a syntactically valid object that the runtime must reject later.
            "properties": {
                "kind": _nullable({"type": "string", "enum": ["overlay_run_command"]}),
                "command": _NULLABLE_STRING,
            },
        },
        "verification_plan": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "claim", "evidence_mode", "clause_ids", "basis", "bound_input_refs",
                "authoritative_structure", "method_summary", "proxy_risk",
            ],
            "properties": {
                "claim": _NULLABLE_STRING,
                # These are the only evidence modes understood by the
                # Verifier protocol.  In particular, provider prose such as
                # ``independent_semantic`` must fail at schema validation,
                # before it can become a later parser/runtime failure.
                "evidence_mode": _nullable({"type": "string", "enum": ["direct", "derived"]}),
                "clause_ids": _NULLABLE_STRING_ARRAY,
                "basis": _nullable({"type": "array", "items": {"$ref": "#/$defs/basis"}}),
                "bound_input_refs": _NULLABLE_STRING_ARRAY,
                "authoritative_structure": _NULLABLE_STRING,
                "method_summary": _NULLABLE_STRING,
                "proxy_risk": _NULLABLE_STRING,
            },
        },
        # Keep an unused union alias for schema introspection/backward tooling.
        # Provider turns below reference phase-specific definitions, so a mixed
        # direct+derived request array cannot validate.
        "inspection_request": _verifier_inspection_request_schema(tuple(sorted(
            DIRECT_OBSERVATION_KINDS | DERIVED_EXECUTION_KINDS
        ))),
        "direct_inspection_request": _verifier_inspection_request_schema(tuple(sorted(DIRECT_OBSERVATION_KINDS))),
        "derived_inspection_request": _verifier_inspection_request_schema(
            tuple(sorted(DERIVED_EXECUTION_KINDS)), allow_legacy_command=False,
        ),
        "direct_inspect_turn": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "requests"],
            "properties": {
                "kind": {"type": "string", "enum": ["inspect"]},
                "requests": {
                    "type": "array", "minItems": 1, "maxItems": 12,
                    "items": {"$ref": "#/$defs/direct_inspection_request"},
                },
            },
        },
        "derived_inspect_turn": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "requests"],
            "properties": {
                "kind": {"type": "string", "enum": ["inspect"]},
                "requests": {
                    "type": "array", "minItems": 1, "maxItems": 12,
                    "items": {"$ref": "#/$defs/derived_inspection_request"},
                },
            },
        },
        "finding": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "finding_id", "verdict", "priority", "summary", "evidence",
                "repair_instruction", "applies_to", "keep_until", "owner",
                "supporting_inspection_ids", "repair_condition", "required_evidence_route",
            ],
            "properties": {
                "finding_id": _NULLABLE_STRING, "verdict": _NULLABLE_STRING,
                "priority": _NULLABLE_STRING, "summary": _NULLABLE_STRING,
                "evidence": {"type": "array", "items": {"type": "string"}},
                "repair_instruction": _NULLABLE_STRING,
                "applies_to": {"type": "array", "items": {"type": "string"}},
                "keep_until": _NULLABLE_STRING, "owner": _NULLABLE_STRING,
                "supporting_inspection_ids": {"type": "array", "items": {"type": "string"}},
                "repair_condition": _NULLABLE_STRING,
                "required_evidence_route": _NULLABLE_STRING,
            },
        },
        "completion_evidence": {
            "type": "object", "additionalProperties": False,
            "required": ["requirement", "observed", "falsification_check", "inspection_refs", "clause_ids", "proof_ids", "evidence_class", "risk_refs"],
            "properties": {
                "requirement": _NULLABLE_STRING, "observed": _NULLABLE_STRING,
                "falsification_check": _NULLABLE_STRING,
                "inspection_refs": {"type": "array", "items": {"type": "string"}},
                "clause_ids": {"type": "array", "items": {"type": "string"}},
                "proof_ids": {"type": "array", "items": {"type": "string"}},
                "evidence_class": {"type": "string", "enum": list(_VERIFIER_EVIDENCE_CLASS_VALUES)},
                "risk_refs": {"type": "array", "items": {"type": "string"}},
            },
        },
        "method_validity": {
            "type": "object", "additionalProperties": False,
            "required": ["observed_structure", "executed_rule", "method_alignment", "authoritative_source_refs", "execution_ref"],
            "properties": {
                "observed_structure": _NULLABLE_STRING, "executed_rule": _NULLABLE_STRING,
                "method_alignment": _NULLABLE_STRING,
                "authoritative_source_refs": {"type": "array", "items": {"type": "string"}},
                "execution_ref": _NULLABLE_STRING,
            },
        },
        "verdict_turn": {
            "type": "object", "additionalProperties": False,
            "required": ["verdict", "confidence", "summary", "findings", "missing_evidence_requests", "completion_evidence", "method_validity"],
            "properties": {
                "verdict": {"type": "string", "enum": [
                    "completed", "needs_repair", "uncertain_missing_evidence", "blocked_by_tooling",
                    "blocked_by_harness_config", "incomplete_state_wrong", "incomplete_missing_required_artifact",
                    "incomplete_semantic_mismatch", "insufficient_inspectable_evidence", "reviewer_tool_execution_failed",
                    "reviewer_capability_missing", "probe_inconclusive", "environment_blocked", "timeout_or_budget_blocked",
                ]},
                "confidence": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "null"}]},
                "summary": _NULLABLE_STRING,
                "findings": {"type": "array", "items": {"$ref": "#/$defs/finding"}},
                "missing_evidence_requests": {"type": "array", "items": {"type": "string"}},
                "completion_evidence": {"type": "array", "items": {"$ref": "#/$defs/completion_evidence"}},
                "method_validity": {"anyOf": [{"$ref": "#/$defs/method_validity"}, {"type": "null"}]},
            },
        },
    },
}

_VERIFIER_CHAT_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "aether_verifier_direct_turn",
        "strict": True,
        "schema": _VERIFIER_DIRECT_TURN_SCHEMA,
    },
}

def _persistent_verifier_direct_turn_schema() -> dict[str, Any]:
    """Return the PERSISTENT V0 Verifier schema aligned to its V3 runtime contract.

    PERSISTENT V0 mechanically compiles a raw-task-only TaskContract and therefore has
    no ``method_constraints``. ``inspect_action_receipts`` is explicitly
    method-only evidence in the inspection registry, so exposing it here gives
    the Verifier a route that cannot be clause-bound under PERSISTENT and can invite
    self-confirmation from Solver-authored execution history.

    The provider contract also mirrors the runtime's causal distinction between
    direct observations, simple derived operations, and ``overlay_run_command``.
    Azure Structured Outputs treats a required nullable field as satisfied by
    ``null``; the generic schema therefore allowed a derived plan such as
    ``basis=null`` to pass provider validation and then be deleted by
    ``_drop_null_fields`` before the V3 parser rejected it.  PERSISTENT closes that
    gap here: an overlay command must carry a non-null, non-empty V3 basis and
    bound-input set plus one non-null execution command.  The kernel still
    decides admissibility/freshness and the Verifier still authors the facts;
    Aether does not synthesize missing proof semantics.
    """
    schema = json.loads(json.dumps(_VERIFIER_DIRECT_TURN_SCHEMA))
    defs = schema["$defs"]

    # F94: only PERSISTENT's native provider contract asks the model to classify each
    # completion requirement. Generic/TRIAD schema remains the shared legacy
    # shape. Admission checks verdict/status coherence, not prose semantics.
    completion_evidence = defs["completion_evidence"]
    completion_evidence["properties"]["requirement_status"] = {
        "type": "string", "enum": ["satisfied", "violated", "unknown"],
    }
    # PERSISTENT repair findings declare the minimum evidence strength they rely on.
    # Runtime route identity remains kernel-owned; this field cannot mint a
    # stronger class than the cited inspection actually earned.
    defs["finding"]["properties"]["required_evidence_route"] = {
        "type": "string", "enum": list(_VERIFIER_EVIDENCE_CLASS_VALUES),
    }
    # PERSISTENT production makes the anti-laundering record shape structural: one evidence
    # record/finding may cite at most one inspection. Multiple observations for
    # one semantic requirement remain expressible as multiple records. Generic
    # and TRIAD schemas retain their legacy multi-ref compatibility.
    completion_evidence["properties"]["inspection_refs"]["maxItems"] = 1
    defs["finding"]["properties"]["supporting_inspection_ids"]["maxItems"] = 1
    completion_evidence["required"] = [
        *completion_evidence["required"], "requirement_status",
    ]

    direct_kinds = tuple(sorted(
        kind for kind in DIRECT_OBSERVATION_KINDS
        if kind not in {"inspect_action_receipts", "inspect_recent_receipts"}
    ))

    # F82 keeps F81's strict route law without cloning the full generic request
    # object once per direct kind. PERSISTENT native direct observations expose one
    # compact ``locator`` surface, then provider canonicalization maps it
    # one-to-one onto the existing runtime path/handle/target field. This keeps
    # impossible command-bearing direct turns out of the provider schema while
    # avoiding the 10-way full-object anyOf that amplified constrained-output
    # tails. Generic/TRIAD Verifier schemas remain unchanged.
    # F87 keeps the runtime direct-observation vocabulary intact while making
    # the provider-facing process route explicitly observational.  Frontier's F86
    # V5N/V6 traces repeatedly intended to run/execute a target yet selected
    # ``probe_process`` and wrote ``run_verifier_command`` into the irrelevant
    # ``receipt_kind`` field.  PERSISTENT therefore exposes a clearer provider alias
    # for that one ambiguous route and removes direct fields no surviving PERSISTENT
    # direct route consumes.  Canonicalization below restores runtime names.
    persistent_direct_locator_routes = {
        "read_file": ("read_file", "path"),
        "read_output": ("read_output", "handle"),
        "compare_initial_path": ("compare_initial_path", "path"),
        "inspect_artifact_history": ("inspect_artifact_history", "path"),
        "probe_port": ("probe_port", "target"),
        "probe_http": ("probe_http", "target"),
        "observe_existing_process": ("probe_process", "target"),
        "probe_job": ("probe_job", "target"),
        "inspect_artifact": ("inspect_artifact", "path"),
        "perceive_artifact": ("perceive_artifact", "path"),
    }
    if {runtime_kind for runtime_kind, _field in persistent_direct_locator_routes.values()} != set(direct_kinds):
        raise RuntimeError("PERSISTENT direct Verifier provider schema is out of sync with runtime direct kinds")

    persistent_direct_span = {
        "anyOf": [
            {"type": "integer", "minimum": 1, "maximum": 8_192},
            {"type": "null"},
        ],
    }
    shared_direct_properties: dict[str, Any] = {
        # F93: PERSISTENT provider transport identity is host-owned. The Verifier
        # parser deterministically assigns inspect-{n} when request_id is absent;
        # model-authored labels must never become inspection:* authority.
        # check_id and receipt_kind are not consumed by any PERSISTENT direct route.
        # Keeping them on every forced native call created a second misleading
        # place for the model to express route intent, so F87 removes them.
        "limit": _NULLABLE_INTEGER,
        "offset": _NULLABLE_INTEGER,
        "span": persistent_direct_span,
        "clause_ids": _NULLABLE_STRING_ARRAY,
        "proof_ids": _NULLABLE_STRING_ARRAY,
    }
    locator_direct_properties = {
        **shared_direct_properties,
        "kind": {"type": "string", "enum": sorted(persistent_direct_locator_routes)},
        "locator": {"type": "string", "pattern": r"\S"},
    }
    defs["persistent_direct_locator_request"] = {
        "type": "object",
        "additionalProperties": False,
        "required": list(locator_direct_properties),
        "properties": locator_direct_properties,
    }
    # PERSISTENT uncertain verdicts may request the exact next direct inspection in a
    # typed field. Free-text missing_evidence_requests remains explanation only
    # and is never routed to a tool by PERSISTENT production.
    # A provider-valid PERSISTENT inspection batch must be mechanically capable of
    # fitting inside the runtime aggregate result-envelope budget.  The generic
    # schema permits twelve requests, but PERSISTENT's current runtime allows at most
    # 65,536 aggregate result bytes with a 16,384-byte envelope ceiling per
    # result.  Therefore four is the largest cardinality for which *every*
    # individually legal result is also aggregate-legal.  This is transport
    # consistency only: Frontier still chooses what to inspect and may request
    # another batch on a later turn.
    max_persistent_inspections_by_envelope = max(
        1,
        PRODUCTION_VERIFIER_PHASE_BUDGET.max_result_bytes_per_batch
        // PRODUCTION_VERIFIER_PHASE_BUDGET.max_result_envelope_bytes_per_request,
    )
    max_persistent_inspections_per_turn = min(
        PRODUCTION_VERIFIER_PHASE_BUDGET.max_direct_requests_per_batch,
        max_persistent_inspections_by_envelope,
    )
    for inspect_turn_name in ("direct_inspect_turn", "derived_inspect_turn"):
        defs[inspect_turn_name]["properties"]["requests"]["maxItems"] = max_persistent_inspections_per_turn

    verdict_schema = defs["verdict_turn"]
    verdict_schema["properties"]["missing_inspection_requests"] = {
        "type": "array", "maxItems": max_persistent_inspections_per_turn,
        "items": {"$ref": "#/$defs/persistent_direct_locator_request"},
    }
    verdict_schema["required"] = [
        *verdict_schema["required"], "missing_inspection_requests",
    ]
    # F91: exact historical-support snapshots already cited by the bound
    # Primary submission get a separate provider branch. The live schema binds
    # locator to an exact kernel-authored receipt-handle enum; this static shape
    # only declares the vocabulary. It is intentionally separate from ordinary
    # read_output so arbitrary receipt IDs cannot ride an open handle field.
    cited_receipt_properties: dict[str, Any] = {
        # F93 shares the host-owned request identity rule with every compact
        # PERSISTENT direct route. Only immutable receipt locator/paging semantics are
        # model-authored here.
        "kind": {"type": "string", "enum": ["read_cited_receipt"]},
        "locator": {"type": "string", "pattern": r"^receipt:\S+"},
        "offset": _NULLABLE_INTEGER,
        "span": json.loads(json.dumps(persistent_direct_span)),
        "clause_ids": _NULLABLE_STRING_ARRAY,
        "proof_ids": _NULLABLE_STRING_ARRAY,
    }
    defs["persistent_cited_receipt_request"] = {
        "type": "object",
        "additionalProperties": False,
        "required": list(cited_receipt_properties),
        "properties": cited_receipt_properties,
    }
    # PERSISTENT's PERSISTENT Verifier does not expose ledger-only recent-receipt browsing.
    # That route is metadata_proxy evidence, cannot independently establish
    # current task state, and can consume the bounded investigation budget
    # without advancing falsification. Generic/TRIAD schemas and kernel-owned
    # fallback inspection support remain unchanged.
    defs["direct_inspection_request"] = {
        "anyOf": [
            {"$ref": "#/$defs/persistent_direct_locator_request"},
            {"$ref": "#/$defs/persistent_cited_receipt_request"},
        ],
    }

    defs["persistent_derived_basis"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref", "supported_fact"],
        "properties": {
            # V3 basis is verifier-observed evidence only. Solver submission
            # receipt handles are visible provenance but are not eligible
            # direct-inspection identities.
            "ref": {"type": "string", "pattern": r"^inspection:"},
            "supported_fact": {"type": "string", "pattern": r"\S"},
        },
    }
    defs["persistent_derived_execution"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "command"],
        "properties": {
            "kind": {"type": "string", "enum": ["overlay_run_command"]},
            "command": {"type": "string"},
        },
    }
    defs["persistent_derived_verification_plan"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "claim", "evidence_mode", "clause_ids", "basis",
            "bound_input_refs", "authoritative_structure", "method_summary",
            "proxy_risk",
        ],
        "properties": {
            "claim": {"type": "string"},
            "evidence_mode": {"type": "string", "enum": ["derived"]},
            "clause_ids": {
                "type": "array", "minItems": 1,
                "items": {"type": "string"},
            },
            "basis": {
                "type": "array", "minItems": 1,
                "items": {"$ref": "#/$defs/persistent_derived_basis"},
            },
            "bound_input_refs": {
                "type": "array", "minItems": 1,
                # Direct observations and verifier-authored fixture receipts
                # are both registered under inspection:* IDs. Never bind a
                # derived execution directly to Solver receipt handles.
                "items": {"type": "string", "pattern": r"^inspection:"},
            },
            "authoritative_structure": {"type": "string"},
            "method_summary": {"type": "string"},
            "proxy_risk": {"type": "string"},
        },
    }

    # The two simple derived operations have different non-null runtime keys.
    # Keep those requirements provider-visible so a schema-valid turn cannot
    # become a guaranteed executor failure after nullable fields are dropped.
    rerun = _verifier_inspection_request_schema(
        ("rerun_check",), allow_legacy_command=False,
    )
    rerun["properties"]["check_id"] = {"type": "string", "pattern": r"\S"}
    # F93: keep the generic rerun object shape but force provider request_id to
    # null so the runtime parser assigns a deterministic host-owned ID.
    rerun["properties"]["request_id"] = {"type": "null"}
    rerun["properties"]["verification_plan"] = {"type": "null"}
    rerun["properties"]["execution"] = {"type": "null"}
    defs["persistent_rerun_check_request"] = rerun

    # F89: PERSISTENT's provider-facing derived command is the minimal causal
    # execution contract. The model authors only executable content, exact
    # proof-clause identity, and exact prior evidence/input refs. Semantic
    # method judgment belongs to the post-execution method_validity verdict
    # record, not duplicated pre-execution prose. Generic/TRIAD V3 is unchanged.
    command = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "kind", "command", "clause_ids", "basis_refs", "bound_input_refs",
        ],
        "properties": {
            "kind": {"type": "string", "enum": ["run_verifier_command"]},
            "command": {"type": "string", "pattern": r"\S"},
            "clause_ids": {
                "type": "array", "minItems": 1,
                "items": {"type": "string", "pattern": r"\S"},
            },
            "basis_refs": {
                "type": "array", "minItems": 1,
                "items": {"type": "string", "pattern": r"^inspection:"},
            },
            "bound_input_refs": {
                "type": "array", "minItems": 1,
                "items": {"type": "string", "pattern": r"^inspection:"},
            },
        },
    }
    defs["persistent_run_verifier_command_request"] = command
    # The nested PERSISTENT-only V3 provider definitions are now dead representation.
    # Runtime V3 remains unchanged after provider canonicalization.
    for obsolete in (
        "persistent_derived_basis", "persistent_derived_verification_plan", "persistent_derived_execution",
    ):
        defs.pop(obsolete, None)
    # F88 PERSISTENT keeps exactly one model-authored derived execution frontier:
    # run_verifier_command.  Standalone verifier fixtures remain available to
    # the generic/TRIAD Verifier runtime, but PERSISTENT does not expose a separate
    # stateful fixture turn. Synthetic setup can be part of one disposable
    # run_verifier_command after authoritative inputs have been observed.
    defs["derived_inspection_request"] = {
        "anyOf": [
            {"$ref": "#/$defs/persistent_rerun_check_request"},
            {"$ref": "#/$defs/persistent_run_verifier_command_request"},
        ],
    }
    return schema


_PERSISTENT_VERIFIER_DIRECT_TURN_SCHEMA: dict[str, Any] = _persistent_verifier_direct_turn_schema()


_VERIFIER_DIRECT_TURN_RESPONSE_INSTRUCTION = (
    "Return exactly one strict JSON object with the sole key turn. turn must be "
    "exactly one Verifier protocol state: either one inspect request object or "
    "one verdict object. Never emit an inspect request and a verdict together."
)

_VERIFIER_NATIVE_TOOL_NAME = "verifier_turn"
_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION = (
    "Call the verifier_turn function exactly once with only the single current "
    "Verifier turn. The turn must be one homogeneous direct-inspection batch, "
    "one homogeneous derived-inspection batch, or one verdict. For derived "
    "overlay_run_command requests, executable content belongs only in "
    "execution.command; the legacy top-level command field is unavailable. "
    "Do not emit a second turn, assistant prose, or any other executable call."
)
_PERSISTENT_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION = (
    "Call the verifier_turn function exactly once with only the single current "
    "Verifier turn. Use only direct route kinds listed in "
    "verifier_packet.verifier_runtime_capabilities.available_direct_observation_kinds; "
    "a route omitted there is unavailable in this executor. Route availability does not "
    "grant permission to inspect every path: PERSISTENT still limits direct workspace inspection "
    "to Solver-observed or Solver-produced paths. Direct locator semantics: read_file=path; probe_http=full http(s) URL; "
    "probe_port=port or host:port; observe_existing_process=actual command-line regex; "
    "probe_job=registered job/name. Live probes execute from inside the current task/executor environment, "
    "not an external client namespace. For a service hosted by the current task machine, use a locally "
    "resolvable endpoint such as localhost/127.0.0.1 when a client-facing hostname is not resolvable there; "
    "a DNS-resolution failure in the probe namespace does not prove the service is absent. "
    "inspect_artifact reports artifact metadata/presence; for directories it does not establish directory "
    "contents or semantic configuration, so use read_file on the relevant task-public config/hook file when "
    "exact contents matter. Never use observe_existing_process for files, ports, or HTTP. "
    "If an uncertain verdict needs another direct observation, put the exact kind+locator request in "
    "missing_inspection_requests; missing_evidence_requests is explanation only and is not executed. "
    "For final evidence, use at most one inspection ref in each completion_evidence entry or repair finding. "
    "If several observations support one requirement, emit separate entries/findings; each record's declared "
    "evidence class must not exceed the kernel-reported actual_evidence_class of its single cited inspection. "
    "Use run_verifier_command only after observing its authoritative "
    "inputs. For that route emit exactly the required fields kind, command, "
    "clause_ids, basis_refs, and bound_input_refs; clause_ids must use only exact "
    "task-contract IDs offered by the tool schema; do not emit optional metadata, "
    "padding, or transport prose. basis_refs/bound_input_refs must use only exact "
    "inspection:* IDs allowed by the tool schema. read_cited_receipt reads only an "
    "exact immutable historical-support receipt snapshot already cited by the Primary submission; use only "
    "the exact receipt handle offered by the schema. If a check needs synthetic input, "
    "create it inside the same disposable run_verifier_command. Do not rewrite "
    "authoritative task inputs before checking them. Semantic method justification "
    "belongs in the final method_validity verdict record after observing execution. "
    "Do not emit runtime-internal verification_plan/execution wrappers, a second "
    "turn, or assistant prose."
)
_VERIFIER_NATIVE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": _VERIFIER_NATIVE_TOOL_NAME,
    "description": (
        "Return exactly one current Verifier protocol turn; the host preserves "
        "the existing Verifier parser, phase budgets, evidence rules, and execution."
    ),
    "parameters": _VERIFIER_DIRECT_TURN_SCHEMA,
    "strict": True,
}
_PERSISTENT_VERIFIER_NATIVE_TOOL: dict[str, Any] = {
    **_VERIFIER_NATIVE_TOOL,
    "parameters": _PERSISTENT_VERIFIER_DIRECT_TURN_SCHEMA,
}


def _persistent_verifier_outcome_clause_ids_from_input(
    user_input: str | list[dict[str, str]],
) -> tuple[str, ...]:
    """Extract the exact compiler-owned PERSISTENT task-clause namespace.

    PERSISTENT exposes task_contract.clauses in the Verifier packet. The provider
    adapter mirrors only those exact non-empty unique clause_id values into
    the native tool schema; it never derives IDs from task prose or prior
    model output. Conflicting packet copies fail closed.
    """
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if not isinstance(item, dict) or str(item.get("role") or "") != "user":
                continue
            texts.append(str(item.get("content") or ""))
    observed: tuple[str, ...] | None = None
    for text in texts:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        packet = payload.get("verifier_packet")
        if not isinstance(packet, dict):
            continue
        contract = packet.get("task_contract")
        if not isinstance(contract, dict) or "clauses" not in contract:
            continue
        clauses = contract.get("clauses")
        if not isinstance(clauses, list):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_clause_namespace_invalid",
                "task_contract.clauses must be a list",
            )
        ids: list[str] = []
        seen: set[str] = set()
        for row in clauses:
            if not isinstance(row, dict):
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_clause_namespace_invalid",
                    "task clause must be an object",
                )
            clause_id = str(row.get("clause_id") or "").strip()
            if not clause_id:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_clause_namespace_invalid",
                    "task clause id must be non-empty",
                )
            if clause_id in seen:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_clause_namespace_invalid",
                    f"duplicate task clause id {clause_id}",
                )
            seen.add(clause_id)
            ids.append(clause_id)
        current = tuple(ids)
        if observed is not None and current != observed:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_clause_namespace_conflict",
                json.dumps({"first": list(observed), "later": list(current)}, sort_keys=True),
            )
        observed = current
    return observed or ()


def _persistent_verifier_authoritative_check_ids_from_input(
    user_input: str | list[dict[str, str]],
) -> tuple[str, ...]:
    """Extract the exact kernel-authored PERSISTENT check namespace from model input.

    The namespace must come from verifier_packet.authoritative_check_ids. This
    adapter never derives IDs from task text, file names, receipts, or prior
    model output. Conflicting or malformed packet copies fail closed.
    """
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if not isinstance(item, dict) or str(item.get("role") or "") != "user":
                continue
            texts.append(str(item.get("content") or ""))
    observed: tuple[str, ...] | None = None
    for text in texts:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        packet = payload.get("verifier_packet")
        if not isinstance(packet, dict) or "authoritative_check_ids" not in packet:
            continue
        raw = packet.get("authoritative_check_ids")
        if not isinstance(raw, list):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_check_namespace_invalid", "expected list",
            )
        ids: list[str] = []
        seen: set[str] = set()
        for value in raw:
            if not isinstance(value, str) or not value.strip():
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_check_namespace_invalid", "check id must be non-empty string",
                )
            check_id = value.strip()
            if check_id in seen:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_check_namespace_invalid", "duplicate check id",
                )
            seen.add(check_id)
            ids.append(check_id)
        current = tuple(ids)
        if observed is not None and current != observed:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_check_namespace_conflict",
                json.dumps({"first": list(observed), "later": list(current)}, sort_keys=True),
            )
        observed = current
    return observed or ()



def _persistent_verifier_output_handles_from_input(
    user_input: str | list[dict[str, str]],
) -> tuple[bool, tuple[str, ...]]:
    """Return the exact kernel-advertised output-handle namespace.

    This is provider affordance binding only.  The handles are already present
    in the kernel-owned Verifier packet; binding them into an enum prevents a
    low-reasoning Verifier turn from inventing labels such as ``stdout`` while
    preserving the existing runtime ``read_output`` route and its behavioral
    evidence ceiling.  The namespace must remain identical throughout one
    immutable verification activation.
    """
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if not isinstance(item, dict) or str(item.get("role") or "") != "user":
                continue
            texts.append(str(item.get("content") or ""))
    observed: tuple[str, ...] | None = None
    for text in texts:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        packet = payload.get("verifier_packet")
        if not isinstance(packet, dict) or "state_inspection_handles" not in packet:
            continue
        rows = packet.get("state_inspection_handles")
        if not isinstance(rows, list):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_output_namespace_invalid",
                "state_inspection_handles must be a list",
            )
        handles: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or str(row.get("kind") or "") != "output":
                continue
            handle = str(row.get("handle") or "").strip()
            if not handle:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_output_namespace_invalid",
                    "output inspection handle must be non-empty",
                )
            if handle.startswith("receipt:"):
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_output_namespace_invalid",
                    "ordinary output namespace may not contain receipt handles",
                )
            if handle in seen:
                continue
            seen.add(handle)
            handles.append(handle)
        current = tuple(handles)
        if observed is not None and current != observed:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_output_namespace_conflict",
                json.dumps({"first": list(observed), "later": list(current)}, sort_keys=True),
            )
        observed = current
    return (observed is not None, observed or ())


def _persistent_verifier_cited_receipt_handles_from_input(
    user_input: str | list[dict[str, str]],
) -> tuple[str, ...]:
    """Extract exact successful cited-read receipt handles from the PERSISTENT packet.

    This is a capability namespace, not evidence admission. The provider only
    mirrors handles already emitted by the kernel-owned PERSISTENT Verifier packet;
    the runtime independently revalidates the latest Primary claim and source
    receipt before returning any snapshot bytes.
    """
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if not isinstance(item, dict) or str(item.get("role") or "") != "user":
                continue
            texts.append(str(item.get("content") or ""))
    observed: tuple[str, ...] | None = None
    for text in texts:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        packet = payload.get("verifier_packet")
        if not isinstance(packet, dict):
            continue
        primary = packet.get("primary_submission")
        if not isinstance(primary, dict) or "cited_evidence_index" not in primary:
            continue
        rows = primary.get("cited_evidence_index")
        if not isinstance(rows, list):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_cited_receipt_namespace_invalid",
                "cited_evidence_index must be a list",
            )
        handles: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_cited_receipt_namespace_invalid",
                    "cited evidence row must be an object",
                )
            # The exact-content route is intentionally narrower than generic
            # cited evidence: only successful immutable read_file observations
            # whose projected receipt proves a captured cryptographic content
            # identity. Large/paged reads can be valid Solver evidence while
            # still lacking replayable snapshot bytes; do not advertise an
            # exact historical-read capability the runtime must reject.
            if str(row.get("kind") or "").strip() != "read_file" or row.get("success") is not True:
                continue
            projection = row.get("current_payload_projection", {})
            content_hash = (
                str(projection.get("content_hash") or "").strip().lower()
                if isinstance(projection, dict) else ""
            )
            if not content_hash or any(ch not in "0123456789abcdef" for ch in content_hash):
                continue
            receipt_id = str(row.get("receipt_id") or "").strip()
            handle = str(row.get("exact_receipt_handle") or "").strip()
            role = str(row.get("evidence_role") or "").strip()
            if not receipt_id or handle != f"receipt:{receipt_id}":
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_cited_receipt_namespace_invalid",
                    "exact receipt handle does not match receipt_id",
                )
            # F90 exists to recover immutable *historical* source bytes for a
            # fresh comparison. Current anchors must be re-observed from live
            # state rather than replayed from the Primary Agent's own receipt.
            if role == "current_anchor":
                continue
            if role != "historical_support":
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_cited_receipt_namespace_invalid",
                    f"unsupported evidence role for {receipt_id}",
                )
            try:
                receipt_generation = int(row.get("receipt_task_state_generation"))
                submission_generation = int(row.get("submission_task_state_generation"))
            except (TypeError, ValueError):
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_cited_receipt_namespace_invalid",
                    f"invalid task-state generation binding for {receipt_id}",
                ) from None
            if receipt_generation >= submission_generation:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_cited_receipt_namespace_invalid",
                    f"inconsistent historical generation binding for {receipt_id}",
                )
            # F91: exact receipt replay is exclusively for historical-support
            # snapshots. A current-anchor citation identifies submission-time
            # evidence but is not current-state authority after the submission;
            # current reality must be re-observed through live direct routes.
            if role == "current_anchor":
                continue
            if handle in seen:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_cited_receipt_namespace_invalid",
                    f"duplicate exact receipt handle {handle}",
                )
            seen.add(handle)
            handles.append(handle)
        current = tuple(handles)
        if observed is not None and current != observed:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_cited_receipt_namespace_conflict",
                json.dumps({"first": list(observed), "later": list(current)}, sort_keys=True),
            )
        observed = current
    return observed or ()


def _persistent_verifier_completed_cited_receipt_handles_from_input(
    user_input: str | list[dict[str, str]],
    *,
    eligible_handles: tuple[str, ...],
) -> tuple[str, ...]:
    """Return only exact cited snapshots fully observed by the runtime this round.

    Completion authority comes exclusively from host-authored user messages that
    carry ``verifier_inspection_results``. Assistant/model output is never read
    here. Malformed rows cannot hide a capability; they simply do not qualify as
    a completed observation.
    """
    eligible = set(eligible_handles)
    if not eligible:
        return ()
    completed: set[str] = set()
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if not isinstance(item, dict) or str(item.get("role") or "") != "user":
                continue
            texts.append(str(item.get("content") or ""))
    for text in texts:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        rows = payload.get("verifier_inspection_results")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or str(row.get("kind") or "") != "read_cited_receipt":
                continue
            handle = str(row.get("handle") or "").strip()
            if handle not in eligible:
                continue
            try:
                total_chars = int(row.get("total_chars"))
                offset = int(row.get("offset"))
                returned_chars = int(row.get("returned_chars"))
                next_offset = int(row.get("next_offset"))
            except (TypeError, ValueError):
                continue
            excerpt = row.get("excerpt")
            if (
                row.get("snapshot_verified") is True
                and row.get("observation_valid") is True
                and not str(row.get("error") or "").strip()
                and row.get("snapshot_complete") is True
                and row.get("more_available") is False
                and total_chars >= 0
                and offset == 0
                and returned_chars == total_chars
                and next_offset == total_chars
                and isinstance(excerpt, str)
                and len(excerpt) == returned_chars
            ):
                completed.add(handle)
    return tuple(handle for handle in eligible_handles if handle in completed)


def _persistent_verifier_prior_inspection_namespaces_from_input(
    user_input: str | list[dict[str, str]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Read exact runtime-owned prior-inspection namespaces from the transcript.

    ``available_authoritative_source_refs`` and ``available_bound_input_refs``
    are emitted by the Verifier runtime after inspection execution.  The
    provider does not infer refs from request IDs, task text, filenames,
    Solver receipts, or model output.  Only ``inspection:*`` IDs are projected
    into the PERSISTENT native-tool schema; task:prompt remains runtime authority but
    is not a legal V3 derived-execution input ref.
    """
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if not isinstance(item, dict) or str(item.get("role") or "") != "user":
                continue
            texts.append(str(item.get("content") or ""))

    latest_authoritative: tuple[str, ...] = ()
    latest_bound: tuple[str, ...] = ()
    saw_authoritative = False
    saw_bound = False

    def _parse_namespace(payload: dict[str, Any], field: str) -> tuple[str, ...] | None:
        if field not in payload:
            return None
        raw = payload.get(field)
        if not isinstance(raw, list):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_inspection_namespace_invalid",
                f"{field} must be a list",
            )
        seen: set[str] = set()
        rows: list[str] = []
        for value in raw:
            if not isinstance(value, str) or not value.strip():
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_inspection_namespace_invalid",
                    f"{field} entries must be non-empty strings",
                )
            ref = value.strip()
            if ref in seen:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_inspection_namespace_invalid",
                    f"{field} contains duplicate ref {ref}",
                )
            seen.add(ref)
            if ref.startswith("inspection:"):
                rows.append(ref)
        return tuple(rows)

    for raw_text in texts:
        try:
            payload = json.loads(raw_text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        authoritative = _parse_namespace(payload, "available_authoritative_source_refs")
        if authoritative is not None:
            if saw_authoritative and not set(latest_authoritative).issubset(set(authoritative)):
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_inspection_namespace_conflict",
                    "authoritative inspection namespace regressed",
                )
            latest_authoritative = authoritative
            saw_authoritative = True
        bound = _parse_namespace(payload, "available_bound_input_refs")
        if bound is not None:
            if saw_bound and not set(latest_bound).issubset(set(bound)):
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_inspection_namespace_conflict",
                    "bound-input inspection namespace regressed",
                )
            latest_bound = bound
            saw_bound = True

    if saw_authoritative and saw_bound and not set(latest_authoritative).issubset(set(latest_bound)):
        raise AzureProviderOutputError(
            "provider_persistent_verifier_inspection_namespace_conflict",
            "authoritative refs are not contained in bound-input refs",
        )
    # Runtime invariant: every admissible proof observation is also a causal
    # input.  If no explicit bound namespace has appeared yet, fail closed by
    # exposing no overlay command rather than guessing that relation here.
    if saw_authoritative and not saw_bound:
        return latest_authoritative, ()
    return latest_authoritative, latest_bound


def _persistent_verifier_verdict_execution_refs_from_input(
    user_input: str | list[dict[str, str]],
) -> tuple[bool, tuple[str, ...]]:
    """Return the latest runtime-owned verdict-eligible derived namespace.

    The field is emitted only by the Verifier runtime after executing an
    inspection batch. The provider never infers derived authority from model
    prose or request IDs. Within one immutable verification activation the
    namespace may grow but must never regress.
    """
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if isinstance(item, dict) and str(item.get("role") or "") == "user":
                texts.append(str(item.get("content") or ""))
    saw = False
    latest: tuple[str, ...] = ()
    for text in texts:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or "verdict_eligible_execution_refs" not in payload:
            continue
        raw = payload.get("verdict_eligible_execution_refs")
        if not isinstance(raw, list):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_execution_namespace_invalid",
                "verdict_eligible_execution_refs must be a list",
            )
        seen: set[str] = set()
        rows: list[str] = []
        for value in raw:
            if not isinstance(value, str) or not value.strip():
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_execution_namespace_invalid",
                    "verdict_eligible_execution_refs entries must be non-empty strings",
                )
            ref = value.strip()
            if not ref.startswith("inspection:") or ref in seen:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_execution_namespace_invalid",
                    f"invalid or duplicate verdict execution ref {ref!r}",
                )
            seen.add(ref)
            rows.append(ref)
        current = tuple(rows)
        if saw and not set(latest).issubset(set(current)):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_execution_namespace_conflict",
                "verdict-eligible execution namespace regressed",
            )
        latest = current
        saw = True
    return saw, latest


def _persistent_verifier_turn_constraint_from_input(
    user_input: str | list[dict[str, str]],
) -> str:
    """Return the latest runtime-owned Verifier turn constraint.

    The completion runtime emits this top-level field only after executing an
    inspection batch. Unknown values fail closed rather than silently widening
    the provider schema. Ordinary verifier packets have no constraint and retain
    the normal inspect-or-verdict surface.
    """
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if not isinstance(item, dict) or str(item.get("role") or "") != "user":
                continue
            texts.append(str(item.get("content") or ""))
    constraint = "inspect_or_verdict"
    for text in texts:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or "verifier_turn_constraint" not in payload:
            continue
        raw = str(payload.get("verifier_turn_constraint") or "").strip()
        if raw not in {"inspect_or_verdict", "verdict_only"}:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_turn_constraint_invalid",
                f"unsupported verifier_turn_constraint={raw!r}",
            )
        constraint = raw
    return constraint


def _persistent_verifier_runtime_direct_routes_from_input(
    user_input: str | list[dict[str, str]],
) -> tuple[bool, frozenset[str]]:
    """Read the kernel-owned live direct-route capability namespace.

    The namespace is optional for legacy/unit packet fixtures.  Production
    PERSISTENT activations include it in ``verifier_packet`` so the native provider
    surface cannot advertise an executor method that is absent in this run.
    Availability is deliberately independent from the PERSISTENT path permission
    boundary enforced after a route is selected.
    """
    texts: list[str] = []
    if isinstance(user_input, str):
        texts.append(user_input)
    else:
        for item in user_input:
            if not isinstance(item, dict) or str(item.get("role") or "") != "user":
                continue
            texts.append(str(item.get("content") or ""))

    observed: frozenset[str] | None = None
    for text in texts:
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        packet = payload.get("verifier_packet")
        if not isinstance(packet, dict) or "verifier_runtime_capabilities" not in packet:
            continue
        capabilities = packet.get("verifier_runtime_capabilities")
        if not isinstance(capabilities, dict):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_capabilities_invalid",
                "verifier_runtime_capabilities must be an object",
            )
        raw_available = capabilities.get("available_direct_observation_kinds")
        if not isinstance(raw_available, list):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_capabilities_invalid",
                "available_direct_observation_kinds must be a list",
            )
        available: set[str] = set()
        for value in raw_available:
            if not isinstance(value, str) or not value.strip():
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_capabilities_invalid",
                    "available direct route names must be non-empty strings",
                )
            route = value.strip()
            if route not in DIRECT_OBSERVATION_KINDS:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_capabilities_invalid",
                    f"unknown direct route {route}",
                )
            if route in available:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_capabilities_invalid",
                    f"duplicate direct route {route}",
                )
            available.add(route)
        raw_unavailable = capabilities.get("unavailable_direct_observation_kinds", {})
        if not isinstance(raw_unavailable, dict):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_capabilities_invalid",
                "unavailable_direct_observation_kinds must be an object",
            )
        for raw_route, detail in raw_unavailable.items():
            route = str(raw_route).strip()
            if route not in DIRECT_OBSERVATION_KINDS:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_capabilities_invalid",
                    f"unknown unavailable direct route {route}",
                )
            if route in available:
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_capabilities_invalid",
                    f"direct route is both available and unavailable: {route}",
                )
            if not isinstance(detail, str) or not detail.strip():
                raise AzureProviderOutputError(
                    "provider_persistent_verifier_capabilities_invalid",
                    f"unavailable direct route lacks a reason: {route}",
                )
        current = frozenset(available)
        if observed is not None and current != observed:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_capabilities_conflict",
                json.dumps({
                    "first": sorted(observed), "later": sorted(current),
                }, sort_keys=True),
            )
        observed = current
    return (observed is not None, observed or frozenset())


def _filter_persistent_direct_route_schema(
    definitions: dict[str, Any], available_runtime_kinds: frozenset[str],
) -> None:
    """Restrict compact PERSISTENT locator kinds to live executable routes."""
    definition = definitions.get("persistent_direct_locator_request")
    if not isinstance(definition, dict):
        raise AzureProviderOutputError(
            "provider_persistent_verifier_capabilities_invalid",
            "PERSISTENT direct locator definition is missing",
        )
    properties = definition.get("properties")
    kind_schema = properties.get("kind") if isinstance(properties, dict) else None
    if not isinstance(kind_schema, dict):
        raise AzureProviderOutputError(
            "provider_persistent_verifier_capabilities_invalid",
            "PERSISTENT direct locator kind schema is missing",
        )
    allowed_provider_kinds = sorted(
        provider_kind
        for provider_kind, (runtime_kind, _field) in _PERSISTENT_VERIFIER_DIRECT_LOCATOR_ROUTE.items()
        if runtime_kind in available_runtime_kinds
    )
    kind_schema["enum"] = allowed_provider_kinds
    # ``read_cited_receipt`` is a provider-only alias over the ledger-owned
    # read_output route.  Remove its separate direct branch when that runtime
    # substrate is unavailable, even if stale cited handles remain in a packet.
    if "read_output" not in available_runtime_kinds:
        direct = definitions.get("direct_inspection_request")
        if isinstance(direct, dict) and isinstance(direct.get("anyOf"), list):
            direct["anyOf"] = [
                arm for arm in direct["anyOf"]
                if arm.get("$ref") != "#/$defs/persistent_cited_receipt_request"
            ]


def _persistent_verifier_native_tool_for_input(
    user_input: str | list[dict[str, str]],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Bind rerun_check to the exact authoritative check IDs in this packet.

    Empty namespace means the route is absent. Non-empty namespace becomes a
    strict enum. No runtime/verdict semantics are changed by this projection.
    """
    turn_constraint = _persistent_verifier_turn_constraint_from_input(user_input)
    check_ids = _persistent_verifier_authoritative_check_ids_from_input(user_input)
    outcome_clause_ids = _persistent_verifier_outcome_clause_ids_from_input(user_input)
    output_namespace_present, output_handles = _persistent_verifier_output_handles_from_input(user_input)
    cited_receipt_handles = _persistent_verifier_cited_receipt_handles_from_input(user_input)
    completed_cited_receipt_handles = _persistent_verifier_completed_cited_receipt_handles_from_input(
        user_input, eligible_handles=cited_receipt_handles,
    )
    completed_cited_receipt_set = set(completed_cited_receipt_handles)
    cited_receipt_handles = tuple(
        handle for handle in cited_receipt_handles if handle not in completed_cited_receipt_set
    )
    basis_refs, bound_input_refs = _persistent_verifier_prior_inspection_namespaces_from_input(user_input)
    execution_namespace_present, verdict_execution_refs = (
        _persistent_verifier_verdict_execution_refs_from_input(user_input)
    )
    schema = json.loads(json.dumps(_PERSISTENT_VERIFIER_DIRECT_TURN_SCHEMA))
    defs = schema["$defs"]
    capabilities_present, available_runtime_kinds = (
        _persistent_verifier_runtime_direct_routes_from_input(user_input)
    )
    if capabilities_present:
        _filter_persistent_direct_route_schema(defs, available_runtime_kinds)

    # Factual output handles are already kernel-advertised in the Verifier
    # packet.  Never leave PERSISTENT read_output as an open free-text locator: bind
    # it to those exact handles through a provider-only alias, while preserving
    # the existing runtime route/evidence semantics after canonicalization.
    direct_locator = defs.get("persistent_direct_locator_request")
    if not isinstance(direct_locator, dict):
        raise AzureProviderOutputError(
            "provider_persistent_verifier_output_namespace_invalid",
            "PERSISTENT direct locator definition is missing",
        )
    direct_props = direct_locator.get("properties")
    kind_schema = direct_props.get("kind") if isinstance(direct_props, dict) else None
    if not isinstance(kind_schema, dict) or not isinstance(kind_schema.get("enum"), list):
        raise AzureProviderOutputError(
            "provider_persistent_verifier_output_namespace_invalid",
            "PERSISTENT direct locator kind enum is missing",
        )
    # Legacy/unit packets that omit the namespace entirely retain the prior
    # open read_output compatibility surface. Production PERSISTENT packets always
    # publish state_inspection_handles, so an explicitly empty namespace means
    # there is no concrete output target to offer.
    if output_namespace_present:
        kind_schema["enum"] = [kind for kind in kind_schema["enum"] if kind != "read_output"]
    output_route_available = (
        output_namespace_present
        and (not capabilities_present or "read_output" in available_runtime_kinds)
        and bool(output_handles)
    )
    if output_route_available:
        bound_output = json.loads(json.dumps(direct_locator))
        bound_props = bound_output["properties"]
        bound_props["kind"] = {"type": "string", "enum": ["read_recorded_output"]}
        bound_props["locator"] = {"type": "string", "enum": list(output_handles)}
        defs["persistent_bound_output_request"] = bound_output
    else:
        defs.pop("persistent_bound_output_request", None)

    if execution_namespace_present:
        if verdict_execution_refs:
            defs["method_validity"]["properties"]["execution_ref"] = {
                "type": "string", "enum": list(verdict_execution_refs),
            }
        else:
            # Direct-only evidence cannot legally support a method_validity
            # execution_ref. Force null instead of letting constrained
            # generation create a record the runtime must reject and repair.
            defs["verdict_turn"]["properties"]["method_validity"] = {"type": "null"}
    if outcome_clause_ids:
        clause_item = {"type": "string", "enum": list(outcome_clause_ids)}
        nullable_clause_array = _nullable({"type": "array", "items": clause_item})
        for name in (
            "persistent_direct_locator_request", "persistent_cited_receipt_request",
            "persistent_rerun_check_request", "persistent_bound_output_request",
        ):
            definition = defs.get(name)
            if isinstance(definition, dict):
                properties = definition.get("properties")
                if isinstance(properties, dict) and "clause_ids" in properties:
                    properties["clause_ids"] = json.loads(json.dumps(nullable_clause_array))
        command_definition = defs.get("persistent_run_verifier_command_request")
        if isinstance(command_definition, dict):
            command_definition["properties"]["clause_ids"] = {
                "type": "array", "minItems": 1, "items": clause_item,
            }
        completion_definition = defs.get("completion_evidence")
        if isinstance(completion_definition, dict):
            completion_definition["properties"]["clause_ids"] = {
                "type": "array", "items": clause_item,
            }
    # Legacy/unit packet fixtures may omit task_contract entirely. Preserve the
    # prior open string schema in that compatibility case. Production PERSISTENT
    # packets expose exact task_contract.clauses, so live clause-bound turns are
    # dynamically enum-restricted above.
    direct = defs["direct_inspection_request"]
    direct_arms = list(direct.get("anyOf", ()))
    cited_ref = "#/$defs/persistent_cited_receipt_request"
    if cited_receipt_handles:
        defs["persistent_cited_receipt_request"]["properties"]["locator"] = {
            "type": "string", "enum": list(cited_receipt_handles),
        }
        direct["anyOf"] = direct_arms
    else:
        direct_arms = [arm for arm in direct_arms if arm.get("$ref") != cited_ref]
        defs.pop("persistent_cited_receipt_request", None)
        if direct_arms != [{"$ref": "#/$defs/persistent_direct_locator_request"}]:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_direct_namespace_invalid",
                "inactive cited-receipt route did not collapse to the canonical direct locator",
            )
        # Preserve F89's exact effective provider shape whenever F90 is inactive.
        # This avoids a semantically-empty one-arm anyOf changing Azure's
        # constrained-generation surface for every unrelated Verifier turn.
        defs["direct_inspection_request"] = {
            "$ref": "#/$defs/persistent_direct_locator_request",
        }

    if output_route_available:
        direct_definition = defs["direct_inspection_request"]
        output_ref = {"$ref": "#/$defs/persistent_bound_output_request"}
        if isinstance(direct_definition, dict) and isinstance(direct_definition.get("anyOf"), list):
            direct_definition["anyOf"].append(output_ref)
        else:
            defs["direct_inspection_request"] = {
                "anyOf": [json.loads(json.dumps(direct_definition)), output_ref],
            }
    # Uncertain-verdict follow-up requests get the same ordinary direct
    # locators plus the bound-output alias, but do not gain the separately
    # governed cited-receipt route.
    if output_route_available:
        defs["verdict_turn"]["properties"]["missing_inspection_requests"]["items"] = {
            "anyOf": [
                {"$ref": "#/$defs/persistent_direct_locator_request"},
                {"$ref": "#/$defs/persistent_bound_output_request"},
            ]
        }
    derived = defs["derived_inspection_request"]
    arms = list(derived.get("anyOf", ()))
    rerun_ref = "#/$defs/persistent_rerun_check_request"
    command_ref = "#/$defs/persistent_run_verifier_command_request"
    if check_ids:
        defs["persistent_rerun_check_request"]["properties"]["check_id"] = {
            "type": "string", "enum": list(check_ids),
        }
    else:
        arms = [arm for arm in arms if arm.get("$ref") != rerun_ref]
        defs.pop("persistent_rerun_check_request", None)

    if basis_refs and bound_input_refs:
        defs["persistent_run_verifier_command_request"]["properties"]["basis_refs"]["items"] = {
            "type": "string", "enum": list(basis_refs),
        }
        defs["persistent_run_verifier_command_request"]["properties"]["bound_input_refs"]["items"] = {
            "type": "string", "enum": list(bound_input_refs),
        }
    else:
        # A V3 derived command requires at least one prior authoritative
        # observation and exact causal input binding. If either namespace is
        # absent, the provider must not offer the compact command alias.
        arms = [arm for arm in arms if arm.get("$ref") != command_ref]
        defs.pop("persistent_run_verifier_command_request", None)

    if arms:
        derived["anyOf"] = arms
    else:
        # JSON Schema anyOf cannot be empty. More importantly, with no exact
        # check namespace and no prior direct-admissible evidence there is no
        # legal PERSISTENT derived operation. Remove the derived turn itself instead
        # of exposing a dead provider choice that can consume verification
        # budget before causal evidence exists.
        defs.pop("derived_inspection_request", None)
        defs.pop("derived_inspect_turn", None)
        root_arms = schema["properties"]["turn"]["anyOf"]
        schema["properties"]["turn"]["anyOf"] = [
            arm for arm in root_arms
            if arm.get("$ref") != "#/$defs/derived_inspect_turn"
        ]
    if turn_constraint == "verdict_only":
        # The phase budget has exactly one model call left. Constrained
        # generation must not offer an inspection that the runtime cannot
        # execute and later judge.
        schema["properties"]["turn"]["anyOf"] = [
            {"$ref": "#/$defs/verdict_turn"},
        ]
    return {**_PERSISTENT_VERIFIER_NATIVE_TOOL, "parameters": schema}, check_ids

# Retained only for bounded Responses diagnostics while that route is blocked
# for production Verifier work.  Its string payload is deliberately not used
# by the Chat Completions production turn contract above.
_VERIFIER_ENVELOPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["payload_json"],
    "properties": {"payload_json": {"type": "string"}},
}
_VERIFIER_ENVELOPE_FORMAT: dict[str, Any] = {
    "format": {
        "type": "json_schema",
        "name": "aether_verifier_legacy_envelope",
        "strict": True,
        "schema": _VERIFIER_ENVELOPE_SCHEMA,
    },
}
_VERIFIER_ENVELOPE_RESPONSE_INSTRUCTION = (
    "Return exactly one strict provider envelope JSON object with the sole key "
    "payload_json. payload_json must encode exactly one Verifier protocol JSON object."
)


class _JobStatusFailure(Exception):
    """Internal marker: a background job reached a terminal failure status.

    Carries the job's ``error.code`` (e.g. ``"rate_limit_exceeded"``, per
    the ``ResponseError`` shape observed in the 15-agent batch rate-limit
    storm) so :func:`is_retryable_azure_error` can classify it without
    re-parsing the formatted error string. Raised only as the ``__cause__``
    of an :class:`AzureModelError` — never surfaced directly.
    """

    def __init__(self, code: str | None) -> None:
        super().__init__(code or "unknown")
        self.code = code


def is_retryable_azure_error(exc: BaseException) -> bool:
    """Classify an exception from a single Azure model-call attempt as transient.

    Transient (worth retrying): HTTP 429 (rate limit) or 5xx from the SDK,
    an SDK-level connection/timeout error, or a background job that ended
    with a retryable ``error.code`` (``rate_limit_exceeded`` /
    ``server_error``).

    Non-transient (must raise immediately): auth failures, bad requests,
    content filter rejections, and any other 4xx or unrecognized job error
    code. These will never succeed no matter how many times they're retried,
    so retrying them would only waste the retry budget and delay a real
    failure signal.

    Looks at ``exc.__cause__`` first because both HTTP-layer failures
    (``responses.create``/``responses.retrieve`` wrap the raw openai/httpx
    exception via ``raise AzureModelError(...) from exc``) and job-status
    failures (wrapped via ``from _JobStatusFailure(code)``) preserve the
    original signal there; falls back to *exc* itself for anything raised
    without a cause.
    """
    cause = exc.__cause__ if exc.__cause__ is not None else exc

    if isinstance(cause, _JobStatusFailure):
        return cause.code in _RETRYABLE_JOB_ERROR_CODES

    # A WebSocket retry is safe only after the provider itself emitted a
    # terminal failed/error event for this response. Ambiguous connection
    # loss after dispatch is deliberately non-retryable because replay could
    # duplicate one model decision.
    if isinstance(cause, ResponsesWebSocketError):
        return bool(cause.terminal and cause.retry_safe)

    status_code = getattr(cause, "status_code", None)
    if isinstance(status_code, int):
        return status_code == 429 or 500 <= status_code < 600

    # SDK connection/timeout errors carry no HTTP status at all but are
    # transient by nature (openai.APITimeoutError subclasses this too).
    if openai is not None and isinstance(cause, openai.APIConnectionError):
        return True

    return False


def _azure_http_error_code(exc: BaseException) -> tuple[int | None, str]:
    """Return bounded HTTP status/provider error code without parsing prose."""
    status = getattr(exc, "status_code", None)
    status_code = status if isinstance(status, int) else None
    body = getattr(exc, "body", None)
    code = ""
    if isinstance(body, dict):
        nested = body.get("error")
        if isinstance(nested, dict):
            code = str(nested.get("code") or "")
        if not code:
            code = str(body.get("code") or "")
    if not code:
        code = str(getattr(exc, "code", "") or "")
    return status_code, code


def _is_previous_response_not_found_error(exc: BaseException) -> bool:
    """Exact recoverable Responses continuity loss, never a generic 400 retry."""
    status, code = _azure_http_error_code(exc)
    return status == 400 and code == "previous_response_not_found"


def _normalize_endpoint(raw: str) -> str:
    """Strip a full Azure endpoint URL down to ``scheme://host``.

    The env var may be ``https://host/openai/responses?api-version=...``;
    the working call uses ``{host}/openai/v1/``.
    """
    value = raw.strip()
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return value.rstrip("/")


def _verifier_poll_timeout_s(default_timeout_s: float) -> float:
    """Keep the provider poll deadline inside the enclosing verifier deadline."""
    return max(
        30.0,
        min(
            float(default_timeout_s),
            PRODUCTION_VERIFIER_CALL_TIMEOUT_S - PRODUCTION_VERIFIER_TIMEOUT_RESERVE_S,
        ),
    )


def _responses_background_enabled() -> bool:
    """Return the explicit Responses execution mode for one callable.

    Background jobs are the historical default, but a provider route can be
    diagnosed in foreground mode without changing the model, prompt, parser,
    or Verifier contract.  Rejecting misspellings prevents a silent transport
    change in a certified run.
    """
    raw = os.environ.get("AETHER_RESPONSES_BACKGROUND", "1").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise AzureModelError(
        "AETHER_RESPONSES_BACKGROUND must be one of 1/0, true/false, yes/no, on/off"
    )


def _remaining_verifier_poll_timeout_s(
    configured_timeout_s: float, *, minimum_reserve_s: float = 0.0,
) -> float:
    """Cap one provider turn to the remaining verifier-generation budget."""
    remaining = remaining_verifier_generation_s()
    if remaining is None:
        return configured_timeout_s
    reserve = max(PRODUCTION_VERIFIER_TIMEOUT_RESERVE_S, minimum_reserve_s)
    available = remaining - max(0.0, reserve)
    if available <= 0:
        raise AzureModelError("verifier generation budget exhausted before provider call")
    return min(configured_timeout_s, available)


def _prompt_cache_mode_from_env() -> str:
    """Return the supported cache-key mode for the Azure Responses route.

    Azure enables prompt caching provider-side.  This route additionally sends
    a stable cache key by default so requests sharing an immutable
    ``instructions`` prefix are more likely to stay cache-affine.  Operators
    can disable only that routing hint with ``AETHER_PROMPT_CACHE_MODE=off``.
    Extended retention is deliberately not exposed here: the active mini
    deployment is safe only with the normal in-memory retention path.
    """
    mode = os.environ.get("AETHER_PROMPT_CACHE_MODE", "stable_prefix").strip().lower()
    if mode not in {"stable_prefix", "off"}:
        raise AzureModelError(
            "AETHER_PROMPT_CACHE_MODE must be 'stable_prefix' or 'off'"
        )
    return mode


def _prompt_cache_namespace_from_env() -> str:
    """Return the bounded, operator-controlled cache affinity namespace.

    This namespace is deliberately independent of task material.  It scopes
    cache routing by an operator-selected protocol generation, while the
    provider itself still decides whether the immutable leading prompt tokens
    match and are cacheable.  It is not evidence of a cache hit.
    """
    namespace = os.environ.get("AETHER_PROMPT_CACHE_NAMESPACE", "aether-next-v1").strip()
    if not namespace or len(namespace) > 128:
        raise AzureModelError(
            "AETHER_PROMPT_CACHE_NAMESPACE must be non-empty and at most 128 characters"
        )
    return namespace


def _stable_prompt_cache_key(*, deployment: str, role: str, namespace: str) -> str:
    """Build an opaque task-independent cache-routing shard.

    The key contains only deployment, fixed role, and an operator namespace.
    It never includes task prompt, EnvMap, architecture/config summaries,
    receipts, or dynamic Responses input.  This avoids needless per-task key
    partitioning without claiming cross-task prefix/cache reuse.
    """
    material = "\x00".join((deployment, role, namespace)).encode("utf-8")
    # Responses prompt_cache_key is capped at 64 characters.  The fixed
    # namespace prefix plus 48 hex chars remains deterministic and leaves
    # ample collision resistance for a routing shard.
    return "aether-next-" + hashlib.sha256(material).hexdigest()[:48]


def _usage_field(value: Any, name: str, default: Any = None) -> Any:
    """Read *name* from either an SDK object or a dict-shaped test payload."""
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _usage_telemetry(response: Any) -> dict[str, Any]:
    """Extract provider-reported usage without turning absence into zero.

    A missing usage object or cached-token field is *unmeasured*, not a cache
    miss.  This distinction is essential for later cost/result analysis.
    """
    usage = _usage_field(response, "usage")
    if usage is None:
        return {
            "usage_status": "omitted",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "cache_write_tokens": None,
            "reasoning_tokens": None,
        }
    input_details = _usage_field(usage, "input_tokens_details")
    if input_details is None:
        input_details = _usage_field(usage, "prompt_tokens_details", {}) or {}
    output_details = _usage_field(usage, "output_tokens_details", {}) or {}
    missing = object()
    cached = _usage_field(input_details, "cached_tokens", missing)
    cache_write = _usage_field(input_details, "cache_write_tokens", missing)
    input_tokens = _usage_field(usage, "input_tokens")
    if input_tokens is None:
        input_tokens = _usage_field(usage, "prompt_tokens")
    output_tokens = _usage_field(usage, "output_tokens")
    if output_tokens is None:
        output_tokens = _usage_field(usage, "completion_tokens")
    return {
        "usage_status": "reported",
        "cache_metrics_status": (
            "reported" if cached is not missing or cache_write is not missing else "unmeasured"
        ),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": _usage_field(usage, "total_tokens"),
        "cached_input_tokens": None if cached is missing else cached,
        "cache_write_tokens": None if cache_write is missing else cache_write,
        "reasoning_tokens": _usage_field(output_details, "reasoning_tokens"),
    }


def _split_messages(messages: list[dict[str, str]]) -> tuple[str, str]:
    """Return (instructions, input_text) for the Responses API.

    Guarantees *input_text* is non-empty whenever there is any message
    content, because the Responses API requires a non-empty ``input``.

    Mapping rules:

    * ``role:system`` messages → ``instructions`` (joined with blank lines).
    * All other roles → ``input`` (joined with blank lines).
    * If ``input`` is empty but system messages exist, the **last** system
      message is promoted to ``input`` and the earlier ones stay in
      ``instructions``.  (In the solver flow the appended solver prompt is
      last — this keeps it as the actual ask while the prefix sections
      become standing context.)
    * A single system message with no other content goes entirely into
      ``input`` with a minimal generic instruction.
    * An empty *messages* list returns a safe fallback so the API never
      receives an empty ``input``.
    """
    system_parts: list[str] = []
    input_parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        else:
            input_parts.append(content)

    instructions = "\n\n".join(system_parts)
    input_text = "\n\n".join(input_parts)

    if input_text:
        # Happy path: non-system messages produced input.
        return instructions or "You are a helpful assistant.", input_text

    if len(system_parts) > 1:
        # All-system case (the solver bug): promote the last system message
        # to input; the rest remain as instructions.
        return "\n\n".join(system_parts[:-1]), system_parts[-1]

    if len(system_parts) == 1:
        # Exactly one system message and nothing else.
        return "You are a helpful assistant.", system_parts[0]

    # No messages at all — return safe minimal values.
    return "You are a helpful assistant.", "Proceed."


def _split_responses_input(
    messages: list[dict[str, str]],
) -> tuple[str, str | list[dict[str, str]]]:
    """Split messages while preserving non-system roles for Responses input.

    ``_split_messages`` remains available for legacy callers and pure string
    tests. Live Responses calls must retain the distinction between a prior
    assistant turn and the user observation that follows it; flattening both
    into one string makes a bounded verifier repair round ambiguous to the
    model.
    """
    system_parts: list[str] = []
    input_messages: list[dict[str, str]] = []
    allowed_roles = {"user", "assistant", "developer"}
    for msg in messages:
        role = str(msg.get("role", "user") or "user")
        content = str(msg.get("content", "") or "")
        if role == "system":
            system_parts.append(content)
            continue
        if role not in allowed_roles:
            role = "user"
        input_messages.append({"role": role, "content": content})

    instructions = "\n\n".join(system_parts)
    if input_messages:
        return instructions or "You are a helpful assistant.", input_messages
    if len(system_parts) > 1:
        return "\n\n".join(system_parts[:-1]), [{
            "role": "user",
            "content": system_parts[-1],
        }]
    if len(system_parts) == 1:
        return "You are a helpful assistant.", [{
            "role": "user",
            "content": system_parts[0],
        }]
    return "You are a helpful assistant.", [{
        "role": "user",
        "content": "Proceed.",
    }]


def _responses_input_text(input_payload: str | list[dict[str, str]]) -> str:
    """Canonical text form used only for telemetry sizes and hashes."""
    if isinstance(input_payload, str):
        return input_payload
    return json.dumps(input_payload, sort_keys=True, separators=(",", ":"))


def _persistent_function_call_output_value(
    current_boundary: str,
    native_image: dict[str, Any] | None,
) -> str | list[dict[str, Any]]:
    """Render the provider-supported function output for one causal observation.

    Text-only requests preserve the exact historical wire shape. A staged image
    adds exact pixels beside the unchanged textual Aether boundary.
    """
    if native_image is None:
        return current_boundary
    raw = native_image.get("image_bytes")
    if not isinstance(raw, bytes):
        raise AzureModelError("persistent_native_image_staging_bytes_missing")
    media_type = str(native_image.get("media_type") or "")
    encoded = base64.b64encode(raw).decode("ascii")
    return [
        {"type": "input_text", "text": current_boundary},
        {
            "type": "input_image",
            "image_url": f"data:{media_type};base64,{encoded}",
        },
    ]


def _function_call_output_sha256(output: Any) -> str:
    if isinstance(output, str):
        material = output
    else:
        material = json.dumps(
            output, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _function_call_output_boundary_text(output: Any) -> str:
    if isinstance(output, str):
        return output
    if not isinstance(output, list):
        return ""
    rows = [
        str(item.get("text") or "")
        for item in output
        if isinstance(item, dict) and str(item.get("type") or "") == "input_text"
    ]
    return rows[0] if len(rows) == 1 else ""




















def _strict_structured_json(text: str) -> tuple[str, str]:
    """Return canonical JSON plus the exact accepted body.

    Exactly one top-level object is accepted.  One optional enclosing JSON
    fence is permitted; leading/trailing prose, arrays, comments, or a second
    object are rejected by the ordinary strict JSON decoder.
    """
    raw = str(text or "").strip()
    if not raw:
        raise AzureProviderOutputError("provider_empty_assistant_message")
    body = raw
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) < 3 or lines[0].strip().lower() not in {"```", "```json"} or lines[-1].strip() != "```":
            raise AzureProviderOutputError("provider_invalid_json_fence")
        body = "\n".join(lines[1:-1]).strip()
        if "```" in body:
            raise AzureProviderOutputError("provider_nested_json_fence")
    def reject_constant(value: str) -> None:
        raise AzureProviderOutputError(
            "provider_structured_output_nonstandard_json_constant", value,
        )

    try:
        parsed = json.loads(body, parse_constant=reject_constant)
    except AzureProviderOutputError:
        raise
    except json.JSONDecodeError as exc:
        raise AzureProviderOutputError(
            "provider_structured_output_invalid_json",
            f"line={exc.lineno} column={exc.colno} {exc.msg}",
        ) from exc
    if not isinstance(parsed, dict):
        raise AzureProviderOutputError(
            "provider_structured_output_not_object",
            type(parsed).__name__,
        )
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return canonical, body


def _provider_json_object_sequence(text: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse every complete provider-envelope JSON object in *text*.

    Chat Completions occasionally returns equivalent envelope objects
    concatenated in one assistant message.  The transport boundary may
    collapse that duplication only after parsing the complete sequence.  A
    malformed, non-object, duplicate-key, or non-standard value remains
    provider-invalid; this helper never selects a prefix or silently drops
    trailing content.
    """
    raw = str(text or "").strip()
    if not raw:
        raise AzureProviderOutputError("provider_envelope_empty")

    def reject_constant(value: str) -> None:
        raise AzureProviderOutputError(
            "provider_envelope_nonstandard_json_constant", value,
        )

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AzureProviderOutputError(
                    "provider_envelope_duplicate_key", str(key),
                )
            result[key] = value
        return result

    decoder = json.JSONDecoder(
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    values: list[tuple[str, dict[str, Any]]] = []
    cursor = 0
    while cursor < len(raw):
        while cursor < len(raw) and raw[cursor].isspace():
            cursor += 1
        if cursor >= len(raw):
            break
        start = cursor
        try:
            value, cursor = decoder.raw_decode(raw, cursor)
        except AzureProviderOutputError:
            raise
        except json.JSONDecodeError as exc:
            raise AzureProviderOutputError(
                "provider_envelope_invalid_json", str(exc),
            ) from exc
        if not isinstance(value, dict):
            raise AzureProviderOutputError("provider_envelope_top_level_not_object")
        values.append((raw[start:cursor], value))

    if not values:
        raise AzureProviderOutputError("provider_envelope_empty")
    return values


def _raw_assistant_messages(response: Any) -> tuple[tuple[dict[str, Any], ...], bool]:
    """Extract assistant message items without consulting response.output_text.

    The boolean reports a mixed executable/tool-call item.  Provider reasoning
    items are harmless metadata and are ignored, while any function/computer
    call mixed with text makes the response ambiguous and fail-closed.
    """
    rows: list[dict[str, Any]] = []
    mixed_call = False
    for index, item in enumerate(_usage_field(response, "output", ()) or ()):
        item_type = str(_usage_field(item, "type", "") or "")
        role = str(_usage_field(item, "role", "") or "")
        if item_type.endswith("_call") or item_type in {
            "function_call", "computer_call", "custom_tool_call",
        }:
            mixed_call = True
        if item_type != "message" or role != "assistant":
            continue
        parts: list[str] = []
        for chunk in _usage_field(item, "content", ()) or ():
            piece = _usage_field(chunk, "text")
            if piece is None:
                piece = _usage_field(chunk, "output_text")
            if piece:
                parts.append(str(piece))
        message = "".join(parts)
        if not message:
            continue
        rows.append({
            "index": index,
            "item_id": str(_usage_field(item, "id", "") or ""),
            "item_type": item_type,
            "text": message,
            "text_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
            "text_bytes": len(message.encode("utf-8")),
        })
    return tuple(rows), mixed_call


def _raw_output_items_for_evidence(response: Any) -> list[dict[str, Any]]:
    """Capture raw output items only for an explicitly enabled diagnostic.

    Normal role telemetry stores hashes and metadata.  The bounded provider
    canary has no workspace/user payload and opts in so an API-envelope defect
    can be audited without another paid task-level run.
    """
    items: list[dict[str, Any]] = []
    for index, item in enumerate(_usage_field(response, "output", ()) or ()):
        content: list[dict[str, Any]] = []
        for chunk in _usage_field(item, "content", ()) or ():
            text = _usage_field(chunk, "text")
            if text is None:
                text = _usage_field(chunk, "output_text")
            content.append({
                "type": str(_usage_field(chunk, "type", "") or ""),
                "text": str(text or ""),
            })
        encrypted_content = _usage_field(item, "encrypted_content")
        encrypted_text = (
            str(encrypted_content)
            if encrypted_content not in (None, "") else ""
        )
        arguments = str(_usage_field(item, "arguments", "") or "")
        items.append({
            "index": index,
            "id": str(_usage_field(item, "id", "") or ""),
            "type": str(_usage_field(item, "type", "") or ""),
            "role": str(_usage_field(item, "role", "") or ""),
            "name": str(_usage_field(item, "name", "") or ""),
            "call_id": str(_usage_field(item, "call_id", "") or ""),
            "arguments": arguments,
            "arguments_sha256": (
                hashlib.sha256(arguments.encode("utf-8")).hexdigest()
                if arguments else ""
            ),
            "arguments_bytes": len(arguments.encode("utf-8")),
            # Opaque reasoning/compaction content remains opaque. Retain only
            # size/hash evidence so continuity and compaction boundaries are
            # auditable without persisting the encrypted payload itself.
            "encrypted_content_sha256": (
                hashlib.sha256(encrypted_text.encode("utf-8")).hexdigest()
                if encrypted_text else ""
            ),
            "encrypted_content_bytes": len(encrypted_text.encode("utf-8")),
            "content": content,
        })
    return items




def _unwrap_solver_provider_turn(text: str) -> tuple[str, dict[str, Any]]:
    """Decode one provider Solver turn under Aether's sole PERSISTENT contract."""
    try:
        return canonicalize_persistent_primary_turn(text)
    except PCRProviderProtocolError as exc:
        raise AzureProviderOutputError(exc.code, exc.detail) from exc




def _provider_computer_action_dict(raw: Any) -> dict[str, Any]:
    """Project one SDK computer action onto the exact canonical action fields."""
    action_type = str(_usage_field(raw, "type", "") or "")
    allowed_fields: dict[str, tuple[str, ...]] = {
        "screenshot": (),
        "wait": (),
        "type": ("text",),
        "keypress": ("keys",),
        "click": ("button", "x", "y", "keys"),
        "double_click": ("x", "y", "keys"),
        "move": ("x", "y", "keys"),
        "scroll": ("x", "y", "scroll_x", "scroll_y", "keys"),
        "drag": ("path", "keys"),
    }
    if action_type not in allowed_fields:
        raise AzureProviderOutputError(
            "provider_persistent_v0_computer_action_type_invalid", action_type or "missing",
        )
    row: dict[str, Any] = {"type": action_type}
    for field in allowed_fields[action_type]:
        value = _usage_field(raw, field)
        if value is None:
            continue
        if field == "path":
            points = []
            for point in list(value or ()):
                points.append({
                    "x": int(_usage_field(point, "x")),
                    "y": int(_usage_field(point, "y")),
                })
            value = points
        elif field in {"keys"}:
            value = [str(item) for item in list(value or ())]
        elif field in {"x", "y", "scroll_x", "scroll_y"}:
            value = int(value)
        else:
            value = str(value)
        row[field] = value
    return row


def _canonicalize_persistent_computer_call(item: Any, *, index: int) -> tuple[str, dict[str, Any]]:
    pending = list(_usage_field(item, "pending_safety_checks", ()) or ())
    if pending:
        raise AzureProviderOutputError(
            "provider_persistent_v0_computer_safety_check_pending",
            json.dumps([
                {
                    "id": str(_usage_field(check, "id", "") or ""),
                    "code": str(_usage_field(check, "code", "") or ""),
                }
                for check in pending
            ], sort_keys=True, separators=(",", ":")),
        )
    actions = list(_usage_field(item, "actions", ()) or ())
    singular = _usage_field(item, "action")
    if actions and singular is not None:
        raise AzureProviderOutputError(
            "provider_persistent_v0_computer_action_representation_ambiguous",
            "both action and actions were populated",
        )
    if actions:
        raw_actions = actions
    elif singular is not None:
        raw_actions = [singular]
    else:
        raise AzureProviderOutputError(
            "provider_persistent_v0_computer_action_count_invalid", "expected>=1 actual=0",
        )
    canonical_actions = [_provider_computer_action_dict(raw_action) for raw_action in raw_actions]
    envelope = {
        "turn": {
            "kind": "act",
            "action": {
                "kind": "computer_action",
                "arguments": {"actions": canonical_actions},
            },
        }
    }
    try:
        canonical, turn_receipt = canonicalize_persistent_primary_turn(
            json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        )
    except PCRProviderProtocolError as exc:
        raise AzureProviderOutputError(exc.code, exc.detail) from exc
    receipt = {
        "native_tool_name": "computer",
        "native_tool_type": "computer_call",
        "native_tool_call_count": 1,
        "native_tool_item_index": index,
        "native_tool_item_id": str(_usage_field(item, "id", "") or ""),
        "native_tool_call_id": str(_usage_field(item, "call_id", "") or ""),
        "provider_computer_action_count": len(canonical_actions),
        "provider_computer_action_types": [action["type"] for action in canonical_actions],
        "provider_turn_arguments_transport": "native_computer_call",
    }
    receipt.update(turn_receipt)
    return canonical, receipt


def canonicalize_persistent_native_tool_output(
    response: Any, *, allow_hosted_tool_search_metadata: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Decode exactly one native function OR computer call into one PERSISTENT action.

    Hosted tool-search metadata may be ignored only after separate schema-custody
    validation by the treatment path. It never counts as an executable action.
    """
    function_calls: list[dict[str, Any]] = []
    computer_calls: list[tuple[int, Any]] = []
    assistant_messages: list[str] = []
    other_calls: list[str] = []
    for index, item in enumerate(_usage_field(response, "output", ()) or ()):
        item_type = str(_usage_field(item, "type", "") or "")
        if item_type == "function_call":
            function_calls.append({
                "index": index,
                "id": str(_usage_field(item, "id", "") or ""),
                "call_id": str(_usage_field(item, "call_id", "") or ""),
                "name": str(_usage_field(item, "name", "") or ""),
                "arguments": str(_usage_field(item, "arguments", "") or ""),
            })
            continue
        if item_type == "computer_call":
            computer_calls.append((index, item))
            continue
        if item_type in {"tool_search_call", "tool_search_output"}:
            if allow_hosted_tool_search_metadata:
                continue
            if item_type.endswith("_call"):
                other_calls.append(item_type)
            else:
                other_calls.append(item_type)
            continue
        if item_type == "message":
            parts: list[str] = []
            for chunk in _usage_field(item, "content", ()) or ():
                piece = _usage_field(chunk, "text")
                if piece is None:
                    piece = _usage_field(chunk, "output_text")
                if piece:
                    parts.append(str(piece))
            if parts:
                assistant_messages.append("".join(parts))
            continue
        if item_type.endswith("_call"):
            other_calls.append(item_type)

    executable_count = len(function_calls) + len(computer_calls)
    mixed_native_types = bool(function_calls and computer_calls)
    if other_calls or mixed_native_types:
        raise AzureProviderOutputError(
            "provider_persistent_v0_native_tool_mixed_output",
            json.dumps({
                "assistant_message_count": len(assistant_messages),
                "other_call_types": other_calls,
                "function_call_count": len(function_calls),
                "computer_call_count": len(computer_calls),
            }, sort_keys=True, separators=(",", ":")),
        )
    if executable_count != 1:
        raise AzureProviderOutputError(
            "provider_persistent_v0_native_tool_call_count_invalid",
            f"expected=1 actual={executable_count}",
        )
    if computer_calls:
        index, item = computer_calls[0]
        canonical, receipt = _canonicalize_persistent_computer_call(item, index=index)
    else:
        call = function_calls[0]
        if call["name"] not in _PERSISTENT_PRIMARY_NATIVE_TOOL_NAMES:
            raise AzureProviderOutputError(
                "provider_persistent_v0_native_tool_name_invalid", call["name"] or "missing",
            )
        try:
            canonical, turn_receipt = canonicalize_persistent_direct_tool_call(
                call["name"], call["arguments"]
            )
        except PCRProviderProtocolError as exc:
            raise AzureProviderOutputError(exc.code, exc.detail) from exc
        receipt = {
            "native_tool_name": call["name"],
            "native_tool_type": "function_call",
            "native_tool_call_count": 1,
            "native_tool_item_index": call["index"],
            "native_tool_item_id": call["id"],
            "native_tool_call_id": call["call_id"],
        }
        receipt.update(turn_receipt)
    receipt.update({
        "response_id": str(_usage_field(response, "id", "") or ""),
        "raw_provider_status": str(_usage_field(response, "status", "") or ""),
        "extraction_path": "response.output[] native call -> persistent_v0_primary_turn",
        "candidate_message_count": len(assistant_messages),
        "provider_ignored_assistant_message_count": len(assistant_messages),
        "provider_ignored_assistant_message_sha256": [
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in assistant_messages
        ],
        "provider_duplicate_output": False,
        "canonical_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    })
    return canonical, receipt


def _native_tool_output_shape_telemetry(response: Any) -> dict[str, Any]:
    """Return bounded provider-output cardinality evidence without model text."""
    output_items = list(_usage_field(response, "output", ()) or ())
    assistant_rows: list[dict[str, Any]] = []
    function_names: list[str] = []
    other_call_types: list[str] = []
    for item in output_items:
        item_type = str(_usage_field(item, "type", "") or "")
        if item_type == "function_call":
            function_names.append(str(_usage_field(item, "name", "") or ""))
            continue
        if item_type == "message":
            parts: list[str] = []
            for chunk in _usage_field(item, "content", ()) or ():
                piece = _usage_field(chunk, "text")
                if piece is None:
                    piece = _usage_field(chunk, "output_text")
                if piece:
                    parts.append(str(piece))
            text = "".join(parts)
            assistant_rows.append({
                "id": str(_usage_field(item, "id", "") or ""),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "bytes": len(text.encode("utf-8")),
            })
            continue
        if item_type.endswith("_call"):
            other_call_types.append(item_type)
    return {
        "provider_output_item_count": len(output_items),
        "assistant_message_item_count": len(assistant_rows),
        "assistant_message_item_ids": tuple(row["id"] for row in assistant_rows),
        "assistant_message_item_hashes": tuple(row["sha256"] for row in assistant_rows),
        "assistant_message_nonempty_count": sum(int(row["bytes"] > 0) for row in assistant_rows),
        "function_call_item_count": len(function_names),
        "function_call_names": tuple(function_names),
        "other_executable_call_types": tuple(other_call_types),
    }


def canonicalize_verifier_native_tool_output(
    response: Any,
) -> tuple[str, dict[str, Any]]:
    """Decode exactly one provider-native ``verifier_turn`` function call.

    Native function-call cardinality is a hard temporal boundary. Unlike the
    legacy Chat decoder, this path never collapses duplicated argument objects:
    arguments must be one complete JSON object, then the unchanged direct-turn
    decoder remains the Verifier semantic authority. The provider never
    executes the proposed inspection or verdict.
    """
    output_items = list(_usage_field(response, "output", ()) or ())
    shape = _native_tool_output_shape_telemetry(response)
    calls: list[dict[str, Any]] = []
    nonempty_assistant_messages = 0
    other_calls: list[str] = []
    for index, item in enumerate(output_items):
        item_type = str(_usage_field(item, "type", "") or "")
        if item_type == "function_call":
            calls.append({
                "index": index,
                "id": str(_usage_field(item, "id", "") or ""),
                "call_id": str(_usage_field(item, "call_id", "") or ""),
                "name": str(_usage_field(item, "name", "") or ""),
                "arguments": str(_usage_field(item, "arguments", "") or ""),
            })
            continue
        if item_type == "message":
            parts: list[str] = []
            for chunk in _usage_field(item, "content", ()) or ():
                piece = _usage_field(chunk, "text")
                if piece is None:
                    piece = _usage_field(chunk, "output_text")
                if piece:
                    parts.append(str(piece))
            if "".join(parts).strip():
                nonempty_assistant_messages += 1
            continue
        if item_type.endswith("_call"):
            other_calls.append(item_type)

    if nonempty_assistant_messages or other_calls:
        raise AzureProviderOutputError(
            "provider_verifier_native_tool_mixed_output",
            json.dumps(shape, sort_keys=True, separators=(",", ":")),
        )
    if len(calls) != 1:
        raise AzureProviderOutputError(
            "provider_verifier_native_tool_call_count_invalid",
            json.dumps(shape, sort_keys=True, separators=(",", ":")),
        )
    call = calls[0]
    if call["name"] != _VERIFIER_NATIVE_TOOL_NAME:
        raise AzureProviderOutputError(
            "provider_verifier_native_tool_name_invalid",
            json.dumps(shape, sort_keys=True, separators=(",", ":")),
        )

    arguments = call["arguments"]
    if not arguments.strip() or arguments.lstrip().startswith("```"):
        raise AzureProviderOutputError(
            "provider_verifier_native_tool_arguments_invalid",
            "arguments must be one bare complete JSON object",
        )
    try:
        strict_wrapper, _body = _strict_structured_json(arguments)
    except AzureProviderOutputError as exc:
        raise AzureProviderOutputError(
            "provider_verifier_native_tool_arguments_invalid", exc.code,
        ) from exc
    canonical, turn_receipt = unwrap_verifier_direct_turn(strict_wrapper)
    receipt = {
        **shape,
        "response_id": str(_usage_field(response, "id", "") or ""),
        "raw_provider_status": str(_usage_field(response, "status", "") or ""),
        "extraction_path": "response.output[].function_call.arguments -> one_json_object -> verifier_direct_turn",
        "candidate_message_count": int(shape["assistant_message_item_count"]),
        "provider_duplicate_output": False,
        "native_tool_name": _VERIFIER_NATIVE_TOOL_NAME,
        "native_tool_call_count": 1,
        "native_tool_item_index": call["index"],
        "native_tool_item_id": call["id"],
        "native_tool_call_id": call["call_id"],
        "native_tool_arguments_sha256": hashlib.sha256(arguments.encode("utf-8")).hexdigest(),
        "native_tool_arguments_bytes": len(arguments.encode("utf-8")),
        "canonical_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    receipt.update(turn_receipt)
    return canonical, receipt



def _drop_null_fields(value: Any) -> Any:
    """Convert Azure's required-but-nullable schema fields to protocol absence."""
    if isinstance(value, dict):
        return {key: _drop_null_fields(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_drop_null_fields(item) for item in value]
    return value


_PERSISTENT_VERIFIER_DIRECT_LOCATOR_ROUTE: dict[str, tuple[str, str]] = {
    "read_file": ("read_file", "path"),
    "read_output": ("read_output", "handle"),
    # Dynamic PERSISTENT provider schemas expose this alias only when the kernel packet
    # supplies an exact output-handle enum. Runtime semantics remain read_output.
    "read_recorded_output": ("read_output", "handle"),
    "compare_initial_path": ("compare_initial_path", "path"),
    # Provider-only F90 alias. Runtime parsing/budgeting stays on read_output;
    # execution upgrades only an exact bound receipt handle to the separately
    # typed read_cited_receipt observation.
    "read_cited_receipt": ("read_output", "handle"),
    "inspect_artifact_history": ("inspect_artifact_history", "path"),
    "probe_port": ("probe_port", "target"),
    "probe_http": ("probe_http", "target"),
    "observe_existing_process": ("probe_process", "target"),
    "probe_job": ("probe_job", "target"),
    "inspect_artifact": ("inspect_artifact", "path"),
    "perceive_artifact": ("perceive_artifact", "path"),
}



_PERSISTENT_DERIVED_TRANSPORT_CLAIM = (
    "PERSISTENT transport placeholder: semantic claim is authored in the final verdict"
)
_PERSISTENT_DERIVED_TRANSPORT_STRUCTURE = (
    "PERSISTENT transport placeholder: authoritative structure is audited in final method_validity"
)
_PERSISTENT_DERIVED_TRANSPORT_METHOD = (
    "PERSISTENT transport placeholder: executed rule is audited in final method_validity"
)
_PERSISTENT_DERIVED_TRANSPORT_PROXY_RISK = (
    "PERSISTENT transport placeholder: proxy risk is audited in final method_validity"
)


def _canonicalize_persistent_verifier_compact_command_turn(
    turn: dict[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Expand PERSISTENT's flat run_verifier_command alias into the V3 runtime shape.

    This is structural canonicalization only for causal authority. Command,
    clause IDs, and evidence/input refs are copied exactly from model output.
    Fixed transport-only strings satisfy the generic V3 parser's legacy
    pre-execution grounding fields; semantic method authority is evaluated from
    the final post-execution method_validity record, never these placeholders.
    """
    if str(turn.get("kind") or "") != "inspect":
        return turn, ()
    requests = turn.get("requests")
    if not isinstance(requests, list):
        return turn, ()
    normalized: list[Any] = []
    mappings: list[dict[str, Any]] = []
    for raw in requests:
        if not isinstance(raw, dict) or str(raw.get("kind") or "") != "run_verifier_command":
            normalized.append(raw)
            continue
        forbidden = {
            "verification_plan", "execution", "path", "handle", "target",
            "check_id", "receipt_kind", "limit", "offset", "span", "content",
            "request_id", "claim", "authoritative_structure", "method_summary",
            "proxy_risk", "proof_ids",
        }
        polluted = sorted(forbidden.intersection(raw))
        if polluted:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_compact_command_ambiguous",
                ",".join(polluted),
            )
        basis_refs = raw.get("basis_refs")
        bound_input_refs = raw.get("bound_input_refs")
        clause_ids = raw.get("clause_ids")
        if not isinstance(basis_refs, list) or not basis_refs:
            raise AzureProviderOutputError("provider_persistent_verifier_compact_command_basis_invalid")
        if not isinstance(bound_input_refs, list) or not bound_input_refs:
            raise AzureProviderOutputError("provider_persistent_verifier_compact_command_inputs_invalid")
        if not isinstance(clause_ids, list) or not clause_ids:
            raise AzureProviderOutputError("provider_persistent_verifier_compact_command_clauses_invalid")
        request: dict[str, Any] = {
            "kind": "overlay_run_command",
            "verification_plan": {
                "claim": _PERSISTENT_DERIVED_TRANSPORT_CLAIM,
                "evidence_mode": "derived",
                "clause_ids": list(clause_ids),
                "basis": [{"ref": ref} for ref in basis_refs],
                "bound_input_refs": list(bound_input_refs),
                "authoritative_structure": _PERSISTENT_DERIVED_TRANSPORT_STRUCTURE,
                "method_summary": _PERSISTENT_DERIVED_TRANSPORT_METHOD,
                "proxy_risk": _PERSISTENT_DERIVED_TRANSPORT_PROXY_RISK,
            },
            "execution": {
                "kind": "overlay_run_command",
                "command": raw.get("command"),
            },
        }
        normalized.append(request)
        mappings.append({
            "provider_kind": "run_verifier_command",
            "runtime_kind": "overlay_run_command",
            "basis_ref_count": len(basis_refs),
            "bound_input_ref_count": len(bound_input_refs),
            "command_sha256": hashlib.sha256(str(raw.get("command") or "").encode("utf-8")).hexdigest(),
        })
    if not mappings:
        return turn, ()
    canonical = dict(turn)
    canonical["requests"] = normalized
    return canonical, tuple(mappings)


def _canonicalize_persistent_verifier_compact_direct_turn(
    turn: dict[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Map PERSISTENT's compact provider-only locator onto the runtime request field.

    This is structural canonicalization only: the model still chooses the route
    and locator value. No target, command, evidence fact, or verdict is inferred.
    F93 additionally keeps transport identity host-owned and collapses only exact
    equivalent reads of the same immutable cited receipt inside one provider turn.
    Generic/TRIAD turns never contain ``locator`` and therefore pass unchanged.
    """
    request_field = "requests" if str(turn.get("kind") or "") == "inspect" else "missing_inspection_requests"
    requests = turn.get(request_field)
    if not isinstance(requests, list):
        return turn, ()
    normalized: list[Any] = []
    mappings: list[dict[str, Any]] = []
    cited_seen: dict[str, int] = {}
    cited_counts: dict[str, int] = {}
    for raw in requests:
        if not isinstance(raw, dict) or "locator" not in raw:
            normalized.append(raw)
            continue
        provider_kind = str(raw.get("kind") or "")
        route = _PERSISTENT_VERIFIER_DIRECT_LOCATOR_ROUTE.get(provider_kind)
        if route is None:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_compact_locator_kind_invalid", provider_kind or "missing",
            )
        if "request_id" in raw:
            raise AzureProviderOutputError(
                "provider_persistent_verifier_direct_request_id_forbidden", provider_kind,
            )
        runtime_kind, field = route
        locator = raw.get("locator")
        if not isinstance(locator, str) or not locator.strip():
            raise AzureProviderOutputError(
                "provider_persistent_verifier_compact_locator_invalid", provider_kind,
            )
        parsed_locator = urlparse(locator)
        is_http_url = parsed_locator.scheme.lower() in {"http", "https"} and bool(parsed_locator.netloc)
        if provider_kind == "probe_http" and not is_http_url:
            raise AzureProviderOutputError(
                "provider_direct_turn_locator_route_mismatch",
                "probe_http requires a full http(s) URL",
            )
        if provider_kind in {
            "read_file", "compare_initial_path", "inspect_artifact_history",
            "inspect_artifact", "perceive_artifact",
        } and is_http_url:
            raise AzureProviderOutputError(
                "provider_direct_turn_locator_route_mismatch",
                f"{provider_kind} cannot consume an http(s) URL",
            )
        if provider_kind in {"read_output", "read_recorded_output"} and locator.startswith("receipt:"):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_receipt_requires_cited_route", locator,
            )
        if any(key in raw for key in ("path", "handle", "target", "command")):
            raise AzureProviderOutputError(
                "provider_persistent_verifier_compact_locator_ambiguous", provider_kind,
            )

        semantic_sha = hashlib.sha256(json.dumps(
            {
                "kind": provider_kind,
                "locator": locator,
                "limit": raw.get("limit"),
                "offset": raw.get("offset"),
                "span": raw.get("span"),
                "clause_ids": raw.get("clause_ids"),
                "proof_ids": raw.get("proof_ids"),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")).hexdigest()

        if provider_kind == "read_cited_receipt" and semantic_sha in cited_seen:
            canonical_ordinal = cited_seen[semantic_sha]
            cited_counts[semantic_sha] = cited_counts.get(semantic_sha, 1) + 1
            mappings.append({
                "provider_kind": provider_kind,
                "runtime_kind": runtime_kind,
                "runtime_field": field,
                "locator_sha256": hashlib.sha256(locator.encode("utf-8")).hexdigest(),
                "semantic_request_sha256": semantic_sha,
                "canonical_request_ordinal": canonical_ordinal,
                "provider_duplicate_equivalent": True,
                "duplicate_equivalent_count": cited_counts[semantic_sha],
            })
            continue

        canonical_ordinal = len(normalized)
        if provider_kind == "read_cited_receipt":
            cited_seen[semantic_sha] = canonical_ordinal
            cited_counts[semantic_sha] = 1
        request = dict(raw)
        request.pop("locator", None)
        request["kind"] = runtime_kind
        request[field] = locator
        normalized.append(request)
        mappings.append({
            "provider_kind": provider_kind,
            "runtime_kind": runtime_kind,
            "runtime_field": field,
            "locator_sha256": hashlib.sha256(locator.encode("utf-8")).hexdigest(),
            "semantic_request_sha256": semantic_sha,
            "canonical_request_ordinal": canonical_ordinal,
            "provider_duplicate_equivalent": False,
            "duplicate_equivalent_count": 1,
        })
    if not mappings:
        return turn, ()
    canonical = dict(turn)
    canonical[request_field] = normalized
    return canonical, tuple(mappings)


def _canonicalize_persistent_verifier_verdict_transport_noise(
    turn: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Drop an executable-missing-inspection field from settled verdicts.

    PERSISTENT's strict provider schema must expose one stable verdict object shape,
    but runtime semantics make ``missing_inspection_requests`` executable only
    for ``uncertain_missing_evidence``.  A non-empty value on any settled
    verdict is therefore transport noise, not task semantics.  Canonicalize it
    to the required empty array before the fail-closed runtime parser so this
    impossible combination cannot waste a protocol-correction model call.
    """
    verdict = str(turn.get("verdict") or "").strip()
    requests = turn.get("missing_inspection_requests")
    if (
        verdict
        and verdict != "uncertain_missing_evidence"
        and isinstance(requests, list)
        and requests
    ):
        canonical = dict(turn)
        canonical["missing_inspection_requests"] = []
        return canonical, True
    return turn, False


def unwrap_verifier_direct_turn(text: str) -> tuple[str, dict[str, Any]]:
    """Extract one direct strict-schema Verifier turn without candidate choice.

    A single Chat choice can still contain a duplicated complete JSON object.
    Preserve that provider anomaly, collapse it only if every decoded turn is
    semantically identical, and fail closed on every distinct candidate.
    """
    try:
        candidates = _provider_json_object_sequence(text)
    except AzureProviderOutputError as exc:
        direct_codes = {
            "provider_envelope_empty": "provider_direct_turn_empty",
            "provider_envelope_invalid_json": "provider_structured_output_invalid_json",
            "provider_envelope_nonstandard_json_constant": "provider_structured_output_nonstandard_json_constant",
            "provider_envelope_duplicate_key": "provider_direct_turn_duplicate_key",
            "provider_envelope_top_level_not_object": "provider_direct_turn_not_object",
        }
        raise AzureProviderOutputError(direct_codes.get(exc.code, exc.code), exc.detail) from exc
    raw_hashes = [hashlib.sha256(raw.encode("utf-8")).hexdigest() for raw, _ in candidates]
    canonical_turns: list[str] = []
    kinds: list[str] = []
    compact_mapping_rows: list[tuple[
        tuple[dict[str, str], ...], tuple[dict[str, Any], ...], bool
    ]] = []
    for _raw, wrapper in candidates:
        if set(wrapper) != {"turn"} or not isinstance(wrapper.get("turn"), dict):
            raise AzureProviderOutputError("provider_direct_turn_invalid_shape")
        turn = _drop_null_fields(wrapper["turn"])
        turn, verdict_transport_noise_removed = _canonicalize_persistent_verifier_verdict_transport_noise(turn)
        turn, compact_command_mappings = _canonicalize_persistent_verifier_compact_command_turn(turn)
        turn, compact_mappings = _canonicalize_persistent_verifier_compact_direct_turn(turn)
        is_inspect = str(turn.get("kind") or "") == "inspect"
        is_verdict = isinstance(turn.get("verdict"), str) and bool(str(turn["verdict"]).strip())
        if is_inspect == is_verdict:
            raise AzureProviderOutputError("provider_direct_turn_ambiguous_payload")
        canonical_turns.append(json.dumps(
            turn, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        ))
        kinds.append("inspect" if is_inspect else "verdict")
        compact_mapping_rows.append((
            compact_mappings, compact_command_mappings, verdict_transport_noise_removed
        ))
    if len(set(canonical_turns)) != 1:
        raise AzureProviderOutputError("provider_direct_turn_multiple_distinct_semantic_payloads")
    canonical_turn = canonical_turns[0]
    return canonical_turn, {
        "provider_turn_contract": "direct_schema",
        "provider_turn_kind": kinds[0],
        "provider_turn_wrapper_sha256": hashlib.sha256(str(text).encode("utf-8")).hexdigest(),
        "provider_turn_payload_sha256": hashlib.sha256(canonical_turn.encode("utf-8")).hexdigest(),
        "provider_turn_candidate_count": len(candidates),
        "provider_turn_raw_candidate_hashes": raw_hashes,
        "provider_turn_duplicate_equivalent": len(candidates) > 1,
        "provider_persistent_verifier_compact_locator_mapping": compact_mapping_rows[0][0],
        "provider_persistent_verifier_compact_command_mapping": compact_mapping_rows[0][1],
        "provider_persistent_verifier_settled_missing_inspections_canonicalized": compact_mapping_rows[0][2],
    }


def _extract_plain_output_text(response: Any) -> str:
    """Extract one unambiguous plain assistant message for the vision lane."""
    messages, mixed_call = _raw_assistant_messages(response)
    if mixed_call:
        raise AzureProviderOutputError("provider_mixed_message_and_tool_output")
    if not messages:
        raise AzureProviderOutputError("provider_no_assistant_message")
    unique = {str(row["text"]) for row in messages}
    if len(unique) != 1:
        raise AzureProviderOutputError("multiple_distinct_assistant_outputs")
    return str(messages[0]["text"])


def _jsonable_provider_value(value: Any) -> Any:
    """Convert an SDK response into bounded JSON evidence without guessing."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable_provider_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable_provider_value(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _jsonable_provider_value(model_dump())
        except Exception:
            pass
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _jsonable_provider_value(to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return {
            str(key): _jsonable_provider_value(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


_RAW_PROVIDER_REQUEST_ENV = "AETHER_CAPTURE_RAW_PROVIDER_REQUEST"
_PROVIDER_REQUEST_CAPTURE_SCOPE = "sdk_kwargs_before_client_dispatch"
AZURE_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
_AZURE_WORKLOAD_IDENTITY_ENV = (
    "AZURE_AUTHORITY_HOST",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_FEDERATED_TOKEN_FILE",
)
_AZURE_SYSTEM_ASSIGNED_IDENTITY_CONFLICT_ENV = (
    "IDENTITY_ENDPOINT",
    "IDENTITY_HEADER",
    "IDENTITY_SERVER_THUMBPRINT",
    "IMDS_ENDPOINT",
    "MSI_ENDPOINT",
    "MSI_SECRET",
    *_AZURE_WORKLOAD_IDENTITY_ENV,
    "AZURE_POD_IDENTITY_AUTHORITY_HOST",
    "AZURE_KUBERNETES_SNI_NAME",
    "AZURE_KUBERNETES_TOKEN_PROXY",
    "AZURE_KUBERNETES_CA_FILE",
    "AZURE_KUBERNETES_CA_DATA",
)
_AZURE_MI_CONNECTION_TIMEOUT_S = 5.0
_AZURE_MI_READ_TIMEOUT_S = 5.0
_AZURE_MI_RETRY_OPTIONS = {
    "retry_total": 0,
    "retry_connect": 0,
    "retry_read": 0,
    "retry_status": 0,
}
_PROVIDER_REQUEST_CREDENTIAL_KEYS = frozenset({
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "auth_token",
    "bearer",
    "bearer_token",
    "client_secret",
    "clientsecret",
    "credential",
    "password",
    "private_key",
    "privatekey",
    "refresh_token",
    "secret",
    "token",
})


def _provider_request_key_is_credential(key: Any) -> bool:
    """Return whether *key* names an obvious credential-bearing field.

    The SDK client owns endpoint authentication; credentials are not part of
    the request dictionaries passed to ``responses.create`` or
    ``chat.completions.create``.  This denylist is defense in depth for a
    caller-supplied nested field and intentionally does not classify ordinary
    measurement fields such as ``max_output_tokens`` as credentials.
    """
    normalized = str(key or "").strip().lower().replace("-", "_")
    if normalized in _PROVIDER_REQUEST_CREDENTIAL_KEYS:
        return True
    return any(
        normalized.startswith(prefix) or normalized.endswith(suffix)
        for prefix, suffix in (
            ("api_key_", "_api_key"),
            ("access_token_", "_access_token"),
            ("auth_token_", "_auth_token"),
            ("client_secret_", "_client_secret"),
            ("private_key_", "_private_key"),
            ("refresh_token_", "_refresh_token"),
        )
    )


def _credential_safe_provider_request(value: Any) -> Any:
    """Make a JSON-safe provider request without retaining credential values."""
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if _provider_request_key_is_credential(key)
                else _credential_safe_provider_request(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_credential_safe_provider_request(item) for item in value]
    if isinstance(value, tuple):
        return [_credential_safe_provider_request(item) for item in value]
    return value


def _capture_finalized_provider_request(
    event: dict[str, Any], request: dict[str, Any],
) -> None:
    """Optionally attach the finalized, credential-safe request to telemetry.

    This is deliberately a telemetry-only seam.  It is disabled unless the
    operator opts in with ``AETHER_CAPTURE_RAW_PROVIDER_REQUEST=1`` and any
    serialization failure is ignored so diagnostics cannot alter provider
    behavior.  The digest is over the exact credential-safe payload retained
    in ``raw_provider_request``.
    """
    if os.environ.get(_RAW_PROVIDER_REQUEST_ENV, "").strip() != "1":
        return
    try:
        payload = _credential_safe_provider_request(
            _jsonable_provider_value(request)
        )
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except Exception:
        # Capture must never become a provider-call failure or a cognition
        # change.  The ordinary input/instruction hashes remain available.
        return
    event["raw_provider_request"] = payload
    event["raw_provider_request_sha256"] = hashlib.sha256(encoded).hexdigest()
    event["provider_request_capture_scope"] = _PROVIDER_REQUEST_CAPTURE_SCOPE


_PERSISTENT_STATELESS_INPUT_FIELDS: dict[str, frozenset[str]] = {
    # Responses output objects expose lifecycle metadata such as ``status``
    # that is not accepted when the same item is submitted as a later input.
    # Keep only the provider's input-shaped fields; do not silently pass an
    # SDK response dump back to the API.
    "reasoning": frozenset({"type", "id", "encrypted_content", "summary"}),
    "compaction": frozenset({"type", "id", "encrypted_content"}),
    "function_call": frozenset({"type", "id", "call_id", "name", "arguments"}),
    "message": frozenset({"type", "id", "role", "content"}),
}




class _AsyncResponsesTransport:
    """Cancellation-aware bridge from Aether's sync kernel to AsyncOpenAI.

    The kernel remains synchronous and the provider request shape is unchanged.
    Each model owns one AsyncOpenAI client on a dedicated event loop so normal
    calls retain connection pooling. The calling worker waits on a thread-safe
    future in short intervals; Harbor cancellation cancels and *awaits* the
    in-flight HTTP coroutine before returning control to the task lifecycle.
    """

    _WAIT_SLICE_S = 0.05
    _CANCEL_DRAIN_S = 5.0

    def __init__(self, *, client_factory: Callable[[], Any]) -> None:
        self._client_factory = client_factory
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._closed = False
        self._active: dict[int, asyncio.Task[Any]] = {}
        self._next_call_id = 0
        self._id_lock = threading.Lock()
        self._client: Any | None = None
        self._thread = threading.Thread(
            target=self._run_loop,
            name="aether-async-responses",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise AzureModelError("async Responses transport failed to initialize")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._client = self._client_factory()
        finally:
            self._ready.set()
        self._loop.run_forever()
        self._loop.close()

    def _allocate_call_id(self) -> int:
        with self._id_lock:
            self._next_call_id += 1
            return self._next_call_id

    async def _execute(
        self,
        call_id: int,
        method: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        task = asyncio.current_task()
        if task is None or self._client is None:
            raise AzureModelError("async Responses transport unavailable")
        self._active[call_id] = task
        try:
            fn = getattr(self._client.responses, method)
            return await fn(*args, **kwargs)
        finally:
            self._active.pop(call_id, None)

    async def _cancel_and_wait(self, call_id: int) -> None:
        task = self._active.get(call_id)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except BaseException:
            pass

    async def _shutdown(self) -> None:
        current = asyncio.current_task()
        active = [task for task in self._active.values() if task is not current]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        client = self._client
        if client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result

    def call(
        self,
        method: str,
        *args: Any,
        cancellation_event: Any | None = None,
        honor_cancellation: bool = True,
        **kwargs: Any,
    ) -> Any:
        if self._closed:
            raise AzureModelError("async Responses transport is closed")
        if honor_cancellation:
            raise_if_run_cancelled(cancellation_event)
        raise_if_run_deadline_exceeded()
        call_id = self._allocate_call_id()
        future = asyncio.run_coroutine_threadsafe(
            self._execute(call_id, method, tuple(args), dict(kwargs)),
            self._loop,
        )
        while True:
            try:
                return future.result(timeout=self._WAIT_SLICE_S)
            except concurrent.futures.TimeoutError:
                try:
                    raise_if_run_deadline_exceeded()
                except KernelRunTimeout:
                    drain = asyncio.run_coroutine_threadsafe(
                        self._cancel_and_wait(call_id), self._loop,
                    )
                    try:
                        drain.result(timeout=self._CANCEL_DRAIN_S)
                    except concurrent.futures.TimeoutError as exc:
                        raise AzureModelError(
                            "provider transport deadline cancellation did not drain"
                        ) from exc
                    raise
                if honor_cancellation and cancellation_requested(cancellation_event):
                    drain = asyncio.run_coroutine_threadsafe(
                        self._cancel_and_wait(call_id), self._loop,
                    )
                    try:
                        drain.result(timeout=self._CANCEL_DRAIN_S)
                    except concurrent.futures.TimeoutError as exc:
                        raise AzureModelError(
                            "provider transport cancellation did not drain"
                        ) from exc
                    raise RunCancellationRequested("task run cancellation requested")
            except concurrent.futures.CancelledError as exc:
                if honor_cancellation and cancellation_requested(cancellation_event):
                    raise RunCancellationRequested(
                        "task run cancellation requested"
                    ) from exc
                raise AzureModelError("async Responses transport cancelled") from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._loop.is_running():
            shutdown = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
            try:
                shutdown.result(timeout=self._CANCEL_DRAIN_S)
            finally:
                self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=self._CANCEL_DRAIN_S)
        if self._thread.is_alive():
            raise AzureModelError("async Responses transport thread did not stop")


def make_azure_callable(
    *,
    deployment_env: str,
    key_env: str,
    endpoint_env: str = "AZURE_OPENAI_ENDPOINT",
    credential_mode: str = API_KEY_CREDENTIAL_MODE,
    expected_model_id: str = "gpt-5.6-luna",
    effort: str = "medium",
    role: str = "unspecified",
    poll_interval_s: float | None = None,
    poll_timeout_s: float | None = None,
    max_retries: int | None = None,
    sdk_max_retries: int | None = None,
    backoff_base_s: float | None = None,
    backoff_cap_s: float | None = None,
    backoff_max_total_s: float | None = None,
    max_rpm: float | None = None,
    responses_background: bool | None = None,
    responses_websocket: bool = False,
    responses_websocket_persistent: bool = False,
    prompt_cache_mode: str | None = None,
    prompt_cache_namespace: str | None = None,
) -> "AzureModelCallable":
    """Build a ``ModelCallable`` backed by an Azure OpenAI deployment.

    Env vars are read at *build time* (not per-call), so a missing var
    raises immediately rather than mid-run.

    Solver and Verifier both use the sole native Responses-tools route.
    Background execution, retry and cache controls are explicit constructor
    inputs supplied by the production profile.

    Transient failures (HTTP 429/5xx, connection errors, or a background
    job that ends with a retryable error code) are retried in place with
    exponential backoff + jitter — see ``providers/model_retry.py``. Every
    retry/backoff knob below falls back to an ``AETHER_MODEL_*`` env var
    when left ``None``, matching the existing ``poll_interval_s`` /
    ``poll_timeout_s`` pattern, and every default preserves prior behavior
    at low volume (a handful of bounded retries) while an optional
    requests-per-minute gate (``max_rpm`` / ``AETHER_MODEL_MAX_RPM``,
    default unlimited) can pace bursts client-side.
    """
    resolved_expected_model_id = str(expected_model_id or "").strip()
    if not resolved_expected_model_id:
        raise AzureModelError("expected_model_id must be non-empty")
    budget_guard = provider_budget_guard_from_env(
        expected_model_id=resolved_expected_model_id,
    )
    if budget_guard is not None:
        contract = getattr(budget_guard, "contract", None)
        if contract is not None:
            expected_provider_retries = contract.provider_max_retries
            expected_sdk_retries = contract.provider_sdk_max_retries
            if max_retries != expected_provider_retries or sdk_max_retries != expected_sdk_retries:
                if expected_provider_retries == 0 and expected_sdk_retries == 0:
                    raise AzureModelError(
                        "budget-constrained provider construction requires explicit provider and SDK retries = 0"
                    )
                raise AzureModelError(
                    "budget-constrained provider construction retry controls must match the bound contract"
                )
        elif max_retries != 0:
            # Interface-compatible lightweight guards used by diagnostics/tests
            # preserve the legacy zero-retry expectation when no contract is exposed.
            raise AzureModelError(
                "budget-constrained provider construction requires explicit provider and SDK retries = 0"
            )
    endpoint = _normalize_endpoint(os.environ[endpoint_env])
    deployment = os.environ[deployment_env]
    resolved_poll_interval_s = (
        float(os.environ.get("AETHER_MODEL_POLL_INTERVAL_S", "10"))
        if poll_interval_s is None
        else poll_interval_s
    )
    resolved_poll_timeout_s = (
        float(os.environ.get("AETHER_MODEL_POLL_TIMEOUT_S", "1200"))
        if poll_timeout_s is None
        else poll_timeout_s
    )
    if role == "verifier":
        resolved_poll_timeout_s = _verifier_poll_timeout_s(float(resolved_poll_timeout_s))
    resolved_max_retries = (
        int(os.environ.get("AETHER_MODEL_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
        if max_retries is None
        else max_retries
    )
    resolved_backoff_base_s = (
        float(os.environ.get("AETHER_MODEL_BACKOFF_BASE_S", str(DEFAULT_BACKOFF_BASE_S)))
        if backoff_base_s is None
        else backoff_base_s
    )
    resolved_backoff_cap_s = (
        float(os.environ.get("AETHER_MODEL_BACKOFF_CAP_S", str(DEFAULT_BACKOFF_CAP_S)))
        if backoff_cap_s is None
        else backoff_cap_s
    )
    resolved_backoff_max_total_s = (
        float(os.environ.get("AETHER_MODEL_BACKOFF_MAX_TOTAL_S", str(DEFAULT_BACKOFF_MAX_TOTAL_S)))
        if backoff_max_total_s is None
        else backoff_max_total_s
    )
    resolved_max_rpm = (
        float(os.environ.get("AETHER_MODEL_MAX_RPM", str(DEFAULT_MAX_RPM)))
        if max_rpm is None
        else max_rpm
    )

    if role not in {"solver", "verifier"}:
        raise AzureModelError("AzureModelCallable supports only the PERSISTENT Solver or Verifier")

    if openai is None:
        raise AzureModelError("openai package is required for AzureModelCallable")
    resolved_background = (
        _responses_background_enabled()
        if responses_background is None
        else bool(responses_background)
    )
    resolved_websocket = bool(responses_websocket)
    resolved_websocket_persistent = bool(responses_websocket_persistent)
    if resolved_websocket_persistent and not resolved_websocket:
        raise AzureModelError("persistent Responses WebSocket requires WebSocket mode")
    if resolved_background and resolved_websocket:
        raise AzureModelError("Responses background HTTP and WebSocket modes are mutually exclusive")
    if credential_mode not in {
        API_KEY_CREDENTIAL_MODE,
        SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE,
    }:
        raise AzureModelError(f"unsupported Azure credential mode: {credential_mode!r}")
    bearer_token_provider: Callable[[], str] | None = None
    deadline_bearer_token_provider: Callable[[float], str] | None = None
    if credential_mode == API_KEY_CREDENTIAL_MODE:
        if not key_env:
            raise AzureModelError("api_key credential mode requires a key environment name")
        api_key: str | Callable[[], str] = os.environ[key_env]
    else:
        if not resolved_websocket:
            raise AzureModelError(
                "system-assigned managed identity currently requires the bounded Responses WebSocket route"
            )
        configured_identity_selectors = tuple(
            name for name in _AZURE_SYSTEM_ASSIGNED_IDENTITY_CONFLICT_ENV
            if str(os.environ.get(name, "") or "").strip()
        )
        if configured_identity_selectors:
            workload_identity_configured = any(
                name in _AZURE_WORKLOAD_IDENTITY_ENV
                for name in configured_identity_selectors
            )
            identity_kind = (
                "workload identity"
                if workload_identity_configured
                else "alternate identity endpoint"
            )
            raise AzureModelError(
                f"{identity_kind} environment detected; refusing to select a non-VM identity"
            )
        try:
            from azure.identity.aio import ManagedIdentityCredential as AsyncManagedIdentityCredential
        except ImportError as exc:
            raise AzureModelError(
                "azure-identity with aiohttp is required for bounded managed identity authentication"
            ) from exc

        def managed_identity_token_for_timeout(timeout_s: float) -> str:
            timeout = float(timeout_s)
            if not math.isfinite(timeout) or timeout <= 0:
                raise AzureModelError("managed identity token deadline expired before acquisition")
            credential_timeout = min(
                timeout,
                _AZURE_MI_CONNECTION_TIMEOUT_S,
                _AZURE_MI_READ_TIMEOUT_S,
            )

            async def acquire_managed_identity_token() -> str:
                # No client_id is supplied: Azure Identity selects the VM's
                # system-assigned identity. A fresh async credential binds its
                # pipeline settings to this request's remaining budget.
                credential = AsyncManagedIdentityCredential(
                    connection_timeout=credential_timeout,
                    read_timeout=credential_timeout,
                    timeout=credential_timeout,
                    **_AZURE_MI_RETRY_OPTIONS,
                )
                try:
                    token_result = await credential.get_token(
                        AZURE_COGNITIVE_SERVICES_SCOPE,
                    )
                    token = str(getattr(token_result, "token", "") or "").strip()
                    if not token:
                        raise AzureModelError(
                            "managed identity returned an empty Cognitive Services token"
                        )
                    return token
                finally:
                    # The async pipeline is cancellation-aware. Closing it in
                    # the cancelled coroutine releases its in-flight transport.
                    await credential.close()

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                raise AzureModelError(
                    "synchronous Responses WebSocket managed identity auth cannot run inside an active event loop"
                )
            try:
                # Azure Core's timeout bounds its retry budget and connection
                # setup, not a single in-flight slow-trickling response. The
                # outer wait_for supplies the absolute operation bound and
                # cancels the async HTTP send before this callback can return.
                return asyncio.run(asyncio.wait_for(
                    acquire_managed_identity_token(),
                    timeout=credential_timeout,
                ))
            except TimeoutError as exc:
                raise AzureModelError(
                    "managed identity authentication exceeded the request deadline"
                ) from exc

        def managed_identity_token() -> str:
            return managed_identity_token_for_timeout(
                min(_AZURE_MI_CONNECTION_TIMEOUT_S, _AZURE_MI_READ_TIMEOUT_S)
            )

        def managed_identity_token_for_deadline(remaining_s: float) -> str:
            return managed_identity_token_for_timeout(remaining_s)

        bearer_token_provider = managed_identity_token
        deadline_bearer_token_provider = managed_identity_token_for_deadline
        # OpenAI 2.x accepts a token callback as api_key and maps it to the
        # Authorization: Bearer header. The MI profile also uses the explicit
        # WebSocket token-provider seam below; no environment key is read.
        api_key = managed_identity_token
    resolved_cache_mode = (
        _prompt_cache_mode_from_env()
        if prompt_cache_mode is None
        else str(prompt_cache_mode)
    )
    resolved_cache_namespace = (
        _prompt_cache_namespace_from_env()
        if prompt_cache_namespace is None
        else str(prompt_cache_namespace)
    )
    resolved_sdk_max_retries = 2 if sdk_max_retries is None else int(sdk_max_retries)
    if resolved_sdk_max_retries < 0:
        raise AzureModelError("sdk_max_retries must be at least 0")
    client_kwargs = {
        "api_key": api_key,
        "base_url": f"{endpoint}/openai/v1/",
        # Foreground Responses are bounded by the official Harbor task clock.
        # An SDK timeout here previously killed a live Solver request at exactly
        # poll_timeout+60 (1260s) while official task time remained. Background
        # jobs retain a transport deadline because their lifecycle is polled by
        # this client rather than held by one cancellable foreground request.
        "timeout": (resolved_poll_timeout_s + 60) if resolved_background else None,
        "max_retries": resolved_sdk_max_retries,
    }
    client = openai.OpenAI(**client_kwargs)
    async_transport = (
        None
        if resolved_websocket
        else _AsyncResponsesTransport(
            client_factory=lambda: openai.AsyncOpenAI(**client_kwargs),
        )
    )
    websocket_transport = (
        ResponsesWebSocketTransport(
            endpoint=endpoint,
            api_key=(
                api_key
                if bearer_token_provider is None and deadline_bearer_token_provider is None
                else None
            ),
            bearer_token_provider=(
                bearer_token_provider
                if deadline_bearer_token_provider is None
                else None
            ),
            deadline_bearer_token_provider=deadline_bearer_token_provider,
            request_timeout_s=resolved_poll_timeout_s,
            persist_completed_connection=resolved_websocket_persistent,
        )
        if resolved_websocket else None
    )

    return AzureModelCallable(
        client=client,
        async_transport=async_transport,
        websocket_transport=websocket_transport,
        deployment=deployment,
        effort=effort,
        role=role,
        prompt_cache_mode=resolved_cache_mode,
        prompt_cache_namespace=resolved_cache_namespace,
        responses_background=resolved_background,
        responses_websocket=resolved_websocket,
        poll_interval_s=resolved_poll_interval_s,
        poll_timeout_s=resolved_poll_timeout_s,
        max_retries=resolved_max_retries,
        backoff_base_s=resolved_backoff_base_s,
        backoff_cap_s=resolved_backoff_cap_s,
        backoff_max_total_s=resolved_backoff_max_total_s,
        rate_limiter=get_rate_limiter_for_deployment(deployment, resolved_max_rpm),
        budget_guard=budget_guard,
    )


class AzureModelCallable:
    """A ``ModelCallable`` wrapping one strict Azure provider transport.

    Transient failures (HTTP 429/5xx, SDK connection errors, or a
    background job that ends with a retryable error code) are retried in
    place with exponential backoff + jitter via ``_retry_call`` — see
    :func:`is_retryable_azure_error` for the exact classification. Every
    other failure (auth, bad request, content filter, an unrecognized job
    error code) raises :class:`AzureModelError` on the first attempt with no
    retry.
    """

    def __init__(
        self,
        *,
        client: openai.OpenAI,
        async_transport: _AsyncResponsesTransport | None = None,
        websocket_transport: ResponsesWebSocketTransport | None = None,
        deployment: str,
        effort: str,
        role: str = "unspecified",
                prompt_cache_mode: str = "stable_prefix",
        prompt_cache_namespace: str = "aether-next-v1",
        responses_background: bool | None = None,
        responses_websocket: bool = False,
        poll_interval_s: float,
        poll_timeout_s: float,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        backoff_cap_s: float = DEFAULT_BACKOFF_CAP_S,
        backoff_max_total_s: float | None = DEFAULT_BACKOFF_MAX_TOTAL_S,
        rate_limiter: RateLimiter | None = None,
        budget_guard: ProviderBudgetGuard | None = None,
                                    sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._client = client
        self._async_transport = async_transport
        self._websocket_transport = websocket_transport
        self._deployment = deployment
        self._effort = effort
        self._role = role
        if role not in {"solver", "verifier"}:
            raise ValueError("AzureModelCallable supports only the PERSISTENT Solver or Verifier")
        if prompt_cache_mode not in {"stable_prefix", "off"}:
            raise ValueError("prompt_cache_mode must be 'stable_prefix' or 'off'")
        self._prompt_cache_mode = prompt_cache_mode
        if not prompt_cache_namespace or len(prompt_cache_namespace) > 128:
            raise ValueError("prompt_cache_namespace must be non-empty and at most 128 characters")
        self._prompt_cache_namespace = prompt_cache_namespace
        # S5 has one provider continuity treatment: Solver carries the provider's
        # previous response with the full reasoning context; Verifier is fresh.
        self._persistent_reasoning_context = "all_turns" if role == "solver" else None
        self._persistent_primary_native_tools = _PERSISTENT_PRIMARY_NATIVE_TOOLS
        self._persistent_policy_instruction = ""
        self._persistent_continuity_states: dict[tuple[str, str], dict[str, Any]] = {}
        self._persistent_continuity_pending_states: dict[tuple[str, str], dict[str, Any]] = {}
        self._persistent_native_image_observations: dict[tuple[str, str], dict[str, Any]] = {}
        self._persistent_computer_observations: dict[tuple[str, str], dict[str, Any]] = {}
        self._persistent_computer_use_scopes: set[tuple[str, str]] = set()
        self._persistent_primary_completion_modes: dict[tuple[str, str], str] = {}
        self._persistent_solver_commitment_modes: dict[tuple[str, str], str] = {}
        self._persistent_completion_disposition_modes: dict[tuple[str, str], str] = {}
        self._persistent_completion_record_modes: dict[tuple[str, str], str] = {}
        self._persistent_reality_transport_modes: dict[tuple[str, str], str] = {}
        self._persistent_reality_delta_state = RealityDeltaTransportState()
        self._persistent_hosted_tool_search_modes: dict[tuple[str, str], str] = {}
        self._persistent_hosted_tool_search_state = HostedToolSearchState()
        self._verifier_activation_continuity_state = VerifierActivationContinuityState()
        self._verifier_activation_bindings: dict[tuple[str, str], dict[str, str]] = {}
        self._persistent_continuity_lock = threading.Lock()
        self._persistent_continuity_admission_events: list[dict[str, Any]] = []
        self._responses_background = (
            _responses_background_enabled()
            if responses_background is None
            else bool(responses_background)
        )
        self._responses_websocket = bool(responses_websocket)
        if self._responses_background and self._responses_websocket:
            raise ValueError("Responses background HTTP and WebSocket modes are mutually exclusive")
        if self._responses_websocket and self._websocket_transport is None:
            raise ValueError("Responses WebSocket mode requires websocket_transport")
        self._poll_interval_s = max(1.0, poll_interval_s)
        self._poll_timeout_s = max(30.0, poll_timeout_s)
        self._max_retries = max(0, max_retries)
        self._backoff_base_s = max(0.0, backoff_base_s)
        self._backoff_cap_s = max(0.0, backoff_cap_s)
        self._backoff_max_total_s = backoff_max_total_s
        self._rate_limiter = rate_limiter
        self._budget_guard = budget_guard
        if self._budget_guard is not None:
            contract = getattr(self._budget_guard, "contract", None)
            if contract is not None and self._max_retries != contract.provider_max_retries:
                raise ValueError(
                    "budget-constrained AzureModelCallable retry control must match bound contract"
                )
        # Injectable for tests only; production callers get real time.sleep
        # / random.random via the defaults above.
        self._retry_sleep = sleep
        self._rand = rand
        self.last_call_telemetry: dict[str, Any] = {}
        self._telemetry_events: list[dict[str, Any]] = []
        self._telemetry_lock = threading.Lock()
        self._next_logical_call_id = 0
        self._run_cancellation_event: Any | None = None
        self._provider_frontier_recovery_mode = PROVIDER_FRONTIER_RECOVERY_CONTROL
        self._provider_frontier_protected_reserve_s: float | None = None
        self._provider_frontier_reserve_consumed = False

    def configure_provider_frontier_recovery(
        self, mode: str, *, protected_reserve_s: float | None
    ) -> None:
        """Bind task-local mechanical final-reserve policy for Solver WebSocket waits."""
        selected = str(mode or PROVIDER_FRONTIER_RECOVERY_CONTROL).strip().lower()
        allowed = {
            PROVIDER_FRONTIER_RECOVERY_CONTROL,
            PROVIDER_FRONTIER_RECOVERY_NO_TOOL_MAX_OUTPUT_V1,
        }
        if selected not in allowed:
            raise ValueError(f"unsupported provider frontier recovery mode: {mode}")
        if self._role != "solver":
            self._provider_frontier_recovery_mode = PROVIDER_FRONTIER_RECOVERY_CONTROL
            self._provider_frontier_protected_reserve_s = None
            return
        reserve = None if protected_reserve_s is None else float(protected_reserve_s)
        if reserve is not None and reserve <= 0:
            raise ValueError("protected provider frontier reserve must be positive")
        self._provider_frontier_recovery_mode = selected
        self._provider_frontier_protected_reserve_s = (
            reserve if selected == PROVIDER_FRONTIER_RECOVERY_NO_TOOL_MAX_OUTPUT_V1 else None
        )
        self._provider_frontier_reserve_consumed = False

    def _provider_frontier_inflight_guard(self, facts: dict[str, Any]) -> None:
        if (
            self._role != "solver"
            or self._provider_frontier_recovery_mode
            != PROVIDER_FRONTIER_RECOVERY_NO_TOOL_MAX_OUTPUT_V1
            or self._provider_frontier_reserve_consumed
        ):
            return
        reserve = self._provider_frontier_protected_reserve_s
        remaining = remaining_run_s()
        if reserve is None or remaining is None or remaining > reserve:
            return
        if facts.get("request_accepted") is not True:
            return
        if facts.get("partial_output_observed") is not True:
            return
        if facts.get("native_tool_call_observed") is not False:
            return
        # Consume the reserve interrupt before raising. The kernel may admit at
        # most one fresh Solver re-anchor; that recovery call must be allowed to
        # use the protected reserve rather than being interrupted on its first
        # reasoning/output item. The hard task deadline still bounds it.
        self._provider_frontier_reserve_consumed = True
        raise ProviderFrontierReserveReached(
            request_accepted=True,
            partial_output_observed=True,
            native_tool_call_observed=False,
            remaining_run_s=float(remaining),
            protected_reserve_s=float(reserve),
        )

    def bind_run_cancellation(self, event: Any | None) -> None:
        """Bind one task-scoped cancellation signal; no provider call occurs."""
        self._run_cancellation_event = event

    def _raise_if_run_cancelled(self) -> None:
        raise_if_run_cancelled(self._run_cancellation_event)
        raise_if_run_deadline_exceeded()

    def _responses_create(self, **kwargs: Any) -> Any:
        lifecycle_observer = kwargs.pop("_aether_lifecycle_observer", None)
        transport_started_observer = kwargs.pop("_aether_transport_started_observer", None)
        budget_reservation_observer = kwargs.pop("_aether_budget_reservation_observer", None)
        budget_input_upper_bound = kwargs.pop("_aether_budget_input_token_upper_bound", None)
        transport_timeout_s = kwargs.pop(
            "_aether_transport_timeout_s", self._poll_timeout_s
        )
        if self._budget_guard is not None:
            reservation_event = self._budget_guard.reserve(
                self._role, kwargs, input_token_upper_bound=budget_input_upper_bound,
            )
            if callable(budget_reservation_observer):
                budget_reservation_observer(dict(reservation_event))
        if callable(transport_started_observer):
            transport_started_observer()
        if self._responses_websocket:
            assert self._websocket_transport is not None
            return self._websocket_transport.call(
                dict(kwargs), timeout_s=transport_timeout_s,
                cancellation_check=self._raise_if_run_cancelled,
                lifecycle_observer=lifecycle_observer,
                inflight_guard=self._provider_frontier_inflight_guard,
            )
        if self._async_transport is not None:
            return self._async_transport.call(
                "create", cancellation_event=self._run_cancellation_event, **kwargs
            )
        return self._client.responses.create(**kwargs)

    def _settle_budget_success(
        self,
        reservation_event: Mapping[str, Any] | None,
        response: Any,
        telemetry_event: dict[str, Any],
    ) -> None:
        """Release only a v2 provisional hold backed by terminal provider usage.

        Failed/ambiguous creates never call this helper. Missing usage is not
        an error and does not release anything. Settlement failures are fatal
        because a successful provider call whose fiscal ledger is inconsistent
        must fail closed rather than continue with reopened spend headroom.
        """
        if self._budget_guard is None or reservation_event is None:
            return
        contract = getattr(self._budget_guard, "contract", None)
        if getattr(contract, "schema_version", None) != "aether.provider_budget.v2":
            return
        usage = _usage_telemetry(response)
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            telemetry_event["provider_budget_settlement_status"] = "retained_missing_usage"
            return
        settlement = self._budget_guard.settle_success(
            reservation_event, input_tokens=input_tokens, output_tokens=output_tokens,
        )
        telemetry_event.update({
            "provider_budget_settlement_status": "settled_terminal_success_usage",
            "provider_budget_settlement_aggregate_create_ordinal": settlement.get("aggregate_create_ordinal"),
            "provider_budget_settled_gbp": settlement.get("settled_gbp"),
            "provider_budget_released_provisional_gbp": settlement.get("released_provisional_gbp"),
            "provider_budget_running_reserved_gbp": settlement.get("running_reserved_gbp"),
        })

    def _responses_retrieve(self, response_id: str) -> Any:
        if self._async_transport is not None:
            return self._async_transport.call(
                "retrieve", response_id, cancellation_event=self._run_cancellation_event
            )
        return self._client.responses.retrieve(response_id)

    def _responses_cancel(self, response_id: str) -> Any:
        if self._async_transport is not None:
            return self._async_transport.call(
                "cancel", response_id, cancellation_event=self._run_cancellation_event,
                honor_cancellation=False,
            )
        return self._client.responses.cancel(response_id)

    def close_run_transport(self) -> None:
        if self._websocket_transport is not None:
            self._websocket_transport.close()
        if self._async_transport is not None:
            self._async_transport.close()
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def drain_telemetry(self) -> tuple[dict[str, Any], ...]:
        """Return and clear immutable provider-attempt telemetry receipts.

        Each row has a ``logical_call_id`` and ``attempt_ordinal``.  This
        deliberately retains failed retries as well as completed attempts; it
        is provider telemetry, not a billing estimate.
        """
        with self._telemetry_lock:
            events = tuple(self._telemetry_events)
            self._telemetry_events.clear()
            return events

    def _allocate_logical_call_id(self) -> int:
        with self._telemetry_lock:
            self._next_logical_call_id += 1
            return self._next_logical_call_id

    def _record_attempt(self, event: dict[str, Any]) -> None:
        """Atomically retain one immutable provider-attempt receipt."""
        snapshot = dict(event)
        with self._telemetry_lock:
            self.last_call_telemetry = snapshot
            self._telemetry_events.append(snapshot)

    def _record_continuity_admission_event(self, event: dict[str, Any]) -> None:
        snapshot = dict(event)
        with self._telemetry_lock:
            self._persistent_continuity_admission_events.append(snapshot)

    def drain_continuity_admission_telemetry(self) -> tuple[dict[str, Any], ...]:
        with self._telemetry_lock:
            events = tuple(self._persistent_continuity_admission_events)
            self._persistent_continuity_admission_events.clear()
            return events

    def begin_verifier_activation(
        self,
        mode: str,
        *,
        run_id: str,
        task_id: str,
        activation_id: str,
    ) -> None:
        """Bind one explicit Verifier activation continuity arm without a provider call."""
        if self._role != "verifier":
            return
        normalized = str(mode or VERIFIER_ACTIVATION_FRESH_CONTROL).strip().lower()
        if normalized not in VERIFIER_ACTIVATION_CONTINUITY_MODES:
            raise AzureModelError(
                f"unsupported Verifier activation continuity mode: {normalized!r}"
            )
        activation_key = self._verifier_activation_continuity_state.key(
            run_id=run_id, task_id=task_id, activation_id=activation_id,
        )
        scope_key = (activation_key[0], activation_key[1])
        binding = {"mode": normalized, "activation_id": activation_key[2]}
        with self._persistent_continuity_lock:
            existing = self._verifier_activation_bindings.get(scope_key)
            if existing is not None and existing != binding:
                raise AzureModelError("Verifier activation continuity binding already active")
            self._verifier_activation_bindings[scope_key] = binding

    def _verifier_activation_binding(
        self, telemetry_scope: dict[str, str | None] | None,
    ) -> dict[str, str] | None:
        if self._role != "verifier" or telemetry_scope is None:
            return None
        run_id = str(telemetry_scope.get("run_id") or "").strip()
        task_id = str(telemetry_scope.get("task_id") or "").strip()
        if not run_id or not task_id:
            return None
        with self._persistent_continuity_lock:
            binding = self._verifier_activation_bindings.get((run_id, task_id))
            return None if binding is None else dict(binding)

    def commit_verifier_activation_candidate(
        self, *, run_id: str, task_id: str, activation_id: str,
    ) -> bool:
        if self._role != "verifier":
            return False
        pending = self._verifier_activation_continuity_state.pending_identity(
            run_id=run_id, task_id=task_id, activation_id=activation_id,
        )
        if pending is None:
            return False
        committed = self._verifier_activation_continuity_state.commit_candidate(
            run_id=run_id, task_id=task_id, activation_id=activation_id,
            response_id=str(pending["response_id"]),
        )
        self._record_continuity_admission_event({
            "event_kind": "verifier_activation_continuity_admission",
            "run_id": str(run_id), "task_id": str(task_id),
            "activation_id": str(activation_id),
            "disposition": "committed",
            "response_id": committed["response_id"],
            "call_id": committed["call_id"],
        })
        return True

    def reject_verifier_activation_candidate(
        self, *, run_id: str, task_id: str, activation_id: str,
    ) -> bool:
        if self._role != "verifier":
            return False
        pending = self._verifier_activation_continuity_state.pending_identity(
            run_id=run_id, task_id=task_id, activation_id=activation_id,
        )
        if pending is None:
            return False
        rejected = self._verifier_activation_continuity_state.reject_candidate(
            run_id=run_id, task_id=task_id, activation_id=activation_id,
            response_id=str(pending["response_id"]),
        )
        if rejected:
            self._record_continuity_admission_event({
                "event_kind": "verifier_activation_continuity_admission",
                "run_id": str(run_id), "task_id": str(task_id),
                "activation_id": str(activation_id),
                "disposition": "rejected",
                "response_id": pending["response_id"],
                "call_id": pending["call_id"],
            })
        return rejected

    def end_verifier_activation(
        self, *, run_id: str, task_id: str, activation_id: str,
    ) -> None:
        if self._role != "verifier":
            return
        key = self._verifier_activation_continuity_state.key(
            run_id=run_id, task_id=task_id, activation_id=activation_id,
        )
        with self._persistent_continuity_lock:
            binding = self._verifier_activation_bindings.get((key[0], key[1]))
            if binding is not None and str(binding.get("activation_id") or "") != key[2]:
                raise AzureModelError("Verifier activation continuity end binding mismatch")
            self._verifier_activation_bindings.pop((key[0], key[1]), None)
        self._verifier_activation_continuity_state.clear_activation(
            run_id=key[0], task_id=key[1], activation_id=key[2],
        )

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int | None = None,
    ) -> str:
        return self._call(messages, max_output_tokens=max_output_tokens, telemetry_scope=None)

    def call_with_telemetry_scope(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int | None = None,
        run_id: str,
        task_id: str | None,
    ) -> str:
        """Call with immutable task/run attribution supplied by ModelHooks."""
        return self._call(
            messages,
            max_output_tokens=max_output_tokens,
            telemetry_scope={"run_id": run_id, "task_id": task_id},
        )

    def _call(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int | None,
        telemetry_scope: dict[str, str | None] | None,
    ) -> str:
        """Send *messages* and return the model's output text.

        Maps the ``messages`` list (with ``role``/``content`` dicts) to the
        Responses API ``instructions`` + ``input`` parameters via
        :func:`_split_messages`, which guarantees a non-empty ``input``, then
        drives one create+poll attempt at a time through ``_retry_call``: a
        transient failure starts a fresh attempt (a new background job —
        a failed job cannot be resumed) after a bounded, jittered backoff;
        a non-transient failure or retry exhaustion propagates the same
        :class:`AzureModelError` a caller would see without retry at all.
        """
        logical_call_id = self._allocate_logical_call_id()
        attempts = 0

        def _attempt() -> str:
            nonlocal attempts
            attempts += 1
            instructions, user_input = _split_responses_input(messages)
            if self._role == "verifier":
                return self._call_verifier_tool_once(
                    instructions,
                    user_input,
                    max_output_tokens,
                    logical_call_id=logical_call_id,
                    attempt_ordinal=attempts,
                    telemetry_scope=telemetry_scope,
                )
            return self._call_persistent_tool_once(
                instructions,
                user_input,
                max_output_tokens,
                logical_call_id=logical_call_id,
                attempt_ordinal=attempts,
                telemetry_scope=telemetry_scope,
            )

        return _retry_call(
            _attempt,
            is_retryable=is_retryable_azure_error,
            max_retries=self._max_retries,
            base_s=self._backoff_base_s,
            cap_s=self._backoff_cap_s,
            max_total_s=self._backoff_max_total_s,
            sleep=self._retry_sleep,
            rand=self._rand,
        )

    def _persistent_continuity_state(
        self, scope_key: tuple[str, str],
    ) -> dict[str, Any] | None:
        with self._persistent_continuity_lock:
            state = self._persistent_continuity_states.get(scope_key)
            return None if state is None else dict(state)

    def _drop_lost_persistent_continuity_parent(
        self, scope_key: tuple[str, str], expected: dict[str, Any],
    ) -> None:
        """Drop only the exact committed parent and its bound reality snapshot."""
        with self._persistent_continuity_lock:
            current = self._persistent_continuity_states.get(scope_key)
            if current is None:
                return
            if dict(current) != dict(expected):
                raise AzureModelError("persistent_continuity_reanchor_parent_changed")
            self._persistent_continuity_states.pop(scope_key, None)
        self._persistent_reality_delta_state.clear_scope(
            run_id=scope_key[0], task_id=scope_key[1]
        )
        self._persistent_hosted_tool_search_state.clear_scope(
            run_id=scope_key[0], task_id=scope_key[1]
        )

    def _persistent_pending_continuity_state(
        self, scope_key: tuple[str, str],
    ) -> dict[str, Any] | None:
        with self._persistent_continuity_lock:
            state = self._persistent_continuity_pending_states.get(scope_key)
            return None if state is None else dict(state)

    def set_reality_transport_mode(
        self, mode: str, *, run_id: str, task_id: str,
    ) -> None:
        """Select a default-off Solver reality transport for one task scope.

        This changes only transport of the already-projected PERSISTENT snapshot.  It
        never selects a different projection or mutates canonical PERSISTENT custody.
        """
        if self._role != "solver":
            return
        normalized = str(mode or PERSISTENT_REALITY_TRANSPORT_CONTROL).strip().lower()
        if normalized not in PERSISTENT_REALITY_TRANSPORT_MODES:
            raise AzureModelError(f"unsupported PERSISTENT reality transport mode: {normalized!r}")
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            self._persistent_reality_transport_modes[key] = normalized

    def _reality_transport_mode(self, scope_key: tuple[str, str]) -> str:
        with self._persistent_continuity_lock:
            return self._persistent_reality_transport_modes.get(
                scope_key, PERSISTENT_REALITY_TRANSPORT_CONTROL
            )

    def set_hosted_tool_search_mode(
        self, mode: str, *, run_id: str, task_id: str,
    ) -> None:
        """Select the default-off provider-hosted Solver tool-search treatment."""
        if self._role != "solver":
            return
        normalized = str(mode or PERSISTENT_HOSTED_TOOL_SEARCH_CONTROL).strip().lower()
        if normalized not in PERSISTENT_HOSTED_TOOL_SEARCH_MODES:
            raise AzureModelError(
                f"unsupported PERSISTENT hosted tool search mode: {normalized!r}"
            )
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            self._persistent_hosted_tool_search_modes[key] = normalized

    def _hosted_tool_search_mode(self, scope_key: tuple[str, str]) -> str:
        with self._persistent_continuity_lock:
            return self._persistent_hosted_tool_search_modes.get(
                scope_key, PERSISTENT_HOSTED_TOOL_SEARCH_CONTROL
            )

    @staticmethod
    def _parse_projected_context_boundary(
        user_input: str | list[dict[str, str]],
    ) -> tuple[dict[str, Any], str]:
        if isinstance(user_input, str):
            content = user_input
            carrier = "string"
        elif (
            isinstance(user_input, list)
            and len(user_input) == 1
            and isinstance(user_input[0], dict)
            and set(user_input[0]) == {"role", "content"}
            and str(user_input[0].get("role") or "") == "user"
            and isinstance(user_input[0].get("content"), str)
        ):
            content = str(user_input[0]["content"])
            carrier = "single_user_message"
        else:
            raise AzureModelError(
                "delta-only PERSISTENT reality transport requires one exact [context_packet] boundary"
            )
        if not content.startswith(_PERSISTENT_CONTEXT_PACKET_PREFIX):
            raise AzureModelError(
                "delta-only PERSISTENT reality transport requires one exact [context_packet] boundary"
            )
        raw = content[len(_PERSISTENT_CONTEXT_PACKET_PREFIX):]
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AzureModelError("delta-only PERSISTENT context packet is invalid JSON") from exc
        if not isinstance(value, dict):
            raise AzureModelError("delta-only PERSISTENT context packet must be a JSON object")
        canonical = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str,
        )
        if raw != canonical:
            raise AzureModelError(
                "delta-only PERSISTENT context packet is not the canonical kernel serialization"
            )
        return value, carrier

    def _prepare_reality_transport(
        self,
        user_input: str | list[dict[str, str]],
        *,
        scope_key: tuple[str, str],
        previous: dict[str, Any] | None,
    ) -> tuple[str | list[dict[str, str]], PreparedRealityTransport | None]:
        mode = self._reality_transport_mode(scope_key)
        if mode == PERSISTENT_REALITY_TRANSPORT_CONTROL:
            return user_input, None
        if mode != PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1:
            raise AzureModelError(f"unsupported PERSISTENT reality transport mode: {mode}")
        snapshot, carrier = self._parse_projected_context_boundary(user_input)
        prepared = self._persistent_reality_delta_state.prepare(
            snapshot, run_id=scope_key[0], task_id=scope_key[1],
            previous_response_id=(
                None if previous is None else str(previous.get("response_id") or "") or None
            ),
        )
        # The treatment begins only on a healthy continuation. First turns and
        # explicit/provider-loss re-anchors preserve the incumbent context packet
        # byte-for-byte so representation drift cannot confound the causal arm.
        if prepared.mode != PERSISTENT_REALITY_DELTA_MODE:
            return user_input, prepared
        rendered = _PERSISTENT_CONTEXT_DELTA_PREFIX + json.dumps(
            prepared.envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        )
        transport_input: str | list[dict[str, str]]
        if carrier == "string":
            transport_input = rendered
        elif carrier == "single_user_message":
            transport_input = [{"role": "user", "content": rendered}]
        else:  # pragma: no cover - parser returns only the two exact carriers.
            raise AzureModelError("delta-only PERSISTENT reality transport carrier drift")
        return transport_input, prepared

    def set_primary_completion_mode(
        self, mode: str, *, run_id: str, task_id: str,
    ) -> None:
        """Bind mechanically legal completion controls for one Solver scope.

        This narrows only completion protocol actions. Ordinary task actions are
        untouched. The runtime sets the mode from exact current-generation
        review state before each Solver call.
        """
        if self._role != "solver":
            return
        normalized = str(mode or "").strip()
        if normalized not in {"finish_intent_only", "finish_only"}:
            raise AzureModelError(f"unsupported primary completion mode: {normalized!r}")
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            self._persistent_primary_completion_modes[key] = normalized

    def set_solver_commitment_mode(
        self, mode: str, *, run_id: str, task_id: str,
    ) -> None:
        """Select the default-off provider-visible Solver commitment schema for one scope."""
        if self._role != "solver":
            return
        normalized = str(mode or "").strip().lower()
        if normalized not in {"control", "commitment_v1"}:
            raise AzureModelError(f"unsupported solver commitment mode: {normalized!r}")
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            self._persistent_solver_commitment_modes[key] = normalized

    def set_completion_disposition_mode(
        self, mode: str, *, run_id: str, task_id: str,
    ) -> None:
        """Select the default-off provider-visible final-finding disposition schema."""
        if self._role != "solver":
            return
        normalized = str(mode or "").strip().lower()
        if normalized not in {"control", "completion_disposition_v1"}:
            raise AzureModelError(f"unsupported completion disposition mode: {normalized!r}")
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            self._persistent_completion_disposition_modes[key] = normalized

    def set_completion_record_mode(
        self, mode: str, *, run_id: str, task_id: str,
    ) -> None:
        """Hide or expose the structured completion-record control for one Solver scope.

        ``off`` (the runtime default) removes ``update_completion_record`` from the
        provider-native tool surface; ``v1`` advertises it. The kernel still
        mechanically validates either choice, so a hidden control can never disable
        the runtime's checks.
        """
        if self._role != "solver":
            return
        normalized = str(mode or "").strip().lower()
        if normalized not in SUPPORTED_COMPLETION_RECORD_MODES:
            raise AzureModelError(f"unsupported completion record mode: {normalized!r}")
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            self._persistent_completion_record_modes[key] = normalized

    def _primary_provider_tools_for_scope(
        self, scope_key: tuple[str, str] | None,
    ) -> tuple[list[dict[str, Any]], str]:
        mode = "inspect_or_finish"
        commitment_mode = "control"
        disposition_mode = "control"
        completion_record_mode = COMPLETION_RECORD_V1
        if scope_key is not None:
            with self._persistent_continuity_lock:
                mode = self._persistent_primary_completion_modes.get(scope_key, mode)
                commitment_mode = self._persistent_solver_commitment_modes.get(scope_key, commitment_mode)
                disposition_mode = self._persistent_completion_disposition_modes.get(scope_key, disposition_mode)
                completion_record_mode = self._persistent_completion_record_modes.get(
                    scope_key, completion_record_mode
                )
        if commitment_mode == "commitment_v1" and disposition_mode == "completion_disposition_v1":
            selected_tools = _PERSISTENT_PRIMARY_NATIVE_TOOLS_COMMITMENT_AND_DISPOSITION_V1
        elif commitment_mode == "commitment_v1":
            selected_tools = _PERSISTENT_PRIMARY_NATIVE_TOOLS_COMMITMENT_V1
        elif disposition_mode == "completion_disposition_v1":
            selected_tools = _PERSISTENT_PRIMARY_NATIVE_TOOLS_COMPLETION_DISPOSITION_V1
        else:
            selected_tools = self._persistent_primary_native_tools
        tools = list(selected_tools)
        if mode == "finish_intent_only":
            tools = [tool for tool in tools if str(tool.get("name") or "") != "finish"]
        elif mode == "finish_only":
            tools = [tool for tool in tools if str(tool.get("name") or "") != "finish_intent"]
        if completion_record_mode == COMPLETION_RECORD_OFF:
            tools = [
                tool for tool in tools
                if str(tool.get("name") or "") != "update_completion_record"
            ]
        return tools, mode

    def set_computer_use_available(
        self, available: bool, *, run_id: str, task_id: str,
    ) -> None:
        if self._role != "solver":
            return
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            if available:
                self._persistent_computer_use_scopes.add(key)
            else:
                self._persistent_computer_use_scopes.discard(key)

    def _computer_use_available(self, scope_key: tuple[str, str] | None) -> bool:
        if scope_key is None:
            return False
        with self._persistent_continuity_lock:
            return scope_key in self._persistent_computer_use_scopes

    def stage_computer_observation(
        self, *, screenshot_bytes: bytes, media_type: str, screenshot_sha256: str,
        source_receipt_id: str, action: Mapping[str, Any], run_id: str, task_id: str,
    ) -> bool:
        """Bind one fresh post-computer-action screenshot to the committed call."""
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        raw = bytes(screenshot_bytes)
        media = str(media_type or "").strip().lower()
        digest = str(screenshot_sha256 or "").strip().lower()
        if media not in _PERSISTENT_NATIVE_IMAGE_MEDIA_TYPES or hashlib.sha256(raw).hexdigest() != digest:
            raise AzureModelError("persistent_computer_screenshot_identity_invalid")
        with self._persistent_continuity_lock:
            state = self._persistent_continuity_states.get(key)
            if state is None or state.get("call_type") != "computer_call":
                return False
            if key in self._persistent_continuity_pending_states:
                raise AzureModelError("persistent_computer_staging_pending_candidate_exists")
            if key in self._persistent_computer_observations:
                raise AzureModelError("persistent_computer_observation_already_staged")
            self._persistent_computer_observations[key] = {
                "screenshot_bytes": raw, "media_type": media,
                "screenshot_sha256": digest, "screenshot_bytes_count": len(raw),
                "source_receipt_id": str(source_receipt_id or ""),
                "action": dict(action or {}),
            }
        return True

    def _persistent_computer_observation(
        self, scope_key: tuple[str, str] | None,
    ) -> dict[str, Any] | None:
        if scope_key is None:
            return None
        with self._persistent_continuity_lock:
            row = self._persistent_computer_observations.get(scope_key)
            return None if row is None else dict(row)

    def stage_native_image_observation(
        self,
        *,
        image_bytes: bytes,
        media_type: str,
        artifact_sha256: str,
        artifact_path: str,
        source_receipt_id: str,
        run_id: str,
        task_id: str,
    ) -> bool:
        """Stage one exact image for the next accepted stateful PERSISTENT continuation.

        Only the selected ``previous_response`` PERSISTENT Solver route is admitted in
        V1. No provider call occurs here. Raw bytes are task-scoped memory only.
        """
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        raw = bytes(image_bytes)
        media = str(media_type or "").strip().lower()
        digest = str(artifact_sha256 or "").strip().lower()
        if media not in _PERSISTENT_NATIVE_IMAGE_MEDIA_TYPES:
            return False
        if hashlib.sha256(raw).hexdigest() != digest:
            raise AzureModelError("persistent_native_image_staging_sha256_mismatch")
        with self._persistent_continuity_lock:
            if key not in self._persistent_continuity_states:
                return False
            if key in self._persistent_continuity_pending_states:
                raise AzureModelError("persistent_native_image_staging_pending_candidate_exists")
            if key in self._persistent_native_image_observations:
                raise AzureModelError("persistent_native_image_observation_already_staged")
            self._persistent_native_image_observations[key] = {
                "image_bytes": raw,
                "media_type": media,
                "artifact_sha256": digest,
                "artifact_bytes": len(raw),
                "artifact_path": str(artifact_path or ""),
                "source_receipt_id": str(source_receipt_id or ""),
            }
        return True

    def _persistent_native_image_observation(
        self, scope_key: tuple[str, str] | None,
    ) -> dict[str, Any] | None:
        if scope_key is None:
            return None
        with self._persistent_continuity_lock:
            row = self._persistent_native_image_observations.get(scope_key)
            return None if row is None else dict(row)

    def commit_pending_response(self, *, run_id: str, task_id: str) -> None:
        if self._role != "solver":
            return
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        reality_transport_mode = self._reality_transport_mode(key)
        with self._persistent_continuity_lock:
            pending = self._persistent_continuity_pending_states.get(key)
            if pending is None:
                raise AzureModelError("persistent_continuity_pending_candidate_missing_at_commit")
            if reality_transport_mode == PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1:
                self._persistent_reality_delta_state.commit_candidate(
                    run_id=key[0], task_id=key[1],
                    response_id=str(pending.get("response_id") or ""),
                )
            hosted_mode = self._persistent_hosted_tool_search_modes.get(
                key, PERSISTENT_HOSTED_TOOL_SEARCH_CONTROL
            )
            if hosted_mode == PERSISTENT_HOSTED_TOOL_SEARCH_V1:
                self._persistent_hosted_tool_search_state.commit_candidate(
                    run_id=key[0], task_id=key[1],
                    response_id=str(pending.get("response_id") or ""),
                )
            pending = self._persistent_continuity_pending_states.pop(key)
            previous = self._persistent_continuity_states.get(key)
            self._persistent_continuity_states[key] = dict(pending)
            consumed_native_image = self._persistent_native_image_observations.pop(key, None)
            consumed_computer_observation = self._persistent_computer_observations.pop(key, None)
        self._record_continuity_admission_event({
            "event_kind": "persistent_continuity_parent_admission",
            "provider": "azure_openai_responses",
            "deployment": self._deployment,
            "role": self._role,
            "run_id": key[0],
            "task_id": key[1],
            "persistent_continuity_mode": "previous_response",
            "persistent_continuity_parent_disposition": "committed",
            "persistent_continuity_response_id": pending.get("response_id"),
            "persistent_continuity_call_id": pending.get("call_id"),
            "persistent_continuity_previous_committed_response_id": None if previous is None else previous.get("response_id"),
            "persistent_native_image_observation_consumed": consumed_native_image is not None,
            "persistent_computer_observation_consumed": consumed_computer_observation is not None,
            "persistent_computer_screenshot_sha256": (
                None if consumed_computer_observation is None
                else consumed_computer_observation.get("screenshot_sha256")
            ),
            "persistent_native_image_artifact_sha256": (
                None if consumed_native_image is None
                else consumed_native_image.get("artifact_sha256")
            ),
        })

    def reject_pending_response(self, *, run_id: str, task_id: str) -> None:
        if self._role != "solver":
            return
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        reality_transport_mode = self._reality_transport_mode(key)
        with self._persistent_continuity_lock:
            pending = self._persistent_continuity_pending_states.get(key)
            previous = self._persistent_continuity_states.get(key)
            if pending is not None and reality_transport_mode == PERSISTENT_REALITY_TRANSPORT_DELTA_ONLY_V1:
                self._persistent_reality_delta_state.reject_candidate(
                    run_id=key[0], task_id=key[1],
                    response_id=str(pending.get("response_id") or ""),
                )
            hosted_mode = self._persistent_hosted_tool_search_modes.get(
                key, PERSISTENT_HOSTED_TOOL_SEARCH_CONTROL
            )
            if pending is not None and hosted_mode == PERSISTENT_HOSTED_TOOL_SEARCH_V1:
                self._persistent_hosted_tool_search_state.reject_candidate(
                    run_id=key[0], task_id=key[1],
                    response_id=str(pending.get("response_id") or ""),
                )
            pending = self._persistent_continuity_pending_states.pop(key, None)
        if pending is None:
            return
        self._record_continuity_admission_event({
            "event_kind": "persistent_continuity_parent_admission",
            "provider": "azure_openai_responses",
            "deployment": self._deployment,
            "role": self._role,
            "run_id": key[0],
            "task_id": key[1],
            "persistent_continuity_mode": "previous_response",
            "persistent_continuity_parent_disposition": "rejected",
            "persistent_continuity_response_id": pending.get("response_id"),
            "persistent_continuity_call_id": pending.get("call_id"),
            "persistent_continuity_previous_committed_response_id": None if previous is None else previous.get("response_id"),
        })

    def clear_continuity_scope(self, *, run_id: str, task_id: str) -> None:
        """Release pending and committed provider-native PERSISTENT state for one run."""
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            return
        self._persistent_reality_delta_state.clear_scope(run_id=key[0], task_id=key[1])
        self._persistent_hosted_tool_search_state.clear_scope(run_id=key[0], task_id=key[1])
        with self._persistent_continuity_lock:
            self._persistent_continuity_pending_states.pop(key, None)
            self._persistent_continuity_states.pop(key, None)
            self._persistent_native_image_observations.pop(key, None)
            self._persistent_computer_observations.pop(key, None)
            self._persistent_computer_use_scopes.discard(key)
            self._persistent_primary_completion_modes.pop(key, None)
            self._persistent_solver_commitment_modes.pop(key, None)
            self._persistent_completion_disposition_modes.pop(key, None)
            self._persistent_completion_record_modes.pop(key, None)
            self._persistent_reality_transport_modes.pop(key, None)
            self._persistent_hosted_tool_search_modes.pop(key, None)

    def _prepare_persistent_continuation_request(
        self,
        request: dict[str, Any],
        *,
        user_input: str | list[dict[str, str]],
        telemetry_scope: dict[str, str | None] | None,
    ) -> tuple[
        dict[str, Any], tuple[str, str], dict[str, Any] | None,
        PreparedRealityTransport | None, str | list[dict[str, str]],
    ]:
        """Bind the Solver boundary to one previous-response and reality chain."""
        scope_key = _persistent_continuity_scope_key(telemetry_scope)
        if self._persistent_pending_continuity_state(scope_key) is not None:
            raise AzureModelError("persistent_continuity_pending_candidate_requires_admission")
        previous = self._persistent_continuity_state(scope_key)
        transport_input, reality_transport = self._prepare_reality_transport(
            user_input, scope_key=scope_key, previous=previous,
        )
        prepared = dict(request)
        prepared["store"] = True
        prepared["input"] = transport_input
        current_boundary = _responses_input_text(transport_input)
        if previous is not None:
            prepared["previous_response_id"] = str(previous["response_id"])
            if previous.get("call_type") == "computer_call":
                computer = self._persistent_computer_observation(scope_key)
                if computer is None:
                    raise AzureModelError("persistent_computer_observation_required_before_next_decision")
                encoded = base64.b64encode(bytes(computer["screenshot_bytes"])).decode("ascii")
                computer_output = {
                    "type": "computer_call_output",
                    "call_id": str(previous["call_id"]),
                    "output": {
                        "type": "computer_screenshot",
                        "image_url": f"data:{computer['media_type']};base64,{encoded}",
                        "detail": "original",
                    },
                }
                boundary_items = (
                    [dict(item) for item in transport_input if isinstance(item, dict)]
                    if isinstance(transport_input, list)
                    else [{"role": "user", "content": str(transport_input)}]
                )
                prepared["input"] = [computer_output, *boundary_items]
            else:
                native_image = self._persistent_native_image_observation(scope_key)
                prepared["input"] = [{
                    "type": "function_call_output",
                    "call_id": str(previous["call_id"]),
                    "output": _persistent_function_call_output_value(current_boundary, native_image),
                }]
        return prepared, scope_key, previous, reality_transport, transport_input

    def _stage_persistent_continuity_state(
        self,
        *,
        scope_key: tuple[str, str] | None,
        previous: dict[str, Any] | None,
        request: dict[str, Any],
        response: Any,
        output_receipt: dict[str, Any],
        reality_transport: PreparedRealityTransport | None = None,
        hosted_tool_search_observation: HostedToolSearchObservation | None = None,
    ) -> dict[str, Any]:
        if scope_key is None:
            raise AzureModelError("persistent_continuity_scope_missing")
        response_id = str(_usage_field(response, "id", "") or "")
        call_id = str(output_receipt.get("native_tool_call_id") or "")
        if not response_id or not call_id:
            raise AzureProviderOutputError(
                "provider_persistent_v0_continuity_identity_missing",
                f"response_id={bool(response_id)} call_id={bool(call_id)}",
            )
        usage = _usage_telemetry(response)
        provider_total_tokens = usage.get("total_tokens")
        if provider_total_tokens is None:
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                provider_total_tokens = input_tokens + output_tokens
        reality_staged = False
        hosted_staged = False
        try:
            if reality_transport is not None:
                self._persistent_reality_delta_state.stage_candidate(
                    reality_transport, response_id=response_id
                )
                reality_staged = True
            if hosted_tool_search_observation is not None:
                self._persistent_hosted_tool_search_state.stage_candidate(
                    run_id=scope_key[0], task_id=scope_key[1],
                    response_id=response_id,
                    observation=hosted_tool_search_observation,
                )
                hosted_staged = True
        except Exception:
            if hosted_staged:
                self._persistent_hosted_tool_search_state.reject_candidate(
                    run_id=scope_key[0], task_id=scope_key[1], response_id=response_id,
                )
            if reality_staged:
                self._persistent_reality_delta_state.reject_candidate(
                    run_id=scope_key[0], task_id=scope_key[1], response_id=response_id,
                )
            raise
        state = {
            "response_id": response_id, "call_id": call_id,
            "call_type": str(output_receipt.get("native_tool_type") or "function_call"),
            "provider_total_tokens": provider_total_tokens,
        }
        try:
            with self._persistent_continuity_lock:
                if scope_key in self._persistent_continuity_pending_states:
                    raise AzureModelError("persistent_continuity_pending_candidate_already_staged")
                self._persistent_continuity_pending_states[scope_key] = state
        except Exception:
            if hosted_staged:
                self._persistent_hosted_tool_search_state.reject_candidate(
                    run_id=scope_key[0], task_id=scope_key[1], response_id=response_id,
                )
            if reality_staged:
                self._persistent_reality_delta_state.reject_candidate(
                    run_id=scope_key[0], task_id=scope_key[1], response_id=response_id,
                )
            raise
        result = {
            "persistent_continuity_mode": "previous_response",
            "persistent_continuity_state_advanced": False,
            "persistent_continuity_candidate_staged": True,
            "persistent_continuity_previous_state_present": previous is not None,
            "persistent_continuity_response_id": response_id,
            "persistent_continuity_call_id": call_id,
        }
        if hosted_tool_search_observation is not None:
            result.update(hosted_tool_search_observation.as_telemetry())
            result["persistent_hosted_tool_search_candidate_staged"] = True
        if reality_transport is not None:
            result.update({
                "persistent_reality_transport_mode": reality_transport.mode,
                "persistent_reality_transport_base_snapshot_sha256": reality_transport.envelope.get("base_snapshot_sha256"),
                "persistent_reality_transport_result_snapshot_sha256": reality_transport.envelope.get("result_snapshot_sha256"),
                "persistent_reality_transport_set_key_count": len(reality_transport.envelope.get("set") or {}),
                "persistent_reality_transport_clear_key_count": len(reality_transport.envelope.get("clear") or []),
                "persistent_reality_transport_omitted_key_count": len(reality_transport.envelope.get("omitted_unchanged_top_level_keys") or []),
            })
        return result

    def _call_persistent_tool_once(
        self,
        instructions: str,
        user_input: str | list[dict[str, str]],
        max_output_tokens: int | None,
        *,
        logical_call_id: int,
        attempt_ordinal: int,
        telemetry_scope: dict[str, str | None] | None,
    ) -> str:
        """Run one PERSISTENT turn through one provider-native function-call boundary.

        This transport is deliberately only an encoding/admission boundary.
        The provider never executes the function; its strict arguments are
        returned to the existing PERSISTENT parser and kernel, which preserve the
        one-action -> observation -> next-decision causal loop.
        """
        prepared_instructions = "\n\n".join(part for part in (
            str(instructions).strip(),
            "[persistent_turn_contract] " + self._persistent_policy_instruction
            if self._persistent_policy_instruction else "",
            "[native_action_boundary] " + _PERSISTENT_PRIMARY_NATIVE_TOOL_RESPONSE_INSTRUCTION,
        ) if part)
        reasoning_request: dict[str, Any] = {"effort": self._effort}
        if self._persistent_reasoning_context is not None:
            reasoning_request["context"] = self._persistent_reasoning_context
        request_scope_key = _persistent_continuity_scope_key(telemetry_scope)
        provider_tools, primary_completion_mode = self._primary_provider_tools_for_scope(
            request_scope_key
        )
        hosted_tool_search_mode = self._hosted_tool_search_mode(request_scope_key)
        hosted_tool_search_catalogue: dict[str, dict[str, Any]] = {}
        if hosted_tool_search_mode == PERSISTENT_HOSTED_TOOL_SEARCH_V1:
            provider_tools, hosted_tool_search_catalogue = hosted_provider_tools(provider_tools)
        if self._computer_use_available(request_scope_key):
            provider_tools.append({"type": "computer"})
        request: dict[str, Any] = {
            "model": self._deployment,
            "instructions": prepared_instructions,
            "input": user_input,
            "reasoning": reasoning_request,
            "tools": provider_tools,
            "tool_choice": "required",
            "parallel_tool_calls": False,
            "max_tool_calls": (
                2 if hosted_tool_search_mode == PERSISTENT_HOSTED_TOOL_SEARCH_V1 else 1
            ),
            "background": bool(self._responses_background),
        }
        if max_output_tokens is not None:
            request["max_output_tokens"] = int(max_output_tokens)
        if self._prompt_cache_mode == "stable_prefix":
            request["prompt_cache_key"] = _stable_prompt_cache_key(
                deployment=self._deployment,
                role=self._role,
                namespace=self._prompt_cache_namespace,
            )
        request, continuity_scope_key, continuity_previous, reality_transport, transport_input = (
            self._prepare_persistent_continuation_request(
                request, user_input=user_input, telemetry_scope=telemetry_scope,
            )
        )
        current_boundary = _responses_input_text(transport_input)
        current_boundary_sha256 = hashlib.sha256(
            current_boundary.encode("utf-8")
        ).hexdigest()
        rendered_request_input = _responses_input_text(request["input"])
        request_input_items = (
            [dict(item) for item in request["input"] if isinstance(item, dict)]
            if isinstance(request.get("input"), list) else []
        )
        function_outputs = [
            item for item in request_input_items
            if str(item.get("type") or "") == "function_call_output"
        ]
        function_output_hashes = [
            _function_call_output_sha256(item.get("output"))
            for item in function_outputs
        ]
        function_output_boundary_hashes = [
            hashlib.sha256(
                _function_call_output_boundary_text(item.get("output")).encode("utf-8")
            ).hexdigest()
            for item in function_outputs
        ]
        direct_boundary_match = (
            hashlib.sha256(rendered_request_input.encode("utf-8")).hexdigest()
            == current_boundary_sha256
        )
        boundary_function_output_matches = sum(
            value == current_boundary_sha256 for value in function_output_boundary_hashes
        )
        native_image_observation = self._persistent_native_image_observation(continuity_scope_key)
        native_image_evidence = (
            {}
            if native_image_observation is None
            else {
                "persistent_native_image_artifact_sha256": native_image_observation.get("artifact_sha256"),
                "persistent_native_image_artifact_bytes": native_image_observation.get("artifact_bytes"),
                "persistent_native_image_media_type": native_image_observation.get("media_type"),
                "persistent_native_image_source_receipt_id": native_image_observation.get("source_receipt_id"),
                "persistent_native_image_artifact_path": native_image_observation.get("artifact_path"),
                "persistent_native_image_raw_bytes_persisted_in_telemetry": False,
            }
        )
        prior_call_id = (
            "" if continuity_previous is None
            else str(continuity_previous.get("call_id") or "")
        )

        event: dict[str, Any] = {
            "event_kind": "provider_attempt",
            "logical_call_id": logical_call_id,
            "attempt_ordinal": attempt_ordinal,
            "provider": "azure_openai_responses",
            "deployment": self._deployment,
            "role": self._role,
            "responses_background": bool(self._responses_background),
            "responses_websocket": bool(self._responses_websocket),
            "provider_transport_mode": ("websocket" if self._responses_websocket else "background_http" if self._responses_background else "foreground_http"),
            "status": "in_progress",
            "attempt_phase": "create",
            "instructions_chars": len(prepared_instructions),
            "input_chars": len(rendered_request_input),
            "instructions_sha256": hashlib.sha256(prepared_instructions.encode("utf-8")).hexdigest(),
            "input_sha256": hashlib.sha256(rendered_request_input.encode("utf-8")).hexdigest(),
            "max_output_tokens": max_output_tokens,
            "structured_output_mode": "persistent_v0_direct_native_tools",
            "native_tool_name": "direct_action_set",
            "persistent_primary_completion_mode": primary_completion_mode,
            "persistent_primary_provider_tool_names": [
                str(tool.get("name") or tool.get("type") or "") for tool in provider_tools
            ],
            "persistent_reasoning_context_requested": self._persistent_reasoning_context,
            "persistent_primary_provider_schema_sha256": hashlib.sha256(
                json.dumps(
                    provider_tools,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest(),
            "persistent_continuity_mode": "previous_response",
            "persistent_continuity_previous_state_present": continuity_previous is not None,
            "persistent_continuity_previous_response_id": (
                None if continuity_previous is None else continuity_previous.get("response_id")
            ),
            "persistent_continuity_store": request.get("store"),
            "persistent_continuity_include": request.get("include"),
            "persistent_continuity_request_previous_response_id": request.get("previous_response_id"),
            "persistent_continuity_request_input_item_count": (
                len(request["input"]) if isinstance(request.get("input"), list) else 1
            ),
            "persistent_continuity_request_input_item_types": [
                str(item.get("type") or ("message:" + str(item.get("role") or "unknown")))
                for item in request_input_items
            ],
            "persistent_continuity_request_function_call_output_count": len(function_outputs),
            "persistent_continuity_request_function_call_output_call_ids": [
                str(item.get("call_id") or "") for item in function_outputs
            ],
            "persistent_continuity_request_function_call_output_sha256": function_output_hashes,
            "persistent_continuity_request_function_call_output_boundary_sha256": function_output_boundary_hashes,
            **native_image_evidence,
            "persistent_native_image_observation_count": int(native_image_observation is not None),
            "persistent_continuity_current_boundary_sha256": current_boundary_sha256,
            "persistent_continuity_current_boundary_direct_input_match": direct_boundary_match,
            "persistent_continuity_current_boundary_function_output_match_count": boundary_function_output_matches,
            "persistent_continuity_expected_prior_call_id": prior_call_id or None,
            "persistent_continuity_prior_call_id_match_count": sum(
                str(item.get("call_id") or "") == prior_call_id
                for item in function_outputs
            ) if prior_call_id else 0,
            "max_tool_calls_requested": int(request["max_tool_calls"]),
            "parallel_tool_calls": False,
            "prompt_cache_key_mode": self._prompt_cache_mode,
            "prompt_cache_namespace": self._prompt_cache_namespace,
            "prompt_cache_retention": None,
            "usage_status": "unmeasured",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "cache_write_tokens": None,
            "reasoning_tokens": None,
            "persistent_continuity_reanchor_attempted": False,
            "persistent_continuity_reanchor_succeeded": False,
            "persistent_continuity_reanchor_reason": None,
            "persistent_continuity_reanchor_create_count": 1,
            "persistent_continuity_reanchor_from_response_id": None,
            "persistent_continuity_reanchor_from_call_id": None,
            "persistent_continuity_reanchor_blocked_reason": None,
        }
        if telemetry_scope is not None:
            event.update(telemetry_scope)
        if hosted_tool_search_mode == PERSISTENT_HOSTED_TOOL_SEARCH_V1:
            catalogue_id = hosted_tool_search_catalogue_identity(hosted_tool_search_catalogue)
            event.update({
                "persistent_hosted_tool_search_mode": PERSISTENT_HOSTED_TOOL_SEARCH_V1,
                "persistent_hosted_tool_search_declared_deferred_tool_count": catalogue_id["tool_count"],
                "persistent_hosted_tool_search_catalogue_sha256": catalogue_id["sha256"],
                "persistent_hosted_tool_search_committed_loaded_names_before_request": list(
                    self._persistent_hosted_tool_search_state.committed_loaded_names(
                        run_id=request_scope_key[0], task_id=request_scope_key[1]
                    )
                ),
                "persistent_hosted_tool_search_completion_pinned": True,
            })
        _capture_finalized_provider_request(event, request)
        _append_provider_lifecycle(
            stage="request_prepared", role=self._role, logical_call_id=logical_call_id,
            attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
            transport_mode=str(event["provider_transport_mode"]), create_ordinal=1,
        )
        started = time.monotonic()
        response: Any | None = None
        response_id: str | None = None
        budget_reservations: list[dict[str, Any]] = []
        transport_started = False
        def mark_transport_started() -> None:
            nonlocal transport_started
            transport_started = True
        try:
            poll_timeout_s = _remaining_verifier_poll_timeout_s(
                self._poll_timeout_s, minimum_reserve_s=self._poll_interval_s + 1.0,
            )
            event["effective_poll_timeout_s"] = round(poll_timeout_s, 3)
            self._raise_if_run_cancelled()
            if self._rate_limiter is not None:
                self._rate_limiter.acquire()
            self._raise_if_run_cancelled()
            _observe_request_anatomy(
                role="primary", request=request,
                run_id=str((telemetry_scope or {}).get("run_id") or ""),
                task_id=str((telemetry_scope or {}).get("task_id") or ""),
                turn_index=logical_call_id,
                call_id=(
                    f"logical-{logical_call_id}:attempt-{attempt_ordinal}:create-1"
                ),
            )
            try:
                _append_provider_lifecycle(
                    stage="dispatch_invocation_started", role=self._role, logical_call_id=logical_call_id,
                    attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                    transport_mode=str(event["provider_transport_mode"]), create_ordinal=1,
                )
                def lifecycle_observer(stage: str, detail: dict[str, Any]) -> None:
                    _append_provider_lifecycle(
                        stage=stage, role=self._role, logical_call_id=logical_call_id,
                        attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                        transport_mode=str(event["provider_transport_mode"]),
                        status=str(detail.get("event_type") or "") or None, create_ordinal=1,
                    )
                budget_input_upper_bound = None
                if self._budget_guard is not None:
                    budget_input_upper_bound = serialized_request_token_upper_bound(request)
                    if continuity_previous is not None:
                        prior_total_tokens = continuity_previous.get("provider_total_tokens")
                        if not isinstance(prior_total_tokens, int) or prior_total_tokens <= 0:
                            raise AzureModelError(
                                "budgeted Solver continuation lacks prior provider token usage"
                            )
                        budget_input_upper_bound += prior_total_tokens
                response = self._responses_create(
                    _aether_lifecycle_observer=lifecycle_observer,
                    _aether_transport_started_observer=mark_transport_started,
                    _aether_budget_reservation_observer=budget_reservations.append,
                    _aether_budget_input_token_upper_bound=budget_input_upper_bound,
                    _aether_transport_timeout_s=poll_timeout_s,
                    **request,
                )
                _append_provider_lifecycle(
                    stage="provider_call_returned", role=self._role, logical_call_id=logical_call_id,
                    attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                    transport_mode=str(event["provider_transport_mode"]),
                    response_id=str(getattr(response, "id", "") or "") or None,
                    status=str(getattr(response, "status", "") or "") or None, create_ordinal=1,
                )
            except Exception as create_exc:
                if not (
                    continuity_previous is not None
                    and _is_previous_response_not_found_error(create_exc)
                ):
                    raise
                event.update({
                    "persistent_continuity_reanchor_attempted": True,
                    "persistent_continuity_reanchor_reason": "previous_response_not_found",
                    "persistent_continuity_reanchor_create_count": 2,
                    "persistent_continuity_reanchor_from_response_id": continuity_previous.get("response_id"),
                    "persistent_continuity_reanchor_from_call_id": continuity_previous.get("call_id"),
                    "persistent_continuity_reanchor_failed_request_input_sha256": event.get("input_sha256"),
                    "persistent_continuity_reanchor_failed_request_previous_response_id": request.get("previous_response_id"),
                    "persistent_continuity_reanchor_failed_request_function_call_output_count": len(function_outputs),
                    "persistent_continuity_reanchor_failed_request_function_call_output_call_ids": [
                        str(item.get("call_id") or "") for item in function_outputs
                    ],
                })
                computer_observation = self._persistent_computer_observation(continuity_scope_key)
                if computer_observation is not None:
                    event["persistent_continuity_reanchor_blocked_reason"] = "computer_screenshot_staged"
                    raise AzureModelError(
                        "persistent_continuity_reanchor_computer_screenshot_requires_lossless_binding"
                    ) from create_exc
                if native_image_observation is not None:
                    event["persistent_continuity_reanchor_blocked_reason"] = "native_image_staged"
                    raise AzureModelError(
                        "persistent_continuity_reanchor_native_image_requires_lossless_binding"
                    ) from create_exc
                self._drop_lost_persistent_continuity_parent(
                    continuity_scope_key, continuity_previous,
                )
                request = dict(request)
                request.pop("previous_response_id", None)
                continuity_previous = None
                transport_input, reality_transport = self._prepare_reality_transport(
                    user_input, scope_key=continuity_scope_key, previous=None,
                )
                request["input"] = transport_input
                current_boundary = _responses_input_text(transport_input)
                current_boundary_sha256 = hashlib.sha256(
                    current_boundary.encode("utf-8")
                ).hexdigest()
                rendered_request_input = _responses_input_text(request["input"])
                request_input_items = (
                    [dict(item) for item in request["input"] if isinstance(item, dict)]
                    if isinstance(request.get("input"), list) else []
                )
                event.update({
                    "input_chars": len(rendered_request_input),
                    "input_sha256": hashlib.sha256(rendered_request_input.encode("utf-8")).hexdigest(),
                    "persistent_continuity_previous_state_present": False,
                    "persistent_continuity_previous_response_id": None,
                    "persistent_continuity_request_previous_response_id": None,
                    "persistent_continuity_request_input_item_count": (
                        len(request["input"]) if isinstance(request.get("input"), list) else 1
                    ),
                    "persistent_continuity_request_input_item_types": [
                        str(item.get("type") or ("message:" + str(item.get("role") or "unknown")))
                        for item in request_input_items
                    ],
                    "persistent_continuity_request_function_call_output_count": 0,
                    "persistent_continuity_request_function_call_output_call_ids": [],
                    "persistent_continuity_request_function_call_output_sha256": [],
                    "persistent_continuity_request_function_call_output_boundary_sha256": [],
                    "persistent_continuity_current_boundary_direct_input_match": True,
                    "persistent_continuity_current_boundary_function_output_match_count": 0,
                    "persistent_continuity_expected_prior_call_id": None,
                    "persistent_continuity_prior_call_id_match_count": 0,
                })
                _capture_finalized_provider_request(event, request)
                _observe_request_anatomy(
                    role="primary", request=request,
                    run_id=str((telemetry_scope or {}).get("run_id") or ""),
                    task_id=str((telemetry_scope or {}).get("task_id") or ""),
                    turn_index=logical_call_id,
                    call_id=(
                        f"logical-{logical_call_id}:attempt-{attempt_ordinal}:create-2"
                    ),
                )
                _append_provider_lifecycle(
                    stage="dispatch_invocation_started", role=self._role, logical_call_id=logical_call_id,
                    attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                    transport_mode=str(event["provider_transport_mode"]), create_ordinal=2,
                )
                def reanchor_lifecycle_observer(stage: str, detail: dict[str, Any]) -> None:
                    _append_provider_lifecycle(
                        stage=stage, role=self._role, logical_call_id=logical_call_id,
                        attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                        transport_mode=str(event["provider_transport_mode"]),
                        status=str(detail.get("event_type") or "") or None, create_ordinal=2,
                    )
                reanchor_budget_input_upper_bound = (
                    serialized_request_token_upper_bound(request)
                    if self._budget_guard is not None else None
                )
                response = self._responses_create(
                    _aether_lifecycle_observer=reanchor_lifecycle_observer,
                    _aether_transport_started_observer=mark_transport_started,
                    _aether_budget_reservation_observer=budget_reservations.append,
                    _aether_budget_input_token_upper_bound=reanchor_budget_input_upper_bound,
                    _aether_transport_timeout_s=poll_timeout_s,
                    **request,
                )
                _append_provider_lifecycle(
                    stage="provider_call_returned", role=self._role, logical_call_id=logical_call_id,
                    attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                    transport_mode=str(event["provider_transport_mode"]),
                    response_id=str(getattr(response, "id", "") or "") or None,
                    status=str(getattr(response, "status", "") or "") or None, create_ordinal=2,
                )
                event["persistent_continuity_reanchor_succeeded"] = True
            raw_response_id = getattr(response, "id", None)
            if not raw_response_id:
                raise AzureModelError("responses.create returned no response id")
            response_id = str(raw_response_id)
            event["job_id"] = response_id
            event["persistent_remote_response_inventory_observed"] = request.get("store") is True
            event["persistent_remote_response_inventory_response_id"] = response_id if request.get("store") is True else None
            event["attempt_phase"] = "poll"
            elapsed = 0.0
            while getattr(response, "status", None) in ("queued", "in_progress"):
                self._raise_if_run_cancelled()
                if elapsed >= poll_timeout_s:
                    raise AzureModelError(
                        f"provider response {response_id} timed out after {elapsed:.0f}s "
                        f"(status={getattr(response, 'status', None)})"
                    )
                time.sleep(self._poll_interval_s)
                elapsed += self._poll_interval_s
                self._raise_if_run_cancelled()
                try:
                    response = self._responses_retrieve(response_id)
                except Exception as exc:
                    raise AzureModelError(
                        f"responses.retrieve failed for {response_id}: {exc}"
                    ) from exc
            status = getattr(response, "status", None)
            event.update({
                "attempt_phase": "terminal",
                "job_status": str(status),
                "poll_elapsed_s": elapsed,
                **_usage_telemetry(response),
            })
            if os.environ.get("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT") == "1":
                event["raw_provider_output_items"] = _raw_output_items_for_evidence(response)
            if status == "completed":
                self._settle_budget_success(
                    budget_reservations[-1] if budget_reservations else None, response, event,
                )
                event.update(_provider_output_item_census(response))
                response_reasoning = _usage_field(response, "reasoning")
                effective_context = _usage_field(response_reasoning, "context")
                event["persistent_reasoning_context_effective"] = effective_context
                if self._persistent_reasoning_context is None:
                    context_status = "not_requested"
                elif effective_context is None:
                    context_status = "unreported"
                elif str(effective_context) == self._persistent_reasoning_context:
                    context_status = "matched"
                else:
                    context_status = "mismatch"
                event["persistent_reasoning_context_effective_status"] = context_status
                event["persistent_reasoning_context_status"] = context_status
                hosted_tool_search_observation: HostedToolSearchObservation | None = None
                if hosted_tool_search_mode == PERSISTENT_HOSTED_TOOL_SEARCH_V1:
                    try:
                        hosted_tool_search_observation = validate_hosted_response(
                            response,
                            catalogue=hosted_tool_search_catalogue,
                            committed_loaded_names=(
                                self._persistent_hosted_tool_search_state.committed_loaded_names(
                                    run_id=request_scope_key[0], task_id=request_scope_key[1]
                                )
                            ),
                        )
                    except HostedToolSearchError as exc:
                        event["provider_output_error"] = exc.code
                        raise AzureProviderOutputError(exc.code, exc.detail) from exc
                    event.update(hosted_tool_search_observation.as_telemetry())
                try:
                    canonical, output_receipt = canonicalize_persistent_native_tool_output(
                        response,
                        allow_hosted_tool_search_metadata=(
                            hosted_tool_search_mode == PERSISTENT_HOSTED_TOOL_SEARCH_V1
                        ),
                    )
                except AzureProviderOutputError as exc:
                    event["provider_output_error"] = exc.code
                    raise
                event.update(output_receipt)
                event.update(self._stage_persistent_continuity_state(
                    scope_key=continuity_scope_key,
                    previous=continuity_previous,
                    request=request,
                    response=response,
                    output_receipt=output_receipt,
                    reality_transport=reality_transport,
                    hosted_tool_search_observation=hosted_tool_search_observation,
                ))
                event["status"] = "completed"
                return canonical
            if status == "incomplete":
                event["provider_output_error"] = "provider_output_incomplete"
                event["status"] = "incomplete"
                raise AzureProviderOutputError(
                    "provider_output_incomplete",
                    str(getattr(response, "incomplete_details", None) or ""),
                )
            error_obj = getattr(response, "error", None)
            detail = error_obj or getattr(response, "incomplete_details", None) or ""
            code = getattr(error_obj, "code", None)
            raise AzureModelError(
                f"provider response {response_id} ended with status={status}: {detail}"
            ) from _JobStatusFailure(code)
        except Exception as exc:
            last_status = str(getattr(response, "status", None) or "")
            if response_id and last_status in {"queued", "in_progress"}:
                event["provider_job_cancel_attempted"] = True
                try:
                    cancelled = self._responses_cancel(response_id)
                    cancel_status = str(getattr(cancelled, "status", None) or "")
                    event["provider_job_cancel_status"] = cancel_status
                    event["provider_job_cancel_succeeded"] = cancel_status in {
                        "cancelled", "canceled", "cancelling", "canceling",
                    }
                except Exception as cancel_exc:
                    event["provider_job_cancel_succeeded"] = False
                    event["provider_job_cancel_error_type"] = cancel_exc.__class__.__name__
                    event["provider_job_cancel_error"] = str(cancel_exc)[:1000]
            event.update({
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "error": str(exc)[:1000],
            })
            if isinstance(exc, AzureProviderOutputError):
                event["provider_output_error"] = exc.code
            if isinstance(exc, ResponsesWebSocketError):
                event["provider_terminal_failure"] = bool(exc.terminal)
                event["provider_terminal_retry_safe"] = bool(exc.retry_safe)
                event["provider_terminal_error_code"] = exc.provider_error_code
                event["provider_terminal_event_type"] = exc.event_type
                event["provider_terminal_response_id"] = exc.response_id
                event["provider_websocket_request_accepted"] = bool(exc.request_accepted)
                event["provider_websocket_acceptance_observed"] = bool(
                    exc.acceptance_observed
                )
                event["provider_websocket_acceptance_known"] = bool(
                    exc.acceptance_known
                )
                event["provider_websocket_acceptance_unknown_after_dispatch"] = bool(
                    exc.provider_acceptance_unknown_after_dispatch
                )
                event["provider_websocket_partial_output_observed"] = bool(exc.partial_output_observed)
                event["provider_websocket_native_tool_call_observed"] = bool(exc.native_tool_call_observed)
                event["provider_websocket_native_tool_execution_observed"] = (
                    exc.native_tool_execution_observed
                )
                event["provider_websocket_incomplete_reason"] = exc.incomplete_reason
                event["provider_websocket_replay_safety_reason"] = exc.replay_safety_reason
            if isinstance(exc, RunCancellationRequested):
                raise
            if exc.__class__.__name__ == "KernelRunTimeout":
                raise
            if isinstance(exc, AzureModelError):
                raise
            raise AzureModelError(f"responses native-tool call failed: {exc}") from exc
        finally:
            if (
                transport_started
                and self._responses_websocket
                and self._websocket_transport is not None
            ):
                observe = getattr(self._websocket_transport, "last_call_observability", None)
                if callable(observe):
                    event.update(observe())
            event["elapsed_s"] = round(time.monotonic() - started, 3)
            _append_provider_lifecycle(
                stage="attempt_terminal", role=self._role, logical_call_id=logical_call_id,
                attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                transport_mode=str(event.get("provider_transport_mode") or ""),
                response_id=response_id, status=str(event.get("status") or ""),
                create_ordinal=int(event.get("persistent_continuity_reanchor_create_count") or 1),
            )
            self._record_attempt(event)

    def _call_verifier_tool_once(
        self,
        instructions: str,
        user_input: str | list[dict[str, str]],
        max_output_tokens: int | None,
        *,
        logical_call_id: int,
        attempt_ordinal: int,
        telemetry_scope: dict[str, str | None] | None,
    ) -> str:
        """Run one Verifier turn through one forced native function-call boundary."""
        native_verifier_instruction = _PERSISTENT_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION
        prepared_instructions = "\n\n".join(part for part in (
            str(instructions).strip(),
            "[native_verifier_boundary] " + native_verifier_instruction,
        ) if part)
        effective_verifier_tool, authoritative_check_ids = (
            _persistent_verifier_native_tool_for_input(user_input)
        )
        provider_parameters, schema_projection_audit = (
            prune_unreachable_local_defs_for_provider(effective_verifier_tool["parameters"])
        )
        effective_verifier_tool = {
            **effective_verifier_tool,
            "parameters": provider_parameters,
        }
        outcome_clause_ids = _persistent_verifier_outcome_clause_ids_from_input(user_input)
        persistent_basis_refs, persistent_bound_input_refs = (
            _persistent_verifier_prior_inspection_namespaces_from_input(user_input)
        )
        persistent_cited_receipt_handles = _persistent_verifier_cited_receipt_handles_from_input(user_input)
        persistent_completed_cited_receipt_handles = _persistent_verifier_completed_cited_receipt_handles_from_input(
            user_input, eligible_handles=persistent_cited_receipt_handles,
        )
        completed_set = set(persistent_completed_cited_receipt_handles)
        persistent_cited_receipt_handles = tuple(
            handle for handle in persistent_cited_receipt_handles if handle not in completed_set
        )
        request: dict[str, Any] = {
            "model": self._deployment,
            "instructions": prepared_instructions,
            "input": user_input,
            "reasoning": {"effort": self._effort},
            "tools": [effective_verifier_tool],
            "tool_choice": {"type": "function", "name": _VERIFIER_NATIVE_TOOL_NAME},
            "parallel_tool_calls": False,
            "max_tool_calls": 1,
            "background": bool(self._responses_background),
        }
        if max_output_tokens is not None:
            request["max_output_tokens"] = int(max_output_tokens)
        if self._prompt_cache_mode == "stable_prefix":
            request["prompt_cache_key"] = _stable_prompt_cache_key(
                deployment=self._deployment,
                role=self._role,
                namespace=self._prompt_cache_namespace,
            )

        verifier_activation_prepared: PreparedVerifierActivationTransport | None = None
        verifier_activation_binding = self._verifier_activation_binding(telemetry_scope)
        if verifier_activation_binding is not None:
            try:
                verifier_activation_prepared = self._verifier_activation_continuity_state.prepare(
                    user_input,
                    mode=verifier_activation_binding["mode"],
                    run_id=str((telemetry_scope or {}).get("run_id") or ""),
                    task_id=str((telemetry_scope or {}).get("task_id") or ""),
                    activation_id=verifier_activation_binding["activation_id"],
                )
            except ValueError as exc:
                raise AzureModelError(f"Verifier activation continuity prepare failed: {exc}") from exc
            if verifier_activation_prepared.configured_mode == VERIFIER_ACTIVATION_PREVIOUS_RESPONSE_V1:
                request["store"] = True
                if verifier_activation_prepared.transport_kind == "delta":
                    request["previous_response_id"] = str(
                        verifier_activation_prepared.previous_response_id or ""
                    )
                    request["input"] = [{
                        "type": "function_call_output",
                        "call_id": str(verifier_activation_prepared.previous_call_id or ""),
                        "output": str(verifier_activation_prepared.rendered),
                    }]

        event: dict[str, Any] = {
            "event_kind": "provider_attempt",
            "logical_call_id": logical_call_id,
            "attempt_ordinal": attempt_ordinal,
            "provider": "azure_openai_responses",
            "deployment": self._deployment,
            "role": self._role,
            "responses_background": bool(self._responses_background),
            "responses_websocket": bool(self._responses_websocket),
            "provider_transport_mode": ("websocket" if self._responses_websocket else "background_http" if self._responses_background else "foreground_http"),
            "status": "in_progress",
            "attempt_phase": "create",
            "instructions_chars": len(prepared_instructions),
            "input_chars": len(_responses_input_text(user_input)),
            "instructions_sha256": hashlib.sha256(prepared_instructions.encode("utf-8")).hexdigest(),
            "input_sha256": hashlib.sha256(_responses_input_text(user_input).encode("utf-8")).hexdigest(),
            "max_output_tokens": max_output_tokens,
            "structured_output_mode": "verifier_direct_turn_native_tool",
            "native_tool_name": _VERIFIER_NATIVE_TOOL_NAME,
            "persistent_authoritative_check_count": len(authoritative_check_ids),
            "persistent_authoritative_check_ids": list(authoritative_check_ids),
            "persistent_outcome_clause_count": len(outcome_clause_ids),
            "persistent_outcome_clause_ids": list(outcome_clause_ids),
            "persistent_outcome_clause_ids_sha256": hashlib.sha256(
                json.dumps(list(outcome_clause_ids), separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "persistent_authoritative_check_ids_sha256": hashlib.sha256(
                json.dumps(list(authoritative_check_ids), separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "persistent_prior_authoritative_inspection_count": len(persistent_basis_refs),
            "persistent_prior_bound_input_count": len(persistent_bound_input_refs),
            "persistent_prior_authoritative_inspection_ids": list(persistent_basis_refs),
            "persistent_prior_bound_input_ids": list(persistent_bound_input_refs),
            "persistent_cited_receipt_count": len(persistent_cited_receipt_handles),
            "persistent_cited_receipt_handles": list(persistent_cited_receipt_handles),
            "persistent_completed_cited_receipt_count": len(persistent_completed_cited_receipt_handles),
            "persistent_completed_cited_receipt_handles": list(persistent_completed_cited_receipt_handles),
            "persistent_cited_receipt_handles_sha256": hashlib.sha256(
                json.dumps(list(persistent_cited_receipt_handles), separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "verifier_provider_schema_projection_status": schema_projection_audit.get("status"),
            "verifier_provider_schema_before_bytes": schema_projection_audit.get("before_bytes"),
            "verifier_provider_schema_after_bytes": schema_projection_audit.get("after_bytes"),
            "verifier_provider_schema_bytes_saved": schema_projection_audit.get("bytes_saved"),
            "verifier_provider_schema_removed_defs": len(schema_projection_audit.get("removed", ())),
            "verifier_provider_schema_before_digest": schema_projection_audit.get("before_digest"),
            "verifier_provider_schema_after_digest": schema_projection_audit.get("after_digest"),
            "max_tool_calls_requested": 1,
            "parallel_tool_calls": False,
            "prompt_cache_key_mode": self._prompt_cache_mode,
            "prompt_cache_namespace": self._prompt_cache_namespace,
            "prompt_cache_retention": None,
            "usage_status": "unmeasured",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "cache_write_tokens": None,
            "reasoning_tokens": None,
        }
        if telemetry_scope is not None:
            event.update(telemetry_scope)
        if verifier_activation_prepared is not None:
            event.update({
                "verifier_activation_continuity_mode": verifier_activation_prepared.configured_mode,
                "verifier_activation_id": verifier_activation_prepared.key[2],
                "verifier_activation_transport_kind": verifier_activation_prepared.transport_kind,
                "verifier_activation_previous_response_id": verifier_activation_prepared.previous_response_id,
                "verifier_activation_previous_call_id": verifier_activation_prepared.previous_call_id,
                "verifier_activation_base_snapshot_sha256": (
                    None if verifier_activation_prepared.envelope is None
                    else verifier_activation_prepared.envelope.get("base_snapshot_sha256")
                ),
                "verifier_activation_result_snapshot_sha256": (
                    None if verifier_activation_prepared.envelope is None
                    else verifier_activation_prepared.envelope.get("result_snapshot_sha256")
                ),
                "verifier_activation_delta_operation_count": (
                    0 if verifier_activation_prepared.envelope is None
                    else int(verifier_activation_prepared.envelope.get("operation_count", 0))
                ),
            })
        _capture_finalized_provider_request(event, request)
        _append_provider_lifecycle(
            stage="request_prepared", role=self._role, logical_call_id=logical_call_id,
            attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
            transport_mode=str(event["provider_transport_mode"]), create_ordinal=1,
        )
        started = time.monotonic()
        response: Any | None = None
        response_id: str | None = None
        budget_reservations: list[dict[str, Any]] = []
        transport_started = False
        def mark_transport_started() -> None:
            nonlocal transport_started
            transport_started = True
        try:
            poll_timeout_s = _remaining_verifier_poll_timeout_s(
                self._poll_timeout_s, minimum_reserve_s=self._poll_interval_s + 1.0,
            )
            event["effective_poll_timeout_s"] = round(poll_timeout_s, 3)
            self._raise_if_run_cancelled()
            if self._rate_limiter is not None:
                self._rate_limiter.acquire()
            self._raise_if_run_cancelled()
            _observe_request_anatomy(
                role="verifier", request=request,
                run_id=str((telemetry_scope or {}).get("run_id") or ""),
                task_id=str((telemetry_scope or {}).get("task_id") or ""),
                turn_index=logical_call_id,
                call_id=(
                    f"logical-{logical_call_id}:attempt-{attempt_ordinal}:create-1"
                ),
            )
            _append_provider_lifecycle(
                stage="dispatch_invocation_started", role=self._role, logical_call_id=logical_call_id,
                attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                transport_mode=str(event["provider_transport_mode"]), create_ordinal=1,
            )
            def verifier_lifecycle_observer(stage: str, detail: dict[str, Any]) -> None:
                _append_provider_lifecycle(
                    stage=stage, role=self._role, logical_call_id=logical_call_id,
                    attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                    transport_mode=str(event["provider_transport_mode"]),
                    status=str(detail.get("event_type") or "") or None, create_ordinal=1,
                )
            verifier_budget_input_upper_bound = (
                serialized_request_token_upper_bound(request)
                if self._budget_guard is not None else None
            )
            response = self._responses_create(
                _aether_lifecycle_observer=verifier_lifecycle_observer,
                _aether_transport_started_observer=mark_transport_started,
                _aether_budget_reservation_observer=budget_reservations.append,
                _aether_budget_input_token_upper_bound=verifier_budget_input_upper_bound,
                _aether_transport_timeout_s=poll_timeout_s,
                **request,
            )
            _append_provider_lifecycle(
                stage="provider_call_returned", role=self._role, logical_call_id=logical_call_id,
                attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                transport_mode=str(event["provider_transport_mode"]),
                response_id=str(getattr(response, "id", "") or "") or None,
                status=str(getattr(response, "status", "") or "") or None, create_ordinal=1,
            )
            raw_response_id = getattr(response, "id", None)
            if not raw_response_id:
                raise AzureModelError("responses.create returned no response id")
            response_id = str(raw_response_id)
            event["job_id"] = response_id
            event["attempt_phase"] = "poll"
            elapsed = 0.0
            while getattr(response, "status", None) in ("queued", "in_progress"):
                self._raise_if_run_cancelled()
                if elapsed >= poll_timeout_s:
                    raise AzureModelError(
                        f"provider response {response_id} timed out after {elapsed:.0f}s "
                        f"(status={getattr(response, 'status', None)})"
                    )
                time.sleep(self._poll_interval_s)
                elapsed += self._poll_interval_s
                self._raise_if_run_cancelled()
                try:
                    response = self._responses_retrieve(response_id)
                except Exception as exc:
                    raise AzureModelError(
                        f"responses.retrieve failed for {response_id}: {exc}"
                    ) from exc
            status = getattr(response, "status", None)
            event.update({
                "attempt_phase": "terminal",
                "job_status": str(status),
                "poll_elapsed_s": elapsed,
                **_usage_telemetry(response),
            })
            if os.environ.get("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT") == "1":
                event["raw_provider_output_items"] = _raw_output_items_for_evidence(response)
            if status == "completed":
                self._settle_budget_success(
                    budget_reservations[-1] if budget_reservations else None, response, event,
                )
                event.update(_native_tool_output_shape_telemetry(response))
                try:
                    canonical, output_receipt = canonicalize_verifier_native_tool_output(response)
                except AzureProviderOutputError as exc:
                    event["provider_output_error"] = exc.code
                    raise
                event.update(output_receipt)
                if verifier_activation_prepared is not None:
                    try:
                        self._verifier_activation_continuity_state.stage_candidate(
                            verifier_activation_prepared,
                            response_id=response_id,
                            call_id=str(output_receipt.get("native_tool_call_id") or ""),
                        )
                    except ValueError as exc:
                        raise AzureModelError(
                            f"Verifier activation continuity stage failed: {exc}"
                        ) from exc
                    event["verifier_activation_candidate_staged"] = True
                event["status"] = "completed"
                return canonical
            if status == "incomplete":
                event["provider_output_error"] = "provider_output_incomplete"
                event["status"] = "incomplete"
                raise AzureProviderOutputError(
                    "provider_output_incomplete",
                    str(getattr(response, "incomplete_details", None) or ""),
                )
            error_obj = getattr(response, "error", None)
            detail = error_obj or getattr(response, "incomplete_details", None) or ""
            code = getattr(error_obj, "code", None)
            raise AzureModelError(
                f"provider response {response_id} ended with status={status}: {detail}"
            ) from _JobStatusFailure(code)
        except Exception as exc:
            last_status = str(getattr(response, "status", None) or "")
            if response_id and last_status in {"queued", "in_progress"}:
                event["provider_job_cancel_attempted"] = True
                try:
                    cancelled = self._responses_cancel(response_id)
                    cancel_status = str(getattr(cancelled, "status", None) or "")
                    event["provider_job_cancel_status"] = cancel_status
                    event["provider_job_cancel_succeeded"] = cancel_status in {
                        "cancelled", "canceled", "cancelling", "canceling",
                    }
                except Exception as cancel_exc:
                    event["provider_job_cancel_succeeded"] = False
                    event["provider_job_cancel_error_type"] = cancel_exc.__class__.__name__
                    event["provider_job_cancel_error"] = str(cancel_exc)[:1000]
            event.update({
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "error": str(exc)[:1000],
            })
            if isinstance(exc, AzureProviderOutputError):
                event["provider_output_error"] = exc.code
            if isinstance(exc, ResponsesWebSocketError):
                event["provider_terminal_failure"] = bool(exc.terminal)
                event["provider_terminal_retry_safe"] = bool(exc.retry_safe)
                event["provider_terminal_error_code"] = exc.provider_error_code
                event["provider_terminal_event_type"] = exc.event_type
                event["provider_terminal_response_id"] = exc.response_id
                event["provider_websocket_request_accepted"] = bool(exc.request_accepted)
                event["provider_websocket_acceptance_observed"] = bool(
                    exc.acceptance_observed
                )
                event["provider_websocket_acceptance_known"] = bool(
                    exc.acceptance_known
                )
                event["provider_websocket_acceptance_unknown_after_dispatch"] = bool(
                    exc.provider_acceptance_unknown_after_dispatch
                )
                event["provider_websocket_partial_output_observed"] = bool(exc.partial_output_observed)
                event["provider_websocket_native_tool_call_observed"] = bool(exc.native_tool_call_observed)
                event["provider_websocket_native_tool_execution_observed"] = (
                    exc.native_tool_execution_observed
                )
                event["provider_websocket_incomplete_reason"] = exc.incomplete_reason
                event["provider_websocket_replay_safety_reason"] = exc.replay_safety_reason
            if isinstance(exc, RunCancellationRequested):
                raise
            if exc.__class__.__name__ == "KernelRunTimeout":
                raise
            if isinstance(exc, AzureModelError):
                raise
            raise AzureModelError(f"responses Verifier native-tool call failed: {exc}") from exc
        finally:
            if (
                transport_started
                and self._responses_websocket
                and self._websocket_transport is not None
            ):
                observe = getattr(self._websocket_transport, "last_call_observability", None)
                if callable(observe):
                    event.update(observe())
            event["elapsed_s"] = round(time.monotonic() - started, 3)
            _append_provider_lifecycle(
                stage="attempt_terminal", role=self._role, logical_call_id=logical_call_id,
                attempt_ordinal=attempt_ordinal, telemetry_scope=telemetry_scope,
                transport_mode=str(event.get("provider_transport_mode") or ""),
                response_id=response_id, status=str(event.get("status") or ""), create_ordinal=1,
            )
            self._record_attempt(event)

    def preflight_request(self, *, max_output_tokens: int | None, logical_role: str) -> dict[str, Any]:
        """Describe the sole native Responses-tools request contract without a call."""
        verifier_native = self._role == "verifier"
        return {
            "provider": "azure_openai_responses",
            "transport": "responses_tools",
            "model": self._deployment,
            "provider_role": self._role,
            "logical_role": logical_role,
            "effort": self._effort,
            "max_output_tokens": (int(max_output_tokens) if max_output_tokens is not None else None),
            "background": getattr(self, "_responses_background", True),
            "reasoning_context": self._persistent_reasoning_context,
            "prompt_cache_mode": self._prompt_cache_mode,
            "poll_interval_s": self._poll_interval_s,
            "poll_timeout_s": self._poll_timeout_s,
            "max_retries": self._max_retries,
            "budget_constrained": self._budget_guard is not None,
            "budget_contract_sha256": (
                None if self._budget_guard is None else self._budget_guard.contract_sha
            ),
            "structured_output_mode": (
                "verifier_direct_turn_native_tool"
                if verifier_native else "persistent_v0_direct_native_tools"
            ),
            "response_cardinality_contract": (
                "exactly_one_forced_verifier_turn_function_call"
                if verifier_native else "exactly_one_required_direct_persistent_function_call"
            ),
            "native_tool_name": (
                _VERIFIER_NATIVE_TOOL_NAME if verifier_native else "direct_action_set"
            ),
            "verifier_protocol": ("persistent_v0" if verifier_native else None),
            "max_tool_calls_requested": 1,
            "parallel_tool_calls": False,
            "persistent_continuity_mode": ("previous_response" if not verifier_native else "fresh"),
            "explicit_json_instruction": False,
            "json_instruction_in_input": False,
            "certification": (
                "responses_single_verifier_native_tool_call_contract"
                if verifier_native else "responses_single_direct_persistent_native_tool_call_contract"
            ),
        }



class AzureVisionCallable:
    """Vision transcription callable: (prompt, image_b64, media_type) -> text.

    Sends a multimodal Responses API request with an inline data-URL image.
    """

    def __init__(
        self, client: Any, deployment: str,
        async_transport: _AsyncResponsesTransport | None = None,
        budget_guard: ProviderBudgetGuard | None = None,
    ) -> None:
        self._client = client
        self._async_transport = async_transport
        self._deployment = deployment
        self._budget_guard = budget_guard
        self._telemetry_events: list[dict[str, Any]] = []
        self._telemetry_lock = threading.Lock()
        self._next_logical_call_id = 0
        self._run_cancellation_event: Any | None = None

    def bind_run_cancellation(self, event: Any | None) -> None:
        """Bind one task-scoped cancellation signal; no provider call occurs."""
        self._run_cancellation_event = event

    def _raise_if_run_cancelled(self) -> None:
        raise_if_run_cancelled(self._run_cancellation_event)

    def _responses_create(self, **kwargs: Any) -> Any:
        budget_reservation_observer = kwargs.pop("_aether_budget_reservation_observer", None)
        if self._budget_guard is not None:
            reservation_event = self._budget_guard.reserve("vision", kwargs)
            if callable(budget_reservation_observer):
                budget_reservation_observer(dict(reservation_event))
        if self._async_transport is not None:
            return self._async_transport.call(
                "create", cancellation_event=self._run_cancellation_event, **kwargs
            )
        return self._client.responses.create(**kwargs)

    def close_run_transport(self) -> None:
        if self._async_transport is not None:
            self._async_transport.close()
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def drain_telemetry(self) -> tuple[dict[str, Any], ...]:
        """Return and clear immutable vision-call telemetry receipts."""
        with self._telemetry_lock:
            events = tuple(self._telemetry_events)
            self._telemetry_events.clear()
            return events

    def _record_telemetry(self, event: dict[str, Any]) -> None:
        with self._telemetry_lock:
            self._telemetry_events.append(dict(event))

    def _allocate_logical_call_id(self) -> int:
        with self._telemetry_lock:
            self._next_logical_call_id += 1
            return self._next_logical_call_id

    def __call__(self, prompt: str, image_b64: str, media_type: str) -> str:
        return self._call(prompt, image_b64, media_type, telemetry_scope=None)

    def call_with_telemetry_scope(
        self,
        prompt: str,
        image_b64: str,
        media_type: str,
        *,
        run_id: str,
        task_id: str | None,
    ) -> str:
        return self._call(
            prompt,
            image_b64,
            media_type,
            telemetry_scope={"run_id": run_id, "task_id": task_id},
        )

    def _vision_output_limit(self) -> int | None:
        """Preserve the legacy 8k limit except for transparent v2 contracts."""
        if self._budget_guard is None:
            return 8000
        contract = getattr(self._budget_guard, "contract", None)
        if getattr(contract, "schema_version", None) != "aether.provider_budget.v2":
            return 8000
        return contract.runtime_max_output_tokens.get("vision")

    def _settle_budget_success(
        self, reservation_event: Mapping[str, Any] | None, response: Any, telemetry_event: dict[str, Any],
    ) -> None:
        if self._budget_guard is None or reservation_event is None:
            return
        contract = getattr(self._budget_guard, "contract", None)
        if getattr(contract, "schema_version", None) != "aether.provider_budget.v2":
            return
        usage = _usage_telemetry(response)
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            telemetry_event["provider_budget_settlement_status"] = "retained_missing_usage"
            return
        settlement = self._budget_guard.settle_success(
            reservation_event, input_tokens=input_tokens, output_tokens=output_tokens,
        )
        telemetry_event.update({
            "provider_budget_settlement_status": "settled_terminal_success_usage",
            "provider_budget_settlement_aggregate_create_ordinal": settlement.get("aggregate_create_ordinal"),
            "provider_budget_settled_gbp": settlement.get("settled_gbp"),
            "provider_budget_released_provisional_gbp": settlement.get("released_provisional_gbp"),
            "provider_budget_running_reserved_gbp": settlement.get("running_reserved_gbp"),
        })

    def _call(
        self,
        prompt: str,
        image_b64: str,
        media_type: str,
        *,
        telemetry_scope: dict[str, str | None] | None,
    ) -> str:
        vision_output_limit = self._vision_output_limit()
        budget_reservations: list[dict[str, Any]] = []
        event: dict[str, Any] = {
            "event_kind": "provider_attempt",
            "logical_call_id": self._allocate_logical_call_id(),
            "attempt_ordinal": 1,
            "provider": "azure_openai_responses_vision",
            "deployment": self._deployment,
            "role": "vision",
            "status": "in_progress",
            "attempt_phase": "create",
            "input_chars": len(prompt),
            "image_base64_chars": len(image_b64),
            "max_output_tokens": vision_output_limit,
            # This synchronous multimodal route sends no cache key; do not
            # imply cache support or a cache miss from absent provider fields.
            "prompt_cache_key_mode": "not_requested",
            "prompt_cache_retention": None,
            "usage_status": "unmeasured",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "cache_write_tokens": None,
            "reasoning_tokens": None,
        }
        if telemetry_scope is not None:
            event.update(telemetry_scope)
        started = time.monotonic()
        try:
            self._raise_if_run_cancelled()
            request: dict[str, Any] = {
                "model": self._deployment,
                "input": [{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{media_type};base64,{image_b64}",
                        },
                    ],
                }],
            }
            if vision_output_limit is not None:
                request["max_output_tokens"] = int(vision_output_limit)
            response = self._responses_create(
                _aether_budget_reservation_observer=budget_reservations.append,
                **request,
            )
            event.update({
                "attempt_phase": "terminal",
                "job_id": str(getattr(response, "id", "")) or None,
                "job_status": str(getattr(response, "status", "completed")),
                **_usage_telemetry(response),
            })
            if str(getattr(response, "status", "completed")) == "completed":
                self._settle_budget_success(
                    budget_reservations[-1] if budget_reservations else None, response, event,
                )
            text = _extract_plain_output_text(response)
            if not text:
                raise AzureModelError("vision response completed but produced no output text")
            event["status"] = "completed"
            return text
        except Exception as exc:
            event.update({
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "error": str(exc)[:1000],
            })
            raise
        finally:
            event["elapsed_s"] = round(time.monotonic() - started, 3)
            self._record_telemetry(event)


def make_azure_vision_callable(
    *,
    deployment_env: str,
    key_env: str,
    endpoint_env: str = "AZURE_OPENAI_ENDPOINT",
    sdk_max_retries: int = 2,
) -> AzureVisionCallable:
    """Build a vision transcription callable from Azure env vars (build-time)."""
    budget_guard = provider_budget_guard_from_env()
    if budget_guard is not None and int(sdk_max_retries) != 0:
        raise AzureModelError(
            "budget-constrained vision construction requires SDK retries = 0"
        )
    endpoint = _normalize_endpoint(os.environ[endpoint_env])
    api_key = os.environ[key_env]
    deployment = os.environ[deployment_env]
    if openai is None:
        raise AzureModelError("openai package is required for AzureVisionCallable")
    client_kwargs = {
        "api_key": api_key,
        "base_url": f"{endpoint}/openai/v1/",
        "timeout": 300,
        "max_retries": max(0, int(sdk_max_retries)),
    }
    client = openai.OpenAI(**client_kwargs)
    async_transport = _AsyncResponsesTransport(
        client_factory=lambda: openai.AsyncOpenAI(**client_kwargs),
    )
    return AzureVisionCallable(
        client, deployment, async_transport=async_transport, budget_guard=budget_guard,
    )
