from __future__ import annotations

import json

from aether.judge_verifier_policy import TypedJudgeVerifierCallable


def _answer(choice: str, **probabilities: float) -> dict:
    return {"choice": choice, "probabilities": probabilities or {choice: 1.0}}


def _packet() -> dict:
    raw = "Create result.txt containing hello."
    return {
        "raw_user_task": raw,
        "task_contract": {
            "schema_version": "persistent_v11_raw",
            "clauses": [{"clause_id": "raw_task", "text": raw, "exact_atoms": []}],
        },
        "verifier_runtime_capabilities": {
            "available_direct_observation_kinds": ["read_file"],
        },
        "state_inspection_handles": [{"kind": "file", "path": "result.txt"}],
        "authoritative_check_ids": [],
        "primary_submission": {"cited_evidence_index": []},
        "dynamic_state": {},
    }


def _messages(packet: dict) -> list[dict[str, str]]:
    result = {
        "inspection_id": "inspection:test:exact",
        "kind": "read_file",
        "path": "result.txt",
        "excerpt": "hello",
        "observation_valid": True,
        "eligible_for_proof": True,
        "actual_evidence_class": "exact_contract",
        "error": "",
    }
    return [
        {"role": "system", "content": "verifier"},
        {
            "role": "user",
            "content": json.dumps({
                "authoritative_task_prompt": packet["raw_user_task"],
                "verifier_packet": packet,
            }),
        },
        {"role": "assistant", "content": json.dumps({"kind": "inspect", "requests": []})},
        {
            "role": "user",
            "content": json.dumps({
                "verifier_turn_constraint": "verdict_only",
                "verifier_inspection_results": [result],
            }),
        },
    ]


def test_pair_guard_questions_name_exact_requirement_and_evidence_referent() -> None:
    rounds: list[tuple[dict, dict]] = []

    def evaluator(state, questions):
        rounds.append((dict(state), dict(questions)))
        answers = {}
        for key, question in questions.items():
            if key.startswith("evidence_"):
                selected = next(item for item in question["criteria"] if item != "none")
                answers[key] = _answer(selected, **{selected: 0.99, "none": 0.01})
            elif key.startswith("relation_"):
                answers[key] = _answer(
                    "supports",
                    supports=0.98,
                    contradicts=0.01,
                    irrelevant=0.0,
                    uncertain=0.01,
                )
            elif key.startswith("dependence_"):
                answers[key] = _answer(
                    "independent",
                    independent=0.98,
                    correlated=0.01,
                    insufficient=0.0,
                    not_required=0.01,
                )
            elif key.startswith("determinant_"):
                answers[key] = _answer("yes", yes=0.98, no=0.01, uncertain=0.01)
            # Compatibility answers make the pre-refactor implementation reach
            # its relation round so this test fails on referent shape, not flow.
            elif key == "verification_dependence":
                answers[key] = _answer(
                    "independent",
                    independent=0.98,
                    correlated=0.01,
                    insufficient=0.0,
                    not_required=0.01,
                )
            elif key == "semantic_determinant":
                answers[key] = _answer("yes", yes=0.98, no=0.01, uncertain=0.01)
        return answers

    verifier = TypedJudgeVerifierCallable(evaluator)
    verifier(_messages(_packet()))

    relation_round = next(
        questions
        for _state, questions in rounds
        if any(key.startswith("relation_") for key in questions)
    )
    assert "relation_0" in relation_round
    assert "dependence_0" in relation_round
    assert "determinant_0" in relation_round

    for key in ("dependence_0", "determinant_0"):
        instructions = relation_round[key]["instructions"]
        assert "Create result.txt containing hello." in instructions
        assert "inspection:test:exact" in instructions
        assert "read_file" in instructions
        assert "hello" in instructions
