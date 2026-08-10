from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from aether.persistent_context_budget import finalize_persistent_context_budget
from aether.runtime_ir import stable_json


def _compiled(*, window: int = 200_000, ratio: float = 0.8):
    return SimpleNamespace(
        context_policy=SimpleNamespace(
            model_context_window_tokens=window,
            compression_trigger_ratio=ratio,
        )
    )


def _evidence(index: int, *, bounded_chars: int = 2_000) -> dict:
    alias = f"evidence:{index:016x}"
    return {
        "evidence_ref": alias,
        "completion_evidence_eligible": True,
        "receipt_id": f"step-{index}:action-{index}:cmd",
        "evidence_type": "run_command",
        "originating_action_id": f"action-{index}",
        "mechanical_description": f"command result {index}",
        "success": True,
        "state_change": False,
        "failure_class": "",
        "step": index,
        "currentness": "historical_task_evidence",
        "bounded_view": {
            "command": "python -c 'check'",
            "stdout": "x" * bounded_chars,
            "exit_code": 0,
        },
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": f"receipt:step-{index}:action-{index}:cmd",
            "sha256": f"{index:064x}"[-64:],
            "bytes": bounded_chars,
            "retrieval": {
                "action_kind": "read_output",
                "arguments": {"handle": f"receipt:step-{index}:action-{index}:cmd"},
                "paging_supported": True,
            },
        },
    }


def test_preferred_hot_context_does_not_expand_small_packet() -> None:
    packet = {
        "runtime_identity": {"task_id": "small"},
        "latest_primary_result": {"status": "no_primary_action_yet"},
        "evidence_index": [],
        "working_state": {"status": "not_authored"},
        "linked_history": {
            "open_obligations": [],
            "persistent_context_boundary": {"linked_history_is_factual_projection": True},
        },
    }
    rendered = finalize_persistent_context_budget(packet, _compiled())

    budget = rendered["context_budget"]
    assert "preferred_hot_context" not in budget["compression_stages"]
    assert rendered["latest_primary_result"] == packet["latest_primary_result"]
    assert rendered["evidence_index"] == []
    assert budget["final_bytes_v1"] == len(stable_json(rendered).encode("utf-8"))


def test_preferred_hot_context_compacts_only_historical_duplicates() -> None:
    evidence = [_evidence(index) for index in range(20)]
    pinned_alias = evidence[0]["evidence_ref"]
    latest_alias = evidence[-1]["evidence_ref"]
    latest = {
        "status": "observed",
        "action_id": "action-19",
        "action_kind": "run_command",
        "outcome_receipts": [deepcopy(evidence[-1])],
        "exact_access_state": "available",
    }
    packet = {
        "runtime_identity": {"task_id": "hot", "run_id": "run-hot"},
        "latest_primary_result": latest,
        "evidence_index": evidence,
        "working_state": {
            "status": "current",
            "evidence_bindings": {pinned_alias: evidence[0]["receipt_id"]},
            "checkpoint": {"current_objective": "finish the task"},
        },
        "linked_history": {
            "command_results": [
                {"receipt_id": f"cmd-{index}", "stdout": "z" * 3_000}
                for index in range(10)
            ],
            "tool_results": [
                {"receipt_id": f"tool-{index}", "payload": "y" * 1_500}
                for index in range(5)
            ],
            "open_obligations": [{"obligation_id": "task:raw", "status": "open"}],
            "persistent_context_boundary": {"linked_history_is_factual_projection": True},
        },
    }
    original = deepcopy(packet)
    original_bytes = len(stable_json(packet).encode("utf-8"))

    rendered = finalize_persistent_context_budget(packet, _compiled())

    assert packet == original
    budget = rendered["context_budget"]
    assert budget["preferred_hot_context"]["applied"] is True
    assert budget["preferred_hot_context"]["latest_primary_result_inline_preserved"] is True
    assert budget["preferred_hot_context"]["semantic_summarization_used"] is False
    assert "preferred_hot_context" in budget["compression_stages"]
    assert "externalize_linked_history" in budget["compression_stages"]
    assert "compact_evidence_views" in budget["compression_stages"]
    assert "trim_evidence_index_preserving_pins" in budget["compression_stages"]

    # The causal action -> observation boundary is not compacted in the
    # preferred profile, even though its duplicate evidence-index row is.
    assert rendered["latest_primary_result"] == latest
    assert "bounded_view" in rendered["latest_primary_result"]["outcome_receipts"][0]

    rows = rendered["evidence_index"]
    aliases = {row["evidence_ref"] for row in rows}
    assert pinned_alias in aliases
    assert latest_alias in aliases
    assert evidence[1]["evidence_ref"] not in aliases
    # Recent is defined by evidence step, not list position. The newest 12
    # synthetic rows are steps 8..19; the old pinned step 0 is appended.
    assert evidence[8]["evidence_ref"] in aliases
    assert evidence[7]["evidence_ref"] not in aliases
    assert rows[0]["evidence_ref"] == latest_alias
    assert len(rows) <= 14  # 12 recent + any non-overlapping model pins.
    assert all("bounded_view" not in row for row in rows)
    assert all(row.get("bounded_view_externalized") is True for row in rows)
    assert all(row.get("exact_access", {}).get("handle") for row in rows)

    assert "command_results" not in rendered["linked_history"]
    assert "tool_results" not in rendered["linked_history"]
    externalized = {row["selector"]: row for row in budget["externalized_sections"]}
    assert externalized["command_results"]["retrieval_actions"] == ["read_output", "query_memory"]
    assert externalized["tool_results"]["retrieval_actions"] == ["query_memory"]

    assert budget["original_bytes_v1"] == original_bytes
    assert budget["final_bytes_v1"] < original_bytes


def test_preferred_hot_context_keeps_latest_result_when_it_is_large() -> None:
    latest_row = _evidence(1, bounded_chars=25_000)
    packet = {
        "runtime_identity": {"task_id": "latest-large"},
        "latest_primary_result": {
            "status": "observed",
            "outcome_receipts": [deepcopy(latest_row)],
        },
        "evidence_index": [deepcopy(latest_row)],
        "working_state": {"status": "not_authored"},
        "linked_history": {
            "command_results": [{"receipt_id": "duplicate", "stdout": "q" * 20_000}],
            "open_obligations": [],
        },
    }
    rendered = finalize_persistent_context_budget(packet, _compiled(window=100_000, ratio=0.9))

    assert "preferred_hot_context" in rendered["context_budget"]["compression_stages"]
    assert rendered["latest_primary_result"] == packet["latest_primary_result"]
    assert "bounded_view" in rendered["latest_primary_result"]["outcome_receipts"][0]
    assert "bounded_view" not in rendered["evidence_index"][0]


def test_preferred_hot_context_recent_selection_is_order_independent() -> None:
    # Production evidence_index is newest-first. This regression prevents the
    # former rows[-limit:] bug from retaining the oldest evidence instead.
    evidence = [_evidence(index, bounded_chars=200) for index in range(20)]
    newest_first = list(reversed(evidence))
    pinned_alias = evidence[0]["evidence_ref"]
    packet = {
        "runtime_identity": {"task_id": "newest-first"},
        "latest_primary_result": {
            "status": "observed",
            "outcome_receipts": [deepcopy(evidence[-1])],
        },
        "evidence_index": newest_first,
        "working_state": {
            "status": "current",
            "evidence_bindings": {pinned_alias: evidence[0]["receipt_id"]},
        },
        "linked_history": {
            "command_results": [{"receipt_id": "dup", "stdout": "q" * 5000}],
        },
    }
    rendered = finalize_persistent_context_budget(packet, _compiled())
    rows = rendered["evidence_index"]
    aliases = {row["evidence_ref"] for row in rows}
    assert rows[0]["evidence_ref"] == evidence[19]["evidence_ref"]
    assert all(evidence[index]["evidence_ref"] in aliases for index in range(8, 20))
    assert pinned_alias in aliases
    assert evidence[7]["evidence_ref"] not in aliases
