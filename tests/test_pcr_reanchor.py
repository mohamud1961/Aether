from __future__ import annotations

from copy import deepcopy

import pytest

from aether.pcr_reanchor import (
    CONTINUITY_FRESH_DELTA_V1,
    CURRENT_FULL,
    REFINED_M,
    continuity_fresh_delta_reanchor,
    project_pcr_context_for_model,
    refined_m_reanchor,
)
from aether.runtime_ir import stable_json


def _packet() -> dict[str, object]:
    return {
        "latest_primary_result": {
            "status": "observed",
            "action_id": "pcr-action-7",
            "outcome_receipt_ids": ["r-latest"],
            "outcome_receipts": [{"receipt_id": "r-latest", "bounded_view": {"stdout": "ok"}}],
        },
        "runtime_identity": {
            "task_id": "task-a",
            "run_id": "run-a",
            "primary_agent_id": "primary:run-a",
            "workspace_id": "/app",
            "environment_id": "env-a",
            "raw_task_sha256": "9" * 64,
            "source_commit": "a" * 40,
            "runtime_manifest_sha256": "b" * 64,
            "source_custody_complete": True,
        },
        "available_capabilities": {
            "action_owners": {
                "read_file": ["filesystem"],
                "run_command": ["terminal"],
            }
        },
        "budgets": {
            "max_kernel_steps": 30,
            "used_solver_provider_turns": 8,
            "remaining_kernel_steps": 22,
            "other_budget_admin": "drop-me",
        },
        "evidence_index": [
            {
                "evidence_ref": "evidence:abc",
                "receipt_id": "r-evidence",
                "evidence_type": "run_command",
                "originating_action_id": "pcr-action-6",
                "mechanical_description": "tests passed",
                "success": True,
                "state_change": False,
                "failure_class": "",
                "step": 6,
                "currentness": "historical_task_evidence",
                "completion_evidence_eligible": True,
                "task_id": "task-a",
                "run_id": "run-a",
                "workspace_id": "/app",
                "bounded_view": {"stdout": "large duplicated payload"},
                "exact_access": {
                    "state": "receipt_handle_exact",
                    "handle": "receipt:r-evidence",
                    "sha256": "c" * 64,
                    "bytes": 123,
                    "related_handles": [{"handle": "output:1", "stream": "stdout", "bytes": 10}],
                    "retrieval": {
                        "action_kind": "read_output",
                        "arguments": {"handle": "receipt:r-evidence"},
                        "paging_supported": True,
                    },
                },
            }
        ],
        "linked_history": {
            "obligation_status": [{"clause_id": "task:1", "status": "open"}],
            "monitor_alerts": [{"code": "x"}],
            "live_processes": [{"process_id": "p1"}],
            "artifacts_present": ["/app/result.txt"],
            "planned_checks": [{"check_id": "c1"}],
            "pending_checks": [{"label": "exists:/app/result.txt", "passed": None}],
            "recent_progress": [{"receipt_id": "old"}],
            "pcr_context_boundary": {"kernel_strategy_guidance_exposed": False},
        },
        "unresolved_runtime_facts": [
            {
                "kind": "source_custody_gap",
                "field": "source_commit",
                "state": "not_supplied",
                "authority": "runtime_identity",
            },
            {
                "kind": "mechanical_failure",
                "receipt_id": "r-failure",
                "receipt_kind": "run_command",
                "failure_class": "exit_nonzero",
                "summary": "pytest failed",
                "step": 5,
                "originating_action_id": "pcr-action-5",
                "resolution_state": "no_later_success_for_same_action_observed",
                "exact_access": {
                    "state": "receipt_handle_exact",
                    "handle": "receipt:r-failure",
                    "sha256": "d" * 64,
                    "bytes": 456,
                    "related_handles": [{"handle": "output:failure", "stream": "stderr"}],
                    "retrieval": {
                        "action_kind": "read_output",
                        "arguments": {"handle": "receipt:r-failure"},
                        "paging_supported": True,
                    },
                },
            },
            {
                "kind": "latest_result_access_gap",
                "state": "missing_indexed_receipt",
                "authority": "primary_action_result_index",
            },
        ],
        "open_completion_findings": [
            {"finding_id": "vf-1", "summary": "clean HTML preservation not established"}
        ],
        "submit_reentry_gate": {
            "active_finding_count": 1,
            "submit_reentry_gate": "awaiting_relevant_evidence",
        },
        "self_extension": {
            "enabled": True,
            "task_local_dir": "/app/.aether_tools",
            "smoke_test_required": True,
            "trust_for_completion": False,
            "current_helpers": [{"path": "/app/.aether_tools/render.py", "generation": 2}],
            "omitted_older_helper_count": 1,
            "execution_guidance": "redundant provider-facing prose",
        },
        "context_budget": {
            "within_budget": True,
            "serialized_chars": 99999,
        },
    }


def test_current_full_is_exact_noop_object_and_serialization() -> None:
    packet = _packet()
    before = stable_json(packet)
    projected = project_pcr_context_for_model(packet, mode=CURRENT_FULL)
    assert projected is packet
    assert stable_json(projected) == before


def test_refined_m_keeps_canonical_section_names_and_does_not_mutate_input() -> None:
    packet = _packet()
    snapshot = deepcopy(packet)
    projected = refined_m_reanchor(packet)

    assert packet == snapshot
    assert projected["latest_primary_result"] == packet["latest_primary_result"]
    assert projected["available_capabilities"] == packet["available_capabilities"]
    assert projected["linked_history"]["obligation_status"] == packet["linked_history"]["obligation_status"]
    assert projected["open_completion_findings"] == packet["open_completion_findings"]
    assert projected["submit_reentry_gate"] == packet["submit_reentry_gate"]
    assert projected["runtime_identity"] == {
        "task_id": "task-a",
        "run_id": "run-a",
        "primary_agent_id": "primary:run-a",
        "workspace_id": "/app",
        "environment_id": "env-a",
    }
    assert projected["budgets"] == {
        "max_kernel_steps": 30,
        "used_solver_provider_turns": 8,
        "remaining_kernel_steps": 22,
    }
    assert "runtime_scope" not in projected
    assert "reality_state" not in projected
    assert "model_evidence_bindings" not in projected
    assert "context_budget" not in projected
    assert "recent_progress" not in projected["linked_history"]
    assert "pcr_context_boundary" not in projected["linked_history"]


def test_refined_m_preserves_every_evidence_row_alias_receipt_and_nested_exact_access_identity() -> None:
    packet = _packet()
    projected = refined_m_reanchor(packet)
    assert len(projected["evidence_index"]) == len(packet["evidence_index"])
    row = projected["evidence_index"][0]
    assert row["evidence_ref"] == "evidence:abc"
    assert row["receipt_id"] == "r-evidence"
    assert row["originating_action_id"] == "pcr-action-6"
    assert row["completion_evidence_eligible"] is True
    assert row["exact_access"] == {
        "state": "receipt_handle_exact",
        "handle": "receipt:r-evidence",
        "sha256": "c" * 64,
        "bytes": 123,
        "related_handles": [{"handle": "output:1", "stream": "stdout", "bytes": 10}],
    }
    assert "bounded_view" not in row
    assert "retrieval" not in row["exact_access"]


def test_refined_m_removes_source_custody_gap_but_preserves_failure_semantics_and_exact_access() -> None:
    facts = refined_m_reanchor(_packet())["unresolved_runtime_facts"]
    assert all(row.get("kind") != "source_custody_gap" for row in facts)
    failure = next(row for row in facts if row.get("kind") == "mechanical_failure")
    assert failure == {
        "kind": "mechanical_failure",
        "receipt_id": "r-failure",
        "receipt_kind": "run_command",
        "failure_class": "exit_nonzero",
        "summary": "pytest failed",
        "step": 5,
        "originating_action_id": "pcr-action-5",
        "resolution_state": "no_later_success_for_same_action_observed",
        "exact_access": {
            "state": "receipt_handle_exact",
            "handle": "receipt:r-failure",
            "sha256": "d" * 64,
            "bytes": 456,
            "related_handles": [{"handle": "output:failure", "stream": "stderr"}],
        },
    }
    other = next(row for row in facts if row.get("kind") == "latest_result_access_gap")
    assert other == {
        "kind": "latest_result_access_gap",
        "state": "missing_indexed_receipt",
        "authority": "primary_action_result_index",
    }


def test_refined_m_preserves_dynamic_helpers_and_irreducible_policy_only() -> None:
    helper = refined_m_reanchor(_packet())["self_extension"]
    assert helper == {
        "enabled": True,
        "task_local_dir": "/app/.aether_tools",
        "smoke_test_required": True,
        "trust_for_completion": False,
        "current_helpers": [{"path": "/app/.aether_tools/render.py", "generation": 2}],
        "omitted_older_helper_count": 1,
    }


def test_refined_m_raw_task_and_source_custody_are_not_duplicated_in_dynamic_identity() -> None:
    identity = refined_m_reanchor(_packet())["runtime_identity"]
    assert "raw_task_sha256" not in identity
    assert "source_commit" not in identity
    assert "runtime_manifest_sha256" not in identity
    assert "source_custody_complete" not in identity


def test_unknown_reanchor_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported PCR Solver re-anchor mode"):
        project_pcr_context_for_model(_packet(), mode="unknown")


def test_refined_mode_dispatches_to_refined_projection() -> None:
    packet = _packet()
    assert project_pcr_context_for_model(packet, mode=REFINED_M) == refined_m_reanchor(packet)


def test_continuity_fresh_delta_drops_only_historical_evidence_without_mutating_canonical_packet() -> None:
    packet = _packet()
    packet["evidence_index"] = [
        *packet["evidence_index"],
        {
            "evidence_ref": "evidence:latest",
            "receipt_id": "r-latest-evidence",
            "evidence_type": "run_command",
            "originating_action_id": "pcr-action-7",
            "mechanical_description": "fresh result",
            "success": True,
            "state_change": True,
            "failure_class": "",
            "step": 7,
            "currentness": "latest_primary_result",
            "completion_evidence_eligible": True,
            "exact_access": {"state": "receipt_handle_exact", "handle": "receipt:r-latest-evidence"},
        },
        {
            "evidence_ref": "evidence:future-tag",
            "receipt_id": "r-future-tag",
            "evidence_type": "read_file",
            "step": 7,
            "currentness": "kernel_current_fact_v2",
            "completion_evidence_eligible": True,
        },
    ]
    snapshot = deepcopy(packet)
    projected = continuity_fresh_delta_reanchor(packet)
    assert packet == snapshot
    assert [row.get("receipt_id") for row in projected["evidence_index"]] == [
        "r-latest-evidence", "r-future-tag"
    ]
    assert projected["latest_primary_result"] == packet["latest_primary_result"]
    assert projected["unresolved_runtime_facts"] == refined_m_reanchor(packet)["unresolved_runtime_facts"]
    assert projected["open_completion_findings"] == packet["open_completion_findings"]
    assert projected["submit_reentry_gate"] == packet["submit_reentry_gate"]


def test_continuity_fresh_delta_is_strictly_smaller_when_historical_evidence_exists() -> None:
    packet = _packet()
    packet["evidence_index"] = packet["evidence_index"] * 8
    refined = stable_json(refined_m_reanchor(packet))
    fresh = stable_json(continuity_fresh_delta_reanchor(packet))
    assert len(fresh.encode("utf-8")) < len(refined.encode("utf-8"))
    assert packet["evidence_index"]


def test_continuity_fresh_delta_mode_dispatches_to_fresh_projection() -> None:
    packet = _packet()
    assert project_pcr_context_for_model(packet, mode=CONTINUITY_FRESH_DELTA_V1) == continuity_fresh_delta_reanchor(packet)
