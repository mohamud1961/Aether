from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

from aether.pcr_verifier_context import (
    pcr_verifier_model_packet,
    verifier_packet_for_model,
)
from aether.providers.azure_model import _pcr_verifier_native_tool_for_input


def _packet() -> dict:
    raw = "Create out.txt containing hello."
    return {
        "schema_version": "verifier_packet.v3",
        "step": 7,
        "reason": "solver_submit",
        "raw_user_task": raw,
        "raw_task_sha256": "a" * 64,
        "raw_task_binding": {"contract_sha256": "b" * 64},
        "runtime_identity": {"run_id": "run-1", "source_commit": "c" * 40},
        "task_contract_identity": "d" * 64,
        "task_contract_sha256": "e" * 64,
        "task_contract": {
            "schema_version": "pcr_v0_source_clauses_v1",
            "raw_task_prompt": raw,
            "contract_identity": "f" * 64,
            "clauses": [
                {"clause_id": "task:001:abc", "text": "Create out.txt.", "exact_atoms": ["out.txt"]},
                {"clause_id": "task:002:def", "text": "It must contain hello.", "exact_atoms": []},
            ],
        },
        "open_obligations": [
            {
                "obligation_id": "task:001:abc",
                "kind": "task",
                "status": "open",
                "description": raw,
                "evidence_ids": [],
            }
        ],
        "primary_submission": {
            "claim": "out.txt contains hello",
            "claim_id": "claim-1",
            "task_state_generation": 3,
            "evidence_set_sha256": "1" * 64,
            "evidence_bindings": [
                {"evidence_ref": "evidence:1", "receipt_id": "step-6:cmd", "role": "current_anchor"}
            ],
            "cited_evidence": [
                {
                    "receipt_id": "step-6:cmd",
                    "exact_receipt_handle": "receipt:step-6:cmd",
                    "kind": "run_command",
                    "success": True,
                    "state_change": False,
                    "evidence_role": "current_anchor",
                    "receipt_task_state_generation": 3,
                    "submission_task_state_generation": 3,
                    "summary": "command exit=0: very long solver-authored validation command",
                    "current_payload_projection": {
                        "exit_code": 0,
                        "stdout_handle": "6:cmd:stdout",
                        "stderr_handle": "6:cmd:stderr",
                        "stdout_bytes": 20,
                        "stderr_bytes": 0,
                        "stdout_full": "solver says PASS",
                        "stderr_full": "",
                        "state_delta": {"large": "narrative"},
                    },
                }
            ],
        },
        "dynamic_state": {
            "files": {"out.txt": {"status": "modified", "bytes": 5}},
            "latest_result": {
                "kind": "run_command",
                "stdout_handle": "7:latest:stdout",
                "stderr_handle": "7:latest:stderr",
            },
        },
        "stable_envmap": {
            "schema_version": "stable_envmap.v1",
            "sha256": "2" * 64,
            "facts": {
                "workspace_root": "/app",
                "network_scope": "loopback_only",
                "resource_limits": {"cpus": 1},
                "file_tree": "/app\n",
                "capabilities": {"shell": {"tool_names": ["run_command"]}},
                "file_map_summary": {"large": "metadata"},
            },
        },
        "authoritative_check_ids": ["check-a", "check-b"],
        "state_inspection_handles": [
            {"kind": "file", "handle": "file:out.txt", "path": "out.txt", "bytes": 5},
            {"kind": "output", "handle": "6:cmd:stdout", "stream": "stdout", "bytes": 20},
            {"kind": "output", "handle": "6:cmd:stderr", "stream": "stderr", "bytes": 0},
            {"kind": "output", "handle": "7:latest:stdout", "stream": "stdout", "bytes": 4},
            {"kind": "output", "handle": "7:latest:stderr", "stream": "stderr", "bytes": 0},
            {"kind": "output", "handle": "2:stale:stdout", "stream": "stdout", "bytes": 999},
        ],
        "active_findings": [
            {
                "finding_id": "vf-1",
                "verdict": "uncertain_missing_evidence",
                "priority": "blocking",
                "status": "active",
                "summary": "Current behavior is not independently established.",
                "applies_to": ["out.txt"],
                "evidence": ["previous observation"],
                "supporting_inspection_ids": ["inspection:old"],
                "repair_instruction": "Run this exact command.",
                "repair_condition": "Follow the previous model's strategy.",
                "required_evidence_route": "overlay_run_command",
                "age_steps": 10,
            }
        ],
        "evidence_requirements": {"false_positive_risks": ["self confirmation"]},
        "compiled_proof_requirements": [{"proof_id": "proof-1"}],
        "verification_task_facts": [{"id": "task-fact:1", "excerpt": "hello"}],
    }


def test_projection_preserves_task_current_state_claim_and_inspectability() -> None:
    packet = _packet()
    original = deepcopy(packet)
    view = pcr_verifier_model_packet(packet)

    assert packet == original
    assert view["task_contract"]["clauses"] == packet["task_contract"]["clauses"]
    assert view["dynamic_state"] == packet["dynamic_state"]
    assert view["primary_submission"]["claim"] == "out.txt contains hello"
    assert view["primary_submission"]["evidence_bindings"] == packet["primary_submission"]["evidence_bindings"]
    assert view["evidence_requirements"] == packet["evidence_requirements"]
    assert view["authoritative_check_ids"] == ["check-a", "check-b"]
    assert view["compiled_proof_requirements"] == packet["compiled_proof_requirements"]
    assert view["verification_task_facts"] == packet["verification_task_facts"]

    handles = {row["handle"] for row in view["state_inspection_handles"]}
    assert "file:out.txt" in handles
    assert "6:cmd:stdout" in handles
    assert "6:cmd:stderr" in handles
    assert "7:latest:stdout" in handles
    assert "7:latest:stderr" in handles
    assert "2:stale:stdout" not in handles


def test_projection_removes_custody_noise_solver_scripts_and_prior_strategy() -> None:
    view = pcr_verifier_model_packet(_packet())

    for key in (
        "raw_user_task", "raw_task_sha256", "raw_task_binding", "runtime_identity",
        "task_contract_identity", "task_contract_sha256",
    ):
        assert key not in view
    assert "raw_task_prompt" not in view["task_contract"]
    assert "contract_identity" not in view["task_contract"]
    assert "description" not in view["open_obligations"][0]

    cited = view["primary_submission"]["cited_evidence_index"][0]
    assert "summary" not in cited
    payload = cited["current_payload_projection"]
    assert "stdout_full" not in payload
    assert "stderr_full" not in payload
    assert "state_delta" not in payload
    assert payload["stdout_handle"] == "6:cmd:stdout"

    finding = view["active_findings"][0]
    assert finding["summary"] == "Current behavior is not independently established."
    assert finding["evidence"] == ["previous observation"]
    assert "repair_instruction" not in finding
    assert "repair_condition" not in finding
    assert "required_evidence_route" not in finding
    assert "age_steps" not in finding

    env_facts = view["stable_envmap"]["facts"]
    assert env_facts["workspace_root"] == "/app"
    assert "capabilities" not in env_facts
    assert "file_map_summary" not in env_facts


def test_model_projection_deduplicates_task_text_for_every_protocol() -> None:
    """Custody copies of the task text must never double as a model payload."""
    packet = _packet()
    packet["raw_user_task"] = "RAW TASK BYTES"
    compiled = SimpleNamespace()
    view = verifier_packet_for_model(compiled, packet)
    assert view is not packet
    assert "raw_user_task" not in view
    assert "raw_task_prompt" not in view.get("task_contract", {})
    assert view["task_contract"]["clauses"] == packet["task_contract"]["clauses"]
    # Custody original stays untouched for the ledger receipt.
    assert packet["raw_user_task"] == "RAW TASK BYTES"
    assert packet["task_contract"]["raw_task_prompt"] == packet["raw_user_task"].replace("RAW TASK BYTES", "Create out.txt containing hello.")


def test_projection_deduplicates_identical_hot_handles() -> None:
    packet = _packet()
    packet["state_inspection_handles"].append(
        {"kind": "file", "handle": "file:out.txt", "path": "out.txt", "bytes": 5}
    )
    view = pcr_verifier_model_packet(packet)
    keys = [(row.get("kind"), row.get("handle"), row.get("path")) for row in view["state_inspection_handles"]]
    assert len(keys) == len(set(keys))



def test_projection_preserves_empty_authoritative_check_namespace() -> None:
    packet = _packet()
    packet["authoritative_check_ids"] = []
    view = pcr_verifier_model_packet(packet)
    assert "authoritative_check_ids" in view
    assert view["authoritative_check_ids"] == []


def test_projected_namespace_drives_exact_pcr_native_rerun_schema() -> None:
    packet = _packet()
    view = pcr_verifier_model_packet(packet)
    user_input = [{
        "role": "user",
        "content": json.dumps({"verifier_packet": view}, sort_keys=True),
    }]
    tool, ids = _pcr_verifier_native_tool_for_input(user_input)
    assert ids == ("check-a", "check-b")
    schema = tool["parameters"]
    assert schema["$defs"]["pcr_rerun_check_request"]["properties"]["check_id"] == {
        "type": "string", "enum": ["check-a", "check-b"],
    }


def test_projected_empty_namespace_removes_entire_unavailable_derived_turn() -> None:
    packet = _packet()
    packet["authoritative_check_ids"] = []
    view = pcr_verifier_model_packet(packet)
    user_input = [{
        "role": "user",
        "content": json.dumps({"verifier_packet": view}, sort_keys=True),
    }]
    tool, ids = _pcr_verifier_native_tool_for_input(user_input)
    assert ids == ()
    schema = tool["parameters"]
    assert "derived_inspection_request" not in schema["$defs"]
    assert "derived_inspect_turn" not in schema["$defs"]
    assert "#/$defs/derived_inspect_turn" not in {
        row["$ref"] for row in schema["properties"]["turn"]["anyOf"]
    }


def test_historical_cited_evidence_uses_exact_receipt_identity_not_live_file_snapshot_metadata() -> None:
    packet = _packet()
    packet["primary_submission"]["cited_evidence"].append({
        "receipt_id": "step-1:read:out.txt",
        "exact_receipt_handle": "receipt:step-1:read:out.txt",
        "kind": "read_file",
        "success": True,
        "state_change": False,
        "evidence_role": "historical_support",
        "receipt_task_state_generation": 0,
        "submission_task_state_generation": 3,
        "current_payload_projection": {
            "path": "out.txt",
            "file_handle": "file:out.txt",
            "bytes": 5,
            "content_hash": "deadbeefdeadbeef",
            "excerpt": "hello",
        },
    })
    view = pcr_verifier_model_packet(packet)
    historical = view["primary_submission"]["cited_evidence_index"][1]
    assert historical["exact_receipt_handle"] == "receipt:step-1:read:out.txt"
    assert historical["receipt_task_state_generation"] == 0
    projection = historical["current_payload_projection"]
    assert projection["path"] == "out.txt"
    assert projection["content_hash"] == "deadbeefdeadbeef"
    assert projection["bytes"] == 5
    assert "file_handle" not in projection
    assert "excerpt" not in projection

    # Live path handles remain navigation only: no historical/current byte/hash
    # identity is attached to the ambiguous file:{path} token.
    file_row = next(row for row in view["state_inspection_handles"] if row["kind"] == "file")
    assert file_row == {"kind": "file", "handle": "file:out.txt", "path": "out.txt"}


def test_native_verifier_schema_enums_exact_task_clause_namespace() -> None:
    packet = _packet()
    view = pcr_verifier_model_packet(packet)
    messages = [{
        "role": "user",
        "content": json.dumps({"verifier_packet": view}, sort_keys=True),
    }, {
        "role": "user",
        "content": json.dumps({
            "available_authoritative_source_refs": ["inspection:1"],
            "available_bound_input_refs": ["inspection:1"],
        }, sort_keys=True),
    }]
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    defs = tool["parameters"]["$defs"]
    expected = ["task:001:abc", "task:002:def"]
    command = defs["pcr_run_verifier_command_request"]
    assert command["properties"]["clause_ids"]["items"] == {
        "type": "string", "enum": expected,
    }
    completion = defs["completion_evidence"]
    assert completion["properties"]["clause_ids"]["items"] == {
        "type": "string", "enum": expected,
    }
    direct_clause = defs["pcr_direct_locator_request"]["properties"]["clause_ids"]
    assert direct_clause["anyOf"][0]["items"] == {
        "type": "string", "enum": expected,
    }


def test_native_verifier_clause_namespace_conflict_fails_closed() -> None:
    packet = _packet()
    first = pcr_verifier_model_packet(packet)
    second = deepcopy(first)
    second["task_contract"]["clauses"][0]["clause_id"] = "task:999:evil"
    messages = [
        {"role": "user", "content": json.dumps({"verifier_packet": first}, sort_keys=True)},
        {"role": "user", "content": json.dumps({"verifier_packet": second}, sort_keys=True)},
    ]
    import pytest
    from aether.providers.azure_model import AzureProviderOutputError
    with pytest.raises(AzureProviderOutputError, match="provider_pcr_verifier_clause_namespace_conflict"):
        _pcr_verifier_native_tool_for_input(messages)
