"""No-network tests for the strict single-envelope Chat Completions route."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.providers import azure_model
from aether.providers.azure_model import (
    AzureModelCallable,
    AzureProviderOutputError,
    make_azure_callable,
    unwrap_solver_chat_turn,
    unwrap_solver_direct_turn,
    unwrap_verifier_direct_turn,
    unwrap_verifier_provider_envelope,
)


def _response(payload: object, *, finish_reason: str = "stop", refusal: str | None = None):
    message = SimpleNamespace(role="assistant", content=payload, refusal=refusal)
    choice = SimpleNamespace(index=0, message=message, finish_reason=finish_reason)
    return SimpleNamespace(
        id="chatcmpl-test",
        choices=[choice],
        usage=SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=55,
            total_tokens=175,
        ),
    )


class _Completions:
    def __init__(self, response):
        self.response = response
        self.requests: list[dict] = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


class _Client:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_Completions(response))


def _model(response) -> tuple[AzureModelCallable, _Client]:
    client = _Client(response)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-5.4-mini",
        effort="medium",
        role="verifier",
        transport="chat_completions",
        poll_interval_s=1,
        poll_timeout_s=30,
        max_retries=0,
        sleep=lambda _seconds: None,
    )
    return model, client


def _solver_chat_model(response) -> tuple[AzureModelCallable, _Client]:
    client = _Client(response)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-5.4-mini",
        effort="low",
        role="solver",
        transport="chat_completions",
        poll_interval_s=1,
        poll_timeout_s=30,
        max_retries=0,
        sleep=lambda _seconds: None,
    )
    return model, client


def _envelope(payload: dict) -> str:
    return json.dumps({"payload_json": json.dumps(payload)})


def _turn(payload: dict) -> str:
    return json.dumps({"turn": payload})


def _envelope_sequence(*payloads: dict, inner_whitespace: bool = False) -> str:
    rendered: list[str] = []
    for index, payload in enumerate(payloads):
        inner = json.dumps(
            payload,
            indent=2 if inner_whitespace and index else None,
            sort_keys=inner_whitespace and index > 0,
        )
        rendered.append(json.dumps({"payload_json": inner}))
    return "\n".join(rendered)


def test_chat_route_requests_one_choice_and_returns_one_direct_turn() -> None:
    model, client = _model(_response(_turn({
        "verdict": "uncertain_missing_evidence",
        "confidence": "low",
        "summary": "need evidence",
        "findings": [],
        "missing_evidence_requests": ["read source"],
        "completion_evidence": [],
        "method_validity": None,
    })))

    result = model([{"role": "user", "content": "Review the state."}], max_output_tokens=6000)

    assert json.loads(result)["verdict"] == "uncertain_missing_evidence"
    request = client.chat.completions.requests[0]
    assert request["n"] == 1
    assert request["max_completion_tokens"] == 6000
    assert request["reasoning_effort"] == "medium"
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert "turn" in request["response_format"]["json_schema"]["schema"]["properties"]
    assert "payload_json" not in json.dumps(request["response_format"], sort_keys=True)
    assert '"type": ["' not in json.dumps(request["response_format"], sort_keys=True)
    assert request["messages"][0]["role"] == "developer"
    assert "exactly one" in request["messages"][0]["content"].lower()


def test_solver_chat_route_requests_one_choice_and_one_strict_direct_turn() -> None:
    model, client = _solver_chat_model(_response(_turn({
        "kind": "act",
        "summary": "inspect source",
        "actions": [{
            "action_id": "inspect-1",
            "kind": "read_file",
            "capability_id": "filesystem",
            "arguments_json": json.dumps({"path": "README.md"}),
            "intent": "inspect source",
            "expected_observation": "file contents",
            "if_fail_next": "inspect workspace",
        }],
        "requested_check_ids": [],
        "claimed_artifacts": [],
        "evidence_gap": "",
    })))

    result = model([{"role": "user", "content": "Choose the next solver turn."}], max_output_tokens=6000)

    parsed = json.loads(result)
    assert parsed["kind"] == "act"
    assert parsed["actions"][0]["arguments"] == {"path": "README.md"}
    assert "arguments_json" not in parsed["actions"][0]
    request = client.chat.completions.requests[0]
    assert request["n"] == 1
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    schema = request["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert "turn" in schema["properties"]
    contract = request["messages"][0]["content"].lower()
    assert "sole key turn" in contract
    assert "exactly one action" in contract
    assert "arguments_json" in contract
    assert "never emit act and submit_outcome together" in contract
    event = model.drain_telemetry()[0]
    assert event["structured_output_mode"] == "solver_direct_turn_json_schema"
    assert event["provider_turn_contract"] == "solver_direct_turn_json_schema"


def test_solver_direct_turn_decodes_dynamic_arguments_before_role_parser() -> None:
    raw, receipt = unwrap_solver_direct_turn(_turn({
        "kind": "act",
        "summary": "run repair",
        "actions": [{
            "action_id": "repair-1",
            "kind": "run_command",
            "capability_id": "shell",
            "arguments_json": json.dumps({"command": "printf ok", "timeout_s": 30}),
            "intent": "repair",
            "expected_observation": "ok",
            "if_fail_next": "inspect stderr",
        }],
        "requested_check_ids": [],
        "claimed_artifacts": [],
        "evidence_gap": "",
    }))
    decoded = json.loads(raw)
    assert decoded["actions"][0]["arguments"] == {"command": "printf ok", "timeout_s": 30}
    assert receipt["provider_turn_contract"] == "solver_direct_turn_json_schema"
    assert receipt["provider_turn_arguments_transport"] == "json_string_decoded_before_role_parser"


def test_solver_direct_turn_rejects_multiple_or_malformed_argument_objects() -> None:
    payload = {
        "kind": "act", "summary": "repair",
        "actions": [{
            "action_id": "repair-1", "kind": "run_command", "capability_id": "shell",
            "arguments_json": '{"command":"one"} {"command":"two"}',
            "intent": "repair", "expected_observation": "ok", "if_fail_next": "inspect",
        }],
        "requested_check_ids": [], "claimed_artifacts": [], "evidence_gap": "",
    }
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_solver_direct_turn(_turn(payload))
    assert excinfo.value.code == "provider_solver_direct_turn_arguments_invalid"


def test_solver_direct_schema_has_one_turn_and_one_act_action() -> None:
    import jsonschema
    schema = azure_model._SOLVER_DIRECT_TURN_SCHEMA
    valid = {
        "turn": {
            "kind": "act", "summary": "inspect",
            "actions": [{
                "action_id": "a1", "kind": "read_file", "capability_id": "filesystem",
                "arguments_json": json.dumps({"path": "README.md"}),
                "intent": "inspect", "expected_observation": "contents", "if_fail_next": "list files",
            }],
            "requested_check_ids": [], "claimed_artifacts": [], "evidence_gap": "",
        }
    }
    jsonschema.validate(valid, schema)
    invalid = json.loads(json.dumps(valid))
    invalid["turn"]["actions"].append(dict(invalid["turn"]["actions"][0]))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"turn": valid["turn"], "alternative": {"kind": "submit_outcome"}}, schema)


def test_equivalent_solver_turn_sequence_collapses_without_selecting_a_prefix() -> None:
    first = json.dumps({
        "kind": "act", "summary": "inspect",
        "actions": [{"kind": "read_file", "arguments": {"path": "/app/a"}}],
    })
    second = json.dumps({
        "actions": [{"arguments": {"path": "/app/a"}, "kind": "read_file"}],
        "summary": "inspect", "kind": "act",
    }, indent=2)

    raw, receipt = unwrap_solver_chat_turn(first + "\n" + second)

    assert json.loads(raw)["kind"] == "act"
    assert receipt["provider_turn_candidate_count"] == 2
    assert receipt["provider_turn_duplicate_equivalent"] is True
    assert len(set(receipt["provider_turn_raw_candidate_hashes"])) == 2
    assert len(set(receipt["provider_turn_semantic_candidate_hashes"])) == 1


def test_solver_chat_callable_collapses_equivalent_strict_envelopes() -> None:
    turn = {
        "kind": "submit_outcome",
        "summary": "done",
        "requested_check_ids": [],
        "claimed_artifacts": [],
        "evidence_gap": "",
    }
    payload = _turn(turn)
    model, _client = _solver_chat_model(_response(payload + "\n" + payload))

    assert json.loads(model([{"role": "user", "content": "Submit."}])) == turn
    event = model.drain_telemetry()[0]
    assert event["status"] == "completed"
    assert event["structured_output_mode"] == "solver_direct_turn_json_schema"
    assert event["provider_turn_candidate_count"] == 2
    assert event["provider_turn_duplicate_output"] is True
    assert event["provider_turn_duplicate_equivalent"] is True
    assert len(set(event["provider_turn_raw_candidate_hashes"])) == 1
    assert len(set(event["provider_turn_semantic_candidate_hashes"])) == 1


def test_solver_direct_turn_rejects_distinct_strict_envelopes() -> None:
    first = _turn({
        "kind": "submit_outcome",
        "summary": "done",
        "requested_check_ids": [],
        "claimed_artifacts": [],
        "evidence_gap": "",
    })
    second = _turn({
        "kind": "submit_outcome",
        "summary": "not done",
        "requested_check_ids": [],
        "claimed_artifacts": [],
        "evidence_gap": "missing proof",
    })
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_solver_direct_turn(first + "\n" + second)
    assert excinfo.value.code == "provider_solver_direct_turn_multiple_distinct_semantic_payloads"


def test_distinct_solver_turn_sequence_fails_closed() -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_solver_chat_turn(
            json.dumps({"kind": "act", "summary": "read", "actions": []})
            + "\n"
            + json.dumps({"kind": "submit_outcome", "summary": "done"})
        )
    assert excinfo.value.code == "provider_solver_turn_multiple_distinct_semantic_payloads"


@pytest.mark.parametrize(("text", "expected_code"), [
    ('{"kind":"act"} trailing', "provider_structured_output_invalid_json"),
    ('{"kind":"act","kind":"submit_outcome"}', "provider_solver_turn_duplicate_key"),
    ('{"kind":NaN}', "provider_structured_output_nonstandard_json_constant"),
    ('[1,2]', "provider_solver_turn_not_object"),
])
def test_malformed_solver_turn_sequence_fails_closed(text: str, expected_code: str) -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_solver_chat_turn(text)
    assert excinfo.value.code == expected_code


def test_direct_turn_rejects_inspect_and_verdict_together() -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_verifier_direct_turn(_turn({
            "kind": "inspect",
            "requests": [],
            "verdict": "uncertain_missing_evidence",
        }))
    assert excinfo.value.code == "provider_direct_turn_ambiguous_payload"


def test_equivalent_direct_turn_duplicates_collapse() -> None:
    payload = {"kind": "inspect", "requests": []}
    raw, receipt = unwrap_verifier_direct_turn(_turn(payload) + "\n" + _turn(payload))

    assert json.loads(raw) == payload
    assert receipt["provider_turn_candidate_count"] == 2
    assert receipt["provider_turn_duplicate_equivalent"] is True


def test_distinct_direct_turn_duplicates_fail_closed() -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_verifier_direct_turn(
            _turn({"kind": "inspect", "requests": []})
            + "\n"
            + _turn({
                "verdict": "uncertain_missing_evidence", "confidence": "low",
                "summary": "need evidence", "findings": [],
                "missing_evidence_requests": ["read source"],
                "completion_evidence": [], "method_validity": None,
            })
        )
    assert excinfo.value.code == "provider_direct_turn_multiple_distinct_semantic_payloads"


def test_direct_turn_preserves_code_bearing_command_without_double_encoding() -> None:
    raw, _receipt = unwrap_verifier_direct_turn(_turn({
        "kind": "inspect",
        "requests": [{
            "request_id": "derive", "kind": "overlay_run_command", "path": None,
            "handle": None, "check_id": None, "receipt_kind": None, "limit": None,
            "command": None, "content": None, "target": None, "offset": None, "span": None,
            "execution": {"kind": "overlay_run_command", "command": "python3 -c 'import re; re.compile(r\\\"\\\\[x\\\\]\\\")'"},
            "verification_plan": {
                "claim": "derive", "evidence_mode": "derived",
                "basis": [{"ref": "inspection:1", "supported_fact": "source"}],
                "bound_input_refs": ["inspection:1"], "authoritative_structure": "grammar",
                "method_summary": "parse", "proxy_risk": "label",
            },
        }],
    }))
    assert "re.compile" in json.loads(raw)["requests"][0]["execution"]["command"]


def test_direct_schema_does_not_force_legacy_v3_plan_fields() -> None:
    plan = azure_model._VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["verification_plan"]
    assert "authoritative_source_refs" not in plan["required"]
    assert "authoritative_source_refs" not in plan["properties"]


def test_equivalent_concatenated_provider_envelopes_collapse() -> None:
    payload = {
        "kind": "inspect",
        "requests": [{"kind": "read_file", "path": "/app/summary.csv"}],
    }
    text, receipt = unwrap_verifier_provider_envelope(
        _envelope_sequence(payload, payload, inner_whitespace=True)
    )

    assert json.loads(text) == payload
    assert receipt["provider_envelope_candidate_count"] == 2
    assert receipt["provider_envelope_duplicate_equivalent"] is True
    assert len(set(receipt["provider_envelope_raw_candidate_hashes"])) == 2
    assert len(set(receipt["provider_envelope_semantic_candidate_hashes"])) == 1


def test_distinct_concatenated_provider_envelopes_fail_closed() -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_verifier_provider_envelope(_envelope_sequence(
            {"kind": "inspect", "requests": []},
            {"verdict": "completed", "summary": "done"},
        ))

    assert excinfo.value.code == "provider_envelope_multiple_distinct_semantic_payloads"


def test_distinct_inner_payloads_fail_closed() -> None:
    outer = json.dumps({
        "payload_json": "\n".join([
            json.dumps({"kind": "inspect", "requests": []}),
            json.dumps({"verdict": "completed", "summary": "done"}),
        ])
    })

    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_verifier_provider_envelope(outer)

    assert excinfo.value.code == "provider_envelope_multiple_distinct_inner_payloads"


@pytest.mark.parametrize("text, expected_code", [
    (json.dumps({"payload_json": '{"a":1,"a":1}'}), "provider_envelope_duplicate_key"),
    (json.dumps({"payload_json": '{"a":NaN}'}), "provider_envelope_nonstandard_json_constant"),
    (json.dumps({"payload_json": '{"kind":"inspect"} trailing'}), "provider_envelope_invalid_json"),
])
def test_nonstandard_or_incomplete_nested_json_fails_closed(text: str, expected_code: str) -> None:
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_verifier_provider_envelope(text)

    assert excinfo.value.code == expected_code


@pytest.mark.parametrize("choices, expected_code", [
    ([], "provider_chat_completion_choice_count_invalid"),
    ([
        SimpleNamespace(message=SimpleNamespace(role="assistant", content="{}"), finish_reason="stop"),
        SimpleNamespace(message=SimpleNamespace(role="assistant", content="{}"), finish_reason="stop"),
    ], "provider_chat_completion_choice_count_invalid"),
])
def test_zero_or_multiple_choices_fail_closed(choices, expected_code: str) -> None:
    model, _client = _model(SimpleNamespace(id="chatcmpl-test", choices=choices, usage=None))

    with pytest.raises(AzureProviderOutputError) as excinfo:
        model([{"role": "user", "content": "Review."}])

    assert excinfo.value.code == expected_code


@pytest.mark.parametrize(("response", "expected_code"), [
    (_response(_turn({"kind": "inspect", "requests": []}), refusal="safety"), "provider_refusal"),
    (_response(_turn({"kind": "inspect", "requests": []}), finish_reason="length"), "provider_output_incomplete"),
    (_response("not json"), "provider_structured_output_invalid_json"),
    (_response('{"turn": NaN}'), "provider_structured_output_nonstandard_json_constant"),
    (_response(_turn({"kind": "other"})), "provider_direct_turn_ambiguous_payload"),
])
def test_refusal_truncation_malformed_and_schema_invalid_fail_closed(response, expected_code: str) -> None:
    model, _client = _model(response)

    with pytest.raises(AzureProviderOutputError) as excinfo:
        model([{"role": "user", "content": "Review."}])

    assert excinfo.value.code == expected_code


def test_chat_route_preserves_usage_and_raw_provider_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT", "1")
    model, _client = _model(_response(_turn({
        "verdict": "uncertain_missing_evidence",
        "confidence": "low", "summary": "need evidence", "findings": [],
        "missing_evidence_requests": ["read source"], "completion_evidence": [], "method_validity": None,
    })))

    model([{"role": "user", "content": "Review."}])
    event = model.drain_telemetry()[0]

    assert event["provider"] == "azure_openai_chat_completions"
    assert event["choice_count_requested"] == 1
    assert event["choice_count"] == 1
    assert event["candidate_message_count"] == 1
    assert event["input_tokens"] == 120
    assert event["output_tokens"] == 55
    assert event["total_tokens"] == 175
    assert event["raw_provider_response"]["id"] == "chatcmpl-test"


def test_factory_uses_responses_route_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    class _OpenAI:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(azure_model, "openai", SimpleNamespace(OpenAI=_OpenAI))
    monkeypatch.setenv("UNIT_ENDPOINT", "https://example.test")
    monkeypatch.setenv("UNIT_DEPLOYMENT", "gpt-5.4-mini")
    monkeypatch.setenv("UNIT_KEY", "secret-for-test")

    verifier = make_azure_callable(
        deployment_env="UNIT_DEPLOYMENT",
        key_env="UNIT_KEY",
        endpoint_env="UNIT_ENDPOINT",
        role="verifier",
    )
    solver = make_azure_callable(
        deployment_env="UNIT_DEPLOYMENT",
        key_env="UNIT_KEY",
        endpoint_env="UNIT_ENDPOINT",
        role="solver",
    )

    assert verifier._transport == "chat_completions"
    assert solver._transport == "responses"


def _completed_turn_with_evidence_class(evidence_class: object) -> dict:
    return {
        "turn": {
            "verdict": "completed",
            "confidence": "high",
            "summary": "verified",
            "findings": [],
            "missing_evidence_requests": [],
            "completion_evidence": [{
                "requirement": "current table is correct",
                "observed": "independent recount matched every cell",
                "falsification_check": "any mismatch would falsify completion",
                "inspection_refs": ["inspection:table", "inspection:recount"],
                "clause_ids": ["clause-summary"],
                "proof_ids": [],
                "evidence_class": evidence_class,
                "risk_refs": ["same-method agreement could mislead"],
            }],
            "method_validity": None,
        },
    }


def test_verifier_schema_requires_canonical_completion_evidence_class() -> None:
    import jsonschema

    schema = azure_model._VERIFIER_DIRECT_TURN_SCHEMA
    allowed = tuple(azure_model._VERIFIER_EVIDENCE_CLASS_VALUES)
    field = schema["$defs"]["completion_evidence"]["properties"]["evidence_class"]

    assert field == {"type": "string", "enum": list(allowed)}
    assert allowed == tuple(item.value for item in azure_model.EvidenceClass)
    jsonschema.validate(_completed_turn_with_evidence_class("exact_contract"), schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            _completed_turn_with_evidence_class("direct read of the complete table"),
            schema,
        )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_completed_turn_with_evidence_class(None), schema)


def test_verifier_runtime_prompt_exposes_completion_evidence_semantic_fields() -> None:
    from aether.model_prompts import VERIFIER_RUNTIME_CONTRACT

    shape = VERIFIER_RUNTIME_CONTRACT["completion_evidence_shape"]
    assert "clause_ids" in shape
    assert "evidence_class" in shape
    for value in azure_model._VERIFIER_EVIDENCE_CLASS_VALUES:
        assert value in shape["evidence_class"]


def _strict_object_schema_findings(schema: object, path: str = "#") -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    if isinstance(schema, dict):
        if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
            properties = set(schema["properties"])
            required = set(schema.get("required") or ())
            findings.append({
                "path": path,
                "missing_from_required": sorted(properties - required),
                "unknown_required": sorted(required - properties),
                "additional_properties": schema.get("additionalProperties"),
            })
        for key, value in schema.items():
            findings.extend(_strict_object_schema_findings(value, f"{path}/{key}"))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            findings.extend(_strict_object_schema_findings(value, f"{path}/{index}"))
    return findings


def test_all_solver_and_verifier_strict_objects_require_every_property() -> None:
    for schema in (
        azure_model._SOLVER_DIRECT_TURN_SCHEMA,
        azure_model._VERIFIER_DIRECT_TURN_SCHEMA,
    ):
        findings = _strict_object_schema_findings(schema)
        assert findings
        assert all(row["additional_properties"] is False for row in findings)
        assert all(row["missing_from_required"] == [] for row in findings)
        assert all(row["unknown_required"] == [] for row in findings)


def test_verifier_completion_evidence_requires_proof_ids_array() -> None:
    schema = azure_model._VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["completion_evidence"]
    assert "proof_ids" in schema["required"]
    assert schema["properties"]["proof_ids"] == {
        "type": "array",
        "items": {"type": "string"},
    }
