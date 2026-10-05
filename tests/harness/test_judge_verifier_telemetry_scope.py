from __future__ import annotations

import json

from aether.judge_verifier_policy import (
    JudgeQuestionAdapter,
    TypedJudgeVerifierCallable,
)


def _messages() -> list[dict[str, str]]:
    raw = "Create result.txt containing hello."
    packet = {
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
    return [
        {"role": "system", "content": "verifier"},
        {
            "role": "user",
            "content": json.dumps({
                "authoritative_task_prompt": raw,
                "verifier_packet": packet,
            }),
        },
    ]


def test_v3_and_nested_judge_telemetry_share_modelhooks_scope() -> None:
    def transport(request):
        question = request["questions"]["next_move"]
        selected = next(
            key for key in question["criteria"]
            if key.startswith("probe_")
        )
        return {
            "provider": "judge",
            "result": {
                "model": "judge-1.13.0",
                "usage": {"input_tokens": 111, "output_tokens": 9},
                "answers": {
                    "next_move": {
                        "choice": selected,
                        "probabilities": {
                            selected: 0.97,
                            "verdict_now": 0.03,
                        },
                    },
                },
            },
        }

    adapter = JudgeQuestionAdapter(transport, model="judge-1.13.0")
    verifier = TypedJudgeVerifierCallable(adapter)
    raw = verifier.call_with_telemetry_scope(
        _messages(),
        run_id="run-scope-1",
        task_id="task-scope-1",
    )
    assert json.loads(raw)["kind"] == "inspect"

    rows = verifier.drain_telemetry()
    assert len(rows) == 2
    assert {row["run_id"] for row in rows} == {"run-scope-1"}
    assert {row["task_id"] for row in rows} == {"task-scope-1"}
    schemas = {row["schema"] for row in rows}
    assert "aether.judge_typed_verifier_trace.v3" in schemas
    assert "aether.judge_adapter_telemetry.v2" in schemas

    adapter_row = next(
        row for row in rows
        if row["schema"] == "aether.judge_adapter_telemetry.v2"
    )
    assert adapter_row["requested_model"] == "judge-1.13.0"
    assert adapter_row["reported_model"] == "judge-1.13.0"
    assert adapter_row["question_policy_version"]
    assert adapter_row["question_schema_version"]
    assert adapter_row["usage"] == {"input_tokens": 111, "output_tokens": 9}
    assert verifier.drain_telemetry() == ()


def test_cancellation_binding_reaches_nested_judge_transport() -> None:
    class Transport:
        def __init__(self) -> None:
            self.bound = None

        def bind_run_cancellation(self, event) -> None:
            self.bound = event

        def __call__(self, request):
            raise AssertionError("transport should not be called")

    marker = object()
    transport = Transport()
    adapter = JudgeQuestionAdapter(transport, model="judge-1.13.0")
    verifier = TypedJudgeVerifierCallable(adapter)
    verifier.bind_run_cancellation(marker)
    assert transport.bound is marker
