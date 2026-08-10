"""Strict provider schema for production Runtime Workbench Architect output.

The parser remains the semantic authority.  This schema is the provider-boundary
shape contract: it prevents malformed JSON, unknown fields, legacy tool
selection, and incomplete typed proof contracts from consuming a repair call.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from .context_views import (
    TOP_LEVEL_CONTEXT_SECTION_SELECTORS,
    _RECENT_RECIPE_SELECTORS,
    _SUPPORTED_EXACT_RECIPE_SELECTORS,
)
from .proof_contract import ROUTE_EVIDENCE_CEILINGS
from .runtime_ir import AUTOMATIC_MEMORY_POLICY_MODES
from .runtime_manual import (
    ALLOWED_VISIBLE_SMOKE_TEST_TYPES,
    SUPPORTED_CONTEXT_POLICIES,
    SUPPORTED_SYNTAX_CHECK_LANGUAGES,
)
from .workbench_config import SUPPORTED_EVIDENCE_CLASSES


def _string_array(*, min_items: int = 0) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string"},
        "minItems": min_items,
    }


def _enum_array(values: list[str] | tuple[str, ...], *, min_items: int = 0) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "enum": list(values)},
        "minItems": min_items,
    }


def _closed_object(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required if required is not None else list(properties),
    }


_SOLVER_PROMPT = _closed_object({
    "role": {"type": "string"},
    "workflow": _string_array(min_items=1),
    "self_verification": _string_array(min_items=1),
    "memory_use": _string_array(min_items=1),
    "stop_conditions": _string_array(min_items=1),
    "avoid": _string_array(),
})

_VERIFIER_PROMPT = _closed_object({
    "role": {"type": "string"},
    "success_criteria": _string_array(min_items=1),
    "required_evidence": _string_array(min_items=1),
    "false_positive_traps": _string_array(min_items=1),
    "verdict_guidance": _string_array(min_items=3),
    "feedback_guidance": _string_array(min_items=1),
})

_CLAUSE_COVERAGE_ITEM = _closed_object({
    "clause_id": {"type": "string"},
    "solver_handling": {"type": "string"},
    "verifier_check": {"type": "string"},
})

_VISIBLE_CONTRACT_ITEM = _closed_object({
    "literal": {
        "type": "string",
        "minLength": 1,
        "description": "Exact required unqualified name or standalone path/version/port/value/state. Never include an owner prefix here.",
    },
    "owner": {
        "anyOf": [
            {"type": "string", "minLength": 1},
            {"type": "null"},
        ],
        "description": "Exact immediate semantic owner when this is a scoped operation, method, field, key, or member; null for a standalone fact. Ownership does not imply a data type.",
    },
    "requirement": {
        "anyOf": [
            {"type": "string", "minLength": 1},
            {"type": "null"},
        ],
        "description": "Exact task-stated type, version, format, or cardinality attached to this exact binding; otherwise null. This is independent of owner and may constrain a standalone fact. Entity categories such as service, RPC, class, module, command, or file are meanings, not requirements.",
    },
    "meaning": {
        "type": "string",
        "minLength": 1,
        "description": "Contract role of this exact binding, including any entity category such as service, operation, class, or path.",
    },
    "contrast": {
        "type": "string",
        "description": "Exact false/lookalike unqualified name or standalone value, or empty when no contrast exists.",
    },
    "contrast_owner": {
        "anyOf": [
            {"type": "string", "minLength": 1},
            {"type": "null"},
        ],
        "description": "Exact immediate owner only when the contrast itself is scoped; null for no contrast or a standalone contrast, independently of the required literal owner.",
    },
})

_VERIFIER_ROUTE_KIND_PATTERN = "^(?:" + "|".join(
    re.escape(kind) for kind in sorted(ROUTE_EVIDENCE_CEILINGS)
) + "):.*$"

_VERIFIER_ROUTE_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "pattern": _VERIFIER_ROUTE_KIND_PATTERN,
    "description": "Route must use one parser-supported route-kind prefix from runtime_contract.supported_values.verifier_route_ceilings, followed by a colon and task-local target.",
}

_VERIFIER_CLAUSE_ITEM = _closed_object({
    "clause_id": {"type": "string"},
    "inspection_route": deepcopy(_VERIFIER_ROUTE_SCHEMA),
    "fallback_route": {"anyOf": [deepcopy(_VERIFIER_ROUTE_SCHEMA), {"type": "null"}]},
    "falsification_check": {"type": "string"},
    "proof_obligation": {
        "type": "string",
        "enum": ["exact_state", "public_behavior", "generated_interface_semantics"],
        "description": "Semantic claim class. public_behavior requires a fresh public-interface operation and observed response; generated_interface_semantics requires independent comparison of the current generated interface against the current source contract; exact_state covers direct current-state facts.",
    },
    "required_evidence_class": {
        "type": "string",
        "enum": sorted(SUPPORTED_EVIDENCE_CLASSES),
        "description": "Classify the claim, not merely the route: exact_contract for exact source/config/metadata; behavioral for a fresh public-interface operation with observed response; independent_semantic for cross-representation comparison. Shape or liveness proxies cannot prove behavior.",
    },
})

_CONTEXT_RECIPE = _closed_object({
    "always_include": _enum_array(sorted(_SUPPORTED_EXACT_RECIPE_SELECTORS)),
    "include_recent": {
        "type": "array",
        "items": _closed_object({
            "selector": {"type": "string", "enum": sorted(_RECENT_RECIPE_SELECTORS)},
            "count": {"type": "integer", "minimum": 0},
        }),
    },
    "include_last_failure": {"type": "integer", "minimum": 0},
    "preserve_exact": _enum_array(sorted(_SUPPORTED_EXACT_RECIPE_SELECTORS)),
    "make_queryable_not_inline": _enum_array(sorted(_SUPPORTED_EXACT_RECIPE_SELECTORS)),
})

_CONTEXT_POLICY = _closed_object({
    "mode": {"type": "string", "enum": list(SUPPORTED_CONTEXT_POLICIES)},
    "always_include": _enum_array(sorted(TOP_LEVEL_CONTEXT_SECTION_SELECTORS)),
    "include_on_failure": _enum_array(sorted(TOP_LEVEL_CONTEXT_SECTION_SELECTORS)),
    "model_context_window_tokens": {"type": "integer", "minimum": 1000, "maximum": 500000},
    "recipe": _CONTEXT_RECIPE,
})

_FILE_EXISTS = _closed_object({
    "type": {"type": "string", "enum": ["file_exists"]},
    "path": {"type": "string"},
})
_FILE_SIZE = _closed_object({
    "type": {"type": "string", "enum": ["file_size"]},
    "path": {"type": "string"},
    "min_bytes": {"type": "integer", "minimum": 0},
})
_SYNTAX_CHECK = _closed_object({
    "type": {"type": "string", "enum": ["syntax_check"]},
    "path": {"type": "string"},
    "language": {
        "anyOf": [
            {"type": "string", "enum": list(SUPPORTED_SYNTAX_CHECK_LANGUAGES)},
            {"type": "null"},
        ]
    },
})
_RUN_FIXTURE = _closed_object({
    "type": {"type": "string", "enum": ["run_deliverable_on_fixture"]},
    "argv": _string_array(min_items=1),
    "stdin_file": {"anyOf": [{"type": "string"}, {"type": "null"}]},
})
_CONTENT_ASSERTION = _closed_object({
    "type": {"type": "string", "enum": ["content_assertion"]},
    "path": {"type": "string"},
    "contains": _string_array(),
    "not_contains": _string_array(),
    "assertions": {
        "type": "array",
        "items": _closed_object({
            "contains": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "not_contains": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        }),
    },
})

_VISIBLE_SMOKE_ITEM = {
    "anyOf": [_FILE_EXISTS, _FILE_SIZE, _SYNTAX_CHECK, _RUN_FIXTURE, _CONTENT_ASSERTION]
}

HARNESS_CONFIG_V1_PROVIDER_SCHEMA: dict[str, Any] = _closed_object({
    "schema_version": {"type": "string", "enum": ["harness_config.v1"]},
    "visible_contract": {
        "type": "array",
        "description": (
            "Sole Architect-authored authority for exact visible identities, optional immediate "
            "ownership, optional exact type/version/format/cardinality requirements, and contrasts. "
            "The model does not choose an internal row kind: the harness derives standalone, "
            "constrained-standalone, scoped, or typed-scoped rendering only from the authored owner and requirement values."
        ),
        "items": _VISIBLE_CONTRACT_ITEM,
    },
    "clause_coverage": {
        "type": "array",
        "description": (
            "Sole Architect-authored authority for material completion clauses. Use one row per "
            "independently judgeable final-state requirement and preserve exact clause identity."
        ),
        "items": _CLAUSE_COVERAGE_ITEM,
        "minItems": 1,
    },
    "verifier_strategy": _closed_object({
        "clause_checks": {
            "type": "array",
            "description": (
                "One evidence route for every clause_coverage row, using the identical clause_id. "
                "This is the sole proof-route authority."
            ),
            "items": _VERIFIER_CLAUSE_ITEM,
            "minItems": 1,
        },
        "false_positive_traps": _string_array(min_items=1),
        "return_all_findings": {"type": "boolean", "enum": [True]},
    }),
    "solver_system_prompt": _SOLVER_PROMPT,
    "verifier_system_prompt": _VERIFIER_PROMPT,
    "re_derivable_claims": _string_array(),
    "context_policy": _CONTEXT_POLICY,
    "memory_policy": _closed_object({
        "automatic_repeat_mode": {
            "type": "string",
            "enum": sorted(AUTOMATIC_MEMORY_POLICY_MODES),
        },
    }),
    "verification_policy": _closed_object({
        "visible_smoke_tests": {
            "type": "array",
            "items": _VISIBLE_SMOKE_ITEM,
        },
    }),
    "model_verifier_policy": _closed_object({
        "enabled": {"type": "boolean", "enum": [True]},
        "runs_on": {
            "type": "array",
            "items": {"type": "string", "enum": ["solver_submit"]},
            "minItems": 1,
            "maxItems": 1,
        },
    }),
    "helper_script_policy": _closed_object({
        "enabled": {"type": "boolean"},
        "directory": {"type": "string"},
    }),
    "expected_steps": {"type": "integer", "minimum": 0},
})

def architect_provider_schema() -> dict[str, Any]:
    """Return an isolated copy suitable for an Azure Responses text format."""
    return deepcopy(HARNESS_CONFIG_V1_PROVIDER_SCHEMA)


def architect_provider_response_format() -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": "aether_harness_config_v1",
            "strict": True,
            "schema": architect_provider_schema(),
        }
    }


assert set(ALLOWED_VISIBLE_SMOKE_TEST_TYPES) == {
    "file_exists",
    "file_size",
    "syntax_check",
    "run_deliverable_on_fixture",
    "content_assertion",
}
assert set(ROUTE_EVIDENCE_CEILINGS)
