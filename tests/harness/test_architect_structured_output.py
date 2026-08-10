from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from aether.providers import azure_model
from aether.architect_output_schema import (
    HARNESS_CONFIG_V1_PROVIDER_SCHEMA,
    architect_provider_response_format,
    architect_provider_schema,
)
from aether.providers.azure_model import AzureModelCallable, make_azure_callable
from aether.workbench_config import parse_harness_config_ir


def _canonical_config() -> dict[str, Any]:
    return {
        "schema_version": "harness_config.v1",
        "visible_contract": [{
            "literal": "out.txt",
            "owner": None,
            "requirement": None,
            "meaning": "required output path",
            "contrast": "",
            "contrast_owner": None,
        }],
        "solver_system_prompt": {
            "role": "Task-specific file solver",
            "workflow": ["inspect inputs", "write out.txt", "verify content"],
            "self_verification": ["read out.txt and compare it with the visible task"],
            "memory_use": ["use prior receipts before repeating an action"],
            "stop_conditions": ["submit only after fresh content evidence"],
            "avoid": ["do not treat file existence alone as semantic proof"],
        },
        "verifier_system_prompt": {
            "role": "Read-only current-state verifier",
            "success_criteria": ["out.txt contains the requested content"],
            "required_evidence": ["direct current out.txt content"],
            "false_positive_traps": ["file exists with wrong content"],
            "verdict_guidance": [
                "completed requires direct evidence",
                "needs_repair requires an inspected defect",
                "use an appropriate blocked or uncertain verdict when inspection cannot establish state",
            ],
            "feedback_guidance": ["name the current mismatch and smallest repair"],
        },
        "clause_coverage": [{
            "clause_id": "out-content",
            "solver_handling": "Write and validate the requested content.",
            "verifier_check": "Read out.txt and establish exact requested content.",
        }],
        "verifier_strategy": {
            "clause_checks": [{
                "clause_id": "out-content",
                "inspection_route": "read_file:out.txt",
                "fallback_route": None,
                "falsification_check": "Missing or different content disproves completion.",
                "proof_obligation": "exact_state",
                "required_evidence_class": "exact_contract",
            }],
            "false_positive_traps": ["existence alone is insufficient"],
            "return_all_findings": True,
        },
        "re_derivable_claims": ["the exact out.txt content"],
        "context_policy": {
            "mode": "retrieval_augmented",
            "always_include": ["pending_checks", "command_results"],
            "include_on_failure": ["recent_progress"],
            "model_context_window_tokens": 50000,
            "recipe": {
                "always_include": ["active_completion_findings"],
                "include_recent": [
                    {"selector": "file_reads", "count": 2},
                    {"selector": "command_results", "count": 2},
                ],
                "include_last_failure": 1,
                "preserve_exact": ["pending_checks"],
                "make_queryable_not_inline": ["artifact_history"],
            },
        },
        "memory_policy": {"automatic_repeat_mode": "advisory"},
        "verification_policy": {"visible_smoke_tests": []},
        "model_verifier_policy": {"enabled": True, "runs_on": ["solver_submit"]},
        "helper_script_policy": {"enabled": True, "directory": "/app/.aether_tools"},
        "expected_steps": 6,
    }


def _assert_recursive_strict_schema(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
            properties = node.get("properties")
            assert isinstance(properties, dict)
            assert set(node.get("required", ())) == set(properties)
        for value in node.values():
            _assert_recursive_strict_schema(value)
    elif isinstance(node, list):
        for value in node:
            _assert_recursive_strict_schema(value)


def test_architect_provider_schema_is_recursive_strict_and_isolated() -> None:
    schema = architect_provider_schema()
    _assert_recursive_strict_schema(schema)
    assert schema == HARNESS_CONFIG_V1_PROVIDER_SCHEMA
    schema["properties"]["schema_version"]["enum"].append("poison")
    assert "poison" not in HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"]["schema_version"]["enum"]


def test_architect_provider_format_has_one_named_strict_schema() -> None:
    response_format = architect_provider_response_format()
    assert response_format["format"]["type"] == "json_schema"
    assert response_format["format"]["name"] == "aether_harness_config_v1"
    assert response_format["format"]["strict"] is True
    assert response_format["format"]["schema"] == HARNESS_CONFIG_V1_PROVIDER_SCHEMA


def test_canonical_config_matches_schema_and_strict_parser() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    raw = _canonical_config()
    jsonschema.Draft202012Validator(HARNESS_CONFIG_V1_PROVIDER_SCHEMA).validate(raw)
    parsed = parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)
    assert parsed.clause_coverage[0].clause_id == "out-content"
    assert parsed.visible_contract[0].literal == "out.txt"
    assert parsed.task_understanding == "Task-specific file solver"
    assert parsed.success_definition == "Read out.txt and establish exact requested content."
    assert parsed.evidence_requirements == ("direct current out.txt content",)
    assert parsed.minimum_completion_evidence == ("direct current out.txt content",)
    assert parsed.false_positive_risks == (
        "file exists with wrong content", "existence alone is insufficient"
    )
    assert parsed.local_verification_limits == ()


def test_schema_excludes_migration_only_and_tool_selection_fields() -> None:
    rendered = json.dumps(HARNESS_CONFIG_V1_PROVIDER_SCHEMA, sort_keys=True)
    for forbidden in (
        '"tool_policy"',
        '"selected_capabilities"',
        '"enabled_tools"',
        '"structural_checks"',
        '"solver_callable_checks"',
        '"require_query_before_repeat"',
        '"trust_level"',
    ):
        assert forbidden not in rendered


class _Responses:
    def __init__(self, payload: str) -> None:
        self.requests: list[dict[str, Any]] = []
        self.job = SimpleNamespace(
            id="resp-architect-1",
            status="completed",
            output=[SimpleNamespace(
                id="msg-1",
                type="message",
                role="assistant",
                content=[SimpleNamespace(type="output_text", text=payload)],
            )],
            output_text="ignored",
            usage=None,
            error=None,
            incomplete_details=None,
        )

    def create(self, **kwargs: Any) -> Any:
        self.requests.append(dict(kwargs))
        return self.job

    def retrieve(self, _job_id: str) -> Any:  # pragma: no cover - terminal fake
        raise AssertionError("terminal job should not be retrieved")


class _Client:
    def __init__(self, payload: str) -> None:
        self.responses = _Responses(payload)


def _model(
    *, schema: dict[str, Any] | None = None, role: str = "architect",
    payload: dict[str, Any] | None = None,
) -> AzureModelCallable:
    return AzureModelCallable(
        client=_Client(json.dumps(payload or _canonical_config())),  # type: ignore[arg-type]
        deployment="test",
        effort="medium",
        role=role,
        poll_interval_s=1,
        poll_timeout_s=30,
        max_retries=0,
        transport="responses",
        structured_output_schema=schema,
        structured_output_name="aether_harness_config_v1",
        sleep=lambda _seconds: None,
    )


def test_architect_responses_request_uses_caller_strict_schema() -> None:
    model = _model(schema=architect_provider_schema())
    output = model([
        {"role": "system", "content": "Return the config."},
        {"role": "user", "content": "Configure this task."},
    ], max_output_tokens=24000)
    assert json.loads(output)["schema_version"] == "harness_config.v1"
    request = model._client.responses.requests[0]
    assert request["reasoning"] == {"effort": "medium"}
    assert request["max_output_tokens"] == 24000
    assert request["text"]["format"] == {
        "type": "json_schema",
        "name": "aether_harness_config_v1",
        "strict": True,
        "schema": HARNESS_CONFIG_V1_PROVIDER_SCHEMA,
    }
    event = model.drain_telemetry()[0]
    assert event["structured_output_mode"] == "caller_json_schema"
    assert event["structured_output_name"] == "aether_harness_config_v1"


def test_solver_responses_route_owns_strict_direct_turn_schema() -> None:
    payload = {
        "turn": {
            "kind": "act",
            "summary": "inspect current state",
            "actions": [{
                "action_id": "step-1",
                "kind": "run_command",
                "capability_id": "shell",
                "arguments_json": json.dumps({"command": "pwd"}),
                "intent": "inspect the current directory",
                "expected_observation": "the active path",
                "if_fail_next": "inspect the exact command error",
            }],
            "requested_check_ids": [],
            "claimed_artifacts": [],
            "evidence_gap": "need current workspace state",
        },
    }
    model = _model(
        schema=azure_model._SOLVER_DIRECT_TURN_SCHEMA,
        role="solver",
        payload=payload,
    )
    output = model([{"role": "user", "content": "Choose one current action."}])
    assert json.loads(output)["actions"][0]["arguments"] == {"command": "pwd"}
    request = model._client.responses.requests[0]
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["name"] == "aether_solver_direct_turn"
    assert request["text"]["format"]["strict"] is True
    assert request["text"]["format"]["schema"]["properties"]["turn"]
    assert "exactly one strict provider object" in request["instructions"].lower()
    assert request["input"][0]["role"] == "developer"
    preflight = model.preflight_request(max_output_tokens=8000, logical_role="solver")
    assert preflight["structured_output_mode"] == "solver_direct_turn_json_schema"
    assert preflight["structured_output_name"] == "aether_solver_direct_turn"
    assert preflight["response_cardinality_contract"] == "one_strict_solver_turn_from_responses_output"
    assert preflight["certification"] == "responses_single_solver_direct_turn_json_schema_contract"
    event = model.drain_telemetry()[0]
    assert event["structured_output_mode"] == "solver_direct_turn_json_schema"
    assert event["provider_turn_contract"] == "solver_direct_turn_json_schema"
    assert event["provider_turn_candidate_count"] == 1


def test_preflight_identifies_architect_strict_schema_without_call() -> None:
    model = _model(schema=architect_provider_schema())
    preflight = model.preflight_request(
        max_output_tokens=24000, logical_role="architect"
    )
    assert preflight["provider"] == "azure_openai_responses"
    assert preflight["structured_output_mode"] == "caller_json_schema"
    assert preflight["structured_output_name"] == "aether_harness_config_v1"
    assert preflight["certification"] == "caller_supplied_strict_json_schema_contract"


def test_frozen_verifier_rejects_caller_schema_override() -> None:
    with pytest.raises(ValueError, match="frozen Verifier"):
        _model(schema=architect_provider_schema(), role="verifier")


def test_factory_preserves_architect_schema_and_production_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNIT_ARCHITECT_ENDPOINT", "https://example.test/openai/responses")
    monkeypatch.setenv("UNIT_ARCHITECT_DEPLOYMENT", "architect-test-deployment")
    monkeypatch.setenv("UNIT_ARCHITECT_KEY", "sk-fake")
    model = make_azure_callable(
        deployment_env="UNIT_ARCHITECT_DEPLOYMENT",
        key_env="UNIT_ARCHITECT_KEY",
        endpoint_env="UNIT_ARCHITECT_ENDPOINT",
        effort="medium",
        role="architect",
        structured_output_schema=architect_provider_schema(),
        structured_output_name="aether_harness_config_v1",
    )
    assert model._transport == "responses"
    assert model._structured_output_schema == HARNESS_CONFIG_V1_PROVIDER_SCHEMA
    assert model._structured_output_name == "aether_harness_config_v1"
    preflight = model.preflight_request(
        max_output_tokens=24000, logical_role="architect"
    )
    assert preflight["effort"] == "medium"
    assert preflight["max_output_tokens"] == 24000
    assert preflight["structured_output_mode"] == "caller_json_schema"


def test_factory_refuses_schema_override_for_frozen_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNIT_VERIFIER_ENDPOINT", "https://example.test/openai/responses")
    monkeypatch.setenv("UNIT_VERIFIER_DEPLOYMENT", "verifier-test-deployment")
    monkeypatch.setenv("UNIT_VERIFIER_KEY", "sk-fake")
    with pytest.raises(Exception, match="frozen Verifier"):
        make_azure_callable(
            deployment_env="UNIT_VERIFIER_DEPLOYMENT",
            key_env="UNIT_VERIFIER_KEY",
            endpoint_env="UNIT_VERIFIER_ENDPOINT",
            role="verifier",
            structured_output_schema=architect_provider_schema(),
        )


def test_solver_responses_rejects_caller_schema_override() -> None:
    with pytest.raises(ValueError, match="Solver Responses route owns"):
        _model(schema=architect_provider_schema(), role="solver")



def _solver_payload(command: str, *, summary: str) -> dict[str, Any]:
    return {
        "turn": {
            "kind": "act",
            "summary": summary,
            "actions": [{
                "action_id": summary,
                "kind": "run_command",
                "capability_id": "shell",
                "arguments_json": json.dumps({"command": command}),
                "intent": summary,
                "expected_observation": "command result",
                "if_fail_next": "inspect the exact failure",
            }],
            "requested_check_ids": [],
            "claimed_artifacts": [],
            "evidence_gap": "need the command result",
        },
    }


def test_solver_responses_collapses_equivalent_duplicate_envelopes() -> None:
    payload = json.dumps(_solver_payload("pwd", summary="inspect"))
    model = AzureModelCallable(
        client=_Client(payload + "\n" + payload),  # type: ignore[arg-type]
        deployment="test", effort="low", role="solver",
        poll_interval_s=1, poll_timeout_s=30, max_retries=0,
        transport="responses",
        structured_output_schema=azure_model._SOLVER_DIRECT_TURN_SCHEMA,
        structured_output_name="aether_solver_direct_turn",
        sleep=lambda _seconds: None,
    )
    output = model([{"role": "user", "content": "Choose one current action."}])
    assert json.loads(output)["actions"][0]["arguments"] == {"command": "pwd"}
    event = model.drain_telemetry()[0]
    assert event["provider_turn_candidate_count"] == 2
    assert event["provider_turn_duplicate_equivalent"] is True


def test_solver_responses_rejects_distinct_envelopes_before_role_parser() -> None:
    first = json.dumps(_solver_payload("pwd", summary="inspect"))
    second = json.dumps(_solver_payload("ls", summary="different"))
    model = AzureModelCallable(
        client=_Client(first + "\n" + second),  # type: ignore[arg-type]
        deployment="test", effort="low", role="solver",
        poll_interval_s=1, poll_timeout_s=30, max_retries=0,
        transport="responses",
        structured_output_schema=azure_model._SOLVER_DIRECT_TURN_SCHEMA,
        structured_output_name="aether_solver_direct_turn",
        sleep=lambda _seconds: None,
    )
    with pytest.raises(Exception, match="multiple_distinct_semantic_payloads"):
        model([{"role": "user", "content": "Choose one current action."}])
    event = model.drain_telemetry()[0]
    assert event["status"] == "failed"
    assert event["provider_output_error"] == "provider_solver_direct_turn_multiple_distinct_semantic_payloads"



def test_factory_binds_solver_responses_strict_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNIT_SOLVER_ENDPOINT", "https://example.test/openai/responses")
    monkeypatch.setenv("UNIT_SOLVER_DEPLOYMENT", "solver-test-deployment")
    monkeypatch.setenv("UNIT_SOLVER_KEY", "sk-fake")
    model = make_azure_callable(
        deployment_env="UNIT_SOLVER_DEPLOYMENT",
        key_env="UNIT_SOLVER_KEY",
        endpoint_env="UNIT_SOLVER_ENDPOINT",
        effort="low",
        role="solver",
        transport="responses",
    )
    assert model._structured_output_schema == azure_model._SOLVER_DIRECT_TURN_SCHEMA
    assert model._structured_output_name == "aether_solver_direct_turn"
    preflight = model.preflight_request(max_output_tokens=16000, logical_role="solver")
    assert preflight["structured_output_mode"] == "solver_direct_turn_json_schema"
    assert preflight["certification"] == "responses_single_solver_direct_turn_json_schema_contract"
