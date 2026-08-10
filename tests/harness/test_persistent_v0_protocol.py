"""Zero-provider contract-equivalence tests for PERSISTENT V0."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from jsonschema import Draft202012Validator

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.compiler_prefix import persistent_model_environment_probe
from aether.envmap_builder import build_envmap_from_task
from aether.model_hooks import ModelOutputError, parse_solver_turn
from aether.persistent_provider_protocol import (
    PERSISTENT_ACTION_ARGUMENT_VARIANTS,
    PERSISTENT_PRIMARY_ACTION_SCHEMA,
    PERSISTENT_PRIMARY_PROVIDER_SCHEMA,
    PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME,
    PERSISTENT_PRIMARY_TURN_SCHEMA,
    PCRProviderProtocolError,
    canonicalize_persistent_primary_turn,
    persistent_action_contract_view,
)
from aether.persistent_primary import persistent_primary_runtime_ir
from aether.providers.azure_model import (
    AzureProviderOutputError,
    _render_azure_responses_request_from_split,
    canonicalize_solver_responses_output,
)
from aether.runtime_ir import ACTION_SCHEMA


def _wrapper(turn: dict[str, object]) -> str:
    return json.dumps({"turn": turn}, separators=(",", ":"))


def _example_value(name: str, schema: Mapping[str, Any]) -> Any:
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    value_type = schema.get("type")
    if value_type == "string":
        values = {
            "path": "artifact.txt",
            "content": "",
            "command": "printf ok",
            "handle": "output:stdout",
            "pattern": "needle",
            "query": "current artifact evidence",
            "observation": "The current artifact was directly observed.",
            "source": "primary_agent",
            "confidence": "medium",
            "service_name": "service-under-test",
            "target": "package-or-process",
            "output": "download.bin",
            "check_id": "check-1",
        }
        return values.get(name, f"value-for-{name}")
    if value_type == "integer":
        return 0 if name in {"offset", "since_step", "wait_ms"} else 30
    if value_type == "number":
        return 1.5
    if value_type == "boolean":
        return True
    if value_type == "array":
        return ["read_file"] if name in {"event_type", "kind"} else ["task-local"]
    if value_type == "object":
        properties = schema.get("properties", {})
        return {
            key: _example_value(key, child)
            for key, child in properties.items()
        }
    raise AssertionError(f"unsupported test schema for {name}: {schema}")


def _act(kind: str, variant_index: int = 0) -> dict[str, object]:
    variant = PERSISTENT_ACTION_ARGUMENT_VARIANTS[kind][variant_index]
    properties = variant.get("properties", {})
    return {
        "kind": "act",
        "action": {
            "kind": kind,
            "capability_id": "kernel" if kind.startswith("query_") else "filesystem",
            "arguments": {
                name: _example_value(name, schema)
                for name, schema in properties.items()
            },
        },
    }


def _response_with_texts(*texts: str) -> SimpleNamespace:
    return SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                role="assistant",
                id=f"message-{index}",
                content=[SimpleNamespace(type="output_text", text=text)],
            )
            for index, text in enumerate(texts)
        ]
    )


def test_schema_is_valid_and_every_action_variant_round_trips() -> None:
    Draft202012Validator.check_schema(PERSISTENT_PRIMARY_TURN_SCHEMA)
    validator = Draft202012Validator(PERSISTENT_PRIMARY_TURN_SCHEMA)

    for kind, variants in PERSISTENT_ACTION_ARGUMENT_VARIANTS.items():
        for variant_index, _variant in enumerate(variants):
            envelope = {"turn": _act(kind, variant_index)}
            assert not list(validator.iter_errors(envelope)), (kind, variant_index)

            canonical, receipt = canonicalize_persistent_primary_turn(json.dumps(envelope))
            turn = parse_solver_turn(canonical, protocol="persistent_v0")
            assert turn.kind == "act"
            assert len(turn.actions) == 1
            action = turn.actions[0]
            assert action.kind == kind
            assert dict(action.arguments) == envelope["turn"]["action"]["arguments"]
            assert action.intent == ""
            assert action.expected_observation == ""
            assert action.if_fail_next == ""
            assert not turn.evidence_gap
            assert not turn.validate(ACTION_SCHEMA, solver_turn_protocol="persistent_v0")
            assert receipt["provider_turn_arguments_transport"] == "direct_json_object"


def test_detailed_contract_preserves_optional_capability_arguments() -> None:
    view = persistent_action_contract_view()
    assert any(row["arguments"] == ["path", "offset", "span"] for row in view["read_file_page"])
    assert any(row["arguments"] == ["handle", "offset", "span"] for row in view["read_output"])
    assert any(row["arguments"] == ["command", "timeout_s"] for row in view["run_command"])
    assert any(row["arguments"] == ["manager", "target"] for row in view["bootstrap_acquire"])
    assert any(row["arguments"] == ["manager", "source", "output"] for row in view["bootstrap_acquire"])
    assert any("filters" in row for row in view["query_memory"])
    assert any("tags" in row["arguments"] for row in view["record_observation"])
    assert any(row["arguments"] == ["session_name", "command", "cwd"] for row in view["start_terminal_session"])
    assert any(row["arguments"] == ["session_id", "data", "append_newline"] for row in view["terminal_send"])
    assert any(row["arguments"] == ["session_id", "max_bytes", "wait_ms"] for row in view["terminal_read"])
    assert any(row["arguments"] == ["session_id", "timeout_s"] for row in view["terminal_wait"])
    assert view["terminal_interrupt"] == [{"arguments": ["session_id"]}]
    assert view["terminal_close"] == [{"arguments": ["session_id"]}]



def test_persistent_terminal_primitives_are_provider_visible_causal_actions() -> None:
    visible = {kind for kind, _arguments in PERSISTENT_PRIMARY_ACTION_SCHEMA}
    terminal_kinds = {
        "start_terminal_session",
        "terminal_send",
        "terminal_read",
        "terminal_wait",
        "terminal_interrupt",
        "terminal_close",
    }
    assert terminal_kinds <= visible
    for kind in terminal_kinds:
        for index in range(len(PERSISTENT_ACTION_ARGUMENT_VARIANTS[kind])):
            canonical, _receipt = canonicalize_persistent_primary_turn(_wrapper(_act(kind, index)))
            turn = parse_solver_turn(canonical, protocol="persistent_v0")
            assert turn.kind == "act"
            assert len(turn.actions) == 1
            assert turn.actions[0].kind == kind


def test_bootstrap_manager_variants_expose_the_arguments_execution_requires() -> None:
    variants = PERSISTENT_ACTION_ARGUMENT_VARIANTS["bootstrap_acquire"]
    accepted = []
    for index in range(len(variants)):
        turn = _act("bootstrap_acquire", index)
        accepted.append(turn["action"]["arguments"])
        canonicalize_persistent_primary_turn(_wrapper(turn))
    assert any(args.get("manager") == "apt" and args.get("target") for args in accepted)
    assert any(args.get("manager") == "git" and args.get("source") for args in accepted)
    assert any(args.get("manager") == "wget" and args.get("output") for args in accepted)


def test_kernel_internal_actions_are_not_provider_visible_or_parseable() -> None:
    visible = {kind for kind, _arguments in PERSISTENT_PRIMARY_ACTION_SCHEMA}
    assert "register_candidate" not in visible
    assert "run_experiment" not in visible
    for kind, arguments in ACTION_SCHEMA:
        if kind in visible:
            continue
        inner = {
            "kind": "act",
            "action": {
                "kind": kind,
                "capability_id": "kernel",
                "arguments": {name: f"value-for-{name}" for name in arguments},
            },
        }
        envelope = {"turn": inner}
        assert list(Draft202012Validator(PERSISTENT_PRIMARY_TURN_SCHEMA).iter_errors(envelope))
        with pytest.raises(PCRProviderProtocolError):
            canonicalize_persistent_primary_turn(json.dumps(envelope))
        with pytest.raises(ModelOutputError):
            parse_solver_turn(json.dumps(inner), protocol="persistent_v0")


def test_submit_round_trips_with_claim_and_visible_evidence_refs() -> None:
    envelope = {
        "turn": {
            "kind": "submit",
            "claim": "The required artifact is complete.",
            "evidence_refs": ["evidence:write-out", "evidence:read-out"],
        }
    }
    assert not list(Draft202012Validator(PERSISTENT_PRIMARY_TURN_SCHEMA).iter_errors(envelope))
    canonical, _receipt = canonicalize_persistent_primary_turn(json.dumps(envelope))
    turn = parse_solver_turn(canonical, protocol="persistent_v0")
    assert turn.kind == "submit_outcome"
    assert turn.claim == "The required artifact is complete."
    assert turn.evidence_refs == ("evidence:write-out", "evidence:read-out")
    assert not turn.validate(ACTION_SCHEMA, solver_turn_protocol="persistent_v0")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"turn": _act("read_file"), "extra": True},
        {"turn": {"kind": "act"}},
        {"turn": {"kind": "act", "action": {"kind": "read_file", "capability_id": "filesystem"}}},
        {"turn": {"kind": "act", "action": {"kind": "unknown", "capability_id": "x", "arguments": {}}}},
        {"turn": {"kind": "act", "action": {"kind": "read_file", "capability_id": "filesystem", "arguments": {}}}},
        {"turn": {"kind": "act", "action": {"kind": "read_file", "capability_id": "filesystem", "arguments": {"path": "a", "extra": "b"}}}},
        {"turn": {"kind": "act", "action": {"kind": "read_file", "capability_id": "filesystem", "arguments": {"path": {"nested": "not allowed"}}}}},
        {"turn": {"kind": "act", "action": {"kind": "run_command", "capability_id": "shell", "arguments": {"command": "echo ok", "timeout_s": 0}}}},
        {"turn": {"kind": "act", "action": {"kind": "bootstrap_acquire", "capability_id": "shell", "arguments": {"manager": "apt"}}}},
        {"turn": {"kind": "submit", "claim": "done"}},
        {"turn": {"kind": "submit", "claim": "done", "evidence_refs": []}},
        {"turn": {"kind": "submit", "claim": "done", "evidence_refs": ["e1"], "action": {}}},
    ],
)
def test_provider_schema_and_deterministic_decoder_reject_same_bad_shapes(
    payload: dict[str, object],
) -> None:
    assert list(Draft202012Validator(PERSISTENT_PRIMARY_TURN_SCHEMA).iter_errors(payload))
    with pytest.raises(PCRProviderProtocolError):
        canonicalize_persistent_primary_turn(json.dumps(payload))


def test_multiple_identical_objects_inside_one_message_fail_closed() -> None:
    first = _wrapper(_act("read_file"))
    second = json.dumps(json.loads(first), indent=2)
    with pytest.raises(
        PCRProviderProtocolError,
        match="provider_persistent_v0_multiple_objects_in_message",
    ):
        canonicalize_persistent_primary_turn(first + "\n" + second)


def test_multiple_distinct_objects_inside_one_message_fail_closed() -> None:
    first = _wrapper(_act("read_file"))
    second = _wrapper(_act("write_file"))
    with pytest.raises(
        PCRProviderProtocolError,
        match="provider_persistent_v0_multiple_objects_in_message",
    ):
        canonicalize_persistent_primary_turn(first + second)


def test_responses_item_canonicalizer_uses_persistent_contract() -> None:
    first = _wrapper(_act("read_file"))
    response = _response_with_texts(first, first)
    canonical, receipt = canonicalize_solver_responses_output(
        response,
        solver_protocol="persistent_v0",
    )
    assert json.loads(canonical)["action"]["kind"] == "read_file"
    assert receipt["candidate_message_count"] == 2
    assert receipt["provider_duplicate_semantic_equivalent"] is True

    distinct = _response_with_texts(first, _wrapper(_act("write_file")))
    with pytest.raises(
        AzureProviderOutputError,
        match="provider_persistent_v0_multiple_distinct_semantic_payloads",
    ):
        canonicalize_solver_responses_output(distinct, solver_protocol="persistent_v0")


def test_persistent_parser_rejects_trailing_text_extra_fields_and_legacy_commitments() -> None:
    canonical = json.dumps(_act("read_file"))
    with pytest.raises(ModelOutputError):
        parse_solver_turn(canonical + " trailing", protocol="persistent_v0")

    with pytest.raises(ModelOutputError, match="provider_persistent_v0_schema_validation"):
        parse_solver_turn(
            json.dumps({
                **_act("read_file"),
                "evidence_gap": "not part of PERSISTENT",
            }),
            protocol="persistent_v0",
        )


def test_kernel_generates_stable_action_identity_from_external_decision() -> None:
    first = {
        "kind": "act",
        "action": {
            "kind": "write_file",
            "capability_id": "filesystem",
            "arguments": {"path": "out.txt", "content": "hello"},
        },
    }
    second = {
        "action": {
            "arguments": {"content": "hello", "path": "out.txt"},
            "capability_id": "filesystem",
            "kind": "write_file",
        },
        "kind": "act",
    }
    one = parse_solver_turn(json.dumps(first), protocol="persistent_v0")
    two = parse_solver_turn(json.dumps(second), protocol="persistent_v0")
    assert one.actions[0].action_id == two.actions[0].action_id
    assert one.actions[0].action_id.startswith("persistent-")


def test_persistent_compiler_renders_minimal_protocol_and_complete_action_catalogue(tmp_path) -> None:
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Create /app/out.txt containing hello.",
        workspace_root=str(tmp_path),
    )
    compiler = ConfigCompiler(CapabilityRegistry.from_envmap(envmap))
    objective, eval_index = compiler.analyze_envmap(envmap)
    runtime = compiler.compile(
        persistent_primary_runtime_ir(envmap, eval_index),
        envmap,
        objective_graph=objective,
        eval_index=eval_index,
    )
    assert runtime.solver_turn_protocol == "persistent_v0"
    sections = dict(runtime.stable_prefix_sections)
    protocol = sections["solver_turn_contract"]
    assert '"protocol":"persistent_v0"' in protocol
    for forbidden in (
        "evidence_gap",
        "expected_observation",
        "if_fail_next",
        "hypothesis",
        "reflection",
    ):
        assert forbidden not in protocol
    assert json.loads(sections["action_schema"]) == persistent_action_contract_view()
    assert "config_realization" not in sections
    assert "selected_capabilities" not in sections
    for custody_only in (
        "architect_summary",
        "architect_visible_contract",
        "success_definition",
        "solver_clause_contract",
        "inspection_plan",
        "proof_plan",
        "workflow_mode",
        "configured_context_policy",
        "configured_advisory_notes",
    ):
        assert custody_only not in sections
    for decision_fact in (
        "task_prompt",
        "envmap",
        "envmap_file_tree",
        "envmap_file_map_summary",
        "objective_graph",
        "eval_index",
        "check_plan",
        "forbidden_paths",
        "environment_probe",
        "refusal_boundary",
        "action_schema",
    ):
        assert decision_fact in sections
    assert "action_schema" in sections
    assert runtime.selected_capabilities
    assert "config_realization" in runtime.config_realization.get("rendered_sections", [])


def test_persistent_environment_probe_projection_preserves_facts_without_negative_row_bloat() -> None:
    probe = {
        "schema_version": "environment_probe.v1",
        "workspace_root": "/app",
        "command_names": {
            "python3": {"available": True, "path": "/usr/bin/python3"},
            "git": {"available": False, "path": ""},
        },
        "python": {
            "preferred": "python3",
            "interpreters": ["python3"],
            "python3": {
                "executable": "/usr/bin/python3",
                "version": "3.13.7",
                "modules": {"pytest": False, "numpy": True},
            },
            "interpreter_details": {
                "python3": {"pip_module_available": True, "site_packages_writable": False},
            },
            "modules": {
                "pytest": {"available": False, "available_in": []},
                "numpy": {"available": True, "available_in": ["python3"]},
            },
            "package_contract": {"pip_available": True},
        },
        "network": {"status": "unknown", "value": "unknown"},
        "task_hints": {"requested_command_names": ["git"], "missing_requested_commands": ["git"]},
        "validation_guidance": {
            "preferred_python": "python3",
            "missing_commands": ["git"],
            "notes": ["Prefer python3"],
        },
    }
    projected = persistent_model_environment_probe(probe)
    assert projected["commands"]["available"]["python3"]["path"] == "/usr/bin/python3"
    assert projected["commands"]["unavailable_names"] == ["git"]
    assert projected["python"]["python3"] == {"executable": "/usr/bin/python3", "version": "3.13.7"}
    assert projected["python"]["modules"]["available"]["numpy"]["available_in"] == ["python3"]
    assert projected["python"]["modules"]["unavailable_names"] == ["pytest"]
    assert projected["network"]["status"] == "unknown"
    assert projected["task_hints"]["missing_requested_commands"] == ["git"]
    assert "validation_guidance" not in projected
    assert len(json.dumps(projected, sort_keys=True)) < len(json.dumps(probe, sort_keys=True))


def test_persistent_environment_probe_projection_preserves_unknown_nonempty_v1_facts() -> None:
    probe = {
        "schema_version": "environment_probe.v1",
        "command_names": {"future": {"available": False, "path": "", "reason": "sandbox policy"}},
        "python": {
            "interpreters": [],
            "modules": {"future_mod": {"available": False, "available_in": [], "reason": "abi mismatch"}},
        },
        "validation_guidance": {"future_fact": {"constraint": "exact"}},
        "future_top": {"opaque": [1, 2, 3]},
    }
    projected = persistent_model_environment_probe(probe)
    assert projected["commands"]["unavailable_details"]["future"]["reason"] == "sandbox policy"
    assert projected["python"]["modules"]["unavailable_details"]["future_mod"]["reason"] == "abi mismatch"
    assert projected["validation_guidance_extra"]["future_fact"] == {"constraint": "exact"}
    assert projected["future_top"] == {"opaque": [1, 2, 3]}


def test_persistent_environment_probe_projection_fails_open_for_unknown_schema() -> None:
    probe = {"schema_version": "environment_probe.v2", "future": {"opaque": [1, 2, 3]}}
    assert persistent_model_environment_probe(probe) == probe


def test_responses_request_uses_persistent_schema_and_visible_contract() -> None:
    request = _render_azure_responses_request_from_split(
        "system authority",
        "current context",
        deployment="deployment",
        effort="low",
        role="solver",
        max_output_tokens=1000,
        background=False,
        structured_output_schema=PERSISTENT_PRIMARY_TURN_SCHEMA,
        structured_output_name=PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME,
        prompt_cache_mode="off",
        prompt_cache_namespace="test",
    )
    assert request["text"]["format"]["schema"] == PERSISTENT_PRIMARY_PROVIDER_SCHEMA
    assert "uniqueItems" in json.dumps(PERSISTENT_PRIMARY_TURN_SCHEMA, sort_keys=True)
    assert "uniqueItems" not in json.dumps(PERSISTENT_PRIMARY_PROVIDER_SCHEMA, sort_keys=True)
    assert request["text"]["format"]["name"] == PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
    schema_text = json.dumps(request["text"]["format"]["schema"], sort_keys=True)
    for forbidden in (
        "evidence_gap",
        "expected_observation",
        "if_fail_next",
        "chain_of_thought",
        "hidden_reasoning",
        "reflection",
    ):
        assert forbidden not in schema_text
    variants = request["text"]["format"]["schema"]["properties"]["turn"]["anyOf"]
    core_variants = [
        variant for variant in variants
        if "working_state" not in variant.get("properties", {})
    ]
    continuity_variants = [
        variant for variant in variants
        if "working_state" in variant.get("properties", {})
    ]
    assert core_variants and continuity_variants
    assert all("hypothesis" not in json.dumps(row, sort_keys=True) for row in core_variants)
    assert all("working_state" in row["required"] for row in continuity_variants)
    assert "exactly one" in request["instructions"].lower()
    assert "do not emit action ids" in request["instructions"].lower()
