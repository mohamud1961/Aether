from __future__ import annotations

from types import SimpleNamespace

from aether.persistent_context_budget import finalize_persistent_context_budget


def _compiled():
    return SimpleNamespace(
        context_policy=SimpleNamespace(
            model_context_window_tokens=200_000,
            compression_trigger_ratio=0.8,
        )
    )


def _evidence(index: int) -> dict:
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
        "bounded_view": {"stdout": "x" * 1000, "exit_code": 0},
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": f"receipt:{receipt_id}",
            "sha256": f"{index:064x}"[-64:],
            "bytes": 1000,
            "retrieval": {
                "action_kind": "read_output",
                "arguments": {"handle": f"receipt:{receipt_id}"},
                "paging_supported": True,
            },
        },
    }


def test_graph_provenance_receipt_stays_mechanically_retrievable_after_hot_trim() -> None:
    evidence = [_evidence(index) for index in range(20)]
    cited = evidence[1]
    packet = {
        "runtime_identity": {"task_id": "graph-pin", "run_id": "run"},
        "latest_primary_result": {"status": "no_primary_action_yet"},
        "evidence_index": evidence,
        "receipt_exact_handles": {
            row["receipt_id"]: row["exact_access"]["handle"] for row in evidence
        },
        "semantic_advice": {
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
                    "relations": [],
                    "provenance": [{
                        "subject_id": "condition:1:x",
                        "receipt_id": cited["receipt_id"],
                        "relation": "cites",
                        "source": "solver_completion_record",
                        "freshness": "current",
                        "origin_id": "command:old",
                        "invalidated": False,
                    }],
                }],
            },
        },
        "linked_history": {"open_obligations": []},
    }

    rendered = finalize_persistent_context_budget(packet, _compiled())
    kept_ids = {row["receipt_id"] for row in rendered["evidence_index"]}

    assert cited["receipt_id"] in kept_ids
    assert cited["receipt_id"] in rendered["receipt_exact_handles"]
    assert "trim_evidence_index_preserving_current" in rendered["context_budget"]["compression_stages"]


def test_graph_relation_receipt_is_also_pinned_without_top_level_judge_item() -> None:
    evidence = [_evidence(index) for index in range(20)]
    cited = evidence[2]
    packet = {
        "runtime_identity": {"task_id": "graph-relation-pin", "run_id": "run"},
        "latest_primary_result": {"status": "no_primary_action_yet"},
        "evidence_index": evidence,
        "receipt_exact_handles": {
            row["receipt_id"]: row["exact_access"]["handle"] for row in evidence
        },
        "semantic_advice": {
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
                        "receipt_id": cited["receipt_id"],
                        "relation": "supports",
                        "source": "judge",
                        "freshness": "current",
                        "origin_id": "command:old",
                        "invalidated": False,
                    }],
                    "provenance": [],
                }],
            },
        },
        "linked_history": {"open_obligations": []},
    }

    rendered = finalize_persistent_context_budget(packet, _compiled())

    assert cited["receipt_id"] in {
        row["receipt_id"] for row in rendered["evidence_index"]
    }
    assert cited["receipt_id"] in rendered["receipt_exact_handles"]
