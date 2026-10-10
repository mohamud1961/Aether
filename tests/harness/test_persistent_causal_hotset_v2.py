from __future__ import annotations

from copy import deepcopy

from aether.persistent_reanchor import (
    CONTINUITY_CAUSAL_HOTSET_V2,
    CONTINUITY_FRESH_DELTA_V1,
    continuity_causal_hotset_v2_reanchor,
    project_persistent_context_for_model,
)
from aether.runtime_ir import stable_json


def _latest_row() -> dict:
    command = "python3 - <<'PY'\nprint('discover')\nPY"
    summary = f"command exit=0: {command}"
    return {
        "evidence_ref": "evidence:latest",
        "receipt_id": "step-0:persistent-action:cmd",
        "evidence_type": "run_command",
        "originating_action_id": "persistent-action",
        "mechanical_description": summary,
        "success": True,
        "state_change": False,
        "failure_class": "",
        "step": 0,
        "currentness": "latest_primary_result",
        "completion_evidence_eligible": True,
        "task_id": "task-a",
        "run_id": "run-a",
        "workspace_id": "/app",
        "bounded_view": {
            "receipt_id": "step-0:persistent-action:cmd",
            "step": 0,
            "kind": "run_command",
            "success": True,
            "summary": summary,
            "command": command,
            "exit_code": 0,
            "stdout": "data/item.txt\nTARGET_TOKEN=VALUE-1\n",
            "stdout_handle": "0:persistent-action:stdout",
            "stderr_handle": "0:persistent-action:stderr",
            "workspace_effects": {
                "mutation_detection_status": "coarse",
                "path_set_delta_status": "complete",
            },
        },
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": "receipt:step-0:persistent-action:cmd",
            "sha256": "a" * 64,
            "bytes": 2048,
            "related_handles": [
                {"handle": "0:persistent-action:stdout", "stream": "stdout", "bytes": 35},
                {"handle": "0:persistent-action:stderr", "stream": "stderr", "bytes": 0},
            ],
            "retrieval": {
                "action_kind": "read_output",
                "arguments": {"handle": "receipt:step-0:persistent-action:cmd"},
                "paging_supported": True,
            },
        },
    }


def _packet() -> dict:
    latest = _latest_row()
    historical = deepcopy(latest)
    historical.update({
        "evidence_ref": "evidence:old",
        "receipt_id": "step-old:persistent-old:cmd",
        "originating_action_id": "persistent-old",
        "step": -1,
        "currentness": "historical_task_evidence",
    })
    unknown_fresh = {
        "evidence_ref": "evidence:other-current",
        "receipt_id": "step-1:persistent-other:file",
        "evidence_type": "read_file",
        "originating_action_id": "persistent-other",
        "mechanical_description": "read answer.txt",
        "success": True,
        "state_change": False,
        "failure_class": "",
        "step": 1,
        "currentness": "kernel_current_fact_v2",
        "completion_evidence_eligible": True,
        "bounded_view": {"path": "answer.txt", "excerpt": "VALUE-1"},
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": "receipt:step-1:persistent-other:file",
            "sha256": "b" * 64,
            "bytes": 256,
            "retrieval": {
                "action_kind": "read_output",
                "arguments": {"handle": "receipt:step-1:persistent-other:file"},
            },
        },
    }
    return {
        "latest_primary_result": {
            "status": "succeeded",
            "index_receipt_id": "step-0:persistent-action:primary_action_result_index",
            "action_id": "persistent-action",
            "action_kind": "run_command",
            "outcome_receipt_ids": [latest["receipt_id"]],
            "missing_outcome_receipt_ids": [],
            "outcome_receipts": [latest],
            "exact_access_state": "available",
        },
        "runtime_identity": {
            "task_id": "task-a",
            "run_id": "run-a",
            "primary_agent_id": "primary:run-a",
            "workspace_id": "/app",
            "environment_id": "env-a",
        },
        "available_capabilities": {"action_kinds": ["read_file", "run_command", "write_file"]},
        "budgets": {
            "max_kernel_steps": 10,
            "used_solver_provider_turns": 1,
            "remaining_kernel_steps": 9,
        },
        "evidence_index": [latest, historical, unknown_fresh],
        "linked_history": {"artifacts_present": ["answer.txt"]},
        "unresolved_runtime_facts": [],
        "self_extension": {
            "enabled": True,
            "task_local_dir": ".aether/tools",
            "smoke_test_required": True,
            "trust_for_completion": False,
        },
    }


def test_causal_hotset_v2_preserves_causal_observation_without_internal_duplication() -> None:
    packet = _packet()
    snapshot = deepcopy(packet)
    projected = continuity_causal_hotset_v2_reanchor(packet)
    assert packet == snapshot

    latest = projected["latest_primary_result"]
    assert latest == {
        "status": "succeeded",
        "action_id": "persistent-action",
        "action_kind": "run_command",
        "exact_access_state": "available",
        "outcome_receipts": latest["outcome_receipts"],
    }
    row = latest["outcome_receipts"][0]
    assert row["evidence_ref"] == "evidence:latest"
    assert row["receipt_id"] == "step-0:persistent-action:cmd"
    assert row["success"] is True
    assert row["bounded_view"]["command"].startswith("python3")
    assert row["bounded_view"]["stdout"] == "data/item.txt\nTARGET_TOKEN=VALUE-1\n"
    assert row["bounded_view"]["stdout_handle"] == "0:persistent-action:stdout"
    assert row["bounded_view"]["workspace_effects"]["path_set_delta_status"] == "complete"
    for duplicate in ("receipt_id", "step", "kind", "success", "summary"):
        assert duplicate not in row["bounded_view"]
    assert "mechanical_description" not in row
    assert row["exact_access"]["handle"] == "receipt:step-0:persistent-action:cmd"
    assert "retrieval" not in row["exact_access"]


def test_causal_hotset_v2_turns_latest_evidence_copy_into_alias_binding_only() -> None:
    projected = continuity_causal_hotset_v2_reanchor(_packet())
    rows = projected["evidence_index"]
    assert [row["receipt_id"] for row in rows] == [
        "step-0:persistent-action:cmd", "step-1:persistent-other:file",
    ]
    latest_alias = rows[0]
    assert latest_alias == {
        "evidence_ref": "evidence:latest",
        "receipt_id": "step-0:persistent-action:cmd",
        "evidence_type": "run_command",
        "currentness": "latest_primary_result",
        "completion_evidence_eligible": True,
        "observation_source": "latest_primary_result",
    }
    assert "exact_access" not in latest_alias
    assert "mechanical_description" not in latest_alias

    # A fresh row not duplicated by latest_primary_result fails safe to the
    # established V1 compact representation rather than being pointer-reduced.
    other = rows[1]
    assert other["mechanical_description"] == "read answer.txt"
    assert other["exact_access"]["handle"] == "receipt:step-1:persistent-other:file"
    assert "bounded_view" not in other


def test_causal_hotset_v2_inherits_fresh_only_policy_and_is_strictly_smaller_than_v1() -> None:
    packet = _packet()
    v1 = project_persistent_context_for_model(packet, mode=CONTINUITY_FRESH_DELTA_V1)
    v2 = project_persistent_context_for_model(packet, mode=CONTINUITY_CAUSAL_HOTSET_V2)
    assert all(row.get("currentness") != "historical_task_evidence" for row in v2["evidence_index"])
    assert len(stable_json(v2).encode("utf-8")) < len(stable_json(v1).encode("utf-8"))
    assert v2 == continuity_causal_hotset_v2_reanchor(packet)


def test_causal_hotset_v2_keeps_unknown_latest_row_description_if_no_bounded_view_exists() -> None:
    packet = _packet()
    row = packet["latest_primary_result"]["outcome_receipts"][0]
    row.pop("bounded_view")
    row["mechanical_description"] = "opaque but factual latest observation"
    projected = continuity_causal_hotset_v2_reanchor(packet)
    latest = projected["latest_primary_result"]["outcome_receipts"][0]
    assert latest["mechanical_description"] == "opaque but factual latest observation"
