from __future__ import annotations

import json

import pytest
import aether.judge_verifier_policy as judge_policy
from aether.judge_verifier_policy import (
    JudgeQuestionAdapter,
    TypedJudgeVerifierCallable,
    _requirements,
    build_inspection_candidates,
)
from aether.verifier import parse_model_verifier_result
from aether.verifier_inspector import parse_verifier_inspection_requests


def _answer(choice: str, **probabilities: float) -> dict:
    return {
        "choice": choice,
        "probabilities": probabilities or {choice: 1.0},
    }


def _messages(packet: dict, *, results: list[dict] | None = None) -> list[dict[str, str]]:
    rows = [
        {"role": "system", "content": "verifier"},
        {
            "role": "user",
            "content": json.dumps({
                "authoritative_task_prompt": packet["raw_user_task"],
                "verifier_packet": packet,
            }),
        },
    ]
    if results is not None:
        rows += [
            {"role": "assistant", "content": json.dumps({"kind": "inspect", "requests": []})},
            {
                "role": "user",
                "content": json.dumps({
                    "verifier_turn_constraint": "verdict_only",
                    "verifier_inspection_results": results,
                }),
            },
        ]
    return rows


def _persistent_packet(raw_task: str) -> dict:
    return {
        "raw_user_task": raw_task,
        "task_contract": {
            "schema_version": "persistent_v11_raw",
            "clauses": [{
                "clause_id": "raw_task",
                "text": raw_task,
                "exact_atoms": [],
            }],
        },
        "verifier_runtime_capabilities": {
            "available_direct_observation_kinds": [
                "read_file",
                "read_output",
                "probe_port",
                "probe_http",
                "inspect_action_receipts",
            ],
        },
        "state_inspection_handles": [],
        "authoritative_check_ids": [],
        "primary_submission": {"cited_evidence_index": []},
        "dynamic_state": {},
    }


def test_persistent_raw_task_is_mechanically_factored_without_inventing_authority() -> None:
    raw = (
        "Build the service.\n"
        "- Create /app/server.py.\n"
        "- Listen on port 5328.\n"
        "- Keep it running in the background.\n"
    )
    requirements = _requirements(_persistent_packet(raw), raw)
    assert len(requirements) >= 3
    assert all(tuple(item.clause_ids) == ("raw_task",) for item in requirements)
    joined = "\n".join(item.text for item in requirements)
    assert "Create /app/server.py." in joined
    assert "Listen on port 5328." in joined
    assert "Keep it running in the background." in joined


def test_candidate_builder_discovers_public_probe_targets_from_raw_task_only() -> None:
    raw = (
        "Run the service on port 5328 and expose http://127.0.0.1:5328/health. "
        "Do not use /grader/secret.txt."
    )
    packet = _persistent_packet(raw)
    packet["state_inspection_handles"] = [
        {"kind": "file", "path": "server.py"},
    ]
    candidates = build_inspection_candidates(
        packet,
        [],
        raw_task=raw,
        requirements=_requirements(packet, raw),
        limit=20,
    )
    requests = [dict(item.request) for item in candidates]
    assert any(
        row.get("kind") == "read_file" and row.get("path") == "server.py"
        for row in requests
    )
    assert any(
        row.get("kind") == "probe_port" and str(row.get("target")) == "5328"
        for row in requests
    )
    assert any(
        row.get("kind") == "probe_http"
        and row.get("target") == "http://127.0.0.1:5328/health"
        for row in requests
    )
    assert "/grader/secret.txt" not in json.dumps(requests)


def test_low_confidence_semantic_support_cannot_complete() -> None:
    raw = "Create result.txt containing hello."
    packet = _persistent_packet(raw)
    result = {
        "inspection_id": "inspection:test:1",
        "kind": "read_file",
        "path": "result.txt",
        "excerpt": "hello",
        "observation_valid": True,
        "eligible_for_proof": True,
        "actual_evidence_class": "exact_contract",
        "error": "",
    }

    def evaluator(state, questions):
        del state
        answers = {}
        for key, question in questions.items():
            if key == "next_move":
                answers[key] = _answer("verdict_now", verdict_now=0.99)
            elif key.startswith("relation_"):
                answers[key] = _answer(
                    "supports",
                    supports=0.55,
                    contradicts=0.02,
                    irrelevant=0.03,
                    uncertain=0.40,
                )
            elif key.startswith("evidence_"):
                choices = list(question["criteria"])
                selected = next(item for item in choices if item != "none")
                answers[key] = _answer(selected, **{selected: 0.95, "none": 0.05})
            elif key == "verification_dependence" or key.startswith("dependence_"):
                answers[key] = _answer(
                    "independent",
                    independent=0.95,
                    correlated=0.02,
                    insufficient=0.02,
                    not_required=0.01,
                )
            elif key == "semantic_determinant" or key.startswith("determinant_"):
                answers[key] = _answer("yes", yes=0.96, no=0.02, uncertain=0.02)
            elif key == "noncompletion_verdict":
                answers[key] = _answer(
                    "uncertain_missing_evidence",
                    uncertain_missing_evidence=0.96,
                )
        return answers

    verifier = TypedJudgeVerifierCallable(evaluator, min_semantic_confidence=0.80)
    parsed = parse_model_verifier_result(verifier(_messages(packet, results=[result])))
    assert parsed.verdict != "completed"


def test_high_confidence_supported_requirement_emits_parser_valid_completion() -> None:
    raw = "Create result.txt containing hello."
    packet = _persistent_packet(raw)
    result = {
        "inspection_id": "inspection:test:1",
        "kind": "read_file",
        "path": "result.txt",
        "excerpt": "hello",
        "observation_valid": True,
        "eligible_for_proof": True,
        "actual_evidence_class": "exact_contract",
        "error": "",
    }

    def evaluator(state, questions):
        del state
        answers = {}
        for key, question in questions.items():
            if key == "next_move":
                answers[key] = _answer("verdict_now", verdict_now=0.99)
            elif key.startswith("relation_"):
                answers[key] = _answer(
                    "supports",
                    supports=0.96,
                    contradicts=0.01,
                    irrelevant=0.01,
                    uncertain=0.02,
                )
            elif key.startswith("evidence_"):
                choices = list(question["criteria"])
                selected = next(item for item in choices if item != "none")
                answers[key] = _answer(selected, **{selected: 0.97, "none": 0.03})
            elif key == "verification_dependence" or key.startswith("dependence_"):
                answers[key] = _answer(
                    "independent",
                    independent=0.96,
                    correlated=0.01,
                    insufficient=0.02,
                    not_required=0.01,
                )
            elif key == "semantic_determinant" or key.startswith("determinant_"):
                answers[key] = _answer("yes", yes=0.97, no=0.01, uncertain=0.02)
            elif key == "noncompletion_verdict":
                answers[key] = _answer("uncertain_missing_evidence", uncertain_missing_evidence=1.0)
        return answers

    verifier = TypedJudgeVerifierCallable(evaluator, min_semantic_confidence=0.80)
    parsed = parse_model_verifier_result(verifier(_messages(packet, results=[result])))
    assert parsed.verdict == "completed"
    assert parsed.completion_evidence
    assert all(entry.clause_ids == ("raw_task",) for entry in parsed.completion_evidence)
    assert all(entry.inspection_refs == ("inspection:test:1",) for entry in parsed.completion_evidence)


def test_typed_probe_is_accepted_by_production_inspection_parser() -> None:
    raw = "Create result.txt containing hello."
    packet = _persistent_packet(raw)
    packet["state_inspection_handles"] = [{"kind": "file", "path": "result.txt"}]

    def evaluator(state, questions):
        del state
        answers = {}
        for key, question in questions.items():
            if key == "next_move":
                probe = next(
                    item
                    for item, description in question["criteria"].items()
                    if item.startswith("probe_")
                    and "result.txt" in str(description)
                    and "Read" in str(description)
                )
                answers[key] = _answer(probe, **{probe: 0.9, "verdict_now": 0.1})
            elif key.startswith("requirement_"):
                answers[key] = _answer("insufficient", insufficient=0.99)
            elif key.startswith("evidence_"):
                answers[key] = _answer("none", none=0.99)
            elif key == "verification_dependence" or key.startswith("dependence_"):
                answers[key] = _answer("insufficient", insufficient=0.99)
            elif key == "semantic_determinant" or key.startswith("determinant_"):
                answers[key] = _answer("uncertain", uncertain=0.99)
            elif key == "noncompletion_verdict":
                answers[key] = _answer(
                    "uncertain_missing_evidence",
                    uncertain_missing_evidence=0.99,
                )
        return answers

    verifier = TypedJudgeVerifierCallable(evaluator)
    output = json.loads(verifier(_messages(packet)))
    parsed = parse_verifier_inspection_requests(output, require_derived_contract=True)
    assert len(parsed) == 1
    assert parsed[0].kind == "read_file"
    assert parsed[0].path == "result.txt"


def test_v3_policy_rejects_invalid_experiment_knobs() -> None:
    def evaluator(state, questions):
        del state, questions
        return {}

    with pytest.raises(ValueError, match="min_semantic_confidence"):
        TypedJudgeVerifierCallable(evaluator, min_semantic_confidence=0.0)
    with pytest.raises(ValueError, match="max_candidates"):
        TypedJudgeVerifierCallable(evaluator, max_candidates=0)
    with pytest.raises(ValueError, match="max_candidates"):
        TypedJudgeVerifierCallable(evaluator, max_candidates=65)
    with pytest.raises(ValueError, match="max_candidates"):
        TypedJudgeVerifierCallable(evaluator, max_candidates=True)


def test_internal_judge_round_ceiling_is_enforced(monkeypatch) -> None:
    raw = "Create result.txt containing hello."
    packet = _persistent_packet(raw)
    packet["state_inspection_handles"] = [{"kind": "file", "path": "result.txt"}]
    result = {
        "inspection_id": "inspection:test:1",
        "kind": "read_file",
        "path": "result.txt",
        "excerpt": "hello",
        "observation_valid": True,
        "eligible_for_proof": True,
        "actual_evidence_class": "exact_contract",
        "error": "",
    }
    messages = _messages(packet)
    messages.extend([
        {"role": "assistant", "content": json.dumps({"kind": "inspect", "requests": []})},
        {
            "role": "user",
            "content": json.dumps({"verifier_inspection_results": [result]}),
        },
    ])

    def evaluator(state, questions):
        del state
        answers = {}
        for key, question in questions.items():
            if key.startswith("evidence_"):
                options = [item for item in question["criteria"] if item != "none"]
                answers[key] = _answer(options[0], **{options[0]: 0.99, "none": 0.01})
            elif key == "verification_dependence" or key.startswith("dependence_"):
                answers[key] = _answer(
                    "correlated",
                    correlated=0.99,
                    independent=0.0,
                    insufficient=0.01,
                    not_required=0.0,
                )
            elif key == "semantic_determinant" or key.startswith("determinant_"):
                answers[key] = _answer("yes", yes=0.99, no=0.0, uncertain=0.01)
            elif key.startswith("relation_"):
                answers[key] = _answer(
                    "uncertain",
                    supports=0.01,
                    contradicts=0.0,
                    irrelevant=0.0,
                    uncertain=0.99,
                )
            elif key == "next_move":
                answers[key] = _answer("verdict_now", verdict_now=0.99)
        return answers

    verifier = TypedJudgeVerifierCallable(evaluator)
    monkeypatch.setattr(judge_policy, "MAX_EVALUATOR_ROUNDS_PER_VERIFIER_CALL", 2)
    with pytest.raises(RuntimeError, match="evaluator-round budget"):
        verifier(messages)


def test_routing_request_does_not_duplicate_unresolved_gap_text_in_state() -> None:
    raw = (
        "Create /app/result.txt containing hello.\n"
        "Preserve the existing input files.\n"
        "Verify the current result independently before completion."
    )
    packet = _persistent_packet(raw)
    packet["state_inspection_handles"] = [
        {"kind": "file", "path": "result.txt"},
        {"kind": "file", "path": "input.txt"},
    ]
    seen: dict[str, object] = {}

    def evaluator(state, questions):
        assert list(questions) == ["next_move"]
        seen["state"] = dict(state)
        seen["question"] = dict(questions["next_move"])
        return {"next_move": _answer("verdict_now", verdict_now=0.99)}

    verifier = TypedJudgeVerifierCallable(evaluator)
    parsed = parse_model_verifier_result(verifier(_messages(packet)))
    assert parsed.verdict == "uncertain_missing_evidence"

    routing_state = seen["state"]
    assert isinstance(routing_state, dict)
    assert routing_state["semantic_phase"] == "inspection_routing"
    assert "unresolved_gaps" not in routing_state

    question = seen["question"]
    assert isinstance(question, dict)
    instruction = str(question["instructions"])
    assert "Current gaps:" in instruction
    assert "No high-confidence current evidence establishes obligation:" in instruction
    for requirement in _requirements(packet, raw):
        assert requirement.text in instruction


def test_relation_provider_projection_deduplicates_pair_referents_without_losing_heads() -> None:
    raw = (
        "Create result.txt containing hello.\n"
        "Preserve input.txt unchanged.\n"
        "Keep output deterministic.\n"
        "Document the result.\n"
        "Preserve the service contract.\n"
        "Keep late updates correct.\n"
        "Retain required cleanup behavior.\n"
        "Do not modify read-only files.\n"
    )
    packet = _persistent_packet(raw)
    result = {
        "inspection_id": "inspection:relation:1",
        "kind": "read_file",
        "path": "result.txt",
        "excerpt": "hello",
        "observation_valid": True,
        "eligible_for_proof": True,
        "actual_evidence_class": "exact_contract",
        "error": "",
    }
    captured: list[dict] = []

    def transport(request):
        captured.append(request)
        answers = {}
        for key, question in request["questions"].items():
            criteria = list(question["criteria"])
            if key.startswith("evidence_"):
                choice = next(item for item in criteria if item != "none")
            elif key.startswith("relation_"):
                choice = "supports"
            elif key.startswith("dependence_"):
                choice = "not_required"
            elif key.startswith("determinant_"):
                choice = "yes"
            else:
                choice = criteria[0]
            answers[key] = _answer(choice, **{choice: 0.99})
        return {
            "provider": "judge",
            "result": {
                "model": "judge-1.13.0",
                "usage": {},
                "answers": answers,
            },
        }

    adapter = JudgeQuestionAdapter(transport)
    verifier = TypedJudgeVerifierCallable(adapter)
    parsed = parse_model_verifier_result(
        verifier(_messages(packet, results=[result]))
    )
    assert parsed.verdict == "completed"
    assert len(captured) == 2

    relation_request = captured[1]
    relation_state = relation_request["state"]
    relation_questions = relation_request["questions"]
    requirements = _requirements(packet, raw)
    assert relation_state["schema"] == judge_policy.V3_RELATION_PROVIDER_PROJECTION_VERSION
    assert len(relation_state["requirements"]) == len(requirements)
    assert len(relation_state["evidence"]) == 1
    assert len(relation_state["relation_pairs"]) == len(requirements)
    assert len(relation_questions) == len(requirements) * 3
    for index, requirement in enumerate(requirements):
        pair_key = f"p{index}"
        pair = relation_state["relation_pairs"][pair_key]
        requirement_row = relation_state["requirements"][pair["requirement_key"]]
        evidence_row = relation_state["evidence"][pair["evidence_key"]]
        assert requirement_row["text"] == requirement.text
        assert evidence_row["inspection_id"] == "inspection:relation:1"
        for prefix in ("relation", "dependence", "determinant"):
            question_id = f"{prefix}_{index}"
            question = relation_questions[question_id]
            binding = relation_state["question_bindings"][question_id]
            assert binding["pair_key"] == pair_key
            assert binding["head"] == prefix
            assert binding["criteria_key"] in relation_state["criteria_catalog"]
            assert question_id in question["instructions"]
            assert requirement.text not in question["instructions"]
            assert set(question["criteria"]) == set(
                relation_state["criteria_catalog"][binding["criteria_key"]]
            )

    telemetry = adapter.drain_telemetry()
    relation_telemetry = telemetry[1]
    assert relation_telemetry["provider_state_projection"] == (
        judge_policy.V3_RELATION_PROVIDER_PROJECTION_VERSION
    )
    assert relation_telemetry["provider_request_bytes"] < (
        judge_policy.V3_PROVIDER_REQUEST_HARD_LIMIT_BYTES
    )


def test_evidence_selection_catalog_bounds_three_long_evidence_options() -> None:
    long_a = "A" * 2200
    long_b = "B" * 2200
    long_c = "C" * 2200
    criteria = {
        "none": "No current registered inspection establishes this requirement.",
        "e1": long_a,
        "e2": long_b,
        "e3": long_c,
    }
    state = {
        "semantic_phase": "evidence_selection",
        "turn_constraint": "inspect_or_verdict",
        "raw_task": "Validate eight exact obligations against current evidence.",
        "requirements": [
            {
                "requirement_id": f"r{i}",
                "text": f"obligation {i}",
                "clause_ids": ["raw_task"],
                "exact_atoms": [],
            }
            for i in range(8)
        ],
        "registered_inspection_results": [{}, {}, {}],
        "candidate_inspections": [],
        "candidate_coverage": {},
    }
    questions = {
        f"evidence_{i}": {
            "type": "choice",
            "instructions": f"Which evidence supports obligation {i}?",
            "criteria": dict(criteria),
        }
        for i in range(8)
    }
    captured: list[dict] = []

    def transport(request):
        captured.append(request)
        return {
            "provider": "judge",
            "result": {
                "model": "judge-1.13.0",
                "usage": {},
                "answers": {
                    key: _answer("none", none=0.99)
                    for key in request["questions"]
                },
            },
        }

    adapter = JudgeQuestionAdapter(transport)
    answers = adapter(state, questions)
    assert set(answers) == set(questions)
    assert len(captured) == 1

    request = captured[0]
    provider_state = request["state"]
    provider_questions = request["questions"]
    assert provider_state["schema"] == "aether.judge.evidence-selection-catalog.v1"
    assert len(provider_state["criteria_catalog"]) == 1
    catalog_key = next(iter(provider_state["criteria_catalog"]))
    assert provider_state["criteria_catalog"][catalog_key] == criteria
    assert len(provider_state["question_bindings"]) == 8
    for question_id, question in provider_questions.items():
        binding = provider_state["question_bindings"][question_id]
        assert binding["criteria_key"] == catalog_key
        assert binding["requirement_key"] in provider_state["requirements"]
        assert set(question["criteria"]) == set(criteria)

    request_bytes = len(
        json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )
    assert request_bytes < judge_policy.V3_PROVIDER_REQUEST_HARD_LIMIT_BYTES
    telemetry = adapter.drain_telemetry()
    assert telemetry[0]["provider_state_projection"] == (
        "aether.judge.evidence-selection-catalog.v1"
    )
    assert telemetry[0]["provider_request_bytes"] == request_bytes


def test_judge_adapter_captures_usage_without_changing_answers() -> None:
    def transport(request):
        assert request["model"] == "judge-1.13.0"
        return {
            "provider": "judge",
            "result": {
                "model": "judge-1.13.0",
                "usage": {"input_tokens": 123, "output_tokens": 7},
                "answers": {
                    "relation": _answer(
                        "supports",
                        supports=0.97,
                        contradicts=0.01,
                        irrelevant=0.01,
                        uncertain=0.01,
                    )
                },
            },
        }

    adapter = JudgeQuestionAdapter(transport)
    state = {"assumption": "A", "evidence": "B"}
    questions = {
        "relation": {
            "type": "choice",
            "instructions": "relation?",
            "criteria": {"supports": "supports", "uncertain": "uncertain"},
        }
    }
    answers = adapter(state, questions)
    assert answers["relation"]["choice"] == "supports"
    telemetry = adapter.drain_telemetry()
    assert len(telemetry) == 1
    assert telemetry[0]["usage"] == {"input_tokens": 123, "output_tokens": 7}
    assert telemetry[0]["provider"] == "judge"
    assert telemetry[0]["question_ids"] == ["relation"]
    assert adapter.drain_telemetry() == []


def test_structured_artifact_result_keeps_mode_in_relation_referent() -> None:
    row = {
        "inspection_id": "inspection:mode",
        "kind": "inspect_artifact",
        "path": "ssl/server.key",
        "exists": True,
        "file_type": "PEM RSA private key",
        "size_bytes": "1704",
        "mode": "600",
        "owner": "root",
        "mtime_epoch": "1783254742",
        "sha256": "a" * 64,
        "observation_valid": True,
        "error": "",
    }
    text = judge_policy._result_excerpt(row)
    assert "mode" in text
    assert "600" in text
    assert "ssl/server.key" in text
    assert text != "registered current verifier observation"


def test_structured_action_history_keeps_exact_command_fact_in_relation_referent() -> None:
    row = {
        "inspection_id": "inspection:actions",
        "kind": "inspect_action_receipts",
        "rows": [{
            "receipt_id": "step-1:build:cmd",
            "kind": "run_command",
            "success": True,
            "failure_class": "",
            "payload": {
                "command": (
                    "cat > /app/kv-store.proto <<'EOF'\n"
                    "message SetValRequest { string key = 1; int32 val = 2; }\n"
                    "EOF"
                ),
                "exit_code": 0,
            },
        }],
        "returned_count": 1,
        "successful_count": 1,
        "method_evidence_only": True,
        "observation_valid": True,
        "error": "",
    }
    text = judge_policy._result_excerpt(row)
    assert "SetValRequest" in text
    assert "int32 val = 2" in text
    assert text != "registered current verifier observation"



def test_judge_adapter_projects_oversized_local_state_before_transport() -> None:
    captured: list[dict] = []

    def transport(request):
        captured.append(request)
        return {
            "provider": "judge",
            "result": {
                "model": "judge-1.13.0",
                "usage": {"input_tokens": 321, "output_tokens": 17},
                "answers": {
                    "next_move": {
                        "choice": "verdict_now",
                        "probabilities": {"verdict_now": 1.0},
                    },
                },
            },
        }

    state = {
        "raw_task": "Create result.txt containing hello.",
        "requirements": [{
            "requirement_id": "raw_task:1",
            "text": "Create result.txt containing hello.",
            "clause_ids": ["raw_task"],
            "exact_atoms": [],
        }],
        "verifier_packet": {"oversized_local_only": "x" * 30000},
        "registered_inspection_results": [],
        "candidate_inspections": [{"candidate_key": "probe_1"}],
        "candidate_coverage": {
            "candidate_limit": 12,
            "eligible_candidate_count": 1,
            "selected_candidate_count": 1,
            "available_direct_routes": ["read_file"],
            "eligible_route_kinds": ["read_file"],
            "selected_route_kinds": ["read_file"],
        },
        "turn_constraint": "inspect_or_verdict",
        "semantic_phase": "inspection_routing",
        "unresolved_gaps": ["Need current evidence for result.txt."],
    }
    questions = {
        "next_move": {
            "type": "choice",
            "instructions": "Choose the next bounded verifier step.",
            "criteria": {"verdict_now": "Return a fail-closed verdict now."},
        },
    }

    adapter = JudgeQuestionAdapter(transport, model="judge-1.13.0")
    answers = adapter(state, questions)

    assert answers["next_move"]["choice"] == "verdict_now"
    assert len(captured) == 1
    request = captured[0]
    assert "verifier_packet" not in request["state"]
    assert request["state"]["schema"] == judge_policy.V3_PROVIDER_STATE_PROJECTION_VERSION
    encoded = json.dumps(
        request, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert len(encoded) <= judge_policy.V3_PROVIDER_REQUEST_HARD_LIMIT_BYTES

    rows = adapter.drain_telemetry()
    assert len(rows) == 1
    row = rows[0]
    assert row["provider_state_projection"] == judge_policy.V3_PROVIDER_STATE_PROJECTION_VERSION
    assert row["provider_request_bytes"] == len(encoded)
    assert row["provider_state_bytes"] < request["state"]["source_state_bytes"]
    assert row["state_sha256"] == request["state"]["source_state_sha256"]


def test_post_inspection_evidence_questions_remain_exact_under_provider_projection() -> None:
    captured: list[dict] = []

    def transport(request):
        captured.append(request)
        answers = {}
        for key in request["questions"]:
            answers[key] = {
                "choice": "e1",
                "probabilities": {"e1": 0.95, "none": 0.05},
            }
        return {
            "provider": "judge",
            "result": {
                "model": "judge-1.13.0",
                "usage": {},
                "answers": answers,
            },
        }

    exact_evidence = (
        "Registered inspection 'inspection:test:design': "
        "Session windows fire when the global watermark advances."
    )
    requirements = [
        {
            "requirement_id": f"raw_task:{idx}",
            "text": f"Requirement {idx}: preserve exact session behavior.",
            "clause_ids": ["raw_task"],
            "exact_atoms": [],
        }
        for idx in range(1, 9)
    ]
    state = {
        "raw_task": "Repair the session window processor without changing required semantics.",
        "requirements": requirements,
        "verifier_packet": {"bulk_local_state": "z" * 40000},
        "registered_inspection_results": [{
            "inspection_id": "inspection:test:design",
            "kind": "read_file",
            "excerpt": "Session windows fire when the global watermark advances.",
            "observation_valid": True,
        }],
        "candidate_inspections": [{"candidate_key": f"probe_{idx}"} for idx in range(1, 13)],
        "candidate_coverage": {
            "candidate_limit": 12,
            "eligible_candidate_count": 12,
            "selected_candidate_count": 12,
            "available_direct_routes": ["read_file", "read_output"],
            "eligible_route_kinds": ["read_file", "read_output"],
            "selected_route_kinds": ["read_file", "read_output"],
        },
        "turn_constraint": "inspect_or_verdict",
        "semantic_phase": "evidence_selection",
        "unresolved_gaps": ["Need exact evidence for every requirement."],
    }
    questions = {
        f"evidence_{idx}": {
            "type": "choice",
            "instructions": f"Select evidence for requirement {idx}.",
            "criteria": {
                "none": "No current registered inspection establishes this requirement.",
                "e1": exact_evidence,
            },
        }
        for idx in range(8)
    }

    adapter = JudgeQuestionAdapter(transport, model="judge-1.13.0")
    answers = adapter(state, questions)

    assert len(answers) == 8
    request = captured[0]
    encoded = json.dumps(
        request, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert len(encoded) <= judge_policy.V3_PROVIDER_REQUEST_HARD_LIMIT_BYTES
    assert "verifier_packet" not in request["state"]
    assert request["state"]["registered_inspection_count"] == 1
    for question in request["questions"].values():
        assert question["criteria"]["e1"] == exact_evidence
