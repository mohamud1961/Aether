from __future__ import annotations

import json

import jsonschema
import pytest

from aether.model_prompts import VERIFIER_RUNTIME_CONTRACT
from aether.providers.azure_model import (
    _PCR_VERIFIER_DIRECT_TURN_SCHEMA,
    _PCR_VERIFIER_NATIVE_TOOL,
    _VERIFIER_DIRECT_TURN_SCHEMA,
    unwrap_verifier_direct_turn,
)
from aether.verifier_budget import (
    DERIVED_EXECUTION_KINDS,
    DIRECT_OBSERVATION_KINDS,
    VerifierBudgetError,
    VerifierPhaseBudget,
    VerifierPhaseState,
)
from aether.verifier_inspector import (
    VerifierInspectionRequest,
    parse_verifier_inspection_requests,
)


def _provider_request(kind: str) -> dict[str, object]:
    row: dict[str, object] = {
        "request_id": f"request-{kind}",
        "kind": kind,
        "path": None,
        "handle": None,
        "check_id": None,
        "receipt_kind": None,
        "limit": None,
        "command": None,
        "content": None,
        "target": None,
        "offset": None,
        "span": None,
        "clause_ids": None,
        "proof_ids": None,
        "verification_plan": None,
        "execution": None,
    }
    if kind == "read_file":
        row["path"] = "out.txt"
    if kind == "rerun_check":
        row["check_id"] = "compiled-check"
    if kind == "overlay_write_fixture":
        row["path"] = "fixture.txt"
        row["content"] = "synthetic verifier input"
    if kind == "overlay_run_command":
        row["verification_plan"] = {
            "claim": "derived claim",
            "evidence_mode": "derived",
            "clause_ids": ["task:raw"],
            "basis": [{"ref": "inspection:prior", "supported_fact": "prior observation"}],
            "bound_input_refs": ["inspection:prior"],
            "authoritative_structure": "observed bytes",
            "method_summary": "derive from prior observation",
            "proxy_risk": "a proxy may agree accidentally",
        }
        row["execution"] = {
            "kind": "overlay_run_command",
            "command": "python3 verify.py",
        }
    return row


def _turn(*requests: dict[str, object]) -> dict[str, object]:
    return {"turn": {"kind": "inspect", "requests": list(requests)}}


def _pcr_direct_request(kind: str, locator: str | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": kind,
        "limit": None,
        "offset": None,
        "span": None,
        "clause_ids": None,
        "proof_ids": None,
    }
    if kind != "inspect_recent_receipts":
        row["locator"] = locator if locator is not None else "out.txt"
    return row


def _pcr_command_request(
    *, basis_refs: list[str] | None = None, bound_input_refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "kind": "run_verifier_command",
        "command": "python3 target.py",
        "clause_ids": ["task:raw"],
        "basis_refs": list(basis_refs or ["inspection:prior"]),
        "bound_input_refs": list(bound_input_refs or ["inspection:prior"]),
    }


def _pcr_fixture_request(path: str = "fixtures/input.txt", content: str = "fixture") -> dict[str, object]:
    return {
        "request_id": "request-fixture",
        "kind": "write_verifier_fixture",
        "path": path,
        "content": content,
    }


def test_provider_schema_phase_vocabularies_exactly_match_runtime() -> None:
    defs = _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    direct = set(defs["direct_inspection_request"]["properties"]["kind"]["enum"])
    derived = set(defs["derived_inspection_request"]["properties"]["kind"]["enum"])
    assert direct == set(DIRECT_OBSERVATION_KINDS)
    assert derived == set(DERIVED_EXECUTION_KINDS)
    assert direct.isdisjoint(derived)


def test_provider_schema_closes_nested_execution_and_evidence_vocabularies() -> None:
    defs = _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    assert defs["execution"]["properties"]["kind"] == {
        "anyOf": [{"type": "string", "enum": ["overlay_run_command"]}, {"type": "null"}],
    }
    assert defs["verification_plan"]["properties"]["evidence_mode"] == {
        "anyOf": [{"type": "string", "enum": ["direct", "derived"]}, {"type": "null"}],
    }

    invalid_execution = _provider_request("overlay_run_command")
    invalid_execution["execution"]["kind"] = "command"  # type: ignore[index]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(invalid_execution), _VERIFIER_DIRECT_TURN_SCHEMA)

    invalid_evidence_mode = _provider_request("overlay_run_command")
    invalid_evidence_mode["verification_plan"]["evidence_mode"] = "independent_semantic"  # type: ignore[index]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(invalid_evidence_mode), _VERIFIER_DIRECT_TURN_SCHEMA)


def test_provider_schema_accepts_homogeneous_direct_and_derived_turns() -> None:
    jsonschema.validate(
        _turn(_provider_request("read_file"), _provider_request("probe_process")),
        _VERIFIER_DIRECT_TURN_SCHEMA,
    )
    jsonschema.validate(
        _turn(
            _provider_request("overlay_write_fixture"),
            _provider_request("overlay_run_command"),
        ),
        _VERIFIER_DIRECT_TURN_SCHEMA,
    )
    jsonschema.validate(
        _turn(_provider_request("rerun_check")),
        _VERIFIER_DIRECT_TURN_SCHEMA,
    )


def test_provider_schema_rejects_mixed_direct_and_derived_turn_before_runtime() -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            _turn(_provider_request("read_file"), _provider_request("overlay_run_command")),
            _VERIFIER_DIRECT_TURN_SCHEMA,
        )


def test_provider_schema_rejects_empty_inspection_turn() -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(), _VERIFIER_DIRECT_TURN_SCHEMA)


def test_runtime_phase_classifier_admits_every_advertised_executable_route() -> None:
    rerun = VerifierInspectionRequest(
        request_id="rerun", kind="rerun_check", check_id="compiled-check",
    )
    fixture = VerifierInspectionRequest(
        request_id="fixture", kind="overlay_write_fixture", path="fixture.txt", content="input",
    )
    derived = VerifierInspectionRequest(
        request_id="derive", kind="overlay_run_command", command="python3 verify.py",
        evidence_mode="derived", basis_refs=("inspection:prior",),
        bound_input_refs=("inspection:prior",),
    )
    state = VerifierPhaseState(VerifierPhaseBudget())
    assert state.classify_and_reserve((rerun,)) == "VERIFY"
    assert state.classify_and_reserve((fixture, derived)) == "VERIFY"
    assert state.derived_execution_batches == 2


def test_runtime_still_rejects_direct_plus_derived_without_executing_a_phase() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget())
    direct = VerifierInspectionRequest(request_id="read", kind="read_file", path="out.txt")
    derived = VerifierInspectionRequest(
        request_id="derive", kind="overlay_run_command", command="python3 verify.py",
        evidence_mode="derived", basis_refs=("inspection:prior",),
        bound_input_refs=("inspection:prior",),
    )
    with pytest.raises(VerifierBudgetError, match="either independent direct observations or derived executions"):
        state.classify_and_reserve((direct, derived))
    assert state.investigation_batches == 0
    assert state.derived_execution_batches == 0


def test_model_facing_contract_states_homogeneous_phase_boundary() -> None:
    rules = "\n".join(VERIFIER_RUNTIME_CONTRACT["read_only_inspector"]["rules"])
    assert "one inspect turn must be homogeneous" in rules
    assert "Never mix a direct observation with a derived operation" in rules
    assert "verifier_phase_budget" in rules



def test_derived_provider_schema_has_only_one_executable_command_surface() -> None:
    defs = _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    assert defs["derived_inspection_request"]["properties"]["command"] == {"type": "null"}
    # Direct/legacy requests retain their existing nullable surface; this
    # treatment is specific to V3 derived execution.
    assert defs["direct_inspection_request"]["properties"]["command"] != {"type": "null"}

    valid = _provider_request("overlay_run_command")
    valid["command"] = None
    jsonschema.validate(_turn(valid), _VERIFIER_DIRECT_TURN_SCHEMA)

    ambiguous = _provider_request("overlay_run_command")
    ambiguous["command"] = "python3 wrong-surface.py"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(ambiguous), _VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_provider_schema_removes_method_only_action_receipt_route() -> None:
    action_receipts = _provider_request("inspect_action_receipts")
    action_receipts["clause_ids"] = ["method:required"]

    # Generic/ASV-compatible Verifier retains action history for real method
    # constraints.
    jsonschema.validate(_turn(action_receipts), _VERIFIER_DIRECT_TURN_SCHEMA)

    # PCR V0 has no method_constraints, so the method-only inspection route is
    # absent regardless of whether clause_ids are populated or null.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(action_receipts), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    action_receipts["clause_ids"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(action_receipts), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_provider_schema_retains_raw_task_tags_on_other_direct_observations() -> None:
    read = _pcr_direct_request("read_file", "out.txt")
    read["clause_ids"] = ["task:raw"]
    jsonschema.validate(_turn(read), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_native_verifier_tool_uses_compact_specialized_schema() -> None:
    assert _PCR_VERIFIER_NATIVE_TOOL["parameters"] is _PCR_VERIFIER_DIRECT_TURN_SCHEMA
    defs = _PCR_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    assert defs["direct_inspection_request"] == {
        "anyOf": [
            {"$ref": "#/$defs/pcr_direct_locator_request"},
            {"$ref": "#/$defs/pcr_cited_receipt_request"},
        ],
    }
    direct_schema = defs["pcr_direct_locator_request"]
    locator_kinds = set(direct_schema["properties"]["kind"]["enum"])
    expected_runtime = set(DIRECT_OBSERVATION_KINDS) - {
        "inspect_action_receipts", "inspect_recent_receipts", "probe_process",
    }
    assert locator_kinds == expected_runtime | {"observe_existing_process"}
    assert "probe_process" not in locator_kinds
    assert "check_id" not in direct_schema["properties"]
    assert "receipt_kind" not in direct_schema["properties"]
    assert "request_id" not in direct_schema["properties"]
    assert "request_id" not in defs["pcr_cited_receipt_request"]["properties"]
    assert defs["pcr_rerun_check_request"]["properties"]["request_id"] == {"type": "null"}


def test_pcr_provider_rejects_runtime_internal_nested_command_shape() -> None:
    nested = _provider_request("overlay_run_command")
    # Generic/ASV compatibility schema remains native V3.
    jsonschema.validate(_turn(nested), _VERIFIER_DIRECT_TURN_SCHEMA)
    # PCR exposes only the compact provider alias.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(nested), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    compact = _pcr_command_request()
    jsonschema.validate(_turn(compact), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    for forbidden, value in (
        ("verification_plan", nested["verification_plan"]),
        ("execution", nested["execution"]),
        ("path", "target.py"),
        ("target", "target.py"),
    ):
        polluted = dict(compact)
        polluted[forbidden] = value
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_turn(polluted), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_compact_command_canonicalizes_exactly_to_runtime_v3() -> None:
    compact = _pcr_command_request(
        basis_refs=["inspection:source"],
        bound_input_refs=["inspection:source", "inspection:fixture"],
    )
    canonical, receipt = unwrap_verifier_direct_turn(json.dumps(_turn(compact)))
    request = json.loads(canonical)["requests"][0]
    assert request["kind"] == "overlay_run_command"
    assert request["execution"] == {
        "kind": "overlay_run_command", "command": "python3 target.py",
    }
    plan = request["verification_plan"]
    assert plan["evidence_mode"] == "derived"
    assert plan["clause_ids"] == ["task:raw"]
    assert plan["basis"] == [{"ref": "inspection:source"}]
    assert plan["bound_input_refs"] == ["inspection:source", "inspection:fixture"]
    for field in ("claim", "authoritative_structure", "method_summary", "proxy_risk"):
        assert "PCR transport placeholder" in plan[field]
    assert "request_id" not in request
    assert "proof_ids" not in request
    parsed = parse_verifier_inspection_requests(
        {"kind": "inspect", "requests": [request]}, require_derived_contract=True,
    )
    assert parsed[0].request_id == "inspect-0"
    assert parsed[0].command == "python3 target.py"
    assert parsed[0].basis_refs == ("inspection:source",)
    assert parsed[0].bound_input_refs == ("inspection:source", "inspection:fixture")
    mapping = receipt["provider_pcr_verifier_compact_command_mapping"]
    assert mapping[0]["provider_kind"] == "run_verifier_command"
    assert mapping[0]["runtime_kind"] == "overlay_run_command"
    assert mapping[0]["basis_ref_count"] == 1
    assert mapping[0]["bound_input_ref_count"] == 2
    assert len(mapping[0]["command_sha256"]) == 64


def test_pcr_schema_keeps_only_rerun_and_command_as_derived_provider_routes() -> None:
    overlay_without_plan = _provider_request("overlay_run_command")
    overlay_without_plan["verification_plan"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(overlay_without_plan), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    overlay_without_execution = _provider_request("overlay_run_command")
    overlay_without_execution["execution"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(overlay_without_execution), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    rerun = _provider_request("rerun_check")
    rerun["request_id"] = None
    jsonschema.validate(_turn(rerun), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    # F88 removes the standalone fixture mechanism from PCR while preserving
    # the generic/ASV runtime route.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(_pcr_fixture_request()), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    nested_fixture = _provider_request("overlay_write_fixture")
    jsonschema.validate(_turn(nested_fixture), _VERIFIER_DIRECT_TURN_SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(nested_fixture), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_static_cited_receipt_branch_is_separate_from_open_direct_locator() -> None:
    defs = _PCR_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    cited = defs["pcr_cited_receipt_request"]
    assert cited["properties"]["kind"] == {"type": "string", "enum": ["read_cited_receipt"]}
    assert cited["properties"]["locator"]["pattern"] == r"^receipt:\S+"
    assert "read_cited_receipt" not in defs["pcr_direct_locator_request"]["properties"]["kind"]["enum"]
    # Generic/ASV vocabulary stays exactly on the shared runtime kinds.
    assert "read_cited_receipt" not in _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["direct_inspection_request"]["properties"]["kind"]["enum"]


def test_pcr_direct_observation_has_no_executable_or_derived_surfaces() -> None:
    direct = _pcr_direct_request("read_file", "out.txt")
    jsonschema.validate(_turn(direct), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    for field, value in (
        ("command", "python3 wrong.py"),
        ("path", "out.txt"),
        ("target", "127.0.0.1:80"),
        ("verification_plan", _provider_request("overlay_run_command")["verification_plan"]),
    ):
        polluted = dict(direct)
        polluted[field] = value
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_turn(polluted), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_rerun_requires_runtime_identity_and_fixture_alias_is_absent() -> None:
    fixture = _pcr_fixture_request()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(fixture), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    nested_fixture = _provider_request("overlay_write_fixture")
    jsonschema.validate(_turn(nested_fixture), _VERIFIER_DIRECT_TURN_SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(nested_fixture), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    rerun = _provider_request("rerun_check")
    rerun["request_id"] = None
    jsonschema.validate(_turn(rerun), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    rerun["check_id"] = None
    jsonschema.validate(_turn(rerun), _VERIFIER_DIRECT_TURN_SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(rerun), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    rerun["check_id"] = ""
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(rerun), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

def test_pcr_compact_direct_route_requires_one_nonempty_locator() -> None:
    locator_by_kind = {
        "read_file": "out.txt",
        "read_output": "step-1:run:stdout",
        "inspect_artifact_history": "out.txt",
        "probe_port": "127.0.0.1:8080",
        "probe_http": "http://127.0.0.1:8080/health",
        "observe_existing_process": "python3 target.py",
        "probe_job": "job-123",
        "inspect_artifact": "out.txt",
        "perceive_artifact": "image.png",
    }
    for kind, locator in locator_by_kind.items():
        row = _pcr_direct_request(kind, locator)
        jsonschema.validate(_turn(row), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

        missing = dict(row)
        missing.pop("locator")
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_turn(missing), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

        empty = dict(row)
        empty["locator"] = ""
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_turn(empty), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    recent = _provider_request("inspect_recent_receipts")
    jsonschema.validate(_turn(recent), _VERIFIER_DIRECT_TURN_SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(recent), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_compact_direct_request_id_is_host_owned() -> None:
    row = _pcr_direct_request("read_file", "out.txt")
    jsonschema.validate(_turn(row), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    null_id = dict(row); null_id["request_id"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(null_id), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    null_canonical, _ = unwrap_verifier_direct_turn(json.dumps(_turn(null_id)))
    assert "request_id" not in json.loads(null_canonical)["requests"][0]
    for unsafe in ("model-label", 'bad\"},{'):
        polluted = dict(row); polluted["request_id"] = unsafe
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_turn(polluted), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
        with pytest.raises(Exception, match="provider_pcr_verifier_direct_request_id_forbidden"):
            unwrap_verifier_direct_turn(json.dumps(_turn(polluted)))
    canonical, _receipt = unwrap_verifier_direct_turn(json.dumps(_turn(row)))
    decoded = json.loads(canonical)
    request = decoded["requests"][0]
    assert request["path"] == "out.txt"
    assert "request_id" not in request
    parsed = parse_verifier_inspection_requests({"kind": "inspect", "requests": [request]})
    assert parsed[0].request_id == "inspect-0"


def test_pcr_compact_direct_locator_canonicalizes_one_to_one_for_runtime() -> None:
    mapping = {
        "read_file": ("out.txt", "read_file", "path"),
        "read_output": ("step-1:run:stdout", "read_output", "handle"),
        "inspect_artifact_history": ("out.txt", "inspect_artifact_history", "path"),
        "probe_port": ("127.0.0.1:8080", "probe_port", "target"),
        "probe_http": ("http://127.0.0.1:8080/health", "probe_http", "target"),
        "observe_existing_process": ("python3 target.py", "probe_process", "target"),
        "probe_job": ("job-123", "probe_job", "target"),
        "inspect_artifact": ("out.txt", "inspect_artifact", "path"),
        "perceive_artifact": ("image.png", "perceive_artifact", "path"),
    }
    for provider_kind, (locator, runtime_kind, runtime_field) in mapping.items():
        wrapper = _turn(_pcr_direct_request(provider_kind, locator))
        canonical, receipt = unwrap_verifier_direct_turn(json.dumps(wrapper))
        turn = json.loads(canonical)
        request = turn["requests"][0]
        assert request["kind"] == runtime_kind
        assert request[runtime_field] == locator
        assert "locator" not in request
        mapping_row = receipt["provider_pcr_verifier_compact_locator_mapping"][0]
        assert mapping_row["provider_kind"] == provider_kind
        assert mapping_row["runtime_kind"] == runtime_kind
        assert mapping_row["runtime_field"] == runtime_field


def test_pcr_process_observation_alias_is_explicit_and_runtime_probe_process_is_hidden() -> None:
    observed = _pcr_direct_request("observe_existing_process", "python3 target.py")
    jsonschema.validate(_turn(observed), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    canonical, receipt = unwrap_verifier_direct_turn(json.dumps(_turn(observed)))
    request = json.loads(canonical)["requests"][0]
    assert request["kind"] == "probe_process"
    assert request["target"] == "python3 target.py"
    row = receipt["provider_pcr_verifier_compact_locator_mapping"][0]
    assert row["provider_kind"] == "observe_existing_process"
    assert row["runtime_kind"] == "probe_process"

    legacy_provider = _pcr_direct_request("probe_process", "python3 target.py")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(legacy_provider), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_direct_schema_rejects_irrelevant_route_intent_fields() -> None:
    direct = _pcr_direct_request("observe_existing_process", "python3 target.py")
    for field in ("receipt_kind", "check_id"):
        polluted = dict(direct)
        polluted[field] = "run_verifier_command"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_turn(polluted), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_static_schema_has_single_command_frontier_and_no_fixture_alias() -> None:
    defs = _PCR_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    refs = {row["$ref"] for row in defs["derived_inspection_request"]["anyOf"]}
    assert refs == {
        "#/$defs/pcr_rerun_check_request",
        "#/$defs/pcr_run_verifier_command_request",
    }
    assert "pcr_write_verifier_fixture_request" not in defs
    assert "write_verifier_fixture" not in json.dumps(_PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(_pcr_fixture_request()), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    # Generic/ASV provider surface remains unchanged.
    nested = _provider_request("overlay_write_fixture")
    jsonschema.validate(_turn(nested), _VERIFIER_DIRECT_TURN_SCHEMA)

def test_pcr_command_provider_surface_is_exactly_five_causal_fields() -> None:
    command = _PCR_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["pcr_run_verifier_command_request"]
    expected = ["kind", "command", "clause_ids", "basis_refs", "bound_input_refs"]
    assert command["required"] == expected
    assert list(command["properties"]) == expected
    valid = _pcr_command_request()
    jsonschema.validate(_turn(valid), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    for polluted_field, value in (
        ("request_id", "run"),
        ("claim", "semantic claim"),
        ("authoritative_structure", "source bytes"),
        ("method_summary", "run a check"),
        ("proxy_risk", "proxy"),
        ("proof_ids", []),
    ):
        polluted = dict(valid); polluted[polluted_field] = value
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_turn(polluted), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_pcr_compact_direct_schema_size_stays_bounded() -> None:
    compact_bytes = len(json.dumps(_PCR_VERIFIER_DIRECT_TURN_SCHEMA, separators=(",", ":")))
    assert compact_bytes <= 15_000


def test_pcr_compact_command_accepts_only_verifier_inspection_identity_refs() -> None:
    valid = _pcr_command_request()
    jsonschema.validate(_turn(valid), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    bad_basis = _pcr_command_request(
        basis_refs=["receipt:step-1:solver"],
        bound_input_refs=["inspection:prior"],
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(bad_basis), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)

    bad_input = _pcr_command_request(
        basis_refs=["inspection:prior"],
        bound_input_refs=["receipt:step-1:solver"],
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_turn(bad_input), _PCR_VERIFIER_DIRECT_TURN_SCHEMA)



def test_f94_requirement_status_is_required_only_by_pcr_provider_schema() -> None:
    generic = _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["completion_evidence"]
    pcr = _PCR_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["completion_evidence"]
    assert "requirement_status" not in generic["properties"]
    assert "requirement_status" not in generic["required"]
    assert pcr["properties"]["requirement_status"] == {
        "type": "string", "enum": ["satisfied", "violated", "unknown"],
    }
    assert pcr["required"].count("requirement_status") == 1
    # Prove the PCR schema object is a deep-cloned specialization rather than
    # an accidental mutation of the generic/ASV schema.
    assert pcr is not generic


def test_pcr_verifier_native_instruction_forbids_mixed_strength_laundering() -> None:
    from aether.providers.azure_model import _PCR_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION
    instruction = _PCR_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION
    assert "at most one inspection ref in each completion_evidence entry or repair finding" in instruction
    assert "emit separate entries/findings" in instruction
    assert "must not exceed the kernel-reported actual_evidence_class" in instruction
