"""Static protocol-card sections of the solver's stable prompt prefix.

Extracted from compiler.py for the 500-LOC cap.  These are byte-stable across
every task and step; dynamic (task/world) sections stay in the compiler.
"""
from __future__ import annotations

from typing import Any, Mapping

from .runtime_ir import stable_json

PROTOCOL_CARD_SECTIONS: tuple[tuple[str, str], ...] = (
            (
                "kernel_contract",
                (
                    "Kernel facts: typed action schema is enforced at dispatch time; receipts are recorded as "
                    "execution evidence; local-only safety and path integrity checks may reject actions; "
                    "submit_outcome asks the runtime to evaluate the current state."
                ),
            ),
            (
                "tool_semantics",
                (
                    "Only action kinds listed in [action_schema] are callable. Disabled tools are rejected before dispatch. "
                    "query_memory, inspect_checks, run_check, query_artifact_history, inspect_diff, and record_observation "
                    "are kernel-owned affordances when present in [action_schema]. Optional action target metadata is used "
                    "for memory matching and does not change tool argument requirements. Use start_job for a detached finite "
                    "job or persistent service that must remain managed by the harness; use probe_job with its returned job_id "
                    "or registered name to observe running/completed/failed state and exit code. probe_service is only for live "
                    "service/process liveness and a not-live result is not proof that a finite job completed."
                ),
            ),
            (
                "automatic_memory_manual",
                (
                    "Automatic memory compares repeated read_file, write_file, run_command, and run_check actions against prior receipts. "
                    "Stable path, check_id, or command-fingerprint metadata lets the runtime attach matching evidence cheaply. "
                    "automatic_memory_findings, files_already_read, and repeated_actions in context describe prior observations; "
                    "repeat_justification may be required by the active memory policy."
                ),
            ),
            (
                "completion_submit_manual",
                (
                    "Completion facts: inspect_checks and run_check expose harness-visible checks when available; "
                    "submit_outcome is a final completion claim evaluated against current task state; "
                    "active_completion_findings may appear in later context packets when unresolved state or evidence issues remain. "
                    "Local checks and local evidence are useful task evidence, not a substitute for genuine task completion."
                ),
            ),
            (
                "solver_turn_contract",
                stable_json(
                    {
                        "emit_format": "strict_json_only",
                        "turn_kinds": ["act", "submit_outcome"],
                        "required_fields": {
                            "always": ["kind", "summary"],
                            "act": ["actions"],
                            "act_cardinality": "exactly_one_action_frontier",
                            "recommended_turn_fields": ["evidence_gap"],
                            "act_action_fields": ["kind", "arguments"],
                            "recommended_action_fields": [
                                "action_id",
                                "intent",
                                "expected_observation",
                                "if_fail_next",
                            ],
                        },
                        "action_schema_section": "action_schema",
                        "notes": [
                            "Only action kinds listed in action_schema are callable.",
                            "An act turn contains exactly one action frontier.",
                            "Choose exactly one causal action per act turn; independent action batching is not available in V1.",
                            "Kernel-owned memory and check affordances are listed in action_schema when available.",
                            "Do not request reconfiguration. Report concrete harness blockers with the report_blocker action.",
                        ],
                    }
                ),
            ),
)

PERSISTENT_PROTOCOL_CARD_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "kernel_contract",
        (
            "The Kernel validates and executes one external action, preserves exact observations, "
            "and enforces safety, budgets, and evidence provenance. It does not choose strategy."
        ),
    ),
    (
        "tool_semantics",
        (
            "Only action kinds listed in [action_schema] are callable. Use exactly the argument "
            "fields declared for the chosen action. One act turn contains one action frontier."
        ),
    ),
    (
        "completion_submit_manual",
        (
            "Submit only from current observed evidence. A submission states one claim and cites "
            "the evidence references visible in context; it contains no action."
        ),
    ),
    (
        "solver_turn_contract",
        stable_json({
            "protocol": "persistent_v0",
            "provider_wrapper": "turn",
            "act": {
                "kind": "act",
                "action": {
                    "kind": "one action kind from action_schema",
                    "capability_id": "the observed capability that owns the action",
                    "arguments": "one JSON object containing exactly the declared arguments",
                },
            },
            "submit": {
                "kind": "submit",
                "claim": "one non-empty completion claim",
                "evidence_refs": ["one or more visible evidence references"],
            },
            "kernel_generated": ["action_id", "receipt identifiers", "administrative bookkeeping"],
            "forbidden": [
                "multiple actions",
                "mixed action and submission",
                "future dependent turns",
                "text outside the provider object",
            ],
        }),
    ),
)


def protocol_card_sections(protocol: str) -> tuple[tuple[str, str], ...]:
    if protocol == "persistent_v0":
        return PERSISTENT_PROTOCOL_CARD_SECTIONS
    if protocol == "solver_v1":
        return PROTOCOL_CARD_SECTIONS
    raise ValueError(f"unknown solver turn protocol: {protocol}")


def persistent_model_environment_probe(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Return a factual PERSISTENT model view of the bounded environment probe.

    The complete probe remains in EnvMap/task metadata and config_realization
    custody. This view removes repeated false/empty rows and derived guidance
    while preserving decision-relevant positive and negative availability.
    Unknown probe schema versions fail open to the exact original mapping.
    """
    source = dict(probe)
    if source.get("schema_version") != "environment_probe.v1":
        return source

    view: dict[str, Any] = {}
    for key in ("schema_version", "workspace_root", "network", "task_hints"):
        if key in source:
            view[key] = source[key]

    command_names = source.get("command_names", {})
    if isinstance(command_names, Mapping):
        available: dict[str, Any] = {}
        unavailable_names: list[str] = []
        unavailable_details: dict[str, Any] = {}
        for raw_name, raw_row in sorted(command_names.items(), key=lambda item: str(item[0])):
            name = str(raw_name)
            if isinstance(raw_row, Mapping) and raw_row.get("available") is True:
                available[name] = {
                    str(key): value
                    for key, value in raw_row.items()
                    if key != "available" and value not in (None, "", [], {}, ())
                }
            else:
                unavailable_names.append(name)
                if isinstance(raw_row, Mapping):
                    extra = {
                        str(key): value
                        for key, value in raw_row.items()
                        if key not in {"available", "path"} and value not in (None, "", [], {}, ())
                    }
                    if extra:
                        unavailable_details[name] = extra
        view["commands"] = {
            "available": available,
            "unavailable_names": unavailable_names,
        }
        if unavailable_details:
            view["commands"]["unavailable_details"] = unavailable_details
    elif "command_names" in source:
        view["command_names"] = source["command_names"]

    python = source.get("python")
    if isinstance(python, Mapping):
        py_view: dict[str, Any] = {}
        for key in ("preferred", "interpreters", "interpreter_details", "package_contract"):
            if key in python:
                py_view[key] = python[key]

        interpreters = python.get("interpreters", ())
        if isinstance(interpreters, (list, tuple)):
            for raw_name in interpreters:
                name = str(raw_name)
                row = python.get(name)
                if isinstance(row, Mapping):
                    py_view[name] = {
                        str(key): value
                        for key, value in row.items()
                        if key != "modules" and value not in (None, "", [], {}, ())
                    }

        modules = python.get("modules")
        if isinstance(modules, Mapping):
            available_modules: dict[str, Any] = {}
            unavailable_module_names: list[str] = []
            unavailable_module_details: dict[str, Any] = {}
            for raw_name, raw_row in sorted(modules.items(), key=lambda item: str(item[0])):
                name = str(raw_name)
                if isinstance(raw_row, Mapping) and raw_row.get("available") is True:
                    available_modules[name] = {
                        str(key): value
                        for key, value in raw_row.items()
                        if key != "available" and value not in (None, "", [], {}, ())
                    }
                else:
                    unavailable_module_names.append(name)
                    if isinstance(raw_row, Mapping):
                        extra = {
                            str(key): value
                            for key, value in raw_row.items()
                            if key not in {"available", "available_in"} and value not in (None, "", [], {}, ())
                        }
                        if extra:
                            unavailable_module_details[name] = extra
            py_view["modules"] = {
                "available": available_modules,
                "unavailable_names": unavailable_module_names,
            }
            if unavailable_module_details:
                py_view["modules"]["unavailable_details"] = unavailable_module_details
        elif "modules" in python:
            py_view["modules"] = python["modules"]

        known_python = {
            "preferred", "interpreters", "interpreter_details", "package_contract", "modules",
            *(str(name) for name in interpreters if isinstance(interpreters, (list, tuple))),
        }
        for key, value in python.items():
            if str(key) not in known_python:
                py_view[str(key)] = value
        view["python"] = py_view
    elif "python" in source:
        view["python"] = source["python"]

    guidance = source.get("validation_guidance")
    if isinstance(guidance, Mapping):
        extra_guidance = {
            str(key): value
            for key, value in guidance.items()
            if key not in {"preferred_python", "missing_commands", "notes"}
            and value not in (None, "", [], {}, ())
        }
        if extra_guidance:
            view["validation_guidance_extra"] = extra_guidance
    elif "validation_guidance" in source and guidance not in (None, "", [], {}, ()):
        view["validation_guidance"] = guidance

    known_top = {
        "schema_version", "workspace_root", "command_names", "python", "network",
        "task_hints", "validation_guidance",
    }
    for key, value in source.items():
        if str(key) not in known_top:
            view[str(key)] = value
    return view
