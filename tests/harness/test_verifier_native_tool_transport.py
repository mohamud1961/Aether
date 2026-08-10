from __future__ import annotations

import json
from types import SimpleNamespace

import jsonschema
import pytest

from aether.model_request_contract import ExpectedModelRequest, preflight_model_request
from aether.providers.azure_model import (
    AzureModelCallable,
    AzureProviderOutputError,
    _persistent_verifier_native_tool_for_input,
    _persistent_verifier_prior_inspection_namespaces_from_input,
    canonicalize_verifier_native_tool_output,
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
        row["path"] = "/app/out.txt"
    elif kind == "overlay_run_command":
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


def _inspect(kind: str) -> str:
    return json.dumps({"turn": {"kind": "inspect", "requests": [_provider_request(kind)]}})


def _verdict() -> str:
    return json.dumps({
        "turn": {
            "verdict": "uncertain_missing_evidence",
            "confidence": "low",
            "summary": "Need one more direct observation.",
            "findings": [],
            "missing_evidence_requests": ["Read the final artifact."],
            "completion_evidence": [],
            "method_validity": None,
        }
    })


def _function_call(
    arguments: str | None = None,
    *,
    name: str = "verifier_turn",
    suffix: str = "1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"fc-{suffix}",
        type="function_call",
        call_id=f"call-{suffix}",
        name=name,
        arguments=_inspect("read_file") if arguments is None else arguments,
    )


def _message(text: str = "unexpected") -> SimpleNamespace:
    return SimpleNamespace(
        id="msg-1",
        type="message",
        role="assistant",
        content=[SimpleNamespace(type="output_text", text=text)],
    )


def _response(*items: object) -> SimpleNamespace:
    return SimpleNamespace(
        id="resp-1",
        status="completed",
        output=list(items),
        usage=None,
        error=None,
        incomplete_details=None,
    )


@pytest.mark.parametrize(
    ("arguments", "expected_kind"),
    [
        (_inspect("read_file"), "inspect"),
        (_inspect("overlay_run_command"), "inspect"),
        (_verdict(), "verdict"),
    ],
)
def test_verifier_native_tool_decoder_accepts_each_existing_turn_class(
    arguments: str,
    expected_kind: str,
) -> None:
    canonical, receipt = canonicalize_verifier_native_tool_output(
        _response(_function_call(arguments))
    )
    decoded = json.loads(canonical)
    if expected_kind == "inspect":
        assert decoded["kind"] == "inspect"
    else:
        assert decoded["verdict"] == "uncertain_missing_evidence"
    assert receipt["provider_turn_kind"] == expected_kind
    assert receipt["native_tool_name"] == "verifier_turn"
    assert receipt["native_tool_call_count"] == 1
    assert receipt["candidate_message_count"] == 0


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (_response(), "provider_verifier_native_tool_call_count_invalid"),
        (
            _response(_function_call(suffix="1"), _function_call(suffix="2")),
            "provider_verifier_native_tool_call_count_invalid",
        ),
        (
            _response(_function_call(name="wrong_tool")),
            "provider_verifier_native_tool_name_invalid",
        ),
        (
            _response(_function_call(), _message()),
            "provider_verifier_native_tool_mixed_output",
        ),
        (
            _response(_function_call(), SimpleNamespace(type="computer_call", id="cc-1")),
            "provider_verifier_native_tool_mixed_output",
        ),
        (
            _response(_function_call(json.dumps({"not_turn": {}}))),
            "provider_direct_turn_invalid_shape",
        ),
    ],
)
def test_verifier_native_tool_decoder_fails_closed(response: object, code: str) -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        canonicalize_verifier_native_tool_output(response)
    assert excinfo.value.code == code


class _FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        return self.response

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("foreground completed fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not cancel")


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.responses = _FakeResponses(response)


def _model(
    response: object, *, verifier_protocol: str = "verifier_v1",
) -> tuple[AzureModelCallable, _FakeClient]:
    client = _FakeClient(response)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-frontier",
        effort="low",
        role="verifier",
        solver_protocol="solver_v1",
        verifier_protocol=verifier_protocol,
        transport="responses_tools",
        responses_background=False,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode="off",
    )
    return model, client


def test_verifier_native_tool_transport_forces_one_nonparallel_call() -> None:
    model, client = _model(_response(_function_call()))
    canonical = model(
        [{"role": "user", "content": "Inspect the final artifact."}],
        max_output_tokens=16000,
    )

    assert json.loads(canonical)["kind"] == "inspect"
    assert len(client.responses.requests) == 1
    request = client.responses.requests[0]
    assert request["background"] is False
    assert request["parallel_tool_calls"] is False
    assert request["max_tool_calls"] == 1
    assert request["tool_choice"] == {"type": "function", "name": "verifier_turn"}
    assert "text" not in request
    tools = request["tools"]
    assert isinstance(tools, list) and len(tools) == 1
    assert tools[0]["name"] == "verifier_turn"
    assert tools[0]["strict"] is True
    assert tools[0]["parameters"]["required"] == ["turn"]

    # The native function reuses the frozen direct Verifier schema, so the
    # provider itself can enforce homogeneous direct/derived turns and verdicts.
    jsonschema.validate(json.loads(_inspect("read_file")), tools[0]["parameters"])
    jsonschema.validate(json.loads(_inspect("overlay_run_command")), tools[0]["parameters"])
    jsonschema.validate(json.loads(_verdict()), tools[0]["parameters"])
    with pytest.raises(jsonschema.ValidationError):
        mixed = json.loads(_inspect("read_file"))
        mixed["turn"]["requests"].append(_provider_request("overlay_run_command"))
        jsonschema.validate(mixed, tools[0]["parameters"])

    telemetry = model.drain_telemetry()
    assert len(telemetry) == 1
    assert telemetry[0]["structured_output_mode"] == "verifier_direct_turn_native_tool"
    assert telemetry[0]["native_tool_name"] == "verifier_turn"
    assert telemetry[0]["max_tool_calls_requested"] == 1
    assert telemetry[0]["parallel_tool_calls"] is False
    assert telemetry[0]["native_tool_call_count"] == 1


def test_verifier_native_tool_preflight_is_explicit_and_admitted() -> None:
    model, _client = _model(_response(_function_call()))
    row = preflight_model_request(
        model,
        ExpectedModelRequest(logical_role="verifier", max_output_tokens=16000),
    )
    assert row["provider"] == "azure_openai_responses"
    assert row["structured_output_mode"] == "verifier_direct_turn_native_tool"
    assert row["native_tool_name"] == "verifier_turn"
    assert row["max_tool_calls_requested"] == 1
    assert row["parallel_tool_calls"] is False
    assert row["background"] is False


def test_responses_tools_still_rejects_unqualified_non_verifier_non_persistent_roles() -> None:
    client = _FakeClient(_response(_function_call()))
    with pytest.raises(ValueError, match="PERSISTENT V0 Solver or Verifier"):
        AzureModelCallable(
            client=client,  # type: ignore[arg-type]
            deployment="unit-test-frontier",
            effort="low",
            role="architect",
            solver_protocol="solver_v1",
            transport="responses_tools",
            responses_background=False,
            poll_interval_s=1.0,
            poll_timeout_s=30.0,
            max_retries=0,
        )


def test_verifier_native_tool_provider_error_is_preserved_in_telemetry() -> None:
    model, _client = _model(_response(_function_call(name="wrong_tool")))
    with pytest.raises(AzureProviderOutputError) as excinfo:
        model([{"role": "user", "content": "Choose one verifier turn."}])
    assert excinfo.value.code == "provider_verifier_native_tool_name_invalid"
    event = model.drain_telemetry()[0]
    assert event["status"] == "failed"
    assert event["provider_output_error"] == "provider_verifier_native_tool_name_invalid"


def test_verifier_native_tool_rejects_identical_concatenated_argument_objects() -> None:
    duplicated = _inspect("read_file") + "\n" + _inspect("read_file")
    with pytest.raises(AzureProviderOutputError) as excinfo:
        canonicalize_verifier_native_tool_output(_response(_function_call(duplicated)))
    assert excinfo.value.code == "provider_verifier_native_tool_arguments_invalid"


def test_verifier_native_tool_rejects_distinct_concatenated_argument_objects() -> None:
    distinct = _inspect("read_file") + "\n" + _verdict()
    with pytest.raises(AzureProviderOutputError) as excinfo:
        canonicalize_verifier_native_tool_output(_response(_function_call(distinct)))
    assert excinfo.value.code == "provider_verifier_native_tool_arguments_invalid"


@pytest.mark.parametrize("bad", [
    _inspect("read_file") + " trailing prose",
    "```json\n" + _inspect("read_file") + "\n```",
    "{not-json",
    "",
])
def test_verifier_native_tool_arguments_must_be_one_bare_complete_json_object(bad: str) -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        canonicalize_verifier_native_tool_output(_response(_function_call(bad)))
    assert excinfo.value.code == "provider_verifier_native_tool_arguments_invalid"


def test_verifier_native_tool_allows_empty_assistant_item_but_records_it() -> None:
    empty = SimpleNamespace(id="msg-empty", type="message", role="assistant", content=[])
    canonical, receipt = canonicalize_verifier_native_tool_output(
        _response(empty, _function_call())
    )
    assert json.loads(canonical)["kind"] == "inspect"
    assert receipt["provider_output_item_count"] == 2
    assert receipt["assistant_message_item_count"] == 1
    assert receipt["assistant_message_nonempty_count"] == 0
    assert receipt["function_call_item_count"] == 1
    assert receipt["function_call_names"] == ("verifier_turn",)
    assert receipt["native_tool_arguments_bytes"] > 0
    assert len(receipt["native_tool_arguments_sha256"]) == 64


def test_verifier_native_preflight_cannot_masquerade_as_solver_role() -> None:
    model, _client = _model(_response(_function_call()))
    with pytest.raises(Exception, match="native-tool preflight"):
        preflight_model_request(
            model,
            ExpectedModelRequest(logical_role="solver", max_output_tokens=16000),
        )


def test_persistent_verifier_native_request_uses_persistent_specific_action_receipt_schema() -> None:
    model, client = _model(_response(_function_call()), verifier_protocol="persistent_v0")
    model([{"role": "user", "content": "Inspect current evidence."}])

    request = client.responses.requests[0]
    schema = request["tools"][0]["parameters"]
    bad = _provider_request("inspect_action_receipts")
    bad["clause_ids"] = ["task:raw"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"turn": {"kind": "inspect", "requests": [bad]}}, schema)
    bad["clause_ids"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"turn": {"kind": "inspect", "requests": [bad]}}, schema)

    read = {
        "kind": "read_file",
        "locator": "/app/out.txt",
        "limit": None,
        "offset": None,
        "span": None,
        "clause_ids": ["task:raw"],
        "proof_ids": None,
    }
    jsonschema.validate({"turn": {"kind": "inspect", "requests": [read]}}, schema)

    canonical, receipt = canonicalize_verifier_native_tool_output(
        _response(_function_call(json.dumps({"turn": {"kind": "inspect", "requests": [read]}})))
    )
    decoded = json.loads(canonical)
    assert decoded["requests"][0]["path"] == "/app/out.txt"
    assert "locator" not in decoded["requests"][0]
    assert receipt["provider_persistent_verifier_compact_locator_mapping"][0]["runtime_field"] == "path"

    preflight = model.preflight_request(max_output_tokens=16000, logical_role="verifier")
    assert preflight["verifier_protocol"] == "persistent_v0"


def test_persistent_verifier_protocol_rejects_non_native_transport() -> None:
    client = _FakeClient(_response(_function_call()))
    with pytest.raises(ValueError, match="requires responses_tools"):
        AzureModelCallable(
            client=client,  # type: ignore[arg-type]
            deployment="unit-test-frontier",
            effort="low",
            role="verifier",
            verifier_protocol="persistent_v0",
            transport="chat_completions",
            responses_background=False,
            poll_interval_s=1.0,
            poll_timeout_s=30.0,
            max_retries=0,
        )


def _persistent_packet_input(check_ids: list[str]) -> list[dict[str, str]]:
    return [{
        "role": "user",
        "content": json.dumps({
            "authoritative_task_prompt": "task",
            "verifier_packet": {"authoritative_check_ids": check_ids},
        }),
    }]


def test_persistent_native_tool_removes_entire_derived_turn_without_authority() -> None:
    tool, ids = _persistent_verifier_native_tool_for_input(_persistent_packet_input([]))
    assert ids == ()
    schema = tool["parameters"]
    defs = schema["$defs"]
    root_refs = {row["$ref"] for row in schema["properties"]["turn"]["anyOf"]}
    assert root_refs == {"#/$defs/direct_inspect_turn", "#/$defs/verdict_turn"}
    assert "derived_inspection_request" not in defs
    assert "derived_inspect_turn" not in defs
    assert "persistent_rerun_check_request" not in defs
    assert "persistent_run_verifier_command_request" not in defs

    rerun = _provider_request("rerun_check")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"turn": {"kind": "inspect", "requests": [rerun]}}, schema)


def test_persistent_native_tool_binds_rerun_check_to_exact_packet_namespace() -> None:
    messages = _persistent_packet_input(["check-a", "check-b"])
    # Later transcript messages must not erase or broaden the original packet namespace.
    messages.extend([
        {"role": "assistant", "content": "{\"kind\":\"inspect\",\"requests\":[]}"},
        {"role": "user", "content": json.dumps({"verifier_inspection_results": []})},
    ])
    tool, ids = _persistent_verifier_native_tool_for_input(messages)
    assert ids == ("check-a", "check-b")
    schema = tool["parameters"]
    assert schema["$defs"]["persistent_rerun_check_request"]["properties"]["check_id"] == {
        "type": "string", "enum": ["check-a", "check-b"],
    }
    assert {
        row["$ref"] for row in schema["$defs"]["derived_inspection_request"]["anyOf"]
    } == {"#/$defs/persistent_rerun_check_request"}
    assert "persistent_run_verifier_command_request" not in schema["$defs"]
    valid = _provider_request("rerun_check")
    valid["request_id"] = None
    valid["check_id"] = "check-b"
    jsonschema.validate({"turn": {"kind": "inspect", "requests": [valid]}}, schema)
    invalid = _provider_request("rerun_check")
    invalid["check_id"] = "invented"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"turn": {"kind": "inspect", "requests": [invalid]}}, schema)



def test_persistent_native_tool_exposes_rerun_and_command_when_both_authorities_exist() -> None:
    source = "inspection:2:0:source"
    messages = _persistent_packet_input(["check-a"])
    messages.append(_persistent_runtime_namespace_message([source], [source]))
    tool, ids = _persistent_verifier_native_tool_for_input(messages)
    assert ids == ("check-a",)
    schema = tool["parameters"]
    refs = {
        row["$ref"] for row in schema["$defs"]["derived_inspection_request"]["anyOf"]
    }
    assert refs == {
        "#/$defs/persistent_rerun_check_request",
        "#/$defs/persistent_run_verifier_command_request",
    }


def test_persistent_native_tool_check_namespace_conflict_fails_closed() -> None:
    messages = _persistent_packet_input(["check-a"])
    messages.append({
        "role": "user",
        "content": json.dumps({"verifier_packet": {"authoritative_check_ids": ["check-b"]}}),
    })
    with pytest.raises(AzureProviderOutputError) as excinfo:
        _persistent_verifier_native_tool_for_input(messages)
    assert excinfo.value.code == "provider_persistent_verifier_check_namespace_conflict"


def test_persistent_live_request_uses_packet_bound_rerun_namespace() -> None:
    model, client = _model(_response(_function_call()), verifier_protocol="persistent_v0")
    messages = _persistent_packet_input(["check-a"])
    model(messages)
    schema = client.responses.requests[0]["tools"][0]["parameters"]
    assert schema["$defs"]["persistent_rerun_check_request"]["properties"]["check_id"] == {
        "type": "string", "enum": ["check-a"],
    }
    event = model.drain_telemetry()[0]
    assert event["persistent_authoritative_check_count"] == 1
    assert event["persistent_authoritative_check_ids"] == ["check-a"]


def test_persistent_live_request_with_empty_authority_has_no_derived_provider_turn() -> None:
    model, client = _model(_response(_function_call()), verifier_protocol="persistent_v0")
    model(_persistent_packet_input([]))
    schema = client.responses.requests[0]["tools"][0]["parameters"]
    root_refs = {row["$ref"] for row in schema["properties"]["turn"]["anyOf"]}
    assert root_refs == {"#/$defs/direct_inspect_turn", "#/$defs/verdict_turn"}
    assert "derived_inspection_request" not in schema["$defs"]
    event = model.drain_telemetry()[0]
    assert event["persistent_authoritative_check_count"] == 0
    assert event["persistent_authoritative_check_ids"] == []



def _persistent_runtime_namespace_message(
    authoritative: list[str], bound: list[str],
) -> dict[str, str]:
    result: dict[str, object] = {
        "kind": "read_file",
        "inspection_id": authoritative[-1],
        "error": "",
        "observation_valid": True,
    }
    return {
        "role": "user",
        "content": json.dumps({
            "verifier_inspection_results": [result],
            "available_authoritative_source_refs": ["task:prompt", *authoritative],
            "available_bound_input_refs": ["task:prompt", *bound],
        }),
    }


def test_persistent_native_tool_omits_command_and_derived_turn_before_prior_inspection() -> None:
    tool, _ids = _persistent_verifier_native_tool_for_input(_persistent_packet_input([]))
    schema = tool["parameters"]
    assert "persistent_run_verifier_command_request" not in schema["$defs"]
    assert "derived_inspection_request" not in schema["$defs"]
    assert "#/$defs/derived_inspect_turn" not in {
        row["$ref"] for row in schema["properties"]["turn"]["anyOf"]
    }


def test_persistent_native_tool_binds_command_to_exact_prior_inspection_namespace() -> None:
    source = "inspection:2:0:source"
    messages = _persistent_packet_input([])
    messages.append(_persistent_runtime_namespace_message([source], [source]))
    basis, bound = _persistent_verifier_prior_inspection_namespaces_from_input(messages)
    assert basis == (source,)
    assert bound == (source,)

    tool, _ids = _persistent_verifier_native_tool_for_input(messages)
    schema = tool["parameters"]
    refs = {
        row["$ref"]
        for row in schema["$defs"]["derived_inspection_request"]["anyOf"]
    }
    assert refs == {"#/$defs/persistent_run_verifier_command_request"}
    assert "persistent_rerun_check_request" not in schema["$defs"]
    command_schema = schema["$defs"]["persistent_run_verifier_command_request"]
    assert command_schema["required"] == [
        "kind", "command", "clause_ids", "basis_refs", "bound_input_refs",
    ]
    assert list(command_schema["properties"]) == command_schema["required"]
    assert command_schema["properties"]["basis_refs"]["items"] == {
        "type": "string", "enum": [source],
    }
    assert command_schema["properties"]["bound_input_refs"]["items"] == {
        "type": "string", "enum": [source],
    }

    valid = {
        "kind": "run_verifier_command",
        "command": "python3 target.py",
        "clause_ids": ["task:raw"],
        "basis_refs": [source],
        "bound_input_refs": [source],
    }
    jsonschema.validate({"turn": {"kind": "inspect", "requests": [valid]}}, schema)

    invented = dict(valid)
    invented["bound_input_refs"] = [source, "inspection:invented"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"turn": {"kind": "inspect", "requests": [invented]}}, schema)


def test_persistent_native_tool_fails_closed_when_runtime_namespaces_regress() -> None:
    source = "inspection:2:0:source"
    messages = _persistent_packet_input([])
    messages.append(_persistent_runtime_namespace_message([source], [source]))
    messages.append({
        "role": "user",
        "content": json.dumps({
            "available_authoritative_source_refs": ["task:prompt"],
            "available_bound_input_refs": ["task:prompt"],
        }),
    })
    with pytest.raises(AzureProviderOutputError) as excinfo:
        _persistent_verifier_native_tool_for_input(messages)
    assert excinfo.value.code == "provider_persistent_verifier_inspection_namespace_conflict"


def test_persistent_live_request_uses_prior_inspection_bound_overlay_schema() -> None:
    source = "inspection:2:0:source"
    model, client = _model(_response(_function_call()), verifier_protocol="persistent_v0")
    messages = _persistent_packet_input([])
    messages.append(_persistent_runtime_namespace_message([source], [source]))
    model(messages)
    schema = client.responses.requests[0]["tools"][0]["parameters"]
    assert schema["$defs"]["persistent_run_verifier_command_request"]["properties"]["basis_refs"]["items"] == {
        "type": "string", "enum": [source],
    }
    event = model.drain_telemetry()[0]
    assert event["persistent_prior_authoritative_inspection_count"] == 1
    assert event["persistent_prior_bound_input_count"] == 1
    assert event["persistent_prior_authoritative_inspection_ids"] == [source]
    assert event["persistent_prior_bound_input_ids"] == [source]



def test_persistent_live_request_exposes_compact_command_not_runtime_nested_shape() -> None:
    source = "inspection:2:0:source"
    model, client = _model(_response(_function_call()), verifier_protocol="persistent_v0")
    messages = _persistent_packet_input([])
    messages.append(_persistent_runtime_namespace_message([source], [source]))
    model(messages)
    request = client.responses.requests[0]
    schema = request["tools"][0]["parameters"]
    refs = {row["$ref"] for row in schema["$defs"]["derived_inspection_request"]["anyOf"]}
    assert "#/$defs/persistent_run_verifier_command_request" in refs
    assert "persistent_overlay_run_command_request" not in schema["$defs"]
    assert "persistent_derived_verification_plan" not in schema["$defs"]
    assert "run_verifier_command" in request["instructions"]
    assert "Do not emit runtime-internal verification_plan/execution wrappers" in request["instructions"]


def test_generic_live_request_keeps_native_overlay_run_command_contract() -> None:
    model, client = _model(_response(_function_call()), verifier_protocol="verifier_v1")
    model([{"role": "user", "content": "verify"}])
    request = client.responses.requests[0]
    schema = request["tools"][0]["parameters"]
    assert "run_verifier_command" not in json.dumps(schema)
    derived = schema["$defs"]["derived_inspection_request"]
    assert "overlay_run_command" in derived["properties"]["kind"]["enum"]
    assert "overlay_run_command" in request["instructions"]


def test_persistent_live_request_disambiguates_process_observation_from_fresh_execution() -> None:
    model, client = _model(_response(_function_call()), verifier_protocol="persistent_v0")
    model(_persistent_packet_input([]))
    request = client.responses.requests[0]
    direct = request["tools"][0]["parameters"]["$defs"]["persistent_direct_locator_request"]
    kinds = set(direct["properties"]["kind"]["enum"])
    assert "observe_existing_process" in kinds
    assert "probe_process" not in kinds
    assert "receipt_kind" not in direct["properties"]
    assert "check_id" not in direct["properties"]
    assert "run_verifier_command" in request["instructions"]


def test_persistent_live_request_has_no_standalone_fixture_route() -> None:
    model, client = _model(_response(_function_call()), verifier_protocol="persistent_v0")
    model(_persistent_packet_input([]))
    request = client.responses.requests[0]
    schema = request["tools"][0]["parameters"]
    assert "write_verifier_fixture" not in json.dumps(schema)
    assert "write_verifier_fixture" not in request["instructions"]
    assert "synthetic input" in request["instructions"]
    assert "run_verifier_command" in request["instructions"]

    old_alias = {
        "request_id": "fixture-1",
        "kind": "write_verifier_fixture",
        "path": "fixtures/input.txt",
        "content": "payload",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"turn": {"kind": "inspect", "requests": [old_alias]}}, schema
        )

def test_generic_live_request_keeps_native_overlay_fixture_contract() -> None:
    model, client = _model(_response(_function_call()), verifier_protocol="verifier_v1")
    model([{"role": "user", "content": "verify"}])
    schema = client.responses.requests[0]["tools"][0]["parameters"]
    assert "write_verifier_fixture" not in json.dumps(schema)
    derived = schema["$defs"]["derived_inspection_request"]
    assert "overlay_write_fixture" in derived["properties"]["kind"]["enum"]
