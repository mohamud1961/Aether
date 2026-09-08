from __future__ import annotations

from copy import deepcopy
import json

from aether.verifier_provider_projection import (
    compact_verifier_messages_for_provider,
    projection_digest,
    prune_unreachable_local_defs_for_provider,
)


def test_schema_pruning_keeps_transitive_cycle_and_does_not_mutate() -> None:
    schema = {
        "type": "object",
        "properties": {"x": {"$ref": "#/$defs/a"}},
        "$defs": {
            "a": {"allOf": [{"$ref": "#/$defs/b"}]},
            "b": {"items": {"$ref": "#/$defs/a"}},
            "dead": {"type": "string"},
        },
    }
    original = deepcopy(schema)
    pruned, audit = prune_unreachable_local_defs_for_provider(schema)
    assert schema == original
    assert set(pruned["$defs"]) == {"a", "b"}
    assert audit["status"] == "pruned"
    assert audit["removed"] == ["dead"]
    assert audit["bytes_saved"] > 0
    assert audit["before_digest"] == projection_digest(original)


def test_schema_pruning_finds_refs_under_unknown_keywords_and_arrays() -> None:
    schema = {
        "x-custom": [{"nested": {"$ref": "#/$defs/keep"}}],
        "$defs": {
            "keep": {"type": "object", "additionalProperties": {"$ref": "#/$defs/child"}},
            "child": {"type": "string"},
            "dead": {"type": "integer"},
        },
    }
    pruned, _audit = prune_unreachable_local_defs_for_provider(schema)
    assert set(pruned["$defs"]) == {"keep", "child"}


def test_schema_pruning_decodes_json_pointer_names() -> None:
    schema = {
        "allOf": [
            {"$ref": "#/$defs/a~1b"},
            {"$ref": "#/$defs/t~0ilde"},
        ],
        "$defs": {
            "a/b": {"type": "string"},
            "t~ilde": {"type": "integer"},
            "dead": {"type": "null"},
        },
    }
    pruned, audit = prune_unreachable_local_defs_for_provider(schema)
    assert set(pruned["$defs"]) == {"a/b", "t~ilde"}
    assert audit["status"] == "pruned"


def test_schema_pruning_missing_ref_fails_closed() -> None:
    schema = {
        "oneOf": [{"$ref": "#/$defs/missing"}],
        "$defs": {"dead": {"type": "string"}},
    }
    original = deepcopy(schema)
    pruned, audit = prune_unreachable_local_defs_for_provider(schema)
    assert pruned == original
    assert audit["status"] == "fail_closed_unpruned"
    assert audit["bytes_saved"] == 0


def test_schema_pruning_dynamic_local_ref_fails_closed() -> None:
    schema = {
        "$dynamicRef": "#/$defs/live",
        "$defs": {"live": {"type": "string"}, "dead": {"type": "integer"}},
    }
    original = deepcopy(schema)
    pruned, audit = prune_unreachable_local_defs_for_provider(schema)
    assert pruned == original
    assert audit["status"] == "fail_closed_unpruned"


def _authority_messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "verifier authority"},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "verifier_packet": {
                        "task_contract": {"clauses": [{"clause_id": "task:1", "text": "R"}]},
                        "authoritative_check_ids": ["check-1"],
                    },
                    "authoritative_task_prompt": "R",
                },
                sort_keys=True,
            ),
        },
    ]


def _inspection_result(inspection_id: str, excerpt: str) -> dict:
    return {
        "inspection_id": inspection_id,
        "kind": "read_file",
        "path": "/app/out.txt",
        "error": None,
        "observation_valid": True,
        "excerpt": excerpt,
        "observation_status": "ok",
    }


def test_message_compaction_accumulates_exact_inspection_results() -> None:
    messages = _authority_messages()
    messages += [
        {
            "role": "assistant",
            "content": json.dumps({"kind": "inspect", "requests": [{"kind": "read_file"}]}),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "verifier_inspection_results": [_inspection_result("inspection:1", "one")],
                    "available_authoritative_source_refs": ["task:prompt", "inspection:1"],
                    "available_bound_input_refs": ["task:prompt", "inspection:1"],
                    "instruction": "continue",
                },
                sort_keys=True,
            ),
        },
        {
            "role": "assistant",
            "content": json.dumps({"kind": "inspect", "requests": [{"kind": "read_file"}]}),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "verifier_inspection_results": [_inspection_result("inspection:2", "two")],
                    "available_authoritative_source_refs": [
                        "task:prompt",
                        "inspection:1",
                        "inspection:2",
                    ],
                    "available_bound_input_refs": [
                        "task:prompt",
                        "inspection:1",
                        "inspection:2",
                    ],
                    "instruction": "judge now",
                },
                sort_keys=True,
            ),
        },
    ]
    original = deepcopy(messages)
    compact, audit = compact_verifier_messages_for_provider(messages)
    assert messages == original
    assert [row["role"] for row in compact] == ["system", "user", "user"]
    payload = json.loads(compact[-1]["content"])
    assert [row["inspection_id"] for row in payload["verifier_inspection_results"]] == [
        "inspection:1",
        "inspection:2",
    ]
    assert payload["verifier_inspection_results"][0]["excerpt"] == "one"
    assert payload["verifier_inspection_results"][1]["excerpt"] == "two"
    assert payload["instruction"] == "judge now"
    assert payload["available_authoritative_source_refs"][-1] == "inspection:2"
    assert audit["status"] == "compacted"
    assert audit["registered_inspection_count"] == 2
    assert audit["after_bytes"] < audit["before_bytes"]


def test_message_compaction_keeps_immediate_assistant_for_correction() -> None:
    messages = _authority_messages()
    messages += [
        {"role": "assistant", "content": "old inspect request"},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "verifier_inspection_results": [_inspection_result("inspection:1", "one")],
                    "available_authoritative_source_refs": ["task:prompt", "inspection:1"],
                    "available_bound_input_refs": ["task:prompt", "inspection:1"],
                    "instruction": "judge",
                },
                sort_keys=True,
            ),
        },
        {"role": "assistant", "content": "malformed verdict needing correction"},
        {
            "role": "user",
            "content": json.dumps(
                {"instruction": "Correct only the completion evidence shape."},
                sort_keys=True,
            ),
        },
    ]
    compact, audit = compact_verifier_messages_for_provider(messages)
    assert [row["role"] for row in compact] == [
        "system",
        "user",
        "user",
        "assistant",
        "user",
    ]
    evidence = json.loads(compact[2]["content"])
    assert evidence["verifier_inspection_results"][0]["inspection_id"] == "inspection:1"
    assert compact[3]["content"] == "malformed verdict needing correction"
    assert audit["status"] == "compacted"


def test_message_compaction_conflicting_duplicate_fails_closed() -> None:
    messages = _authority_messages()
    for excerpt in ("one", "DIFFERENT"):
        messages += [
            {"role": "assistant", "content": "inspect"},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "verifier_inspection_results": [
                            _inspection_result("inspection:1", excerpt)
                        ],
                        "available_authoritative_source_refs": ["task:prompt", "inspection:1"],
                        "available_bound_input_refs": ["task:prompt", "inspection:1"],
                    },
                    sort_keys=True,
                ),
            },
        ]
    compact, audit = compact_verifier_messages_for_provider(messages)
    assert compact == messages
    assert audit["status"] == "fail_closed_original"
    assert "conflicting duplicate" in audit["error"]


def test_message_compaction_namespace_regression_fails_closed() -> None:
    messages = _authority_messages()
    messages += [
        {"role": "assistant", "content": "inspect"},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "verifier_inspection_results": [_inspection_result("inspection:1", "one")],
                    "available_authoritative_source_refs": ["task:prompt", "inspection:1"],
                    "available_bound_input_refs": ["task:prompt", "inspection:1"],
                },
                sort_keys=True,
            ),
        },
        {"role": "assistant", "content": "inspect again"},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "verifier_inspection_results": [_inspection_result("inspection:2", "two")],
                    "available_authoritative_source_refs": ["task:prompt", "inspection:2"],
                    "available_bound_input_refs": ["task:prompt", "inspection:2"],
                },
                sort_keys=True,
            ),
        },
    ]
    compact, audit = compact_verifier_messages_for_provider(messages)
    assert compact == messages
    assert audit["status"] == "fail_closed_original"
    assert "regressed" in audit["error"]



def test_initial_authority_keeps_only_replayable_historical_citations() -> None:
    messages = _authority_messages()
    initial = json.loads(messages[1]["content"])
    initial["verifier_packet"]["primary_submission"] = {
        "claim": "candidate is complete",
        "task_state_generation": 3,
        "evidence_bindings": [
            {"evidence_ref": "e1", "receipt_id": "step-1:write", "role": "historical_support"},
            {"evidence_ref": "e2", "receipt_id": "step-3:cmd", "role": "current_anchor"},
        ],
        "cited_evidence_index": [
            {
                "receipt_id": "step-1:write",
                "exact_receipt_handle": "receipt:step-1:write",
                "kind": "write_file",
                "success": True,
                "evidence_role": "historical_support",
                "receipt_task_state_generation": 1,
                "submission_task_state_generation": 3,
                "current_payload_projection": {"path": "out.txt", "bytes": 3},
            },
            {
                "receipt_id": "step-3:cmd",
                "exact_receipt_handle": "receipt:step-3:cmd",
                "kind": "run_command",
                "success": True,
                "evidence_role": "current_anchor",
                "receipt_task_state_generation": 3,
                "submission_task_state_generation": 3,
            },
            {
                "receipt_id": "step-0:read",
                "exact_receipt_handle": "receipt:step-0:read",
                "kind": "read_file",
                "success": True,
                "evidence_role": "historical_support",
                "receipt_task_state_generation": 0,
                "submission_task_state_generation": 3,
                "current_payload_projection": {
                    "path": "reference.txt",
                    "bytes": 9,
                    "content_hash": "ab12",
                    "excerpt": "not provider authority",
                },
            },
        ],
    }
    messages[1]["content"] = json.dumps(initial, sort_keys=True)
    compact, audit = compact_verifier_messages_for_provider(messages)
    assert audit["status"] == "authority_compacted"
    projected = json.loads(compact[1]["content"])["verifier_packet"]["primary_submission"]
    assert "claim" not in projected
    assert projected["task_state_generation"] == 3
    assert "evidence_bindings" not in projected
    assert len(projected["cited_evidence_index"]) == 1
    cited = projected["cited_evidence_index"][0]
    assert cited["receipt_id"] == "step-0:read"
    assert cited["exact_receipt_handle"] == "receipt:step-0:read"
    assert cited["current_payload_projection"] == {
        "path": "reference.txt",
        "bytes": 9,
        "content_hash": "ab12",
    }


def test_initial_authority_drops_historical_read_without_content_identity() -> None:
    messages = _authority_messages()
    initial = json.loads(messages[1]["content"])
    initial["verifier_packet"]["primary_submission"] = {
        "claim": "candidate is complete",
        "task_state_generation": 2,
        "cited_evidence_index": [{
            "receipt_id": "step-0:read",
            "exact_receipt_handle": "receipt:step-0:read",
            "kind": "read_file",
            "success": True,
            "evidence_role": "historical_support",
            "receipt_task_state_generation": 0,
            "submission_task_state_generation": 2,
            "current_payload_projection": {"path": "reference.txt", "bytes": 9},
        }],
    }
    messages[1]["content"] = json.dumps(initial, sort_keys=True)
    compact, _ = compact_verifier_messages_for_provider(messages)
    projected = json.loads(compact[1]["content"])["verifier_packet"]["primary_submission"]
    assert projected == {"task_state_generation": 2}



def test_provider_navigation_deduplicates_file_aliases_and_keeps_output_handles() -> None:
    messages = _authority_messages()
    initial = json.loads(messages[1]["content"])
    initial["verifier_phase_budget"] = {"max_model_calls": 4, "max_direct_requests_per_batch": 4}
    initial["verifier_packet"].update({
        "schema_version": "pcr_verifier_model_view.v1",
        "stable_envmap": {"facts": {"workspace_root": "/app", "network_scope": "unknown"}},
        "state_inspection_handles": [
            {"kind": "file", "handle": "file:out.txt", "path": "out.txt"},
            {"kind": "file", "handle": "out.txt", "path": "out.txt"},
            {"kind": "output", "handle": "2:stdout", "stream": "stdout", "bytes": 77},
        ],
    })
    messages[1]["content"] = json.dumps(initial, sort_keys=True)
    compact, _ = compact_verifier_messages_for_provider(messages)
    payload = json.loads(compact[1]["content"])
    packet = payload["verifier_packet"]
    assert "schema_version" not in packet
    assert "stable_envmap" not in packet
    assert "verifier_phase_budget" not in payload
    assert packet["state_inspection_handles"] == [
        {"kind": "file", "path": "out.txt"},
        {"kind": "output", "handle": "2:stdout", "stream": "stdout"},
    ]


def test_direct_evidence_drops_request_boilerplate_but_keeps_provenance() -> None:
    messages = _authority_messages() + [
        {"role": "assistant", "content": json.dumps({
            "kind": "inspect",
            "requests": [{
                "kind": "read_file", "path": "out.txt", "offset": 0, "span": 100,
                "clause_ids": ["task:1"], "proof_ids": ["proof:1"],
            }],
        })},
        {"role": "user", "content": json.dumps({
            "verifier_inspection_results": [{
                "inspection_id": "inspection:1", "request_id": "inspect-0",
                "kind": "read_file", "path": "out.txt", "observation_valid": True,
                "observation_type": "file", "excerpt": "exact bytes", "content_chars": 11,
                "result_hash": "a" * 64, "eligible_for_basis": True,
                "eligible_for_proof": True, "observation_origin": "kernel",
                "observed_task_state_generation": 4,
            }],
            "available_authoritative_source_refs": ["task:prompt", "inspection:1"],
            "available_bound_input_refs": ["task:prompt", "inspection:1"],
        })},
    ]
    compact, _ = compact_verifier_messages_for_provider(messages)
    row = json.loads(compact[-1]["content"])["verifier_inspection_results"][0]
    assert row["inspection_id"] == "inspection:1"
    assert row["path"] == "out.txt"
    assert row["excerpt"] == "exact bytes"
    assert row["result_hash"] == "a" * 64
    assert row["eligible_for_basis"] is True and row["eligible_for_proof"] is True
    assert row["observation_origin"] == "kernel"
    assert row["observed_task_state_generation"] == 4
    assert "request_id" not in row and "observation_type" not in row and "content_chars" not in row
    assert row["requested"] == {"clause_ids": ["task:1"], "proof_ids": ["proof:1"]}


def test_derived_evidence_preserves_verifier_authored_method_and_command() -> None:
    messages = _authority_messages() + [
        {"role": "assistant", "content": json.dumps({
            "kind": "inspect",
            "requests": [{
                "kind": "overlay_run_command",
                "clause_ids": ["task:1"],
                "proof_ids": ["proof:1"],
                "verification_plan": {"claim": "derive independently", "basis": [{"ref": "inspection:0"}]},
                "execution": {"kind": "overlay_run_command", "command": "python check.py"},
            }],
        })},
        {"role": "user", "content": json.dumps({
            "verifier_inspection_results": [{
                "inspection_id": "inspection:2", "kind": "overlay_run_command",
                "observation_valid": True, "stdout": "PASS", "exit_code": 0,
                "result_hash": "b" * 64, "eligible_for_basis": True,
                "eligible_for_proof": True, "observation_origin": "verifier_overlay",
            }],
            "available_authoritative_source_refs": ["task:prompt", "inspection:2"],
            "available_bound_input_refs": ["task:prompt", "inspection:2"],
        })},
    ]
    compact, _ = compact_verifier_messages_for_provider(messages)
    row = json.loads(compact[-1]["content"])["verifier_inspection_results"][0]
    assert row["requested"]["verification_plan"]["claim"] == "derive independently"
    assert row["requested"]["execution"]["command"] == "python check.py"
