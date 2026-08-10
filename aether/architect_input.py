"""Compact, factual input contract for the Runtime Workbench Architect.

The Architect owns task interpretation and the task-local work/proof contract.
The kernel contributes only visible facts, observed environment support, exact
runtime enums, and kernel-owned invariants.  No deterministic semantic task
model is presented as authority.
"""
from __future__ import annotations

from typing import Any, Mapping

from .architect_field_manifest import (
    ADVISORY_METADATA,
    ARCHITECT_RUNTIME_CONTROL,
    KERNEL_INVARIANT,
    MIGRATION_ONLY,
    FIELD_REALIZATION_MANIFEST,
)
from .context_views import (
    TOP_LEVEL_CONTEXT_SECTION_SELECTORS,
    _RECENT_RECIPE_SELECTORS,
    _SUPPORTED_EXACT_RECIPE_SELECTORS,
)
from .proof_contract import ROUTE_EVIDENCE_CEILINGS
from .runtime_ir import (
    AUTOMATIC_MEMORY_POLICY_MODES,
    FIXED_KERNEL_TOOL_SURFACE,
    EnvMap,
    normalize_relpath,
)
from .runtime_manual import ALLOWED_VISIBLE_SMOKE_TEST_TYPES, SUPPORTED_CONTEXT_POLICIES
from .workbench_config import (
    DEPRECATED_MIGRATION_FIELD_PATHS,
    SUPPORTED_EVIDENCE_CLASSES,
)

_REQUEST_SCHEMA_VERSION = "architect_request.v2"
_OUTPUT_SCHEMA_VERSION = "harness_config.v1"


def _bounded_rows(value: Any, *, limit: int) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    return list(value[: max(0, limit)])


def _path_facts(envmap: EnvMap) -> dict[str, Any]:
    summary = dict(envmap.file_map_summary or {})
    keys = (
        "top_level",
        "extension_counts",
        "visible_file_count",
        "visible_dir_count",
        "instruction_output_paths",
        "instruction_referenced_paths",
        "instruction_referenced_visible_paths",
        "instruction_referenced_missing_paths",
        "instruction_referenced_alias_matches",
        "prompt_declared_output_paths",
        "prompt_declared_output_visible_paths",
        "prompt_declared_output_missing_paths",
        "prompt_declared_output_alias_matches",
    )
    return {
        key: summary[key]
        for key in keys
        if key in summary and summary[key] not in (None, "", (), [], {})
    }


def _visible_materials(task_metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "validation_candidates": _bounded_rows(
            task_metadata.get("visible_validation_surfaces", ()), limit=40
        ),
        "declared_assets": _bounded_rows(task_metadata.get("declared_assets", ()), limit=80),
        "visible_examples": _bounded_rows(task_metadata.get("visible_examples", ()), limit=60),
        "summary": dict(task_metadata.get("visible_material_summary", {}) or {}),
    }


def _capability_availability(envmap: EnvMap) -> list[dict[str, Any]]:
    return [
        {
            "capability_id": cap.capability_id,
            "available": bool(cap.available),
            "tools": list(cap.tool_names),
        }
        for cap in sorted(envmap.capabilities.values(), key=lambda item: item.capability_id)
    ]


def _compact_probe(probe: Mapping[str, Any]) -> dict[str, Any]:
    commands = probe.get("command_names") if isinstance(probe.get("command_names"), Mapping) else {}
    python = probe.get("python") if isinstance(probe.get("python"), Mapping) else {}
    modules = python.get("modules") if isinstance(python.get("modules"), Mapping) else {}

    compact_commands: dict[str, Any] = {}
    for name, raw in sorted(commands.items()):
        if not isinstance(raw, Mapping):
            continue
        row = {
            key: raw.get(key)
            for key in ("available", "path", "version")
            if raw.get(key) not in (None, "", (), [], {})
        }
        if row:
            compact_commands[str(name)] = row

    compact_modules: dict[str, Any] = {}
    for name, raw in sorted(modules.items()):
        if not isinstance(raw, Mapping):
            continue
        row = {
            key: raw.get(key)
            for key in ("available", "version")
            if raw.get(key) not in (None, "", (), [], {})
        }
        if row:
            compact_modules[str(name)] = row

    compact_python = {
        key: python.get(key)
        for key in ("preferred", "interpreters", "package_contract")
        if python.get(key) not in (None, "", (), [], {})
    }
    if compact_modules:
        compact_python["modules"] = compact_modules

    result: dict[str, Any] = {}
    if compact_commands:
        result["commands"] = compact_commands
    if compact_python:
        result["python"] = compact_python
    network = probe.get("network")
    if isinstance(network, Mapping) and network:
        result["network"] = dict(network)
    return result


def _field_authority() -> dict[str, list[str]]:
    groups = {
        ARCHITECT_RUNTIME_CONTROL: [],
        ADVISORY_METADATA: [],
        KERNEL_INVARIANT: [],
        MIGRATION_ONLY: [],
    }
    for entry in FIELD_REALIZATION_MANIFEST:
        # Child fields carry the useful authority boundary.  Keep the contract
        # compact by excluding parent rows that merely repeat child authority.
        path = entry.path.removeprefix("$.")
        if path in {
            "context_policy",
            "memory_policy",
            "verification_policy",
            "model_verifier_policy",
            "reconfigure_policy",
            "helper_script_policy",
        }:
            continue
        groups[entry.authority].append(path)
    return {
        "architect_controls": sorted(groups[ARCHITECT_RUNTIME_CONTROL]),
        "advisory_fields": sorted(groups[ADVISORY_METADATA]),
        "kernel_owned": sorted(groups[KERNEL_INVARIANT]),
        "migration_only_forbidden_in_output": sorted(
            set(groups[MIGRATION_ONLY])
            | {path.removeprefix("$.") for path in DEPRECATED_MIGRATION_FIELD_PATHS}
        ),
    }


def build_architect_runtime_contract() -> dict[str, Any]:
    """Return the exact compact contract the Architect may rely on."""
    return {
        "output_schema_version": _OUTPUT_SCHEMA_VERSION,
        "kernel_invariants": {
            "architect_selects_tools": False,
            "fixed_solver_action_surface": list(FIXED_KERNEL_TOOL_SURFACE),
            "submit_is_final_completion_claim": True,
            "official_grader_is_external": True,
            "helper_output_is_not_completion_authority": True,
            "task_semantics_are_architect_authored": True,
        },
        "supported_values": {
            "context_modes": list(SUPPORTED_CONTEXT_POLICIES),
            "context_top_level_sections": sorted(TOP_LEVEL_CONTEXT_SECTION_SELECTORS),
            "context_exact_selectors": sorted(_SUPPORTED_EXACT_RECIPE_SELECTORS),
            "context_recent_selectors": sorted(_RECENT_RECIPE_SELECTORS),
            "automatic_repeat_modes": sorted(AUTOMATIC_MEMORY_POLICY_MODES),
            "visible_smoke_test_types": list(ALLOWED_VISIBLE_SMOKE_TEST_TYPES),
            "visible_smoke_test_schemas": {
                "syntax_check": {"required": ["type", "path"], "optional": ["language"]},
                "content_assertion": {"required": ["type", "path"], "one_of": ["contains", "not_contains"]},
                "file_exists": {"required": ["type", "path"]},
                "file_size": {"required": ["type", "path"], "optional": ["min_bytes"]},
                "run_deliverable_on_fixture": {"required": ["type", "argv"], "optional": ["stdin_file"]},
            },
            "evidence_classes": sorted(SUPPORTED_EVIDENCE_CLASSES),
            "verifier_route_ceilings": dict(sorted(ROUTE_EVIDENCE_CEILINGS.items())),
            "model_verifier_runs_on": ["solver_submit"],
        },
        "field_authority": _field_authority(),
        "semantic_contract": {
            "owner": "architect",
            "clause_coverage_required_with_verifier_strategy": True,
            "matching_clause_ids_required": True,
            "route_format": "<supported_route_kind>[:<visible target>]",
            "return_all_findings": True,
            "proof_obligation_route_rules": {
                "exact_state": {
                    "minimum_evidence_class": "exact_contract",
                    "route_ceiling_must_meet": True,
                },
                "public_behavior": {
                    "minimum_evidence_class": "behavioral",
                    "route_ceiling_must_meet": True,
                },
                "generated_interface_semantics": {
                    "minimum_evidence_class": "independent_semantic",
                    "route_ceiling_must_meet": True,
                    "requires_available_route": True,
                },
                "unavailable_required_route": (
                    "Do not emit an impossible proof obligation. Represent only the directly "
                    "observable contract as exact_state, retain the stronger machine-re-derivable "
                    "claim, and state blocked_by_harness_config in Verifier guidance."
                ),
            },
            "visible_contract_contrast_rule": (
                "When the task distinguishes lookalike identifiers or values across scopes, "
                "emit each exact binding and record the relevant lookalike as its contrast with "
                "the correct contrast owner."
            ),
        },
    }


def build_architect_factual_input(envmap: EnvMap) -> dict[str, Any]:
    """Build the shared visible fact envelope without any runtime manual."""
    metadata = dict(envmap.task_metadata or {})
    probe = metadata.get("environment_probe") if isinstance(metadata.get("environment_probe"), Mapping) else {}
    observed_support = metadata.get("observed_environment_support")
    reviewer_support = metadata.get("reviewer_probe_support")
    return {
        "request_identity": {
            "envmap_digest": envmap.digest(),
        },
        "task": {
            "prompt": envmap.task_prompt,
            "workspace_root": envmap.workspace_root,
            "file_tree": envmap.file_tree,
            "path_facts": _path_facts(envmap),
            "visible_materials": _visible_materials(metadata),
        },
        "environment": {
            "network_scope": envmap.network_scope,
            "enforced_network_policy": dict(metadata.get("network_policy", {}) or {}),
            "resource_limits": dict(envmap.resource_limits),
            "permissions": dict(envmap.permissions),
            "services": dict(envmap.services),
            "interactive_features": dict(envmap.interactive_features),
            "capability_availability": _capability_availability(envmap),
            "observed_support": dict(observed_support or {}),
            "reviewer_support": dict(reviewer_support or {}),
            "probe_facts": _compact_probe(probe),
        },
    }


def build_architect_input(envmap: EnvMap) -> dict[str, Any]:
    """Build the V1 workbench request from facts plus its runtime contract."""
    factual = build_architect_factual_input(envmap)
    return {
        "schema_version": _REQUEST_SCHEMA_VERSION,
        **factual,
        "runtime_contract": build_architect_runtime_contract(),
    }
