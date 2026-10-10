from __future__ import annotations

import json
import os
import tempfile

from aether.judge_verifier_policy import TypedJudgeVerifierCallable
from aether.run_adapter import run_task


def answer(choice: str, **probabilities: float) -> dict:
    return {"choice": choice, "probabilities": probabilities or {choice: 1.0}}


class Solver:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, *, max_output_tokens=None):
        del max_output_tokens
        self.calls += 1
        if self.calls == 1:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "write_file",
                    "arguments": {"path": "result.txt", "content": "hello"},
                },
            })
        if self.calls == 2:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "read_file",
                    "arguments": {"path": "result.txt"},
                },
            })
        refs: list[str] = []
        for message in messages:
            body = str(message.get("content", ""))
            start = 0
            while True:
                idx = body.find("evidence:", start)
                if idx < 0:
                    break
                candidate = body[idx:idx + len("evidence:") + 16]
                if len(candidate) == len("evidence:") + 16:
                    refs.append(candidate)
                start = idx + 1
        refs = list(dict.fromkeys(refs))
        assert refs
        return json.dumps({
            "kind": "submit",
            "claim": "result.txt contains hello",
            "evidence_refs": refs,
        })


def evaluator(state, questions):
    answers = {}
    for key, question in questions.items():
        if key == "next_move":
            probes = [item for item in question["criteria"] if item.startswith("probe_")]
            if probes:
                answers[key] = answer(probes[0], **{probes[0]: 0.91, "verdict_now": 0.09})
            else:
                answers[key] = answer("verdict_now", verdict_now=0.99)
        elif key.startswith("evidence_"):
            options = [item for item in question["criteria"] if item != "none"]
            assert options, state
            answers[key] = answer(options[0], **{options[0]: 0.97, "none": 0.03})
        elif key.startswith("relation_"):
            answers[key] = answer(
                "supports",
                supports=0.97,
                contradicts=0.01,
                irrelevant=0.01,
                uncertain=0.01,
            )
        elif key == "verification_dependence" or key.startswith("dependence_"):
            answers[key] = answer(
                "not_required",
                independent=0.01,
                correlated=0.01,
                insufficient=0.01,
                not_required=0.97,
            )
        elif key == "semantic_determinant" or key.startswith("determinant_"):
            answers[key] = answer("yes", yes=0.98, no=0.01, uncertain=0.01)
    return answers


def test_typed_v3_runs_through_real_production_verifier_loop() -> None:
    verifier = TypedJudgeVerifierCallable(evaluator)
    solver = Solver()
    with tempfile.TemporaryDirectory() as task_dir, tempfile.TemporaryDirectory() as workspace:
        with open(os.path.join(task_dir, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("provider-free V3 integration")
        record = run_task(
            task_dir=task_dir,
            instruction_text="Create result.txt containing hello.",
            solver_model=solver,
            verifier_model=verifier,
            workspace_root=workspace,
            max_steps=6,
            runtime_identity={
                "task_id": "judge-v3-provider-free",
                "run_id": "judge-v3-provider-free-run",
                "primary_agent_id": "primary",
                "source_commit": "a" * 40,
                "runtime_manifest_sha256": "b" * 64,
            },
        )

    assert record["status"] == "completed"
    receipts = record["receipt_records"]
    assert any(row["kind"] == "model_verifier_inspection" for row in receipts)
    assert any(
        row["kind"] == "model_verifier_result"
        and row["payload"].get("verdict") == "completed"
        for row in receipts
    )
    trace = [
        row for row in record["model_call_telemetry"]
        if row.get("schema") == "aether.judge_typed_verifier_trace.v3"
    ]
    assert len(trace) == 2
    assert trace[0]["decision"] == "typed_probe_selected"
    assert trace[1]["decision"] == "typed_completed"
    assert {row.get("run_id") for row in trace} == {"judge-v3-provider-free-run"}
    assert {row.get("task_id") for row in trace} == {"judge-v3-provider-free"}
    assert trace[1]["policy"]["max_evaluator_rounds_per_verifier_call"] == 3
    assert trace[1]["policy"]["min_semantic_confidence"] == 0.80
    assert trace[1]["policy"]["question_policy_version"]
    assert trace[1]["policy"]["question_schema_version"]
    coverage = trace[0]["state"]["candidate_coverage"]
    assert coverage["candidate_limit"] == 12
    assert coverage["eligible_candidate_count"] >= coverage["selected_candidate_count"] >= 1
    assert "read_file" in coverage["eligible_route_kinds"]
    assert "overlay_run_command" in coverage["reserved_for_v4"]
    assert any(
        round_row["label"] == "requirement_evidence_relation"
        for round_row in trace[1]["evaluation_rounds"]
    )
    assert verifier.drain_trace() == []
