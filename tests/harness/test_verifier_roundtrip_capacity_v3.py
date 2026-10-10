from __future__ import annotations

import json

import pytest

from aether.model_hooks import ModelHooks
from aether.model_prompts import VERIFIER_RUNTIME_CONTRACT
from aether.providers.chat_model import ChatModelOutputError
from aether.providers.azure_model import _persistent_verifier_native_tool_for_input
from aether.persistent_runtime import build_persistent_runtime
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.verifier import parse_model_verifier_result
from aether.verifier_budget import VerifierPhaseBudget, VerifierPhaseState


def _compiled():
    envmap = EnvMap(
        task_prompt="Produce result.txt and verify it.",
        workspace_root="/app",
        visible_files=("a.txt", "b.txt", "c.txt", "result.txt"),
        capabilities={
            "shell": CapabilityDescriptor(capability_id="shell", summary="run commands"),
            "filesystem": CapabilityDescriptor(capability_id="filesystem", summary="read files"),
        },
    )
    resolved = build_persistent_runtime(envmap)
    assert resolved.compiled is not None
    return resolved.compiled


def _inspect(request_id: str, path: str) -> str:
    return json.dumps({
        "kind": "inspect",
        "summary": f"Inspect {path}",
        "requests": [{"request_id": request_id, "kind": "read_file", "path": path}],
    })


def test_inspection_roundtrip_capacity_reserves_a_later_verdict_call() -> None:
    state = VerifierPhaseState(VerifierPhaseBudget(max_model_calls=4))
    assert state.remaining_model_calls == 4
    assert state.has_inspection_roundtrip_capacity is True

    state.reserve_model_call()
    state.reserve_model_call()
    assert state.remaining_model_calls == 2
    assert state.has_inspection_roundtrip_capacity is True

    state.reserve_model_call()
    assert state.remaining_model_calls == 1
    assert state.has_model_call_capacity is True
    assert state.has_inspection_roundtrip_capacity is False

    state.reserve_model_call()
    assert state.remaining_model_calls == 0
    assert state.has_model_call_capacity is False
    assert state.has_inspection_roundtrip_capacity is False


def test_third_inspection_under_four_call_budget_reserves_final_call_for_verdict() -> None:
    responses = [
        _inspect("probe-a", "a.txt"),
        _inspect("probe-b", "b.txt"),
        _inspect("probe-c", "c.txt"),
        json.dumps({
            "verdict": "blocked_by_tooling",
            "confidence": "low",
            "summary": "Synthetic terminal verdict for budget-affordance regression.",
        }),
    ]
    calls: list[list[dict[str, str]]] = []

    def verifier_model(messages, *, max_output_tokens=8000):
        calls.append(list(messages))
        if len(calls) == 2:
            runtime_payload = json.loads(calls[-1][-1]["content"])
            assert runtime_payload["verdict_eligible_execution_refs"] == []
            tool, _ids = _persistent_verifier_native_tool_for_input(calls[-1])
            verdict = tool["parameters"]["$defs"]["verdict_turn"]
            assert verdict["properties"]["method_validity"] == {"type": "null"}
        if len(calls) == 3:
            penultimate_payload = json.loads(calls[-1][-1]["content"])
            assert penultimate_payload["verifier_turn_constraint"] == "inspect_or_verdict"
            tool, _ids = _persistent_verifier_native_tool_for_input(calls[-1])
            root_arms = tool["parameters"]["properties"]["turn"]["anyOf"]
            assert {arm.get("$ref") for arm in root_arms} != {"#/$defs/verdict_turn"}
        if len(calls) == 4:
            final_payload = json.loads(calls[-1][-1]["content"])
            final_instruction = final_payload["instruction"]
            assert "final Verifier verdict JSON object now" in final_instruction
            assert "no inspection request is available on this final model call" in final_instruction
            assert "return either a final verdict or another bounded inspection request" not in final_instruction
            assert final_payload["verifier_turn_constraint"] == "verdict_only"
            tool, _ids = _persistent_verifier_native_tool_for_input(calls[-1])
            assert tool["parameters"]["properties"]["turn"]["anyOf"] == [
                {"$ref": "#/$defs/verdict_turn"},
            ]
        return responses[len(calls) - 1]

    def inspector(requests):
        return [{
            "request_id": req.request_id,
            "inspection_id": f"inspection:test:{req.request_id}",
            "kind": req.kind,
            "path": req.path,
            "excerpt": f"current contents for {req.path}",
            "eligible_for_proof": True,
            "observation_valid": True,
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "exact_contract",
        } for req in requests]

    hooks = ModelHooks(
        solver_model=lambda messages, *, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )
    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()

    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Produce result.txt", "artifacts_present": ["result.txt"]},
        _compiled(),
        ledger=ledger,
        inspector=inspector,
    )
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "blocked_by_tooling"
    assert len(calls) == 4



def test_unexpected_native_tool_call_is_rejected_then_corrected_once(monkeypatch) -> None:
    import aether.verify_completion_protocol as protocol

    monkeypatch.setattr(
        protocol,
        "PRODUCTION_VERIFIER_PHASE_BUDGET",
        VerifierPhaseBudget(max_model_calls=3, max_provider_corrections=1),
    )
    hooks = ModelHooks(
        solver_model=lambda messages, *, max_output_tokens=8000: "{}",
        verifier_model=lambda messages, *, max_output_tokens=8000: "{}",
    )
    calls: list[list[dict[str, str]]] = []
    inspector_calls: list[object] = []

    def call_verifier(messages, *, max_output_tokens=None):
        calls.append(list(messages))
        if len(calls) == 1:
            raise ChatModelOutputError("unexpected_native_tool_call")
        if len(calls) == 2:
            correction = json.loads(calls[-1][-1]["content"])
            assert correction["provider_protocol_error"] == "unexpected_native_tool_call"
            assert correction["rejected_response_executed"] == "false"
            assert "No tool call was executed" in correction["instruction"]
            return _inspect("post-correction-read", "result.txt")
        inspection_payload = json.loads(calls[-1][-1]["content"])
        assert inspection_payload["verifier_inspection_results"][0]["inspection_id"] == (
            "inspection:test:post-correction-read"
        )
        return json.dumps({
            "verdict": "blocked_by_tooling",
            "confidence": "low",
            "summary": "Synthetic terminal verdict after corrected typed inspection.",
        })

    monkeypatch.setattr(hooks, "call_verifier", call_verifier)

    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()

    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Produce result.txt", "artifacts_present": ["result.txt"]},
        _compiled(),
        ledger=ledger,
        inspector=lambda requests: inspector_calls.append(tuple(requests)) or [{
            "request_id": requests[0].request_id,
            "inspection_id": "inspection:test:post-correction-read",
            "kind": requests[0].kind,
            "path": requests[0].path,
            "excerpt": "current result",
            "eligible_for_proof": True,
            "observation_valid": True,
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "exact_contract",
        }],
    )
    assert parse_model_verifier_result(raw).verdict == "blocked_by_tooling"
    assert len(calls) == 3
    assert len(inspector_calls) == 1
    assert inspector_calls[0][0].kind == "read_file"
    assert inspector_calls[0][0].path == "result.txt"


def test_v3_native_correction_path_repairs_path_only_inspection_then_reserves_final_verdict(monkeypatch) -> None:
    import aether.verify_completion_protocol as protocol

    monkeypatch.setattr(
        protocol,
        "PRODUCTION_VERIFIER_PHASE_BUDGET",
        VerifierPhaseBudget(
            max_model_calls=4,
            max_provider_corrections=1,
            max_protocol_corrections=1,
        ),
    )
    hooks = ModelHooks(
        solver_model=lambda messages, *, max_output_tokens=8000: "{}",
        verifier_model=lambda messages, *, max_output_tokens=8000: "{}",
    )
    calls: list[list[dict[str, str]]] = []
    inspector_calls: list[tuple[object, ...]] = []

    def call_verifier(messages, *, max_output_tokens=None):
        calls.append(list(messages))
        payload = json.loads(calls[-1][-1]["content"])
        if len(calls) == 1:
            assert payload["verifier_turn_constraint"] == "inspect_or_verdict"
            raise ChatModelOutputError("unexpected_native_tool_call")
        if len(calls) == 2:
            assert payload["provider_protocol_error"] == "unexpected_native_tool_call"
            assert payload["rejected_response_executed"] == "false"
            assert payload["verifier_turn_constraint"] == "inspect_or_verdict"
            assert '"kind":"read_file"' in payload["instruction"]
            # Exact V3 live failure: outer inspect object was valid-looking but
            # every inner entry omitted the route kind. It must remain inert.
            return json.dumps({
                "kind": "inspect",
                "requests": [{"path": "result.txt"}],
            })
        if len(calls) == 3:
            assert payload["verifier_turn_constraint"] == "inspect_or_verdict"
            assert "explicit route kind" in payload["instruction"]
            assert '"kind":"read_file"' in payload["instruction"]
            return _inspect("typed-after-correction", "result.txt")
        assert len(calls) == 4
        assert payload["verifier_turn_constraint"] == "verdict_only"
        assert "no inspection request is available on this final model call" in payload["instruction"]
        assert "either a final verifier verdict" not in payload["instruction"]
        tool, _ids = _persistent_verifier_native_tool_for_input(calls[-1])
        assert tool["parameters"]["properties"]["turn"]["anyOf"] == [
            {"$ref": "#/$defs/verdict_turn"},
        ]
        return json.dumps({
            "verdict": "blocked_by_tooling",
            "confidence": "low",
            "summary": "Synthetic terminal verdict after typed inspection.",
        })

    monkeypatch.setattr(hooks, "call_verifier", call_verifier)

    def inspector(requests):
        inspector_calls.append(tuple(requests))
        assert len(requests) == 1
        assert requests[0].kind == "read_file"
        assert requests[0].path == "result.txt"
        return [{
            "request_id": requests[0].request_id,
            "inspection_id": "inspection:test:typed-after-correction",
            "kind": "read_file",
            "path": "result.txt",
            "excerpt": "current result",
            "eligible_for_proof": True,
            "observation_valid": True,
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "exact_contract",
        }]

    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()
    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Produce result.txt", "artifacts_present": ["result.txt"]},
        _compiled(),
        ledger=ledger,
        inspector=inspector,
    )
    assert parse_model_verifier_result(raw).verdict == "blocked_by_tooling"
    assert len(calls) == 4
    assert len(inspector_calls) == 1


def test_v4_prose_after_typed_inspection_repairs_final_uncertain_verdict(monkeypatch) -> None:
    import aether.verify_completion_protocol as protocol

    monkeypatch.setattr(
        protocol,
        "PRODUCTION_VERIFIER_PHASE_BUDGET",
        VerifierPhaseBudget(
            max_model_calls=4,
            max_provider_corrections=1,
            max_protocol_corrections=1,
        ),
    )
    hooks = ModelHooks(
        solver_model=lambda messages, *, max_output_tokens=8000: "{}",
        verifier_model=lambda messages, *, max_output_tokens=8000: "{}",
    )
    calls: list[list[dict[str, str]]] = []
    inspector_calls: list[tuple[object, ...]] = []

    def call_verifier(messages, *, max_output_tokens=None):
        calls.append(list(messages))
        payload = json.loads(calls[-1][-1]["content"])
        if len(calls) == 1:
            raise ChatModelOutputError("unexpected_native_tool_call")
        if len(calls) == 2:
            assert payload["verifier_turn_constraint"] == "inspect_or_verdict"
            return _inspect("typed-live-read", "result.txt")
        if len(calls) == 3:
            assert payload["verifier_turn_constraint"] == "inspect_or_verdict"
            assert payload["verifier_inspection_results"][0]["inspection_id"] == (
                "inspection:test:typed-live-read"
            )
            # Exact V4 failure class: model describes a desired next check in prose
            # instead of emitting one protocol JSON turn. This must stay inert.
            return "I need more execution evidence before I can judge completion."
        assert len(calls) == 4
        assert payload["verifier_turn_constraint"] == "verdict_only"
        assert "verifier_protocol_error" in payload
        assert "no JSON object found" in payload["verifier_protocol_error"]
        reqs = payload["verifier_final_verdict_requirements"]
        assert reqs["allowed_verdicts"] == VERIFIER_RUNTIME_CONTRACT["allowed_verdicts"]
        assert reqs["required_fields"] == VERIFIER_RUNTIME_CONTRACT["required_fields"]
        assert reqs["required_fields"]["uncertain_missing_evidence"] == [
            "missing_evidence_requests"
        ]
        assert "no inspection request is available" in payload["instruction"]
        assert "chosen verdict branch" in payload["instruction"]
        return json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "medium",
            "summary": "One direct inspection completed, but execution evidence is still missing.",
            "missing_evidence_requests": ["Run one independent behavioral probe."],
        })

    monkeypatch.setattr(hooks, "call_verifier", call_verifier)

    def inspector(requests):
        inspector_calls.append(tuple(requests))
        assert len(requests) == 1
        assert requests[0].kind == "read_file"
        return [{
            "request_id": requests[0].request_id,
            "inspection_id": "inspection:test:typed-live-read",
            "kind": "read_file",
            "path": "result.txt",
            "excerpt": "current result",
            "eligible_for_proof": True,
            "observation_valid": True,
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "exact_contract",
        }]

    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()
    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Produce result.txt", "artifacts_present": ["result.txt"]},
        _compiled(),
        ledger=ledger,
        inspector=inspector,
    )
    parsed = parse_model_verifier_result(raw)
    assert parsed.verdict == "uncertain_missing_evidence"
    assert parsed.missing_evidence_requests == ("Run one independent behavioral probe.",)
    assert len(calls) == 4
    assert len(inspector_calls) == 1


def test_protocol_correction_final_call_is_provider_verdict_only(monkeypatch) -> None:
    import aether.verify_completion_protocol as protocol

    monkeypatch.setattr(
        protocol,
        "PRODUCTION_VERIFIER_PHASE_BUDGET",
        VerifierPhaseBudget(max_model_calls=2),
    )
    responses = [
        "not-json",
        json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "low",
            "summary": "Terminal verdict after bounded protocol correction.",
            "missing_evidence_requests": ["inspect"],
        }),
    ]
    calls: list[list[dict[str, str]]] = []

    def verifier_model(messages, *, max_output_tokens=8000):
        calls.append(list(messages))
        payload = json.loads(calls[-1][-1]["content"])
        if len(calls) == 2:
            assert payload["verifier_turn_constraint"] == "verdict_only"
            assert "verifier_protocol_error" in payload
            reqs = payload["verifier_final_verdict_requirements"]
            assert reqs["allowed_verdicts"] == VERIFIER_RUNTIME_CONTRACT["allowed_verdicts"]
            assert reqs["required_fields"] == VERIFIER_RUNTIME_CONTRACT["required_fields"]
            assert reqs["required_fields"]["uncertain_missing_evidence"] == [
                "missing_evidence_requests"
            ]
            assert reqs["required_fields"]["needs_repair"] == ["findings"]
            assert "no inspection request is available" in payload["instruction"]
        tool, _ids = _persistent_verifier_native_tool_for_input(calls[-1])
        root_arms = tool["parameters"]["properties"]["turn"]["anyOf"]
        if len(calls) == 2:
            assert root_arms == [{"$ref": "#/$defs/verdict_turn"}]
        else:
            assert {arm.get("$ref") for arm in root_arms} != {"#/$defs/verdict_turn"}
        return responses[len(calls) - 1]

    hooks = ModelHooks(
        solver_model=lambda messages, *, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )
    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()

    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Produce result.txt", "artifacts_present": ["result.txt"]},
        _compiled(),
        ledger=ledger,
        inspector=lambda requests: [],
    )
    assert parse_model_verifier_result(raw).verdict == "uncertain_missing_evidence"
    assert len(calls) == 2



def test_final_uncertain_verdict_contract_does_not_relax_parser(monkeypatch) -> None:
    import aether.verify_completion_protocol as protocol

    monkeypatch.setattr(
        protocol,
        "PRODUCTION_VERIFIER_PHASE_BUDGET",
        VerifierPhaseBudget(max_model_calls=2, max_protocol_corrections=1),
    )
    hooks = ModelHooks(
        solver_model=lambda messages, *, max_output_tokens=8000: "{}",
        verifier_model=lambda messages, *, max_output_tokens=8000: "{}",
    )
    calls: list[list[dict[str, str]]] = []

    def call_verifier(messages, *, max_output_tokens=None):
        calls.append(list(messages))
        payload = json.loads(calls[-1][-1]["content"])
        if len(calls) == 1:
            return "not-json"
        assert payload["verifier_turn_constraint"] == "verdict_only"
        reqs = payload["verifier_final_verdict_requirements"]
        assert reqs["required_fields"]["uncertain_missing_evidence"] == [
            "missing_evidence_requests"
        ]
        assert "verifier_protocol_error" in payload
        return json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "medium",
            "summary": "Still missing decisive evidence.",
        })

    monkeypatch.setattr(hooks, "call_verifier", call_verifier)
    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()

    with pytest.raises(Exception, match="not an inspection request"):
        hooks.verify_with_inspector(
            {"reason": "solver_submit", "task_prompt": "Produce result.txt", "artifacts_present": ["result.txt"]},
            _compiled(),
            ledger=ledger,
            inspector=lambda requests: [],
        )
    assert len(calls) == 2
    assert any(
        "uncertain_missing_evidence requires missing_evidence_requests" in str(error)
        for error in hooks.last_parse_errors
    )


def test_missing_evidence_realization_final_call_is_provider_verdict_only(monkeypatch) -> None:
    import aether.verify_completion_protocol as protocol

    monkeypatch.setattr(
        protocol,
        "PRODUCTION_VERIFIER_PHASE_BUDGET",
        VerifierPhaseBudget(max_model_calls=2),
    )
    responses = [
        json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "low",
            "summary": "Need one current file observation.",
            "missing_evidence_requests": ["Read a.txt"],
            "missing_inspection_requests": [{"kind": "read_file", "path": "a.txt"}],
        }),
        json.dumps({
            "verdict": "uncertain_missing_evidence",
            "confidence": "low",
            "summary": "Observed the file; evidence remains insufficient.",
            "missing_evidence_requests": ["No further bounded evidence available"],
            "missing_inspection_requests": [],
        }),
    ]
    calls: list[list[dict[str, str]]] = []

    def verifier_model(messages, *, max_output_tokens=8000):
        calls.append(list(messages))
        if len(calls) == 2:
            final_payload = json.loads(calls[-1][-1]["content"])
            assert final_payload["verifier_turn_constraint"] == "verdict_only"
            assert final_payload["verifier_inspection_results"][0]["inspection_id"] == "inspection:test:missing-a"
            tool, _ids = _persistent_verifier_native_tool_for_input(calls[-1])
            assert tool["parameters"]["properties"]["turn"]["anyOf"] == [
                {"$ref": "#/$defs/verdict_turn"},
            ]
        return responses[len(calls) - 1]

    def inspector(requests):
        assert len(requests) == 1
        assert requests[0].kind == "read_file"
        return [{
            "request_id": requests[0].request_id,
            "inspection_id": "inspection:test:missing-a",
            "kind": "read_file",
            "path": "a.txt",
            "excerpt": "current contents",
            "eligible_for_proof": True,
            "observation_valid": True,
            "evidence_ceiling": "exact_contract",
            "actual_evidence_class": "exact_contract",
        }]

    hooks = ModelHooks(
        solver_model=lambda messages, *, max_output_tokens=8000: "{}",
        verifier_model=verifier_model,
    )
    ledger = type("Ledger", (), {
        "all_receipts": lambda self: [],
        "task_state_generation": lambda self: 0,
    })()
    raw = hooks.verify_with_inspector(
        {"reason": "solver_submit", "task_prompt": "Produce result.txt", "artifacts_present": ["result.txt"]},
        _compiled(),
        ledger=ledger,
        inspector=inspector,
    )
    assert parse_model_verifier_result(raw).verdict == "uncertain_missing_evidence"
    assert len(calls) == 2
