from __future__ import annotations

from copy import deepcopy
import json

import pytest

from aether.completion_record import canonical_task_hash, update_completion_record_receipt
from aether.ledger import ExecutionLedger, Receipt
from aether.semantic_graph_assistance import GraphSemanticAssistance

TASK = "Produce the required report."


def fixture() -> ExecutionLedger:
    ledger = ExecutionLedger()
    ledger.install_runtime_identity({
        "task_id": "task",
        "run_id": "run",
        "workspace_id": "workspace",
    })
    record = {
        "schema_version": 1,
        "revision": 1,
        "task_hash": canonical_task_hash(TASK),
        "revision_reason": "Interpret visible contract",
        "conditions": [{
            "id": "format",
            "outcome": "Output is ordered newest first",
            "proof_needed": "Find current order requirement",
            "kind": "derived",
            "source_refs": [{
                "task_hash": canonical_task_hash(TASK),
                "start_byte": 0,
                "end_byte": len(TASK.encode()),
            }],
            "evidence_refs": [],
            "assessment": "open",
            "uncertainty": "Check revision",
            "retirement_reason": None,
        }],
    }
    receipt = update_completion_record_receipt(
        ledger=ledger,
        expected_revision=0,
        replacement_record=record,
        task_text=TASK,
        step=0,
        action_id="record",
    )
    assert receipt.success
    ledger.record(receipt)
    ledger.record(Receipt(
        "read",
        1,
        "read_file",
        True,
        "read current spec",
        payload={"content": "Revision 2: oldest first", "path": "spec.txt"},
    ))
    return ledger


def invoke(assistant: GraphSemanticAssistance, ledger: ExecutionLedger, *, run_id: str = "run"):
    return assistant(
        task_text=TASK,
        ledger=ledger,
        step=2,
        runtime_identity={"task_id": "task", "run_id": run_id},
    )


def answer(request: dict) -> dict:
    head = next(iter(request["questions"]))
    choices = request["questions"][head]["criteria"]
    selected = "relevant" if head == "ranking" else "contradicts"
    return {
        "answers": {
            head: {
                "choice": selected,
                "probabilities": {choice: float(choice == selected) for choice in choices},
            }
        }
    }


def test_graph_only_builds_persistent_view_without_semantic_calls() -> None:
    ledger = fixture()
    assistant = GraphSemanticAssistance()
    before = deepcopy(ledger.all_receipts())

    result = invoke(assistant, ledger)

    assert result["authority"] == "advisory_only"
    assert result["projection"] == "persistent_provenance_graph_v0"
    assert result["status"] == "graph_only"
    assert result["calls_total"] == 0
    assert result["items"] == []
    assert result["counts"]["hypotheses"] == 1
    assert result["counts"]["current_observations"] == 1
    assert assistant.graph is not None
    assert assistant.graph.authority == "advisory_only"
    assert ledger.all_receipts() == before


def test_judge_relation_is_source_bound_cached_and_not_recalled() -> None:
    ledger = fixture()
    calls = []
    assistant = GraphSemanticAssistance(
        lambda request: calls.append(request) or answer(request),
        model="test-only",
        heads=("ranking", "assumption"),
    )

    first = invoke(assistant, ledger)
    second = invoke(assistant, ledger)

    assert assistant.calls == 2
    assert len(calls) == 2
    assert all(call["state"]["question_policy_version"] == "gjudge0-explicit-referent-v1" for call in calls)
    assert all(call["state"]["response_schema_version"] == "gjudge0-relation-v1" for call in calls)
    assert all(call["state"]["evidence_ref"].startswith("evidence:") for call in calls)
    assert all("'format'" in next(iter(call["questions"].values()))["instructions"] for call in calls)
    assert all("'read'" in next(iter(call["questions"].values()))["instructions"] for call in calls)
    assert len(first["items"]) == 2
    assert len(second["items"]) == 2
    assert {item["receipt_id"] for item in second["items"]} == {"read"}
    assert all(item["evidence_ref"].startswith("evidence:") for item in second["items"])
    assert all(item["freshness"] == "current" for item in second["items"])
    assert assistant.graph is not None
    # Cached reevaluation must not create duplicate graph edges.
    assert len(assistant.graph.relations) == 2


def test_mutation_preserves_old_relation_as_historical_and_does_not_requery_it() -> None:
    ledger = fixture()
    calls = []
    assistant = GraphSemanticAssistance(
        lambda request: calls.append(request) or answer(request),
        model="test-only",
        heads=("ranking",),
    )
    first = invoke(assistant, ledger)
    assert len(first["items"]) == 1
    assert len(calls) == 1

    ledger.record(Receipt(
        "write",
        3,
        "write_file",
        True,
        "changed artifact",
        state_change=True,
        payload={"path": "report.py"},
    ))
    after_mutation = invoke(assistant, ledger)

    assert len(calls) == 1
    assert assistant.graph is not None
    old = assistant.graph.relation_rows("condition:1:format")
    assert old[0]["freshness"] == "historical"
    assert after_mutation["counts"]["historical_observations"] == 1
    assert after_mutation["counts"]["current_observations"] == 0


def test_new_current_observation_after_mutation_gets_new_relation() -> None:
    ledger = fixture()
    calls = []
    assistant = GraphSemanticAssistance(
        lambda request: calls.append(request) or answer(request),
        model="test-only",
        heads=("ranking",),
    )
    invoke(assistant, ledger)
    ledger.record(Receipt(
        "write",
        3,
        "write_file",
        True,
        "changed artifact",
        state_change=True,
        payload={"path": "report.py"},
    ))
    ledger.record(Receipt(
        "read-new",
        4,
        "read_file",
        True,
        "read changed artifact",
        payload={"path": "report.py", "content": "new"},
    ))

    result = invoke(assistant, ledger)

    assert len(calls) == 2
    assert assistant.graph is not None
    rows = assistant.graph.relation_rows("condition:1:format")
    freshness = {row["receipt_id"]: row["freshness"] for row in rows}
    assert freshness == {"read-new": "current", "read": "historical"}
    assert any(item["receipt_id"] == "read-new" for item in result["items"])


def test_cross_run_reuse_fails_closed() -> None:
    ledger = fixture()
    assistant = GraphSemanticAssistance()
    invoke(assistant, ledger)
    with pytest.raises(ValueError, match="cross runs"):
        invoke(assistant, ledger, run_id="other")


def test_malformed_judge_response_abstains_and_is_not_retried() -> None:
    ledger = fixture()
    calls = []
    assistant = GraphSemanticAssistance(
        lambda request: calls.append(request) or {},
        model="test-only",
        heads=("ranking",),
    )
    first = invoke(assistant, ledger)
    second = invoke(assistant, ledger)

    assert first["items"] == []
    assert second["items"] == []
    assert assistant.calls == 1
    assert len(calls) == 1
    assert len(assistant._failed_requests) == 1


def test_render_is_bounded_and_never_embeds_raw_observation_payload() -> None:
    ledger = fixture()
    assistant = GraphSemanticAssistance(
        answer,
        model="test-only",
        heads=("ranking",),
        max_render_bytes=4096,
    )
    result = invoke(assistant, ledger)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()

    assert len(encoded) <= 4096
    assert "Revision 2: oldest first" not in encoded.decode()


def test_graph_retains_check_results_without_expanding_judge_eligibility() -> None:
    ledger = fixture()
    ledger.record(Receipt(
        "check",
        2,
        "check_result",
        True,
        "independent check passed",
        payload={"check_id": "independent", "passed": True},
    ))
    calls = []
    assistant = GraphSemanticAssistance(
        lambda request: calls.append(request) or answer(request),
        model="test-only",
        heads=("ranking",),
    )

    result = invoke(assistant, ledger)

    assert result["counts"]["observations"] == 2
    assert assistant.graph is not None
    assert "check" in assistant.graph.observations
    # Current flat-JUDGE eligibility remains unchanged: only read_file is queried.
    assert len(calls) == 1
    assert calls[0]["state"]["observation"]["receipt_id"] == "read"
    rendered = result["graph"]["observations"]
    assert {row["receipt_id"] for row in rendered} == {"read", "check"}


def test_graph_does_not_promote_mutating_action_receipt_to_observation() -> None:
    ledger = fixture()
    ledger.record(Receipt(
        "write",
        2,
        "write_file",
        True,
        "changed candidate",
        state_change=True,
        payload={"path": "report.py"},
    ))
    assistant = GraphSemanticAssistance()

    result = invoke(assistant, ledger)

    assert assistant.graph is not None
    assert "write" not in assistant.graph.observations
    assert result["counts"]["historical_observations"] == 1


def test_graph_judge_uses_same_last_four_receipts_as_flat() -> None:
    ledger = fixture()
    for index in range(2, 6):
        ledger.record(Receipt(
            f"read-{index}",
            index,
            "read_file",
            True,
            f"read {index}",
            payload={"path": f"{index}.txt", "content": str(index)},
        ))
    calls = []
    assistant = GraphSemanticAssistance(
        lambda request: calls.append(request) or answer(request),
        model="test-only",
        heads=("ranking",),
        max_calls=20,
        calls_per_turn=20,
    )

    invoke(assistant, ledger)

    ids = [request["state"]["observation"]["receipt_id"] for request in calls]
    assert ids == ["read-5", "read-4", "read-3", "read-2"]
    assert assistant.graph is not None
    assert "read" in assistant.graph.observations


def test_graph_judge_uses_same_first_four_conditions_as_flat() -> None:
    ledger = ExecutionLedger()
    ledger.install_runtime_identity({
        "task_id": "task",
        "run_id": "run",
        "workspace_id": "workspace",
    })
    conditions = []
    for index in range(5):
        conditions.append({
            "id": f"condition-{index}",
            "outcome": f"outcome {index}",
            "proof_needed": f"proof {index}",
            "kind": "explicit",
            "source_refs": [{
                "task_hash": canonical_task_hash(TASK),
                "start_byte": 0,
                "end_byte": len(TASK.encode()),
            }],
            "evidence_refs": [],
            "assessment": "open",
            "uncertainty": "",
            "retirement_reason": None,
        })
    record = {
        "schema_version": 1,
        "revision": 1,
        "task_hash": canonical_task_hash(TASK),
        "revision_reason": "five-condition fixture",
        "conditions": conditions,
    }
    receipt = update_completion_record_receipt(
        ledger=ledger,
        expected_revision=0,
        replacement_record=record,
        task_text=TASK,
        step=0,
        action_id="record-many",
    )
    assert receipt.success
    ledger.record(receipt)
    ledger.record(Receipt(
        "read",
        1,
        "read_file",
        True,
        "read current spec",
        payload={"content": "current", "path": "spec.txt"},
    ))
    calls = []
    assistant = GraphSemanticAssistance(
        lambda request: calls.append(request) or answer(request),
        model="test-only",
        heads=("ranking",),
        max_calls=20,
        calls_per_turn=20,
    )

    invoke(assistant, ledger)

    ids = [request["state"]["condition"]["id"] for request in calls]
    assert ids == [
        "condition-0", "condition-1", "condition-2", "condition-3"
    ]
    assert assistant.graph is not None
    assert any(
        hypothesis.text == "outcome 4"
        for hypothesis in assistant.graph.hypotheses.values()
    )


def test_read_origin_uses_canonical_receipt_path_instead_of_kind_bucket() -> None:
    first = Receipt(
        "r1", 1, "read_file", True, "read one",
        payload={"path": "/app/workspace/spec.md", "content_sha256": "a" * 64},
    )
    same = Receipt(
        "r2", 2, "read_file", True, "read one again",
        payload={"path": "workspace/spec.md", "content_sha256": "a" * 64},
    )
    other = Receipt(
        "r3", 3, "read_file", True, "read another",
        payload={"path": "workspace/other.md", "content_sha256": "b" * 64},
    )

    assert GraphSemanticAssistance._origin_id(first) == "path:workspace/spec.md"
    assert GraphSemanticAssistance._origin_id(same) == "path:workspace/spec.md"
    assert GraphSemanticAssistance._origin_id(other) == "path:workspace/other.md"
