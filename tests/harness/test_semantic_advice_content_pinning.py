from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from aether.persistent_context_budget import finalize_persistent_context_budget


def _compiled():
    return SimpleNamespace(
        context_policy=SimpleNamespace(
            model_context_window_tokens=200_000,
            compression_trigger_ratio=0.8,
        )
    )


def _evidence(index: int, *, chars: int = 1200) -> dict:
    receipt_id = f"step-{index}:action-{index}:cmd"
    return {
        "evidence_ref": f"evidence:{index:016x}",
        "completion_evidence_eligible": True,
        "receipt_id": receipt_id,
        "evidence_type": "run_command",
        "originating_action_id": f"action-{index}",
        "mechanical_description": f"command result {index}",
        "success": True,
        "state_change": False,
        "failure_class": "",
        "step": index,
        "currentness": "historical_task_evidence",
        "bounded_view": {
            "stdout": f"DECISIVE-{index}-" + ("x" * chars),
            "exit_code": 0,
        },
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": f"receipt:{receipt_id}",
            "sha256": f"{index:064x}"[-64:],
            "bytes": chars,
            "retrieval": {
                "action_kind": "read_output",
                "arguments": {"handle": f"receipt:{receipt_id}"},
                "paging_supported": True,
            },
        },
    }


def _base(evidence: list[dict]) -> dict:
    latest = evidence[-1]
    return {
        "runtime_identity": {"task_id": "semantic-content-pin", "run_id": "run"},
        "latest_primary_result": {
            "status": "observed",
            "outcome_receipts": [deepcopy(latest)],
        },
        "evidence_index": evidence,
        "receipt_exact_handles": {
            row["receipt_id"]: row["exact_access"]["handle"] for row in evidence
        },
        "linked_history": {
            "command_results": [{"receipt_id": "dup", "stdout": "q" * 7000}],
        },
    }


def _by_receipt(rendered: dict) -> dict[str, dict]:
    return {
        str(row["receipt_id"]): row
        for row in rendered["evidence_index"]
        if isinstance(row, dict) and row.get("receipt_id")
    }


def test_flat_semantic_advice_keeps_cited_bounded_evidence_hot() -> None:
    evidence = [_evidence(index) for index in range(20)]
    cited = evidence[1]
    packet = _base(evidence)
    packet["semantic_advice"] = {
        "schema": "aether.semantic_advice.v1",
        "authority": "advisory_only",
        "projection": "relation_only_provenance_v1",
        "items": [{
            "head": "assumption_relation",
            "condition_id": "condition-1",
            "evidence_ref": cited["evidence_ref"],
            "receipt_id": cited["receipt_id"],
            "choice": "contradicts",
            "probabilities": {
                "supports": 0.01,
                "contradicts": 0.96,
                "irrelevant": 0.01,
                "uncertain": 0.02,
            },
        }],
    }

    rendered = finalize_persistent_context_budget(packet, _compiled())
    rows = _by_receipt(rendered)

    assert cited["receipt_id"] in rows
    assert rows[cited["receipt_id"]]["bounded_view"] == cited["bounded_view"]
    assert rows[cited["receipt_id"]].get("bounded_view_externalized") is not True

    # An ordinary historical row remains cold/compact.
    ordinary = evidence[8]
    assert ordinary["receipt_id"] in rows
    assert "bounded_view" not in rows[ordinary["receipt_id"]]
    assert rows[ordinary["receipt_id"]]["bounded_view_externalized"] is True


def test_graph_relation_and_provenance_keep_cited_bounded_evidence_hot() -> None:
    evidence = [_evidence(index) for index in range(20)]
    relation = evidence[2]
    provenance = evidence[3]
    packet = _base(evidence)
    packet["semantic_advice"] = {
        "schema": "aether.semantic_graph_advice.v0",
        "authority": "advisory_only",
        "projection": "persistent_provenance_graph_v0",
        "items": [],
        "graph": {
            "schema": "aether.evidence_graph_summary.v0",
            "authority": "advisory_only",
            "task_state_generation": 1,
            "subjects": [{
                "subject_id": "condition:1:x",
                "relations": [{
                    "subject_id": "condition:1:x",
                    "receipt_id": relation["receipt_id"],
                    "relation": "contradicts",
                    "source": "judge",
                    "freshness": "current",
                    "origin_id": "command:relation",
                    "invalidated": False,
                }],
                "provenance": [{
                    "subject_id": "condition:1:x",
                    "receipt_id": provenance["receipt_id"],
                    "relation": "cites",
                    "source": "solver",
                    "freshness": "current",
                    "origin_id": "command:provenance",
                    "invalidated": False,
                }],
            }],
        },
    }

    rendered = finalize_persistent_context_budget(packet, _compiled())
    rows = _by_receipt(rendered)

    for cited in (relation, provenance):
        assert cited["receipt_id"] in rows
        assert rows[cited["receipt_id"]]["bounded_view"] == cited["bounded_view"]
        assert rows[cited["receipt_id"]].get("bounded_view_externalized") is not True

    ordinary = evidence[8]
    assert "bounded_view" not in rows[ordinary["receipt_id"]]


def test_semantic_pin_does_not_duplicate_latest_primary_result() -> None:
    evidence = [_evidence(index) for index in range(20)]
    latest = evidence[-1]
    packet = _base(evidence)
    packet["semantic_advice"] = {
        "schema": "aether.semantic_advice.v1",
        "authority": "advisory_only",
        "items": [{
            "evidence_ref": latest["evidence_ref"],
            "receipt_id": latest["receipt_id"],
            "choice": "supports",
            "probabilities": {"supports": 0.95, "uncertain": 0.05},
        }],
    }
    expected_latest = deepcopy(packet["latest_primary_result"])

    rendered = finalize_persistent_context_budget(packet, _compiled())

    assert rendered["latest_primary_result"] == expected_latest
    rows = _by_receipt(rendered)
    assert "bounded_view" not in rows[latest["receipt_id"]]
    assert rows[latest["receipt_id"]]["bounded_view_hot_via"] == "latest_primary_result"
