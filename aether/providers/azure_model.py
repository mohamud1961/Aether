"""Azure OpenAI model providers with strict structured-output boundaries.

This is the ONLY module allowed to ``import openai``.  It builds a
``ModelCallable`` that the kernel's ``ModelHooks`` layer can consume.

Solver and Architect retain the Responses background route.  Factory-created
Verifier calls use Chat Completions with one choice because the Verifier
protocol requires one authoritative envelope, while Responses exposes an
output array whose cardinality is provider-controlled.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse

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
from ..verifier_recovery import EvidenceClass
from ..verifier_budget import DIRECT_OBSERVATION_KINDS, DERIVED_EXECUTION_KINDS
from ..persistent_provider_protocol import (
    PERSISTENT_PRIMARY_CHAT_RESPONSE_FORMAT,
    PERSISTENT_PRIMARY_PROVIDER_SCHEMA,
    PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME,
    PERSISTENT_PRIMARY_TURN_RESPONSE_INSTRUCTION,
    PERSISTENT_PRIMARY_TURN_SCHEMA,
    PCRProviderProtocolError,
    canonicalize_persistent_primary_turn,
    normalize_persistent_working_state_policy,
    persistent_primary_provider_schema,
    persistent_primary_turn_response_instruction,
)

try:
    import openai
except ModuleNotFoundError:  # pragma: no cover - provider construction requires dependency.
    openai = None  # type: ignore[assignment]


class AzureModelError(Exception):
    """Raised when the Azure Responses API returns an unrecoverable error."""


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

_PERSISTENT_PRIMARY_NATIVE_TOOL_NAME = "persistent_turn"
_PERSISTENT_PRIMARY_NATIVE_TOOL_RESPONSE_INSTRUCTION = (
    "Call the persistent_turn function exactly once with only the single current causal "
    "PERSISTENT turn. The host will execute or observe that turn before any future "
    "decision. Do not emit or plan future turns in this response."
)
def _persistent_primary_native_tool_for_policy(working_state_policy: str) -> dict[str, Any]:
    policy = normalize_persistent_working_state_policy(working_state_policy)
    return {
        "type": "function",
        "name": _PERSISTENT_PRIMARY_NATIVE_TOOL_NAME,
        "description": (
            "Propose exactly one current PERSISTENT turn. The host executes or observes it "
            "before the model may decide again."
        ),
        "parameters": persistent_primary_provider_schema(working_state_policy=policy),
        "strict": True,
    }


_PERSISTENT_PRIMARY_NATIVE_TOOL: dict[str, Any] = _persistent_primary_native_tool_for_policy("optional")

# Experimental PERSISTENT provider-native continuity modes. ``explicit`` is the
# production default and preserves the current reconstruction path exactly.
# The other modes are opt-in experiment seams only until live canaries prove
# provider acceptance, continuity quality, and compaction behavior.
_PERSISTENT_REASONING_CONTEXT_MODES = frozenset({'current_turn'})

_PERSISTENT_CONTINUITY_MODES = frozenset({
    "explicit",
    "previous_response",
    "previous_response_compaction",
    "stateless_encrypted",
    "stateless_compaction",
})


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


def _responses_input_items(
    value: str | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return [{"role": "user", "content": value}]
    return [dict(item) for item in value]


def _latest_compaction_index(items: list[dict[str, Any]]) -> int | None:
    latest: int | None = None
    for index, item in enumerate(items):
        if str(item.get("type") or "") == "compaction":
            latest = index
    return latest


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

_SOLVER_TURN_RESPONSE_INSTRUCTION = (
    "Return exactly one strict provider object with the sole key turn. turn must "
    "be exactly one Solver protocol state: act or submit_outcome. An act turn has "
    "exactly one action in actions. Encode that action's arguments as one JSON "
    "object string in arguments_json; the provider boundary decodes it before the "
    "existing Solver parser and action schema validate the turn. requested_check_ids "
    "and claimed_artifacts are arrays, and evidence_gap is a string; use empty values "
    "when none apply. Never emit act and submit_outcome together, a second object, "
    "markdown, prose, or an alternative candidate."
)

_SOLVER_DIRECT_TURN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["turn"],
    "properties": {
        "turn": {
            "anyOf": [
                {"$ref": "#/$defs/act_turn"},
                {"$ref": "#/$defs/submit_turn"},
            ],
        },
    },
    "$defs": {
        "action": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "action_id", "kind", "capability_id", "arguments_json",
                "intent", "expected_observation", "if_fail_next",
            ],
            "properties": {
                "action_id": {"type": "string"},
                "kind": {"type": "string"},
                "capability_id": {"type": "string"},
                "arguments_json": {"type": "string"},
                "intent": {"type": "string"},
                "expected_observation": {"type": "string"},
                "if_fail_next": {"type": "string"},
            },
        },
        "act_turn": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "kind", "summary", "actions", "requested_check_ids",
                "claimed_artifacts", "evidence_gap",
            ],
            "properties": {
                "kind": {"type": "string", "enum": ["act"]},
                "summary": {"type": "string"},
                "actions": {
                    "type": "array", "minItems": 1, "maxItems": 1,
                    "items": {"$ref": "#/$defs/action"},
                },
                "requested_check_ids": {"type": "array", "items": {"type": "string"}},
                "claimed_artifacts": {"type": "array", "items": {"type": "string"}},
                "evidence_gap": {"type": "string"},
            },
        },
        "submit_turn": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "kind", "summary", "requested_check_ids",
                "claimed_artifacts", "evidence_gap",
            ],
            "properties": {
                "kind": {"type": "string", "enum": ["submit_outcome"]},
                "summary": {"type": "string"},
                "requested_check_ids": {"type": "array", "items": {"type": "string"}},
                "claimed_artifacts": {"type": "array", "items": {"type": "string"}},
                "evidence_gap": {"type": "string"},
            },
        },
    },
}

_SOLVER_STRUCTURED_OUTPUT_NAME = "aether_solver_direct_turn"
_SOLVER_CHAT_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": _SOLVER_STRUCTURED_OUTPUT_NAME,
        "strict": True,
        "schema": _SOLVER_DIRECT_TURN_SCHEMA,
    },
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

    shared_direct_properties: dict[str, Any] = {
        # F93: PERSISTENT provider transport identity is host-owned. The Verifier
        # parser deterministically assigns inspect-{n} when request_id is absent;
        # model-authored labels must never become inspection:* authority.
        # check_id and receipt_kind are not consumed by any PERSISTENT direct route.
        # Keeping them on every forced native call created a second misleading
        # place for the model to express route intent, so F87 removes them.
        "limit": _NULLABLE_INTEGER,
        "offset": _NULLABLE_INTEGER,
        "span": _NULLABLE_INTEGER,
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
        "span": _NULLABLE_INTEGER,
        "clause_ids": _NULLABLE_STRING_ARRAY,
        "proof_ids": _NULLABLE_STRING_ARRAY,
    }
    defs["persistent_cited_receipt_request"] = {
        "type": "object",
        "additionalProperties": False,
        "required": list(cited_receipt_properties),
        "properties": cited_receipt_properties,
    }
    # PERSISTENT's thin Verifier does not expose ledger-only recent-receipt browsing.
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
    "Verifier turn. Use run_verifier_command only after observing its authoritative "
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



def _persistent_verifier_cited_receipt_handles_from_input(
    user_input: str | list[dict[str, str]],
) -> tuple[str, ...]:
    """Extract exact successful cited-read receipt handles from the PERSISTENT packet.

    This is a capability namespace, not evidence admission. The provider only
    mirrors handles already emitted by the kernel-owned thin Verifier packet;
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
            # cited evidence: only successful immutable read_file observations.
            if str(row.get("kind") or "").strip() != "read_file" or row.get("success") is not True:
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


def _persistent_verifier_native_tool_for_input(
    user_input: str | list[dict[str, str]],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Bind rerun_check to the exact authoritative check IDs in this packet.

    Empty namespace means the route is absent. Non-empty namespace becomes a
    strict enum. No runtime/verdict semantics are changed by this projection.
    """
    check_ids = _persistent_verifier_authoritative_check_ids_from_input(user_input)
    outcome_clause_ids = _persistent_verifier_outcome_clause_ids_from_input(user_input)
    cited_receipt_handles = _persistent_verifier_cited_receipt_handles_from_input(user_input)
    completed_cited_receipt_handles = _persistent_verifier_completed_cited_receipt_handles_from_input(
        user_input, eligible_handles=cited_receipt_handles,
    )
    completed_cited_receipt_set = set(completed_cited_receipt_handles)
    cited_receipt_handles = tuple(
        handle for handle in cited_receipt_handles if handle not in completed_cited_receipt_set
    )
    basis_refs, bound_input_refs = _persistent_verifier_prior_inspection_namespaces_from_input(user_input)
    schema = json.loads(json.dumps(_PERSISTENT_VERIFIER_DIRECT_TURN_SCHEMA))
    defs = schema["$defs"]
    if outcome_clause_ids:
        clause_item = {"type": "string", "enum": list(outcome_clause_ids)}
        nullable_clause_array = _nullable({"type": "array", "items": clause_item})
        for name in (
            "persistent_direct_locator_request", "persistent_cited_receipt_request",
            "persistent_rerun_check_request",
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

    status_code = getattr(cause, "status_code", None)
    if isinstance(status_code, int):
        return status_code == 429 or 500 <= status_code < 600

    # SDK connection/timeout errors carry no HTTP status at all but are
    # transient by nature (openai.APITimeoutError subclasses this too).
    if openai is not None and isinstance(cause, openai.APIConnectionError):
        return True

    return False


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
    configured = float(os.environ.get("AETHER_VERIFIER_POLL_TIMEOUT_S", default_timeout_s))
    verifier_deadline = float(os.environ.get(
        "AETHER_MODEL_VERIFIER_CALL_TIMEOUT_S",
        os.environ.get("AETHER_MODEL_VERIFIER_TIMEOUT_S", "180"),
    ))
    reserve = float(os.environ.get("AETHER_VERIFIER_TIMEOUT_RESERVE_S", "10"))
    return max(30.0, min(configured, verifier_deadline - max(0.0, reserve)))


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
    reserve = max(
        float(os.environ.get("AETHER_VERIFIER_TIMEOUT_RESERVE_S", "10")),
        minimum_reserve_s,
    )
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
            "reasoning_tokens": None,
        }
    input_details = _usage_field(usage, "input_tokens_details")
    if input_details is None:
        input_details = _usage_field(usage, "prompt_tokens_details", {}) or {}
    output_details = _usage_field(usage, "output_tokens_details", {}) or {}
    missing = object()
    cached = _usage_field(input_details, "cached_tokens", missing)
    input_tokens = _usage_field(usage, "input_tokens")
    if input_tokens is None:
        input_tokens = _usage_field(usage, "prompt_tokens")
    output_tokens = _usage_field(usage, "output_tokens")
    if output_tokens is None:
        output_tokens = _usage_field(usage, "completion_tokens")
    return {
        "usage_status": "reported",
        "cache_metrics_status": "reported" if cached is not missing else "unmeasured",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": _usage_field(usage, "total_tokens"),
        "cached_input_tokens": None if cached is missing else cached,
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


def _prepare_json_object_instructions(instructions: str) -> str:
    """Make Azure JSON-mode's textual requirement explicit before dispatch.

    Azure rejects ``text.format=json_object`` requests unless the model-facing
    material mentions JSON.  Aether's structured-output boundary is generic,
    so the provider adapter owns this invariant rather than relying on task or
    role prompts to happen to contain that word.  The returned string is used
    for the initial request and every retry of the same logical call.
    """
    prepared = "\n\n".join(part for part in (
        str(instructions).strip(),
        "[structured_output_contract] " + _JSON_OBJECT_RESPONSE_INSTRUCTION,
    ) if part)
    if "json" not in prepared.lower():
        # Fail locally before a provider request can spend budget. This should
        # be unreachable while the constant above remains valid, but protects
        # future edits to the request builder.
        raise AzureModelError(
            "json_object_request_contract_invalid: explicit JSON instruction missing"
        )
    return prepared


def _prepare_json_object_input(
    input_payload: str | list[dict[str, str]],
) -> str | list[dict[str, str]]:
    """Place the JSON-mode contract in Responses ``input`` as well.

    Some Azure Responses routes enforce the textual JSON-mode requirement
    against ``input`` messages specifically, rather than against the separate
    ``instructions`` field.  Keeping the same generic contract in both
    model-visible surfaces makes the request valid for either interpretation
    without relying on incidental wording in a task or role prompt.
    """
    contract_message = {
        "role": "developer",
        "content": "[structured_output_contract] " + _JSON_OBJECT_RESPONSE_INSTRUCTION,
    }
    if isinstance(input_payload, str):
        return contract_message["content"] + "\n\n" + input_payload
    return [contract_message, *input_payload]


def _prepare_verifier_envelope_instructions(instructions: str) -> str:
    """Add the generic provider-envelope contract for Verifier calls."""
    return "\n\n".join(part for part in (
        str(instructions).strip(),
        "[structured_output_contract] " + _VERIFIER_ENVELOPE_RESPONSE_INSTRUCTION,
    ) if part)


def _prepare_verifier_envelope_input(
    input_payload: str | list[dict[str, str]],
) -> str | list[dict[str, str]]:
    contract = {
        "role": "developer",
        "content": "[structured_output_contract] " + _VERIFIER_ENVELOPE_RESPONSE_INSTRUCTION,
    }
    if isinstance(input_payload, str):
        return contract["content"] + "\n\n" + input_payload
    return [contract, *input_payload]


def _prepare_verifier_chat_messages(
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Add the direct one-turn contract to a Chat Completions request."""
    contract = {
        "role": "developer",
        "content": "[structured_output_contract] " + _VERIFIER_DIRECT_TURN_RESPONSE_INSTRUCTION,
    }
    return [contract, *messages]


def _prepare_json_object_chat_messages(
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Add the generic one-object contract to a Chat Completions request."""
    contract = {
        "role": "developer",
        "content": "[structured_output_contract] " + _JSON_OBJECT_RESPONSE_INSTRUCTION,
    }
    return [contract, *messages]


def _prepare_solver_chat_messages(
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Keep the exact SolverTurn protocol salient on every Chat call.

    The stable runtime prefix remains the complete contract. This provider
    message is a task-independent projection of the same turn boundary so a
    long task context cannot drift into legacy ``action`` or ``status`` shapes.
    The runtime parser and action schema remain the execution authority.
    """
    contract = {
        "role": "developer",
        "content": "[structured_output_contract] " + _SOLVER_TURN_RESPONSE_INSTRUCTION,
    }
    return [contract, *messages]


def _prepare_persistent_primary_chat_messages(
    messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    contract = {
        "role": "developer",
        "content": "[structured_output_contract] " + PERSISTENT_PRIMARY_TURN_RESPONSE_INSTRUCTION,
    }
    return [contract, *messages]


def _prepare_persistent_primary_responses_instructions(instructions: str) -> str:
    return "\n\n".join(part for part in (
        str(instructions).strip(),
        "[structured_output_contract] " + PERSISTENT_PRIMARY_TURN_RESPONSE_INSTRUCTION,
    ) if part)


def _prepare_persistent_primary_responses_input(
    input_payload: str | list[dict[str, str]],
) -> str | list[dict[str, str]]:
    contract = {
        "role": "developer",
        "content": "[structured_output_contract] " + PERSISTENT_PRIMARY_TURN_RESPONSE_INSTRUCTION,
    }
    if isinstance(input_payload, str):
        return contract["content"] + "\n\n" + input_payload
    return [contract, *input_payload]


def _prepare_solver_responses_instructions(instructions: str) -> str:
    """Keep the exact SolverTurn boundary salient in Responses instructions."""
    return "\n\n".join(part for part in (
        str(instructions).strip(),
        "[structured_output_contract] " + _SOLVER_TURN_RESPONSE_INSTRUCTION,
    ) if part)


def _prepare_solver_responses_input(
    input_payload: str | list[dict[str, str]],
) -> str | list[dict[str, str]]:
    """Repeat the SolverTurn contract in Responses input for Azure routing."""
    contract = {
        "role": "developer",
        "content": "[structured_output_contract] " + _SOLVER_TURN_RESPONSE_INSTRUCTION,
    }
    if isinstance(input_payload, str):
        return contract["content"] + "\n\n" + input_payload
    return [contract, *input_payload]


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


def canonicalize_structured_output(
    response: Any,
) -> tuple[str, dict[str, Any]]:
    """Select one structured assistant message, fail-closed by default.

    Byte-different payloads remain provider-invalid.  The adapter may
    deduplicate canonically identical JSON messages, but it never selects one
    among distinct plausible assistant decisions; protocol correction belongs
    above this transport boundary.
    """
    messages, mixed_call = _raw_assistant_messages(response)
    receipt: dict[str, Any] = {
        "response_id": str(_usage_field(response, "id", "") or ""),
        "raw_provider_status": str(_usage_field(response, "status", "") or ""),
        "extraction_path": "response.output[].message.content[].text",
        "candidate_message_count": len(messages),
        "candidate_hashes": tuple(row["text_sha256"] for row in messages),
        "provider_duplicate_output": False,
    }
    if mixed_call:
        raise AzureProviderOutputError("provider_mixed_message_and_tool_output")
    if not messages:
        raise AzureProviderOutputError("provider_no_assistant_message")
    canonical_rows: list[tuple[dict[str, Any], str]] = []
    for row in messages:
        canonical, _body = _strict_structured_json(str(row["text"]))
        canonical_rows.append((row, canonical))
    canonical_forms = {canonical for _row, canonical in canonical_rows}
    if len(canonical_forms) != 1:
        # Keep the ambiguity fail-closed, but retain enough non-content
        # metadata to distinguish a provider transport duplication from a
        # genuinely different model decision.  Never persist model text here.
        detail = json.dumps({
            "candidate_count": len(canonical_rows),
            "candidate_hashes": [row["text_sha256"] for row, _canonical in canonical_rows],
            "candidate_bytes": [row["text_bytes"] for row, _canonical in canonical_rows],
            "candidate_item_ids": [row["item_id"] for row, _canonical in canonical_rows],
            "candidate_top_level_keys": [sorted(json.loads(canonical).keys()) for _row, canonical in canonical_rows],
            "candidate_verdicts": [json.loads(canonical).get("verdict") for _row, canonical in canonical_rows],
        }, sort_keys=True, separators=(",", ":"))
        raise AzureProviderOutputError("multiple_distinct_assistant_outputs", detail)
    source, canonical = canonical_rows[0]
    receipt.update({
        "canonical_item_index": source["index"],
        "canonical_item_id": source["item_id"],
        "canonical_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "provider_duplicate_output": len(messages) > 1,
        "provider_duplicate_semantic_equivalent": len(messages) > 1,
    })
    return canonical, receipt


def unwrap_solver_direct_turn(text: str) -> tuple[str, dict[str, Any]]:
    """Decode one unambiguous strict Solver provider turn.

    Azure may concatenate an identical strict-schema envelope inside one
    assistant message. Parse the complete sequence and decode every candidate,
    including ``arguments_json``. Collapse only when all resulting Solver turns
    are semantically identical. Distinct, malformed, partial, duplicate-key, or
    non-object candidates remain provider-invalid. ``parse_solver_turn`` and
    ``ActionRequest.validate`` remain the semantic and execution authorities.
    """
    try:
        candidates = _provider_json_object_sequence(text)
    except AzureProviderOutputError as exc:
        codes = {
            "provider_envelope_empty": "provider_solver_direct_turn_empty",
            "provider_envelope_invalid_json": "provider_structured_output_invalid_json",
            "provider_envelope_nonstandard_json_constant": "provider_structured_output_nonstandard_json_constant",
            "provider_envelope_duplicate_key": "provider_solver_direct_turn_duplicate_key",
            "provider_envelope_top_level_not_object": "provider_solver_direct_turn_not_object",
        }
        raise AzureProviderOutputError(codes.get(exc.code, exc.code), exc.detail) from exc

    decoded_rows: list[tuple[str, str, str]] = []
    raw_hashes: list[str] = []
    for raw_envelope, envelope in candidates:
        raw_hashes.append(hashlib.sha256(raw_envelope.encode("utf-8")).hexdigest())
        if set(envelope) != {"turn"} or not isinstance(envelope.get("turn"), dict):
            raise AzureProviderOutputError("provider_solver_direct_turn_invalid_shape")
        turn = dict(envelope["turn"])
        kind = str(turn.get("kind", "")).strip()
        if kind == "act":
            actions = turn.get("actions")
            if not isinstance(actions, list) or len(actions) != 1 or not isinstance(actions[0], dict):
                raise AzureProviderOutputError("provider_solver_direct_turn_ambiguous_payload")
            action = dict(actions[0])
            arguments_text = action.pop("arguments_json", None)
            if not isinstance(arguments_text, str):
                raise AzureProviderOutputError("provider_solver_direct_turn_arguments_invalid")
            try:
                canonical_arguments, _arguments_body = _strict_structured_json(arguments_text)
            except AzureProviderOutputError as exc:
                raise AzureProviderOutputError(
                    "provider_solver_direct_turn_arguments_invalid", exc.code,
                ) from exc
            action["arguments"] = json.loads(canonical_arguments)
            turn["actions"] = [action]
        elif kind == "submit_outcome":
            if "actions" in turn:
                raise AzureProviderOutputError("provider_solver_direct_turn_ambiguous_payload")
        else:
            raise AzureProviderOutputError("provider_solver_direct_turn_ambiguous_payload")
        canonical_turn = json.dumps(
            turn, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        decoded_rows.append((canonical_turn, kind, raw_envelope))

    semantic_hashes = [
        hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        for canonical, _kind, _raw in decoded_rows
    ]
    if len({canonical for canonical, _kind, _raw in decoded_rows}) != 1:
        raise AzureProviderOutputError(
            "provider_solver_direct_turn_multiple_distinct_semantic_payloads",
            json.dumps({
                "candidate_count": len(decoded_rows),
                "candidate_hashes": semantic_hashes,
                "candidate_turn_kinds": [kind for _canonical, kind, _raw in decoded_rows],
            }, sort_keys=True, separators=(",", ":")),
        )

    canonical_turn, kind, _raw = decoded_rows[0]
    return canonical_turn, {
        "provider_turn_contract": "solver_direct_turn_json_schema",
        "provider_turn_kind": kind,
        "provider_turn_wrapper_sha256": hashlib.sha256(str(text).encode("utf-8")).hexdigest(),
        "provider_turn_payload_sha256": hashlib.sha256(canonical_turn.encode("utf-8")).hexdigest(),
        "provider_turn_candidate_count": len(decoded_rows),
        "provider_turn_raw_candidate_hashes": raw_hashes,
        "provider_turn_semantic_candidate_hashes": semantic_hashes,
        "provider_turn_duplicate_output": len(decoded_rows) > 1,
        "provider_turn_duplicate_equivalent": len(decoded_rows) > 1,
        "provider_turn_arguments_transport": "json_string_decoded_before_role_parser",
    }


def _unwrap_solver_provider_turn(
    text: str,
    *,
    solver_protocol: str,
) -> tuple[str, dict[str, Any]]:
    if solver_protocol == "persistent_v0":
        try:
            return canonicalize_persistent_primary_turn(text)
        except PCRProviderProtocolError as exc:
            raise AzureProviderOutputError(exc.code, exc.detail) from exc
    if solver_protocol == "solver_v1":
        return unwrap_solver_direct_turn(text)
    raise AzureProviderOutputError(
        "provider_unknown_solver_protocol", solver_protocol,
    )


def canonicalize_solver_responses_output(
    response: Any,
    *,
    solver_protocol: str = "solver_v1",
) -> tuple[str, dict[str, Any]]:
    """Decode one unambiguous Solver turn from Responses output items.

    Responses may contain reasoning metadata plus one or more assistant message
    items. Each assistant message is decoded with the strict Solver envelope
    parser before message-level equivalence is considered. This preserves the
    distinction between harmless duplicate turns and distinct future rollouts;
    no candidate is selected among distinct decisions.
    """
    messages, mixed_call = _raw_assistant_messages(response)
    receipt: dict[str, Any] = {
        "response_id": str(_usage_field(response, "id", "") or ""),
        "raw_provider_status": str(_usage_field(response, "status", "") or ""),
        "extraction_path": (
            "response.output[].message.content[].text -> persistent_v0_primary_turn"
            if solver_protocol == "persistent_v0"
            else "response.output[].message.content[].text -> solver_direct_turn"
        ),
        "candidate_message_count": len(messages),
        "candidate_hashes": tuple(row["text_sha256"] for row in messages),
        "provider_duplicate_output": False,
    }
    if mixed_call:
        raise AzureProviderOutputError("provider_mixed_message_and_tool_output")
    if not messages:
        raise AzureProviderOutputError("provider_no_assistant_message")

    canonical_rows: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
    for row in messages:
        canonical, turn_receipt = _unwrap_solver_provider_turn(
            str(row["text"]), solver_protocol=solver_protocol,
        )
        canonical_rows.append((row, canonical, turn_receipt))
    canonical_forms = {canonical for _row, canonical, _turn_receipt in canonical_rows}
    if len(canonical_forms) != 1:
        detail = json.dumps({
            "candidate_count": len(canonical_rows),
            "candidate_hashes": [
                hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                for _row, canonical, _turn_receipt in canonical_rows
            ],
            "candidate_bytes": [row["text_bytes"] for row, _canonical, _turn_receipt in canonical_rows],
            "candidate_item_ids": [row["item_id"] for row, _canonical, _turn_receipt in canonical_rows],
            "candidate_turn_kinds": [
                str(turn_receipt.get("provider_turn_kind", ""))
                for _row, _canonical, turn_receipt in canonical_rows
            ],
        }, sort_keys=True, separators=(",", ":"))
        raise AzureProviderOutputError(
            (
                "provider_persistent_v0_multiple_distinct_semantic_payloads"
                if solver_protocol == "persistent_v0"
                else "provider_solver_direct_turn_multiple_distinct_semantic_payloads"
            ),
            detail,
        )

    source, canonical, turn_receipt = canonical_rows[0]
    receipt.update(turn_receipt)
    receipt.update({
        "canonical_item_index": source["index"],
        "canonical_item_id": source["item_id"],
        "canonical_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "provider_duplicate_output": (
            len(messages) > 1
            or bool(turn_receipt.get("provider_turn_duplicate_output"))
        ),
        "provider_duplicate_semantic_equivalent": (
            len(messages) > 1
            or bool(turn_receipt.get("provider_turn_duplicate_equivalent"))
        ),
    })
    return canonical, receipt


def canonicalize_persistent_native_tool_output(
    response: Any,
    *,
    working_state_policy: str = "optional",
) -> tuple[str, dict[str, Any]]:
    """Decode exactly one provider-native ``persistent_turn`` function call.

    The Responses request itself enforces ``parallel_tool_calls=False`` and
    ``max_tool_calls=1``. This decoder independently fails closed unless the
    terminal response contains exactly one named PERSISTENT function call and no
    assistant message text or other executable call item. The function
    arguments are then validated by the same canonical PERSISTENT turn authority used
    by the text transports; the kernel remains the only executor.
    """
    calls: list[dict[str, Any]] = []
    assistant_messages: list[str] = []
    other_calls: list[str] = []
    for index, item in enumerate(_usage_field(response, "output", ()) or ()):
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
            if parts:
                assistant_messages.append("".join(parts))
            continue
        if item_type.endswith("_call"):
            other_calls.append(item_type)

    if assistant_messages or other_calls:
        raise AzureProviderOutputError(
            "provider_persistent_v0_native_tool_mixed_output",
            json.dumps({
                "assistant_message_count": len(assistant_messages),
                "other_call_types": other_calls,
                "persistent_function_call_count": len(calls),
            }, sort_keys=True, separators=(",", ":")),
        )
    if len(calls) != 1:
        raise AzureProviderOutputError(
            "provider_persistent_v0_native_tool_call_count_invalid",
            f"expected=1 actual={len(calls)}",
        )
    call = calls[0]
    if call["name"] != _PERSISTENT_PRIMARY_NATIVE_TOOL_NAME:
        raise AzureProviderOutputError(
            "provider_persistent_v0_native_tool_name_invalid", call["name"] or "missing",
        )
    try:
        canonical, turn_receipt = canonicalize_persistent_primary_turn(
            call["arguments"], working_state_policy=working_state_policy,
        )
    except PCRProviderProtocolError as exc:
        raise AzureProviderOutputError(exc.code, exc.detail) from exc
    receipt = {
        "response_id": str(_usage_field(response, "id", "") or ""),
        "raw_provider_status": str(_usage_field(response, "status", "") or ""),
        "extraction_path": "response.output[].function_call.arguments -> persistent_v0_primary_turn",
        "candidate_message_count": 0,
        "provider_duplicate_output": False,
        "native_tool_name": _PERSISTENT_PRIMARY_NATIVE_TOOL_NAME,
        "native_tool_call_count": 1,
        "native_tool_item_index": call["index"],
        "native_tool_item_id": call["id"],
        "native_tool_call_id": call["call_id"],
        "canonical_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    receipt.update(turn_receipt)
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

def unwrap_solver_chat_turn(text: str) -> tuple[str, dict[str, Any]]:
    """Collapse only a complete, semantically identical Solver object sequence.

    Azure Chat can place an equivalent JSON object twice inside its single
    assistant message. Parse the complete sequence, preserve candidate hashes,
    and collapse only when every object has the same canonical JSON value.
    Distinct, malformed, non-object, duplicate-key, non-standard, or trailing
    candidates remain provider-invalid. This function does not validate the
    SolverTurn schema; ``parse_solver_turn`` remains the role authority.
    """
    try:
        candidates = _provider_json_object_sequence(text)
    except AzureProviderOutputError as exc:
        codes = {
            "provider_envelope_empty": "provider_solver_turn_empty",
            "provider_envelope_invalid_json": "provider_structured_output_invalid_json",
            "provider_envelope_nonstandard_json_constant": "provider_structured_output_nonstandard_json_constant",
            "provider_envelope_duplicate_key": "provider_solver_turn_duplicate_key",
            "provider_envelope_top_level_not_object": "provider_solver_turn_not_object",
        }
        raise AzureProviderOutputError(codes.get(exc.code, exc.code), exc.detail) from exc

    canonical = [
        json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        for _raw, value in candidates
    ]
    hashes = [hashlib.sha256(value.encode("utf-8")).hexdigest() for value in canonical]
    raw_hashes = [
        hashlib.sha256(raw.encode("utf-8")).hexdigest()
        for raw, _value in candidates
    ]
    if len(set(canonical)) != 1:
        raise AzureProviderOutputError(
            "provider_solver_turn_multiple_distinct_semantic_payloads",
            json.dumps({
                "candidate_count": len(candidates),
                "candidate_hashes": hashes,
                "candidate_top_level_keys": [sorted(value) for _raw, value in candidates],
            }, sort_keys=True, separators=(",", ":")),
        )
    accepted = canonical[0]
    decoded = json.loads(accepted)
    return accepted, {
        "provider_turn_contract": "solver_turn_json_object",
        "provider_turn_kind": str(decoded.get("kind") or "role_parser"),
        "provider_turn_wrapper_sha256": hashlib.sha256(str(text).encode("utf-8")).hexdigest(),
        "provider_turn_payload_sha256": hashlib.sha256(accepted.encode("utf-8")).hexdigest(),
        "provider_turn_candidate_count": len(candidates),
        "provider_turn_raw_candidate_hashes": raw_hashes,
        "provider_turn_semantic_candidate_hashes": hashes,
        "provider_turn_duplicate_equivalent": len(candidates) > 1,
    }


def unwrap_verifier_provider_envelope(
    text: str,
) -> tuple[str, dict[str, Any]]:
    """Unwrap equivalent provider-envelope renderings without choosing a reply.

    The regular inspection/verdict parsers decide whether the payload is valid
    and admissible; this boundary only proves that every complete provider
    rendering carries the same unambiguous envelope.  Azure may concatenate
    equivalent outer objects or equivalent ``payload_json`` values in one
    assistant message.  We preserve hashes for every candidate and collapse
    only semantic duplicates.  Distinct, malformed, truncated, or duplicate-
    key candidates remain provider-invalid.
    """
    outer_candidates = _provider_json_object_sequence(text)
    outer_raw_hashes = [
        hashlib.sha256(raw.encode("utf-8")).hexdigest()
        for raw, _envelope in outer_candidates
    ]
    semantic_candidates: list[str] = []
    inner_raw_hashes: list[list[str]] = []
    inner_candidate_counts: list[int] = []
    inner_duplicate_equivalent: list[bool] = []

    for _raw, envelope in outer_candidates:
        if set(envelope) != {"payload_json"}:
            raise AzureProviderOutputError("provider_envelope_invalid_shape")
        payload = envelope.get("payload_json")
        if not isinstance(payload, str):
            raise AzureProviderOutputError("provider_envelope_invalid_shape")

        inner_candidates = _provider_json_object_sequence(payload)
        inner_canonical = [
            json.dumps(
                candidate,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            for _inner_raw, candidate in inner_candidates
        ]
        if len(set(inner_canonical)) != 1:
            raise AzureProviderOutputError(
                "provider_envelope_multiple_distinct_inner_payloads",
                json.dumps({
                    "candidate_count": len(inner_candidates),
                    "candidate_hashes": [
                        hashlib.sha256(value.encode("utf-8")).hexdigest()
                        for value in inner_canonical
                    ],
                }, sort_keys=True, separators=(",", ":")),
            )
        semantic_candidates.append(inner_canonical[0])
        inner_raw_hashes.append([
            hashlib.sha256(raw_inner.encode("utf-8")).hexdigest()
            for raw_inner, _candidate in inner_candidates
        ])
        inner_candidate_counts.append(len(inner_candidates))
        inner_duplicate_equivalent.append(len(inner_candidates) > 1)

    semantic_hashes = [
        hashlib.sha256(value.encode("utf-8")).hexdigest()
        for value in semantic_candidates
    ]
    if len(set(semantic_candidates)) != 1:
        raise AzureProviderOutputError(
            "provider_envelope_multiple_distinct_semantic_payloads",
            json.dumps({
                "candidate_count": len(semantic_candidates),
                "candidate_hashes": semantic_hashes,
            }, sort_keys=True, separators=(",", ":")),
        )

    canonical = semantic_candidates[0]
    decoded = json.loads(canonical)
    is_inspect = str(decoded.get("kind") or "") == "inspect"
    is_verdict = isinstance(decoded.get("verdict"), str) and bool(str(decoded["verdict"]).strip())
    if is_inspect == is_verdict:
        raise AzureProviderOutputError("provider_envelope_ambiguous_payload")
    return canonical, {
        "provider_envelope_kind": "inspect" if is_inspect else "verdict",
        "provider_envelope_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "provider_envelope_payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "provider_envelope_candidate_count": len(outer_candidates),
        "provider_envelope_raw_candidate_hashes": outer_raw_hashes,
        "provider_envelope_semantic_candidate_hashes": semantic_hashes,
        "provider_envelope_duplicate_equivalent": len(outer_candidates) > 1,
        "provider_envelope_inner_candidate_counts": inner_candidate_counts,
        "provider_envelope_inner_raw_candidate_hashes": inner_raw_hashes,
        "provider_envelope_inner_duplicate_equivalent": inner_duplicate_equivalent,
    }


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
    if str(turn.get("kind") or "") != "inspect":
        return turn, ()
    requests = turn.get("requests")
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
        if provider_kind == "read_output" and locator.startswith("receipt:"):
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
    canonical["requests"] = normalized
    return canonical, tuple(mappings)


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
        tuple[dict[str, str], ...], tuple[dict[str, Any], ...]
    ]] = []
    for _raw, wrapper in candidates:
        if set(wrapper) != {"turn"} or not isinstance(wrapper.get("turn"), dict):
            raise AzureProviderOutputError("provider_direct_turn_invalid_shape")
        turn = _drop_null_fields(wrapper["turn"])
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
        compact_mapping_rows.append((compact_mappings, compact_command_mappings))
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


def _prepare_persistent_stateless_input_item(value: Any) -> dict[str, Any]:
    """Convert one provider output item into an accepted stateless input item.

    The Responses API distinguishes output-item and input-item shapes.  In
    particular, SDK response dumps may include ``status`` even though Azure
    rejects that field when the item is replayed as input.  Unknown item types
    fail closed rather than being silently dropped or guessed.
    """
    item = _jsonable_provider_value(value)
    if not isinstance(item, dict):
        raise AzureProviderOutputError(
            "provider_stateless_history_item_invalid",
            f"expected_object={type(item).__name__}",
        )
    item_type = str(item.get("type") or "")
    allowed = _PERSISTENT_STATELESS_INPUT_FIELDS.get(item_type)
    if allowed is None:
        raise AzureProviderOutputError(
            "provider_stateless_history_item_type_unsupported",
            f"type={item_type or 'missing'}",
        )
    prepared = {
        key: item[key]
        for key in allowed
        if key in item and item[key] is not None
    }
    if prepared.get("type") != item_type:
        raise AzureProviderOutputError(
            "provider_stateless_history_item_type_missing",
            f"type={item_type or 'missing'}",
        )
    return prepared


def _chat_completion_text(response: Any) -> tuple[str, dict[str, Any]]:
    """Extract exactly one Chat Completions assistant message, fail-closed."""
    choices = _usage_field(response, "choices", ()) or ()
    if not isinstance(choices, (list, tuple)) or len(choices) != 1:
        raise AzureProviderOutputError(
            "provider_chat_completion_choice_count_invalid",
            f"expected=1 actual={len(choices) if isinstance(choices, (list, tuple)) else 'non_sequence'}",
        )
    choice = choices[0]
    message = _usage_field(choice, "message")
    if message is None:
        raise AzureProviderOutputError("provider_chat_completion_message_missing")
    role = str(_usage_field(message, "role", "") or "")
    if role != "assistant":
        raise AzureProviderOutputError(
            "provider_chat_completion_message_role_invalid", role or "missing",
        )
    refusal = _usage_field(message, "refusal")
    if refusal:
        raise AzureProviderOutputError("provider_refusal", str(refusal)[:1000])
    finish_reason = str(_usage_field(choice, "finish_reason", "") or "")
    if finish_reason == "length":
        raise AzureProviderOutputError("provider_output_incomplete", "finish_reason=length")
    if finish_reason == "content_filter":
        raise AzureProviderOutputError("provider_content_filter")
    content = _usage_field(message, "content")
    if not isinstance(content, str) or not content.strip():
        raise AzureProviderOutputError("provider_empty_assistant_message")
    return content, {
        "choice_count": len(choices),
        "canonical_item_index": 0,
        "canonical_item_id": str(_usage_field(message, "id", "") or ""),
        "candidate_message_count": len(choices),
        "finish_reason": finish_reason,
        "extraction_path": "chat.completions.choices[0].message.content",
        "canonical_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "canonical_bytes": len(content.encode("utf-8")),
    }


def _extract_output_text(response: Any) -> str:
    """Compatibility name for strict structured-output extraction."""
    return canonicalize_structured_output(response)[0]


def _render_azure_responses_request_from_split(
    instructions: str,
    user_input: str | list[dict[str, str]],
    *,
    deployment: str,
    effort: str,
    role: str,
    max_output_tokens: int,
    background: bool,
    structured_output_schema: dict[str, Any] | None = None,
    structured_output_name: str = "aether_structured_output",
    prompt_cache_mode: str = "stable_prefix",
    prompt_cache_namespace: str = "aether-next-v1",
) -> dict[str, Any]:
    """Render one exact request from the adapter's already-split surfaces."""
    if prompt_cache_mode not in {"stable_prefix", "off"}:
        raise AzureModelError("prompt_cache_mode must be 'stable_prefix' or 'off'")
    if not prompt_cache_namespace or len(prompt_cache_namespace) > 128:
        raise AzureModelError(
            "prompt_cache_namespace must be non-empty and at most 128 characters"
        )
    if structured_output_schema is not None:
        if not isinstance(structured_output_schema, dict) or not structured_output_schema:
            raise AzureModelError("structured_output_schema must be a non-empty object")
        if not structured_output_name or len(structured_output_name) > 64:
            raise AzureModelError(
                "structured_output_name must be non-empty and at most 64 characters"
            )
    verifier_envelope = role == "verifier"
    persistent_primary_turn = (
        role == "solver"
        and structured_output_schema == PERSISTENT_PRIMARY_TURN_SCHEMA
        and structured_output_name == PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
    )
    solver_direct_turn = (
        role == "solver"
        and structured_output_schema == _SOLVER_DIRECT_TURN_SCHEMA
        and structured_output_name == _SOLVER_STRUCTURED_OUTPUT_NAME
    )
    if verifier_envelope:
        instructions = _prepare_verifier_envelope_instructions(instructions)
        user_input = _prepare_verifier_envelope_input(user_input)
    elif persistent_primary_turn:
        instructions = _prepare_persistent_primary_responses_instructions(instructions)
        user_input = _prepare_persistent_primary_responses_input(user_input)
    elif solver_direct_turn:
        instructions = _prepare_solver_responses_instructions(instructions)
        user_input = _prepare_solver_responses_input(user_input)
    else:
        instructions = _prepare_json_object_instructions(instructions)
        user_input = _prepare_json_object_input(user_input)
    provider_structured_output_schema = (
        PERSISTENT_PRIMARY_PROVIDER_SCHEMA if persistent_primary_turn else structured_output_schema
    )
    request: dict[str, Any] = {
        "model": deployment,
        "instructions": instructions,
        "input": user_input,
        "reasoning": {"effort": effort},
        "max_output_tokens": int(max_output_tokens),
        "text": (
            _VERIFIER_ENVELOPE_FORMAT
            if verifier_envelope
            else (
                {
                    "format": {
                        "type": "json_schema",
                        "name": structured_output_name,
                        "strict": True,
                        "schema": provider_structured_output_schema,
                    }
                }
                if structured_output_schema is not None
                else {"format": {"type": "json_object"}}
            )
        ),
        "background": bool(background),
    }
    if prompt_cache_mode == "stable_prefix":
        request["prompt_cache_key"] = _stable_prompt_cache_key(
            deployment=deployment,
            role=role,
            namespace=prompt_cache_namespace,
        )
        request["prompt_cache_retention"] = "in_memory"
    return request


def render_azure_responses_request(
    messages: list[dict[str, str]],
    *,
    deployment: str,
    effort: str,
    role: str,
    max_output_tokens: int,
    background: bool,
    structured_output_schema: dict[str, Any] | None = None,
    structured_output_name: str = "aether_structured_output",
    prompt_cache_mode: str = "stable_prefix",
    prompt_cache_namespace: str = "aether-next-v1",
) -> dict[str, Any]:
    """Render the exact Azure Responses request without making a provider call.

    This is the public logical-message entry point. Live dispatch calls the
    same split-surface authority after the adapter's normal message split.
    """
    instructions, user_input = _split_responses_input(messages)
    return _render_azure_responses_request_from_split(
        instructions,
        user_input,
        deployment=deployment,
        effort=effort,
        role=role,
        max_output_tokens=max_output_tokens,
        background=background,
        structured_output_schema=structured_output_schema,
        structured_output_name=structured_output_name,
        prompt_cache_mode=prompt_cache_mode,
        prompt_cache_namespace=prompt_cache_namespace,
    )


def make_azure_callable(
    *,
    deployment_env: str,
    key_env: str,
    endpoint_env: str = "AZURE_OPENAI_ENDPOINT",
    effort: str = "medium",
    role: str = "unspecified",
    solver_protocol: str = "solver_v1",
    verifier_protocol: str = "verifier_v1",
    poll_interval_s: float | None = None,
    poll_timeout_s: float | None = None,
    max_retries: int | None = None,
    sdk_max_retries: int | None = None,
    backoff_base_s: float | None = None,
    backoff_cap_s: float | None = None,
    backoff_max_total_s: float | None = None,
    max_rpm: float | None = None,
    transport: str | None = None,
    responses_background: bool | None = None,
    prompt_cache_mode: str | None = None,
    prompt_cache_namespace: str | None = None,
    structured_output_schema: dict[str, Any] | None = None,
    structured_output_name: str = "aether_structured_output",
    persistent_continuity_mode: str = "explicit",
    persistent_compact_threshold: int | None = None,
    persistent_reasoning_context: str | None = None,
    persistent_working_state_policy: str = "optional",
) -> "AzureModelCallable":
    """Build a ``ModelCallable`` backed by an Azure OpenAI deployment.

    Env vars are read at *build time* (not per-call), so a missing var
    raises immediately rather than mid-run.

    Verifier calls default to Chat Completions with one choice and a direct
    strict-schema turn. Other roles use the Responses API in background mode:
    create with ``background=True``, then poll ``retrieve`` until the status
    leaves ``queued`` / ``in_progress``.

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
    endpoint = _normalize_endpoint(os.environ[endpoint_env])
    deployment = os.environ[deployment_env]
    api_key = os.environ[key_env]
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

    # The Verifier needs an atomic turn.  Chat Completions requests one choice
    # and one assistant message, while the direct nested schema avoids the
    # former string-envelope escaping defect. Other roles retain Responses.
    resolved_transport = transport or ("chat_completions" if role == "verifier" else "responses")
    if resolved_transport not in {"responses", "responses_tools", "chat_completions"}:
        raise AzureModelError(f"unsupported Azure model transport: {resolved_transport}")
    if resolved_transport == "responses_tools" and not (
        role == "verifier" or (role == "solver" and solver_protocol == "persistent_v0")
    ):
        raise AzureModelError("responses_tools is certified only for the PERSISTENT V0 Solver or Verifier")
    if solver_protocol not in {"solver_v1", "persistent_v0"}:
        raise AzureModelError(f"unsupported Solver protocol: {solver_protocol}")
    if role != "solver" and solver_protocol != "solver_v1":
        raise AzureModelError("solver_protocol is valid only for the Solver role")
    if verifier_protocol not in {"verifier_v1", "persistent_v0"}:
        raise AzureModelError(f"unsupported Verifier protocol: {verifier_protocol}")
    if role != "verifier" and verifier_protocol != "verifier_v1":
        raise AzureModelError("verifier_protocol is valid only for the Verifier role")
    if verifier_protocol == "persistent_v0" and resolved_transport != "responses_tools":
        raise AzureModelError("PERSISTENT V0 Verifier protocol requires responses_tools transport")
    resolved_persistent_continuity_mode = str(persistent_continuity_mode or "explicit").strip().lower()
    if resolved_persistent_continuity_mode not in _PERSISTENT_CONTINUITY_MODES:
        raise AzureModelError(
            "persistent_continuity_mode must be explicit, previous_response, "
            "previous_response_compaction, stateless_encrypted, or stateless_compaction"
        )
    if resolved_persistent_continuity_mode != "explicit" and not (
        role == "solver"
        and solver_protocol == "persistent_v0"
        and resolved_transport == "responses_tools"
    ):
        raise AzureModelError(
            "PERSISTENT native continuity is experimental and requires the PERSISTENT V0 Solver responses_tools route"
        )
    if resolved_persistent_continuity_mode in {"previous_response_compaction", "stateless_compaction"}:
        if persistent_compact_threshold is None or int(persistent_compact_threshold) <= 0:
            raise AzureModelError(
                f"{resolved_persistent_continuity_mode} requires a positive persistent_compact_threshold"
            )
    elif persistent_compact_threshold is not None:
        raise AzureModelError(
            "persistent_compact_threshold is accepted only with a compaction continuity mode"
        )
    resolved_persistent_reasoning_context = (
        None if persistent_reasoning_context in (None, "")
        else str(persistent_reasoning_context).strip().lower()
    )
    if resolved_persistent_reasoning_context is not None and resolved_persistent_reasoning_context not in _PERSISTENT_REASONING_CONTEXT_MODES:
        raise AzureModelError(
            "persistent_reasoning_context must be current_turn, all_turns, or omitted"
        )
    if resolved_persistent_reasoning_context is not None and not (
        role == "solver"
        and solver_protocol == "persistent_v0"
        and resolved_transport == "responses_tools"
        and resolved_persistent_continuity_mode in {"previous_response", "previous_response_compaction"}
    ):
        raise AzureModelError(
            "PERSISTENT reasoning.context requires the PERSISTENT V0 Solver responses_tools "
            "stateful previous_response route"
        )
    try:
        resolved_persistent_working_state_policy = normalize_persistent_working_state_policy(
            persistent_working_state_policy
        )
    except PCRProviderProtocolError as exc:
        raise AzureModelError(str(exc)) from exc
    if resolved_persistent_working_state_policy != "optional" and not (
        role == "solver"
        and solver_protocol == "persistent_v0"
        and resolved_transport == "responses_tools"
    ):
        raise AzureModelError(
            "PERSISTENT working-state policy is valid only for the PERSISTENT V0 Solver responses_tools route"
        )
    if role == "solver" and resolved_transport == "responses":
        expected_solver_schema = (
            PERSISTENT_PRIMARY_TURN_SCHEMA
            if solver_protocol == "persistent_v0"
            else _SOLVER_DIRECT_TURN_SCHEMA
        )
        expected_solver_name = (
            PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
            if solver_protocol == "persistent_v0"
            else _SOLVER_STRUCTURED_OUTPUT_NAME
        )
        if (
            structured_output_schema is not None
            and structured_output_schema != expected_solver_schema
        ):
            raise AzureModelError("the Solver Responses route owns its strict turn schema for the selected protocol")
        structured_output_schema = expected_solver_schema
        structured_output_name = expected_solver_name
    if structured_output_schema is not None:
        if role == "verifier":
            raise AzureModelError(
                "custom structured_output_schema is not accepted for the frozen Verifier route"
            )
        if resolved_transport != "responses":
            raise AzureModelError(
                "custom structured_output_schema currently requires the Responses transport"
            )
        if not isinstance(structured_output_schema, dict) or not structured_output_schema:
            raise AzureModelError("structured_output_schema must be a non-empty object")
        if not structured_output_name or len(structured_output_name) > 64:
            raise AzureModelError(
                "structured_output_name must be non-empty and at most 64 characters"
            )

    if openai is None:
        raise AzureModelError("openai package is required for AzureModelCallable")
    resolved_background = (
        _responses_background_enabled()
        if responses_background is None
        else bool(responses_background)
    )
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
    client = openai.OpenAI(
        api_key=api_key,
        base_url=f"{endpoint}/openai/v1/",
        timeout=resolved_poll_timeout_s + 60,
        max_retries=resolved_sdk_max_retries,
    )

    return AzureModelCallable(
        client=client,
        deployment=deployment,
        effort=effort,
        role=role,
        solver_protocol=solver_protocol,
        verifier_protocol=verifier_protocol,
        prompt_cache_mode=resolved_cache_mode,
        prompt_cache_namespace=resolved_cache_namespace,
        responses_background=resolved_background,
        poll_interval_s=resolved_poll_interval_s,
        poll_timeout_s=resolved_poll_timeout_s,
        max_retries=resolved_max_retries,
        backoff_base_s=resolved_backoff_base_s,
        backoff_cap_s=resolved_backoff_cap_s,
        backoff_max_total_s=resolved_backoff_max_total_s,
        rate_limiter=get_rate_limiter_for_deployment(deployment, resolved_max_rpm),
        transport=resolved_transport,
        structured_output_schema=structured_output_schema,
        structured_output_name=structured_output_name,
        persistent_continuity_mode=resolved_persistent_continuity_mode,
        persistent_compact_threshold=persistent_compact_threshold,
        persistent_reasoning_context=resolved_persistent_reasoning_context,
        persistent_working_state_policy=resolved_persistent_working_state_policy,
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
        deployment: str,
        effort: str,
        role: str = "unspecified",
        solver_protocol: str = "solver_v1",
        verifier_protocol: str = "verifier_v1",
        prompt_cache_mode: str = "stable_prefix",
        prompt_cache_namespace: str = "aether-next-v1",
        responses_background: bool | None = None,
        poll_interval_s: float,
        poll_timeout_s: float,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        backoff_cap_s: float = DEFAULT_BACKOFF_CAP_S,
        backoff_max_total_s: float | None = DEFAULT_BACKOFF_MAX_TOTAL_S,
        rate_limiter: RateLimiter | None = None,
        transport: str = "responses",
        structured_output_schema: dict[str, Any] | None = None,
        structured_output_name: str = "aether_structured_output",
        persistent_continuity_mode: str = "explicit",
        persistent_compact_threshold: int | None = None,
        persistent_reasoning_context: str | None = None,
        persistent_working_state_policy: str = "optional",
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._client = client
        self._deployment = deployment
        self._effort = effort
        self._role = role
        if solver_protocol not in {"solver_v1", "persistent_v0"}:
            raise ValueError(f"unsupported Solver protocol: {solver_protocol}")
        if role != "solver" and solver_protocol != "solver_v1":
            raise ValueError("solver_protocol is valid only for the Solver role")
        self._solver_protocol = solver_protocol
        if verifier_protocol not in {"verifier_v1", "persistent_v0"}:
            raise ValueError(f"unsupported Verifier protocol: {verifier_protocol}")
        if role != "verifier" and verifier_protocol != "verifier_v1":
            raise ValueError("verifier_protocol is valid only for the Verifier role")
        if verifier_protocol == "persistent_v0" and transport != "responses_tools":
            raise ValueError("PERSISTENT V0 Verifier protocol requires responses_tools transport")
        self._verifier_protocol = verifier_protocol
        if transport not in {"responses", "responses_tools", "chat_completions"}:
            raise ValueError("transport must be 'responses', 'responses_tools', or 'chat_completions'")
        if transport == "responses_tools" and not (
            role == "verifier" or (role == "solver" and solver_protocol == "persistent_v0")
        ):
            raise ValueError("responses_tools is certified only for the PERSISTENT V0 Solver or Verifier")
        self._transport = transport
        if (
            role == "solver"
            and transport == "responses"
            and structured_output_schema is not None
        ):
            expected_solver_schema = (
                PERSISTENT_PRIMARY_TURN_SCHEMA
                if solver_protocol == "persistent_v0"
                else _SOLVER_DIRECT_TURN_SCHEMA
            )
            expected_solver_name = (
                PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
                if solver_protocol == "persistent_v0"
                else _SOLVER_STRUCTURED_OUTPUT_NAME
            )
            if structured_output_schema != expected_solver_schema:
                raise ValueError("the Solver Responses route owns its strict turn schema for the selected protocol")
            structured_output_name = expected_solver_name
        if structured_output_schema is not None and transport != "responses":
            raise ValueError("structured_output_schema requires Responses transport")
        if structured_output_schema is not None and role == "verifier":
            raise ValueError("the frozen Verifier route owns its own strict schema")
        if structured_output_schema is not None and (
            not isinstance(structured_output_schema, dict) or not structured_output_schema
        ):
            raise ValueError("structured_output_schema must be a non-empty object")
        if not structured_output_name or len(structured_output_name) > 64:
            raise ValueError("structured_output_name must be non-empty and at most 64 characters")
        self._structured_output_schema = structured_output_schema
        self._structured_output_name = structured_output_name
        if prompt_cache_mode not in {"stable_prefix", "off"}:
            raise ValueError("prompt_cache_mode must be 'stable_prefix' or 'off'")
        self._prompt_cache_mode = prompt_cache_mode
        if not prompt_cache_namespace or len(prompt_cache_namespace) > 128:
            raise ValueError("prompt_cache_namespace must be non-empty and at most 128 characters")
        self._prompt_cache_namespace = prompt_cache_namespace
        resolved_persistent_continuity_mode = str(persistent_continuity_mode or "explicit").strip().lower()
        if resolved_persistent_continuity_mode not in _PERSISTENT_CONTINUITY_MODES:
            raise ValueError(
                "persistent_continuity_mode must be explicit, previous_response, "
                "stateless_encrypted, or stateless_compaction"
            )
        if resolved_persistent_continuity_mode != "explicit" and not (
            role == "solver" and solver_protocol == "persistent_v0" and transport == "responses_tools"
        ):
            raise ValueError(
                "PERSISTENT native continuity is experimental and requires the PERSISTENT V0 Solver responses_tools route"
            )
        if resolved_persistent_continuity_mode in {"previous_response_compaction", "stateless_compaction"}:
            if persistent_compact_threshold is None or int(persistent_compact_threshold) <= 0:
                raise ValueError(
                    f"{resolved_persistent_continuity_mode} requires a positive persistent_compact_threshold"
                )
            self._persistent_compact_threshold = int(persistent_compact_threshold)
        else:
            if persistent_compact_threshold is not None:
                raise ValueError(
                    "persistent_compact_threshold is accepted only with a compaction continuity mode"
                )
            self._persistent_compact_threshold = None
        self._persistent_continuity_mode = resolved_persistent_continuity_mode
        resolved_persistent_reasoning_context = (
            None if persistent_reasoning_context in (None, "")
            else str(persistent_reasoning_context).strip().lower()
        )
        if resolved_persistent_reasoning_context is not None and resolved_persistent_reasoning_context not in _PERSISTENT_REASONING_CONTEXT_MODES:
            raise ValueError(
                "persistent_reasoning_context must be current_turn, all_turns, or omitted"
            )
        if resolved_persistent_reasoning_context is not None and not (
            role == "solver"
            and solver_protocol == "persistent_v0"
            and transport == "responses_tools"
            and resolved_persistent_continuity_mode in {
                "previous_response", "previous_response_compaction",
            }
        ):
            raise ValueError(
                "PERSISTENT reasoning.context requires the PERSISTENT V0 Solver responses_tools "
                "stateful previous_response route"
            )
        try:
            resolved_persistent_working_state_policy = normalize_persistent_working_state_policy(
                persistent_working_state_policy
            )
        except PCRProviderProtocolError as exc:
            raise ValueError(str(exc)) from exc
        if resolved_persistent_working_state_policy != "optional" and not (
            role == "solver"
            and solver_protocol == "persistent_v0"
            and transport == "responses_tools"
        ):
            raise ValueError(
                "PERSISTENT working-state policy is valid only for the PERSISTENT V0 Solver responses_tools route"
            )
        self._persistent_reasoning_context = resolved_persistent_reasoning_context
        self._persistent_working_state_policy = resolved_persistent_working_state_policy
        self._persistent_primary_native_tool = _persistent_primary_native_tool_for_policy(
            resolved_persistent_working_state_policy
        )
        self._persistent_policy_instruction = (
            ""
            if resolved_persistent_working_state_policy == "optional"
            else persistent_primary_turn_response_instruction(
                working_state_policy=resolved_persistent_working_state_policy
            )
        )
        self._persistent_continuity_states: dict[tuple[str, str], dict[str, Any]] = {}
        self._persistent_continuity_pending_states: dict[tuple[str, str], dict[str, Any]] = {}
        self._persistent_continuity_lock = threading.Lock()
        self._persistent_continuity_admission_events: list[dict[str, Any]] = []
        self._responses_background = (
            _responses_background_enabled()
            if responses_background is None
            else bool(responses_background)
        )
        self._poll_interval_s = max(1.0, poll_interval_s)
        self._poll_timeout_s = max(30.0, poll_timeout_s)
        self._max_retries = max(0, max_retries)
        self._backoff_base_s = max(0.0, backoff_base_s)
        self._backoff_cap_s = max(0.0, backoff_cap_s)
        self._backoff_max_total_s = backoff_max_total_s
        self._rate_limiter = rate_limiter
        # Injectable for tests only; production callers get real time.sleep
        # / random.random via the defaults above.
        self._retry_sleep = sleep
        self._rand = rand
        self.last_call_telemetry: dict[str, Any] = {}
        self._telemetry_events: list[dict[str, Any]] = []
        self._telemetry_lock = threading.Lock()
        self._next_logical_call_id = 0

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

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return self._call(messages, max_output_tokens=max_output_tokens, telemetry_scope=None)

    def call_with_telemetry_scope(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
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
        max_output_tokens: int,
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
            if self._transport == "chat_completions":
                return self._call_chat_once(
                    messages,
                    max_output_tokens,
                    logical_call_id=logical_call_id,
                    attempt_ordinal=attempts,
                    telemetry_scope=telemetry_scope,
                )
            instructions, user_input = _split_responses_input(messages)
            if self._transport == "responses_tools":
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
            return self._call_once(
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

    def _call_chat_once(
        self,
        messages: list[dict[str, str]],
        max_output_tokens: int,
        *,
        logical_call_id: int,
        attempt_ordinal: int,
        telemetry_scope: dict[str, str | None] | None,
    ) -> str:
        """Run one one-choice Chat Completions attempt.

        Verifier retains its typed direct-turn schema. Other roles may use
        generic JSON-object Chat transport when explicitly selected; their
        role parser remains the authority for the returned object.
        """
        verifier_direct_turn = self._role == "verifier"
        solver_direct_turn = self._role == "solver"
        persistent_primary_turn = solver_direct_turn and self._solver_protocol == "persistent_v0"
        prepared_messages = (
            _prepare_verifier_chat_messages(messages)
            if verifier_direct_turn
            else (
                _prepare_persistent_primary_chat_messages(messages)
                if persistent_primary_turn
                else (
                    _prepare_solver_chat_messages(messages)
                    if solver_direct_turn
                    else _prepare_json_object_chat_messages(messages)
                )
            )
        )
        event: dict[str, Any] = {
            "event_kind": "provider_attempt",
            "logical_call_id": logical_call_id,
            "attempt_ordinal": attempt_ordinal,
            "provider": "azure_openai_chat_completions",
            "deployment": self._deployment,
            "role": self._role,
            "status": "in_progress",
            "attempt_phase": "create",
            "instructions_chars": sum(
                len(str(msg.get("content", ""))) for msg in prepared_messages
            ),
            "input_chars": len(json.dumps(prepared_messages, sort_keys=True)),
            "instructions_sha256": hashlib.sha256(
                json.dumps(prepared_messages, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "input_sha256": hashlib.sha256(
                json.dumps(prepared_messages, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "max_output_tokens": max_output_tokens,
            "choice_count_requested": 1,
            "structured_output_mode": (
                "verifier_direct_turn_json_schema"
                if verifier_direct_turn
                else (
                    "persistent_v0_primary_turn_json_schema"
                    if persistent_primary_turn
                    else ("solver_direct_turn_json_schema" if solver_direct_turn else "chat_json_object")
                )
            ),
            "usage_status": "unmeasured",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "reasoning_tokens": None,
        }
        if telemetry_scope is not None:
            event.update(telemetry_scope)
        started = time.monotonic()
        try:
            if self._rate_limiter is not None:
                self._rate_limiter.acquire()
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=prepared_messages,
                reasoning_effort=self._effort,
                max_completion_tokens=max_output_tokens,
                n=1,
                response_format=(
                    _VERIFIER_CHAT_RESPONSE_FORMAT
                    if verifier_direct_turn
                    else (
                        PERSISTENT_PRIMARY_CHAT_RESPONSE_FORMAT
                        if persistent_primary_turn
                        else (_SOLVER_CHAT_RESPONSE_FORMAT if solver_direct_turn else {"type": "json_object"})
                    )
                ),
            )
            event.update({
                "attempt_phase": "terminal",
                "job_status": "completed",
                "response_id": str(_usage_field(response, "id", "") or ""),
                **_usage_telemetry(response),
            })
            if os.environ.get("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT") == "1":
                event["raw_provider_response"] = _jsonable_provider_value(response)
            text, output_receipt = _chat_completion_text(response)
            if verifier_direct_turn:
                canonical, turn_receipt = unwrap_verifier_direct_turn(text)
            elif solver_direct_turn:
                canonical, turn_receipt = _unwrap_solver_provider_turn(
                    text, solver_protocol=self._solver_protocol,
                )
            else:
                canonical, _body = _strict_structured_json(text)
                turn_receipt = {
                    "provider_turn_contract": "chat_json_object",
                    "provider_turn_kind": "role_parser",
                    "provider_turn_wrapper_sha256": hashlib.sha256(
                        str(text).encode("utf-8")
                    ).hexdigest(),
                    "provider_turn_payload_sha256": hashlib.sha256(
                        canonical.encode("utf-8")
                    ).hexdigest(),
                    "provider_turn_candidate_count": 1,
                    "provider_turn_duplicate_equivalent": False,
                }
            event.update(output_receipt)
            event.update(turn_receipt)
            event["status"] = "completed"
            return canonical
        except Exception as exc:
            event.update({
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "error": str(exc)[:1000],
            })
            if isinstance(exc, AzureProviderOutputError):
                event["provider_output_error"] = exc.code
            if exc.__class__.__name__ == "KernelRunTimeout":
                raise
            if isinstance(exc, AzureModelError):
                raise
            raise AzureModelError(f"chat.completions.create failed: {exc}") from exc
        finally:
            event["elapsed_s"] = round(time.monotonic() - started, 3)
            self._record_attempt(event)

    def _persistent_continuity_state(
        self, scope_key: tuple[str, str],
    ) -> dict[str, Any] | None:
        with self._persistent_continuity_lock:
            state = self._persistent_continuity_states.get(scope_key)
            return None if state is None else dict(state)

    def _persistent_pending_continuity_state(
        self, scope_key: tuple[str, str],
    ) -> dict[str, Any] | None:
        with self._persistent_continuity_lock:
            state = self._persistent_continuity_pending_states.get(scope_key)
            return None if state is None else dict(state)

    def commit_pending_response(self, *, run_id: str, task_id: str) -> None:
        if self._persistent_continuity_mode == "explicit":
            return
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            pending = self._persistent_continuity_pending_states.pop(key, None)
            if pending is None:
                raise AzureModelError("persistent_continuity_pending_candidate_missing_at_commit")
            previous = self._persistent_continuity_states.get(key)
            self._persistent_continuity_states[key] = dict(pending)
        self._record_continuity_admission_event({
            "event_kind": "persistent_continuity_parent_admission",
            "provider": "azure_openai_responses",
            "deployment": self._deployment,
            "role": self._role,
            "run_id": key[0],
            "task_id": key[1],
            "persistent_continuity_mode": self._persistent_continuity_mode,
            "persistent_continuity_parent_disposition": "committed",
            "persistent_continuity_response_id": pending.get("response_id"),
            "persistent_continuity_call_id": pending.get("call_id"),
            "persistent_continuity_previous_committed_response_id": None if previous is None else previous.get("response_id"),
            "persistent_continuity_history_item_count": len(pending.get("history_items", [])),
        })

    def reject_pending_response(self, *, run_id: str, task_id: str) -> None:
        if self._persistent_continuity_mode == "explicit":
            return
        key = _persistent_continuity_scope_key({"run_id": run_id, "task_id": task_id})
        with self._persistent_continuity_lock:
            pending = self._persistent_continuity_pending_states.pop(key, None)
            previous = self._persistent_continuity_states.get(key)
        if pending is None:
            return
        self._record_continuity_admission_event({
            "event_kind": "persistent_continuity_parent_admission",
            "provider": "azure_openai_responses",
            "deployment": self._deployment,
            "role": self._role,
            "run_id": key[0],
            "task_id": key[1],
            "persistent_continuity_mode": self._persistent_continuity_mode,
            "persistent_continuity_parent_disposition": "rejected",
            "persistent_continuity_response_id": pending.get("response_id"),
            "persistent_continuity_call_id": pending.get("call_id"),
            "persistent_continuity_previous_committed_response_id": None if previous is None else previous.get("response_id"),
            "persistent_continuity_history_item_count": len(pending.get("history_items", [])),
        })

    def clear_continuity_scope(self, *, run_id: str, task_id: str) -> None:
        """Release pending and committed provider-native PERSISTENT state for one run."""
        key = (str(run_id).strip(), str(task_id).strip())
        if not all(key):
            return
        with self._persistent_continuity_lock:
            self._persistent_continuity_pending_states.pop(key, None)
            self._persistent_continuity_states.pop(key, None)

    def _prepare_persistent_continuation_request(
        self,
        request: dict[str, Any],
        *,
        user_input: str | list[dict[str, str]],
        telemetry_scope: dict[str, str | None] | None,
    ) -> tuple[dict[str, Any], tuple[str, str] | None, dict[str, Any] | None]:
        mode = self._persistent_continuity_mode
        if mode == "explicit":
            return request, None, None
        scope_key = _persistent_continuity_scope_key(telemetry_scope)
        if self._persistent_pending_continuity_state(scope_key) is not None:
            raise AzureModelError("persistent_continuity_pending_candidate_requires_admission")
        previous = self._persistent_continuity_state(scope_key)
        prepared = dict(request)
        current_boundary = _responses_input_text(user_input)
        if mode in {"previous_response", "previous_response_compaction"}:
            # Response-ID chaining keeps client wire bounded. Ordinary stored
            # chaining uses store=true. Azure's current server-side compaction
            # contract explicitly requires store=false, so the compaction arm
            # renders that exact combination and remains provider-unqualified
            # until the no-dispatch canary proves previous_response_id chaining
            # against a non-stored compacting response on the target deployment.
            prepared["store"] = (mode == "previous_response")
            if mode == "previous_response_compaction":
                prepared["context_management"] = [{
                    "type": "compaction",
                    "compact_threshold": int(self._persistent_compact_threshold or 0),
                }]
            if previous is not None:
                prepared["previous_response_id"] = str(previous["response_id"])
                prepared["input"] = [{
                    "type": "function_call_output",
                    "call_id": str(previous["call_id"]),
                    "output": current_boundary,
                }]
            return prepared, scope_key, previous

        # Stateless native reasoning continuity: carry the exact provider output
        # items plus host function outputs. The provider owns opaque reasoning;
        # Aether owns the current external-truth boundary supplied as tool output.
        prepared["store"] = False
        prepared["include"] = ["reasoning.encrypted_content"]
        if mode == "stateless_compaction":
            prepared["context_management"] = [{
                "type": "compaction",
                "compact_threshold": int(self._persistent_compact_threshold or 0),
            }]
        if previous is not None:
            history = [dict(item) for item in previous.get("history_items", [])]
            history.append({
                "type": "function_call_output",
                "call_id": str(previous["call_id"]),
                "output": current_boundary,
            })
            prepared["input"] = history
        return prepared, scope_key, previous

    def _stage_persistent_continuity_state(
        self,
        *,
        scope_key: tuple[str, str] | None,
        previous: dict[str, Any] | None,
        request: dict[str, Any],
        response: Any,
        output_receipt: dict[str, Any],
    ) -> dict[str, Any]:
        mode = self._persistent_continuity_mode
        if mode == "explicit" or scope_key is None:
            return {
                "persistent_continuity_mode": "explicit",
                "persistent_continuity_state_advanced": False,
            }
        response_id = str(_usage_field(response, "id", "") or "")
        call_id = str(output_receipt.get("native_tool_call_id") or "")
        if not response_id or not call_id:
            raise AzureProviderOutputError(
                "provider_persistent_v0_continuity_identity_missing",
                f"response_id={bool(response_id)} call_id={bool(call_id)}",
            )
        state: dict[str, Any] = {
            "response_id": response_id,
            "call_id": call_id,
        }
        response_output_items = [
            item for item in (
                _jsonable_provider_value(item)
                for item in (_usage_field(response, "output", ()) or ())
            )
            if isinstance(item, dict)
        ]
        response_compaction_observed = (
            _latest_compaction_index(response_output_items) is not None
        )
        history_pruned_to_compaction = False
        if mode in {"stateless_encrypted", "stateless_compaction"}:
            input_items = _responses_input_items(request.get("input", []))
            output_items = [
                _prepare_persistent_stateless_input_item(item)
                for item in response_output_items
            ]
            if mode == "stateless_compaction" and response_compaction_observed:
                # The provider API does not guarantee a fixed order for output
                # items. A current function_call may therefore appear before or
                # after the compaction item. The compaction item makes prior
                # request history discardable, but keep this response's entire
                # output array in provider order so the accepted function call
                # can always be paired with the host's next function_call_output.
                history = output_items
                history_pruned_to_compaction = bool(input_items)
            else:
                history = input_items + output_items
            state["history_items"] = history
        with self._persistent_continuity_lock:
            if scope_key in self._persistent_continuity_pending_states:
                raise AzureModelError("persistent_continuity_pending_candidate_already_staged")
            self._persistent_continuity_pending_states[scope_key] = state
        return {
            "persistent_continuity_mode": mode,
            "persistent_continuity_state_advanced": False,
            "persistent_continuity_candidate_staged": True,
            "persistent_continuity_previous_state_present": previous is not None,
            "persistent_continuity_response_id": response_id,
            "persistent_continuity_call_id": call_id,
            "persistent_continuity_history_item_count": len(state.get("history_items", [])),
            "persistent_continuity_compaction_observed": response_compaction_observed,
            "persistent_continuity_history_pruned_to_compaction": history_pruned_to_compaction,
        }

    def _call_persistent_tool_once(
        self,
        instructions: str,
        user_input: str | list[dict[str, str]],
        max_output_tokens: int,
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
        request: dict[str, Any] = {
            "model": self._deployment,
            "instructions": prepared_instructions,
            "input": user_input,
            "reasoning": reasoning_request,
            "max_output_tokens": int(max_output_tokens),
            "tools": [self._persistent_primary_native_tool],
            "tool_choice": {"type": "function", "name": _PERSISTENT_PRIMARY_NATIVE_TOOL_NAME},
            "parallel_tool_calls": False,
            "max_tool_calls": 1,
            "background": bool(self._responses_background),
        }
        if self._prompt_cache_mode == "stable_prefix":
            request["prompt_cache_key"] = _stable_prompt_cache_key(
                deployment=self._deployment,
                role=self._role,
                namespace=self._prompt_cache_namespace,
            )
            request["prompt_cache_retention"] = "in_memory"
        current_boundary = _responses_input_text(user_input)
        current_boundary_sha256 = hashlib.sha256(
            current_boundary.encode("utf-8")
        ).hexdigest()
        request, continuity_scope_key, continuity_previous = (
            self._prepare_persistent_continuation_request(
                request, user_input=user_input, telemetry_scope=telemetry_scope,
            )
        )
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
            hashlib.sha256(str(item.get("output") or "").encode("utf-8")).hexdigest()
            for item in function_outputs
        ]
        direct_boundary_match = (
            hashlib.sha256(rendered_request_input.encode("utf-8")).hexdigest()
            == current_boundary_sha256
        )
        boundary_function_output_matches = sum(
            value == current_boundary_sha256 for value in function_output_hashes
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
            "status": "in_progress",
            "attempt_phase": "create",
            "instructions_chars": len(prepared_instructions),
            "input_chars": len(rendered_request_input),
            "instructions_sha256": hashlib.sha256(prepared_instructions.encode("utf-8")).hexdigest(),
            "input_sha256": hashlib.sha256(rendered_request_input.encode("utf-8")).hexdigest(),
            "max_output_tokens": max_output_tokens,
            "structured_output_mode": "persistent_v0_primary_turn_native_tool",
            "native_tool_name": _PERSISTENT_PRIMARY_NATIVE_TOOL_NAME,
            "persistent_reasoning_context_requested": self._persistent_reasoning_context,
            "persistent_working_state_policy": self._persistent_working_state_policy,
            "persistent_working_state_mode": self._persistent_working_state_policy,
            "persistent_primary_provider_schema_sha256": hashlib.sha256(
                json.dumps(
                    self._persistent_primary_native_tool["parameters"],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest(),
            "persistent_continuity_mode": self._persistent_continuity_mode,
            "persistent_continuity_previous_state_present": continuity_previous is not None,
            "persistent_continuity_previous_response_id": (
                None if continuity_previous is None else continuity_previous.get("response_id")
            ),
            "persistent_continuity_store": request.get("store"),
            "persistent_continuity_include": request.get("include"),
            "persistent_continuity_context_management": request.get("context_management"),
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
            "persistent_continuity_current_boundary_sha256": current_boundary_sha256,
            "persistent_continuity_current_boundary_direct_input_match": direct_boundary_match,
            "persistent_continuity_current_boundary_function_output_match_count": boundary_function_output_matches,
            "persistent_continuity_expected_prior_call_id": prior_call_id or None,
            "persistent_continuity_prior_call_id_match_count": sum(
                str(item.get("call_id") or "") == prior_call_id
                for item in function_outputs
            ) if prior_call_id else 0,
            "max_tool_calls_requested": 1,
            "parallel_tool_calls": False,
            "prompt_cache_key_mode": self._prompt_cache_mode,
            "prompt_cache_namespace": self._prompt_cache_namespace,
            "prompt_cache_retention": "in_memory" if self._prompt_cache_mode == "stable_prefix" else None,
            "usage_status": "unmeasured",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "reasoning_tokens": None,
        }
        if telemetry_scope is not None:
            event.update(telemetry_scope)
        started = time.monotonic()
        response: Any | None = None
        response_id: str | None = None
        try:
            poll_timeout_s = _remaining_verifier_poll_timeout_s(
                self._poll_timeout_s, minimum_reserve_s=self._poll_interval_s + 1.0,
            )
            event["effective_poll_timeout_s"] = round(poll_timeout_s, 3)
            if self._rate_limiter is not None:
                self._rate_limiter.acquire()
            response = self._client.responses.create(**request)
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
                if elapsed >= poll_timeout_s:
                    raise AzureModelError(
                        f"provider response {response_id} timed out after {elapsed:.0f}s "
                        f"(status={getattr(response, 'status', None)})"
                    )
                time.sleep(self._poll_interval_s)
                elapsed += self._poll_interval_s
                try:
                    response = self._client.responses.retrieve(response_id)
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
                try:
                    canonical, output_receipt = canonicalize_persistent_native_tool_output(
                        response,
                        working_state_policy=self._persistent_working_state_policy,
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
                    cancelled = self._client.responses.cancel(response_id)
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
            if exc.__class__.__name__ == "KernelRunTimeout":
                raise
            if isinstance(exc, AzureModelError):
                raise
            raise AzureModelError(f"responses native-tool call failed: {exc}") from exc
        finally:
            event["elapsed_s"] = round(time.monotonic() - started, 3)
            self._record_attempt(event)

    def _call_verifier_tool_once(
        self,
        instructions: str,
        user_input: str | list[dict[str, str]],
        max_output_tokens: int,
        *,
        logical_call_id: int,
        attempt_ordinal: int,
        telemetry_scope: dict[str, str | None] | None,
    ) -> str:
        """Run one Verifier turn through one forced native function-call boundary."""
        native_verifier_instruction = (
            _PERSISTENT_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION
            if self._verifier_protocol == "persistent_v0"
            else _VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION
        )
        prepared_instructions = "\n\n".join(part for part in (
            str(instructions).strip(),
            "[native_verifier_boundary] " + native_verifier_instruction,
        ) if part)
        effective_verifier_tool = _VERIFIER_NATIVE_TOOL
        authoritative_check_ids: tuple[str, ...] = ()
        outcome_clause_ids: tuple[str, ...] = ()
        persistent_basis_refs: tuple[str, ...] = ()
        persistent_bound_input_refs: tuple[str, ...] = ()
        persistent_cited_receipt_handles: tuple[str, ...] = ()
        persistent_completed_cited_receipt_handles: tuple[str, ...] = ()
        if self._verifier_protocol == "persistent_v0":
            effective_verifier_tool, authoritative_check_ids = (
                _persistent_verifier_native_tool_for_input(user_input)
            )
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
            "max_output_tokens": int(max_output_tokens),
            "tools": [effective_verifier_tool],
            "tool_choice": {"type": "function", "name": _VERIFIER_NATIVE_TOOL_NAME},
            "parallel_tool_calls": False,
            "max_tool_calls": 1,
            "background": bool(self._responses_background),
        }
        if self._prompt_cache_mode == "stable_prefix":
            request["prompt_cache_key"] = _stable_prompt_cache_key(
                deployment=self._deployment,
                role=self._role,
                namespace=self._prompt_cache_namespace,
            )
            request["prompt_cache_retention"] = "in_memory"

        event: dict[str, Any] = {
            "event_kind": "provider_attempt",
            "logical_call_id": logical_call_id,
            "attempt_ordinal": attempt_ordinal,
            "provider": "azure_openai_responses",
            "deployment": self._deployment,
            "role": self._role,
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
            "max_tool_calls_requested": 1,
            "parallel_tool_calls": False,
            "prompt_cache_key_mode": self._prompt_cache_mode,
            "prompt_cache_namespace": self._prompt_cache_namespace,
            "prompt_cache_retention": "in_memory" if self._prompt_cache_mode == "stable_prefix" else None,
            "usage_status": "unmeasured",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "reasoning_tokens": None,
        }
        if telemetry_scope is not None:
            event.update(telemetry_scope)
        started = time.monotonic()
        response: Any | None = None
        response_id: str | None = None
        try:
            poll_timeout_s = _remaining_verifier_poll_timeout_s(
                self._poll_timeout_s, minimum_reserve_s=self._poll_interval_s + 1.0,
            )
            event["effective_poll_timeout_s"] = round(poll_timeout_s, 3)
            if self._rate_limiter is not None:
                self._rate_limiter.acquire()
            response = self._client.responses.create(**request)
            raw_response_id = getattr(response, "id", None)
            if not raw_response_id:
                raise AzureModelError("responses.create returned no response id")
            response_id = str(raw_response_id)
            event["job_id"] = response_id
            event["attempt_phase"] = "poll"
            elapsed = 0.0
            while getattr(response, "status", None) in ("queued", "in_progress"):
                if elapsed >= poll_timeout_s:
                    raise AzureModelError(
                        f"provider response {response_id} timed out after {elapsed:.0f}s "
                        f"(status={getattr(response, 'status', None)})"
                    )
                time.sleep(self._poll_interval_s)
                elapsed += self._poll_interval_s
                try:
                    response = self._client.responses.retrieve(response_id)
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
                event.update(_native_tool_output_shape_telemetry(response))
                try:
                    canonical, output_receipt = canonicalize_verifier_native_tool_output(response)
                except AzureProviderOutputError as exc:
                    event["provider_output_error"] = exc.code
                    raise
                event.update(output_receipt)
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
                    cancelled = self._client.responses.cancel(response_id)
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
            if exc.__class__.__name__ == "KernelRunTimeout":
                raise
            if isinstance(exc, AzureModelError):
                raise
            raise AzureModelError(f"responses Verifier native-tool call failed: {exc}") from exc
        finally:
            event["elapsed_s"] = round(time.monotonic() - started, 3)
            self._record_attempt(event)

    def preflight_request(self, *, max_output_tokens: int, logical_role: str) -> dict[str, Any]:
        """Describe the native request contract without making a provider call."""
        verifier_envelope = self._role == "verifier"
        custom_schema = getattr(self, "_structured_output_schema", None)
        if getattr(self, "_transport", "responses") == "responses_tools":
            verifier_native = self._role == "verifier"
            return {
                "provider": "azure_openai_responses",
                "model": self._deployment,
                "provider_role": self._role,
                "logical_role": logical_role,
                "effort": self._effort,
                "max_output_tokens": int(max_output_tokens),
                "background": getattr(self, "_responses_background", True),
                "structured_output_mode": (
                    "verifier_direct_turn_native_tool"
                    if verifier_native else "persistent_v0_primary_turn_native_tool"
                ),
                "response_cardinality_contract": (
                    "exactly_one_forced_verifier_turn_function_call"
                    if verifier_native else "exactly_one_forced_persistent_turn_function_call"
                ),
                "native_tool_name": (
                    _VERIFIER_NATIVE_TOOL_NAME if verifier_native else _PERSISTENT_PRIMARY_NATIVE_TOOL_NAME
                ),
                "verifier_protocol": (
                    getattr(self, "_verifier_protocol", "verifier_v1")
                    if verifier_native else None
                ),
                "max_tool_calls_requested": 1,
                "parallel_tool_calls": False,
                "persistent_continuity_mode": (
                    getattr(self, "_persistent_continuity_mode", "explicit")
                    if not verifier_native else None
                ),
                "persistent_compact_threshold": (
                    getattr(self, "_persistent_compact_threshold", None)
                    if not verifier_native else None
                ),
                "persistent_continuity_qualification": (
                    None
                    if verifier_native
                    else (
                        "baseline_explicit"
                        if getattr(self, "_persistent_continuity_mode", "explicit") == "explicit"
                        else "experimental_unqualified"
                    )
                ),
                "explicit_json_instruction": False,
                "json_instruction_in_input": False,
                "certification": (
                    "responses_single_verifier_native_tool_call_contract"
                    if verifier_native
                    else (
                        "responses_single_persistent_v0_native_tool_call_contract"
                        if getattr(self, "_persistent_continuity_mode", "explicit") == "explicit"
                        else "experimental_persistent_native_continuity_unqualified"
                    )
                ),
            }
        # A few contract probes construct this callable with ``object.__new__``
        # to inspect the request surface without provider setup.  Match normal
        # construction: Verifier defaults to the single-choice Chat contract.
        transport_default = "chat_completions" if verifier_envelope else "responses"
        if getattr(self, "_transport", transport_default) == "chat_completions":
            direct_schema = verifier_envelope
            solver_turn = self._role == "solver"
            solver_protocol = getattr(self, "_solver_protocol", "solver_v1")
            persistent_primary_turn = solver_turn and solver_protocol == "persistent_v0"
            return {
                "provider": "azure_openai_chat_completions",
                "model": self._deployment,
                "provider_role": self._role,
                "logical_role": logical_role,
                "effort": self._effort,
                "max_output_tokens": int(max_output_tokens),
                "background": False,
                "choice_count_requested": 1,
                "structured_output_mode": (
                    "verifier_direct_turn_json_schema"
                    if direct_schema
                    else (
                        "persistent_v0_primary_turn_json_schema"
                        if persistent_primary_turn
                        else ("solver_direct_turn_json_schema" if solver_turn else "chat_json_object")
                    )
                ),
                "response_cardinality_contract": "exactly_one_choice_and_one_assistant_message",
                "explicit_json_instruction": True,
                "json_instruction_in_input": True,
                "certification": (
                    "chat_completions_single_verifier_direct_turn_json_schema_contract"
                    if direct_schema
                    else (
                        "chat_completions_single_persistent_v0_primary_turn_json_schema_contract"
                        if persistent_primary_turn
                        else (
                            "chat_completions_single_solver_direct_turn_json_schema_contract"
                            if solver_turn else "chat_completions_single_json_object_contract"
                        )
                    )
                ),
            }
        solver_protocol = getattr(self, "_solver_protocol", "solver_v1")
        persistent_primary = (
            self._role == "solver"
            and solver_protocol == "persistent_v0"
            and custom_schema == PERSISTENT_PRIMARY_TURN_SCHEMA
            and self._structured_output_name == PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
        )
        solver_direct = (
            self._role == "solver"
            and solver_protocol == "solver_v1"
            and custom_schema == _SOLVER_DIRECT_TURN_SCHEMA
            and self._structured_output_name == _SOLVER_STRUCTURED_OUTPUT_NAME
        )
        return {
            "provider": "azure_openai_responses",
            "model": self._deployment,
            "provider_role": self._role,
            "logical_role": logical_role,
            "effort": self._effort,
            "max_output_tokens": int(max_output_tokens),
            "background": getattr(self, "_responses_background", True),
            "structured_output_mode": (
                "verifier_envelope_json_schema"
                if verifier_envelope
                else (
                    "persistent_v0_primary_turn_json_schema"
                    if persistent_primary
                    else (
                        "solver_direct_turn_json_schema"
                        if solver_direct
                        else ("caller_json_schema" if custom_schema is not None else "json_object")
                    )
                )
            ),
            "structured_output_name": (
                PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
                if persistent_primary
                else (
                    _SOLVER_STRUCTURED_OUTPUT_NAME
                    if solver_direct
                    else (
                        getattr(self, "_structured_output_name", "")
                        if custom_schema is not None else None
                    )
                )
            ),
            "response_cardinality_contract": (
                "one_strict_persistent_v0_turn_from_responses_output"
                if persistent_primary
                else ("one_strict_solver_turn_from_responses_output" if solver_direct else None)
            ),
            "explicit_json_instruction": True,
            "json_instruction_in_input": True,
            "certification": (
                "native_verifier_envelope_json_schema_contract"
                if verifier_envelope
                else (
                    "responses_single_persistent_v0_primary_turn_json_schema_contract"
                    if persistent_primary
                    else (
                        "responses_single_solver_direct_turn_json_schema_contract"
                        if solver_direct
                        else (
                            "caller_supplied_strict_json_schema_contract"
                            if custom_schema is not None
                            else "native_json_object_request_contract"
                        )
                    )
                )
            ),
        }

    def _call_once(
        self,
        instructions: str,
        user_input: str | list[dict[str, str]],
        max_output_tokens: int,
        *,
        logical_call_id: int,
        attempt_ordinal: int,
        telemetry_scope: dict[str, str | None] | None,
    ) -> str:
        """Run exactly one create+poll attempt. Never retries internally —
        that's ``__call__``'s job via ``_retry_call``."""
        # Render through the same pure authority used by evidence capture so
        # model-facing custody cannot drift from live dispatch.
        verifier_envelope = self._role == "verifier"
        custom_schema = self._structured_output_schema
        persistent_primary_turn = (
            self._role == "solver"
            and self._solver_protocol == "persistent_v0"
            and custom_schema == PERSISTENT_PRIMARY_TURN_SCHEMA
            and self._structured_output_name == PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
        )
        solver_direct_turn = (
            self._role == "solver"
            and self._solver_protocol == "solver_v1"
            and custom_schema == _SOLVER_DIRECT_TURN_SCHEMA
            and self._structured_output_name == _SOLVER_STRUCTURED_OUTPUT_NAME
        )
        request = _render_azure_responses_request_from_split(
            instructions,
            user_input,
            deployment=self._deployment,
            effort=self._effort,
            role=self._role,
            max_output_tokens=max_output_tokens,
            background=self._responses_background,
            structured_output_schema=custom_schema,
            structured_output_name=self._structured_output_name,
            prompt_cache_mode=self._prompt_cache_mode,
            prompt_cache_namespace=self._prompt_cache_namespace,
        )
        instructions = str(request["instructions"])
        user_input = request["input"]
        event: dict[str, Any] = {
            "event_kind": "provider_attempt",
            "logical_call_id": logical_call_id,
            "attempt_ordinal": attempt_ordinal,
            "provider": "azure_openai_responses",
            "deployment": self._deployment,
            "role": self._role,
            "status": "in_progress",
            "attempt_phase": "create",
            "instructions_chars": len(instructions),
            "input_chars": len(_responses_input_text(user_input)),
            "instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
            "input_sha256": hashlib.sha256(
                _responses_input_text(user_input).encode("utf-8")
            ).hexdigest(),
            "max_output_tokens": max_output_tokens,
            "structured_output_mode": (
                "verifier_envelope_json_schema"
                if verifier_envelope
                else (
                    "persistent_v0_primary_turn_json_schema"
                    if persistent_primary_turn
                    else (
                        "solver_direct_turn_json_schema"
                        if solver_direct_turn
                        else ("caller_json_schema" if custom_schema is not None else "json_object")
                    )
                )
            ),
            "structured_output_name": (
                PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
                if persistent_primary_turn
                else (
                    _SOLVER_STRUCTURED_OUTPUT_NAME
                    if solver_direct_turn
                    else (self._structured_output_name if custom_schema is not None else None)
                )
            ),
            "prompt_cache_key_mode": self._prompt_cache_mode,
            "prompt_cache_namespace": self._prompt_cache_namespace,
            "prompt_cache_retention": "in_memory" if self._prompt_cache_mode == "stable_prefix" else None,
            "usage_status": "unmeasured",
            "cache_metrics_status": "unmeasured",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cached_input_tokens": None,
            "reasoning_tokens": None,
        }
        if telemetry_scope is not None:
            event.update(telemetry_scope)
        started = time.monotonic()
        job: Any | None = None
        job_id: str | None = None
        try:
            poll_timeout_s = _remaining_verifier_poll_timeout_s(
                self._poll_timeout_s,
                minimum_reserve_s=self._poll_interval_s + 1.0,
            )
            event["effective_poll_timeout_s"] = round(poll_timeout_s, 3)
            if self._rate_limiter is not None:
                self._rate_limiter.acquire()
            job = self._client.responses.create(**request)
            raw_job_id = getattr(job, "id", None)
            if not raw_job_id:
                raise AzureModelError("responses.create returned no job id")
            job_id = str(raw_job_id)
            event["job_id"] = job_id
            event["attempt_phase"] = "poll"

            # Poll until terminal status.
            elapsed = 0.0
            while getattr(job, "status", None) in ("queued", "in_progress"):
                if elapsed >= poll_timeout_s:
                    raise AzureModelError(
                        f"background job {job_id} timed out after {elapsed:.0f}s "
                        f"(status={getattr(job, 'status', None)})"
                    )
                time.sleep(self._poll_interval_s)
                elapsed += self._poll_interval_s
                try:
                    job = self._client.responses.retrieve(job_id)
                except Exception as exc:
                    raise AzureModelError(
                        f"responses.retrieve failed for {job_id}: {exc}"
                    ) from exc

            status = getattr(job, "status", None)
            event.update({
                "attempt_phase": "terminal",
                "job_status": str(status),
                "poll_elapsed_s": elapsed,
                **_usage_telemetry(job),
            })
            if os.environ.get("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT") == "1":
                event["raw_provider_output_items"] = _raw_output_items_for_evidence(job)
            if status == "completed":
                try:
                    if solver_direct_turn or persistent_primary_turn:
                        text, output_receipt = canonicalize_solver_responses_output(
                            job,
                            solver_protocol=self._solver_protocol,
                        )
                    else:
                        text, output_receipt = canonicalize_structured_output(job)
                        if verifier_envelope:
                            text, envelope_receipt = unwrap_verifier_provider_envelope(text)
                            output_receipt.update(envelope_receipt)
                except AzureProviderOutputError as exc:
                    event["provider_output_error"] = exc.code
                    raise
                event.update(output_receipt)
                event["status"] = "completed"
                return text

            if status == "incomplete":
                # Partial text is evidence, never an executable model turn.
                # Even syntactically valid JSON may be a truncated semantic
                # decision, so quarantine the whole provider response.
                event["provider_output_error"] = "provider_output_incomplete"
                event["status"] = "incomplete"
                raise AzureProviderOutputError(
                    "provider_output_incomplete",
                    str(getattr(job, "incomplete_details", None) or ""),
                )

            error_obj = getattr(job, "error", None)
            detail = error_obj or getattr(job, "incomplete_details", None) or ""
            code = getattr(error_obj, "code", None)
            raise AzureModelError(
                f"background job {job_id} ended with status={status}: {detail}"
            ) from _JobStatusFailure(code)
        except Exception as exc:
            last_job_status = str(getattr(job, "status", None) or "")
            if job_id and last_job_status in {"queued", "in_progress"}:
                event["provider_job_cancel_attempted"] = True
                event["provider_job_status_before_cancel"] = last_job_status
                try:
                    cancelled = self._client.responses.cancel(job_id)
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
            # The runner's wall-clock interrupt is control flow, not a
            # provider failure.  Match ModelHooks' canonical handling without
            # importing the runner here (which would create a provider/runner
            # dependency cycle).  The finally block still records this
            # interrupted provider attempt for cost/latency audit.
            if exc.__class__.__name__ == "KernelRunTimeout":
                raise
            if isinstance(exc, AzureModelError):
                raise
            raise AzureModelError(f"responses.create failed: {exc}") from exc
        finally:
            event["elapsed_s"] = round(time.monotonic() - started, 3)
            self._record_attempt(event)


class AzureVisionCallable:
    """Vision transcription callable: (prompt, image_b64, media_type) -> text.

    Sends a multimodal Responses API request with an inline data-URL image.
    """

    def __init__(self, client: Any, deployment: str) -> None:
        self._client = client
        self._deployment = deployment
        self._telemetry_events: list[dict[str, Any]] = []
        self._telemetry_lock = threading.Lock()
        self._next_logical_call_id = 0

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

    def _call(
        self,
        prompt: str,
        image_b64: str,
        media_type: str,
        *,
        telemetry_scope: dict[str, str | None] | None,
    ) -> str:
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
            "max_output_tokens": 8000,
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
            "reasoning_tokens": None,
        }
        if telemetry_scope is not None:
            event.update(telemetry_scope)
        started = time.monotonic()
        try:
            response = self._client.responses.create(
                model=self._deployment,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{media_type};base64,{image_b64}",
                        },
                    ],
                }],
                max_output_tokens=8000,
            )
            event.update({
                "attempt_phase": "terminal",
                "job_id": str(getattr(response, "id", "")) or None,
                "job_status": str(getattr(response, "status", "completed")),
                **_usage_telemetry(response),
            })
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
) -> AzureVisionCallable:
    """Build a vision transcription callable from Azure env vars (build-time)."""
    endpoint = _normalize_endpoint(os.environ[endpoint_env])
    api_key = os.environ[key_env]
    deployment = os.environ[deployment_env]
    if openai is None:
        raise AzureModelError("openai package is required for AzureVisionCallable")
    client = openai.OpenAI(
        api_key=api_key,
        base_url=f"{endpoint}/openai/v1/",
        timeout=300,
        max_retries=2,
    )
    return AzureVisionCallable(client, deployment)
