from __future__ import annotations

from hashlib import sha256
import json
from types import SimpleNamespace

import jsonschema
import pytest

from aether.inspection_registry import admissible_verdict_refs, register_inspection_results
from aether.ledger import ExecutionLedger, Receipt
from aether.providers.azure_model import (
    AzureProviderOutputError,
    _pcr_verifier_cited_receipt_handles_from_input,
    _pcr_verifier_completed_cited_receipt_handles_from_input,
    _pcr_verifier_native_tool_for_input,
    canonicalize_verifier_native_tool_output,
    unwrap_verifier_direct_turn,
)
from aether.verifier_inspector import (
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
)
from aether.verify_inspection_requests import (
    _basis_refs_from_inspections,
    _refs_from_inspections,
)


class _Executor:
    pass


def _compiled():
    return SimpleNamespace(planned_checks=lambda: ())


def _envmap():
    return SimpleNamespace(workspace_root="/app")


def _read_receipt(
    receipt_id: str,
    content: str,
    *,
    step: int = 1,
    include_content: bool = True,
    excerpt: str | None = None,
    hash_prefix: int | None = None,
) -> Receipt:
    digest = sha256(content.encode("utf-8", "replace")).hexdigest()
    if hash_prefix:
        digest = digest[:hash_prefix]
    payload = {
        "path": "config.txt",
        "bytes": len(content.encode("utf-8", "replace")),
        "content_hash": digest,
        "excerpt": content if excerpt is None else excerpt,
        "file_handle": "file:config.txt",
    }
    if include_content:
        payload["content"] = content
    return Receipt(
        receipt_id=receipt_id,
        step=step,
        kind="read_file",
        success=True,
        summary="read config.txt",
        payload=payload,
    )


def _claim_receipt(
    source: Receipt,
    *,
    role: str = "historical_support",
    source_generation: int = 0,
    submission_generation: int = 1,
    include_source: bool = True,
) -> Receipt:
    source_ids = [source.receipt_id] if include_source else []
    bindings = ([{
        "evidence_ref": "evidence:source",
        "receipt_id": source.receipt_id,
        "role": role,
        "task_state_generation": source_generation,
    }] if include_source else [])
    return Receipt(
        receipt_id=f"step-4:primary_submission_claim:claim:test:g{submission_generation}",
        step=4,
        kind="primary_submission_claim",
        success=True,
        summary="only the intended bytes changed",
        payload={
            "claim": "only the intended bytes changed",
            "evidence_receipt_ids": source_ids,
            "evidence_exact_handles": [f"receipt:{item}" for item in source_ids],
            "evidence_bindings": bindings,
            "task_state_generation": submission_generation,
        },
    )


def _ledger_with_historical_read(content: str = "mode=dev\n") -> tuple[ExecutionLedger, Receipt]:
    ledger = ExecutionLedger()
    source = _read_receipt("step-1:read:config", content)
    ledger.record(source)
    ledger.record(Receipt(
        receipt_id="step-2:write:config",
        step=2,
        kind="write_file",
        success=True,
        summary="mutated config",
        state_change=True,
        payload={"path": "config.txt", "modified_paths": ["config.txt"]},
    ))
    ledger.record(_claim_receipt(source))
    assert ledger.task_state_generation() == 1
    return ledger, source


def _execute(
    ledger: ExecutionLedger, handle: str, *, proof_ids: tuple[str, ...] = (),
    offset: int = 0, span: int = 8192,
) -> tuple[VerifierInspectionRequest, dict]:
    request = VerifierInspectionRequest(
        request_id="cited",
        kind="read_output",
        handle=handle,
        offset=offset,
        span=span,
        proof_ids=proof_ids,
    )
    result = execute_verifier_inspection_requests(
        (request,),
        compiled=_compiled(),
        ledger=ledger,
        executor=_Executor(),
        envmap=_envmap(),
        overlay=None,
        hooks=None,
    )[0]
    return request, result


def test_exact_cited_historical_read_is_snapshot_bound_and_exact_contract() -> None:
    original = "header=alpha\nmode=dev\nfooter=omega\n"
    ledger, source = _ledger_with_historical_read(original)
    request, result = _execute(ledger, f"receipt:{source.receipt_id}", proof_ids=("proof-x",))

    assert result["kind"] == "read_cited_receipt"
    assert result["excerpt"] == original
    assert result["source_receipt_id"] == source.receipt_id
    assert result["source_receipt_kind"] == "read_file"
    assert result["evidence_role"] == "historical_support"
    assert result["source_task_state_generation"] == 0
    assert result["submission_task_state_generation"] == 1
    assert result["snapshot_verified"] is True
    assert result["observation_origin"] == "ledger_cited_receipt"
    assert result["content_hash"] == sha256(original.encode()).hexdigest()
    assert result["total_chars"] == len(original)
    assert result["returned_chars"] == len(original)
    assert result["next_offset"] == len(original)
    assert result["more_available"] is False
    assert result["snapshot_complete"] is True

    enriched = register_inspection_results(
        (request,),
        (result,),
        ledger=ledger,
        step=4,
        requester="model_verifier",
        executor=_Executor(),
        overlay=_Executor(),
        packet_signature="packet",
    )[0]
    inspection_id = enriched["inspection_id"]
    receipt = next(item for item in ledger.all_receipts() if item.receipt_id == inspection_id)
    assert receipt.payload["route_kind"] == "read_cited_receipt"
    assert receipt.payload["target_identity"] == f"receipt:{source.receipt_id}"
    assert receipt.payload["task_state_generation"] == 1
    assert receipt.payload["route_parameters"]["handle"] == f"receipt:{source.receipt_id}"
    assert receipt.payload["admissibility"] == "direct_admissible"
    assert receipt.payload["evidence_ceiling"] == "exact_contract"
    assert receipt.payload["eligible_for_proof"] is False
    assert receipt.payload["eligible_for_basis"] is True
    assert receipt.payload["source_receipt_id"] == source.receipt_id
    assert receipt.payload["source_receipt_kind"] == "read_file"
    assert receipt.payload["evidence_role"] == "historical_support"
    assert receipt.payload["source_task_state_generation"] == 0
    assert receipt.payload["submission_task_state_generation"] == 1
    assert receipt.payload["snapshot_verified"] is True
    direct, _derived = admissible_verdict_refs(ledger)
    assert inspection_id not in direct
    assert inspection_id not in _refs_from_inspections((request,), (enriched,))
    assert inspection_id in _basis_refs_from_inspections((request,), (enriched,))


def test_stale_submission_is_rejected_after_live_state_change_and_rebound_snapshot_stays_immutable() -> None:
    ledger, source = _ledger_with_historical_read("before\n")
    ledger.record(Receipt(
        receipt_id="step-5:write:again",
        step=5,
        kind="write_file",
        success=True,
        summary="mutated again",
        state_change=True,
        payload={"path": "config.txt", "modified_paths": ["config.txt"], "content": "after\n"},
    ))
    _request, stale = _execute(ledger, f"receipt:{source.receipt_id}")
    assert "stale for the current task-state generation" in stale["error"]
    assert ledger.task_state_generation() == 2

    # Rebinding the same immutable historical observation into a current claim
    # proves the snapshot itself did not drift with the live file.
    ledger.record(_claim_receipt(source, source_generation=0, submission_generation=2))
    _request, rebound = _execute(ledger, f"receipt:{source.receipt_id}")
    assert rebound["excerpt"] == "before\n"
    assert rebound["source_task_state_generation"] == 0
    assert rebound["submission_task_state_generation"] == 2


def test_uncited_or_invented_receipt_is_rejected_by_runtime() -> None:
    ledger, source = _ledger_with_historical_read("before\n")
    uncited = _read_receipt("step-0:uncited", "secret\n", step=0)
    # It exists in the immutable ledger but is not part of the current claim.
    ledger.receipts.insert(0, uncited)

    _request, result = _execute(ledger, f"receipt:{uncited.receipt_id}")
    assert result["kind"] == "read_cited_receipt"
    assert "not cited" in result["error"]

    _request, result = _execute(ledger, "receipt:invented")
    assert "not cited" in result["error"]

    # The genuinely cited source still works.
    _request, result = _execute(ledger, f"receipt:{source.receipt_id}")
    assert result["snapshot_verified"] is True


def test_runtime_rejects_forged_generation_binding_even_when_receipt_is_cited() -> None:
    ledger = ExecutionLedger()
    source = _read_receipt("step-1:read", "before\n")
    ledger.record(source)
    ledger.record(Receipt(
        receipt_id="step-2:write", step=2, kind="write_file", success=True,
        summary="mutated", state_change=True, payload={"modified_paths": ["config.txt"]},
    ))
    # The immutable source was observed at generation 0, but this forged claim
    # lies and labels it as current generation 1. Runtime must derive and compare.
    ledger.record(_claim_receipt(
        source, role="historical_support", source_generation=1, submission_generation=1,
    ))
    _request, result = _execute(ledger, f"receipt:{source.receipt_id}")
    assert "does not match immutable ledger history" in result["error"]


def test_runtime_rejects_current_anchor_replay_even_when_exactly_cited() -> None:
    ledger = ExecutionLedger()
    source = _read_receipt("step-1:read-current", "current\n")
    ledger.record(source)
    ledger.record(_claim_receipt(
        source, role="current_anchor", source_generation=0, submission_generation=0,
    ))
    _request, result = _execute(ledger, f"receipt:{source.receipt_id}")
    assert "requires a historical-support evidence binding" in result["error"]


def test_cited_non_read_or_failed_receipt_is_not_exact_content() -> None:
    for source in (
        Receipt("step-1:cmd", 1, "run_command", True, "cmd", payload={"content": "x"}),
        Receipt("step-1:read", 1, "read_file", False, "failed", payload={"path": "config.txt"}),
    ):
        ledger = ExecutionLedger()
        ledger.record(source)
        ledger.record(_claim_receipt(source, source_generation=0, submission_generation=0))
        _request, result = _execute(ledger, f"receipt:{source.receipt_id}")
        assert "not a successful read_file" in result["error"]


def test_hash_verifiable_excerpt_can_recover_exact_snapshot_but_truncation_fails_closed() -> None:
    full = "small exact snapshot\n"
    source = _read_receipt(
        "step-1:read", full, include_content=False, excerpt=full, hash_prefix=16,
    )
    ledger = ExecutionLedger(); ledger.record(source)
    ledger.record(Receipt("step-2:write", 2, "write_file", True, "mutated", state_change=True, payload={"modified_paths": ["config.txt"]}))
    ledger.record(_claim_receipt(source, role="historical_support", source_generation=0, submission_generation=1))
    _request, result = _execute(ledger, f"receipt:{source.receipt_id}")
    assert result["snapshot_verified"] is True
    assert result["snapshot_content_source"] == "excerpt"
    assert result["excerpt"] == full

    bad = _read_receipt(
        "step-1:bad", full, include_content=False, excerpt="small exact", hash_prefix=16,
    )
    ledger = ExecutionLedger(); ledger.record(bad)
    ledger.record(Receipt("step-2:write-bad", 2, "write_file", True, "mutated", state_change=True, payload={"modified_paths": ["config.txt"]}))
    ledger.record(_claim_receipt(bad, role="historical_support", source_generation=0, submission_generation=1))
    _request, result = _execute(ledger, f"receipt:{bad.receipt_id}")
    assert "not a hash-verifiable complete snapshot" in result["error"]


def _packet_message(rows: list[dict]) -> list[dict[str, str]]:
    return [{
        "role": "user",
        "content": json.dumps({
            "authoritative_task_prompt": "task",
            "verifier_packet": {
                "authoritative_check_ids": [],
                "primary_submission": {"cited_evidence_index": rows},
            },
        }, sort_keys=True),
    }]


def _cited_row(receipt_id: str, *, kind: str = "read_file", success: bool = True, role: str = "historical_support") -> dict:
    return {
        "receipt_id": receipt_id,
        "exact_receipt_handle": f"receipt:{receipt_id}",
        "kind": kind,
        "success": success,
        "evidence_role": role,
        "receipt_task_state_generation": 0,
        "submission_task_state_generation": 1,
        "current_payload_projection": {
            "path": "config.txt",
            "bytes": 6,
            "content_hash": "a" * 64,
        },
    }


def test_provider_exposes_only_exact_successful_cited_read_handle_enum() -> None:
    rows = [
        _cited_row("step-1:old"),
        _cited_row("step-2:cmd", kind="run_command"),
    ]
    messages = _packet_message(rows)
    assert _pcr_verifier_cited_receipt_handles_from_input(messages) == ("receipt:step-1:old",)
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    schema = tool["parameters"]
    direct = schema["$defs"]["direct_inspection_request"]["anyOf"]
    refs = {row["$ref"] for row in direct}
    assert "#/$defs/pcr_cited_receipt_request" in refs
    cited = schema["$defs"]["pcr_cited_receipt_request"]
    assert cited["properties"]["locator"] == {
        "type": "string", "enum": ["receipt:step-1:old"],
    }
    valid = {
        "kind": "read_cited_receipt",
        "locator": "receipt:step-1:old",
        "offset": None,
        "span": 8192,
        "clause_ids": None,
        "proof_ids": None,
    }
    jsonschema.validate({"turn": {"kind": "inspect", "requests": [valid]}}, schema)
    invented = dict(valid); invented["locator"] = "receipt:invented"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"turn": {"kind": "inspect", "requests": [invented]}}, schema)


def test_provider_does_not_offer_current_anchor_receipts_as_snapshot_replay() -> None:
    row = _cited_row("step-1:current", role="current_anchor")
    row["receipt_task_state_generation"] = 1
    row["submission_task_state_generation"] = 1
    messages = _packet_message([row])
    assert _pcr_verifier_cited_receipt_handles_from_input(messages) == ()
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    schema = tool["parameters"]
    assert "pcr_cited_receipt_request" not in schema["$defs"]
    assert schema["$defs"]["direct_inspection_request"] == {
        "$ref": "#/$defs/pcr_direct_locator_request",
    }


def test_provider_removes_cited_route_when_no_eligible_handle_exists() -> None:
    messages = _packet_message([_cited_row("step-2:cmd", kind="run_command")])
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    schema = tool["parameters"]
    assert "pcr_cited_receipt_request" not in schema["$defs"]
    assert schema["$defs"]["direct_inspection_request"] == {
        "$ref": "#/$defs/pcr_direct_locator_request",
    }


def test_f90_live_schema_stays_bounded_with_max_cited_history_and_derived_frontier() -> None:
    rows = [_cited_row(f"step-{i + 1}:read:config-{i:02d}") for i in range(24)]
    first = {
        "role": "user",
        "content": json.dumps({
            "verifier_packet": {
                "authoritative_check_ids": ["check-a"],
                "primary_submission": {"cited_evidence_index": rows},
            },
        }, sort_keys=True),
    }
    source = "inspection:4:0:historical-source"
    runtime = {
        "role": "user",
        "content": json.dumps({
            "verifier_inspection_results": [{
                "kind": "read_cited_receipt",
                "inspection_id": source,
                "eligible_for_basis": True,
                "eligible_for_proof": False,
                "observation_valid": True,
            }],
            "available_authoritative_source_refs": ["task:prompt", source],
            "available_bound_input_refs": ["task:prompt", source],
        }, sort_keys=True),
    }
    tool, _ids = _pcr_verifier_native_tool_for_input([first, runtime])
    schema_bytes = len(json.dumps(tool["parameters"], separators=(",", ":"), sort_keys=True).encode())
    assert schema_bytes <= 12_000


def test_provider_cited_alias_canonicalizes_to_runtime_read_output_but_ordinary_read_output_cannot_smuggle_receipt() -> None:
    row = {
        "kind": "read_cited_receipt",
        "locator": "receipt:step-1:old",
        "offset": 0,
        "span": 4000,
        "clause_ids": None,
        "proof_ids": None,
    }
    canonical, receipt = unwrap_verifier_direct_turn(json.dumps({
        "turn": {"kind": "inspect", "requests": [row]},
    }))
    request = json.loads(canonical)["requests"][0]
    assert request["kind"] == "read_output"
    assert request["handle"] == "receipt:step-1:old"
    assert "locator" not in request
    mapping = receipt["provider_pcr_verifier_compact_locator_mapping"][0]
    assert mapping["provider_kind"] == "read_cited_receipt"
    assert mapping["runtime_kind"] == "read_output"

    ordinary = dict(row)
    ordinary["kind"] = "read_output"
    with pytest.raises(AzureProviderOutputError) as excinfo:
        unwrap_verifier_direct_turn(json.dumps({"turn": {"kind": "inspect", "requests": [ordinary]}}))
    assert excinfo.value.code == "provider_pcr_verifier_receipt_requires_cited_route"


def test_provider_rejects_mismatched_or_conflicting_cited_handle_namespace() -> None:
    bad = _cited_row("step-1:old")
    bad["exact_receipt_handle"] = "receipt:other"
    with pytest.raises(AzureProviderOutputError) as excinfo:
        _pcr_verifier_native_tool_for_input(_packet_message([bad]))
    assert excinfo.value.code == "provider_pcr_verifier_cited_receipt_namespace_invalid"

    first = _packet_message([_cited_row("step-1:old")])
    second = _packet_message([_cited_row("step-2:different")])[0]
    with pytest.raises(AzureProviderOutputError) as excinfo:
        _pcr_verifier_native_tool_for_input([*first, second])
    assert excinfo.value.code == "provider_pcr_verifier_cited_receipt_namespace_conflict"

    forged = _cited_row("step-3:forged", role="historical_support")
    forged["receipt_task_state_generation"] = 1
    forged["submission_task_state_generation"] = 1
    with pytest.raises(AzureProviderOutputError) as excinfo:
        _pcr_verifier_native_tool_for_input(_packet_message([forged]))
    assert excinfo.value.code == "provider_pcr_verifier_cited_receipt_namespace_invalid"


def test_malformed_cited_snapshot_cannot_inherit_exact_contract_without_proof_ids() -> None:
    ledger = ExecutionLedger()
    request = VerifierInspectionRequest(
        request_id="malformed", kind="read_output", handle="receipt:step-1:read",
    )
    row = register_inspection_results(
        (request,),
        ({
            "request_id": "malformed",
            "kind": "read_cited_receipt",
            "handle": "receipt:step-1:read",
            "source_receipt_id": "step-1:read",
            "source_receipt_kind": "read_file",
            "evidence_role": "historical_support",
            "source_task_state_generation": 0,
            "content_hash": "a" * 64,
            # Deliberately missing snapshot_verified and wrong origin.
            "observation_origin": "model_claim",
        },),
        ledger=ledger, step=1, requester="model_verifier", executor=_Executor(),
        overlay=_Executor(), packet_signature="packet",
    )[0]
    assert row["observation_valid"] is False
    assert row["admissibility"] == "exploratory"
    assert row["eligible_for_proof"] is False
    receipt = ledger.latest_receipt("inspection_record")
    assert receipt is not None
    assert receipt.payload["evidence_ceiling"] == "exact_contract"
    assert receipt.payload["observation_failure"] == "read_cited_receipt lacks exact cited snapshot provenance, hash, or paging truth"


def _runtime_result_message(row: dict) -> dict[str, str]:
    return {"role": "user", "content": json.dumps({"verifier_inspection_results": [row]}, sort_keys=True)}


def _complete_cited_result(handle: str, content: str = "before\n") -> dict:
    total = len(content)
    return {
        "kind": "read_cited_receipt",
        "handle": handle,
        "snapshot_verified": True,
        "observation_valid": True,
        "error": "",
        "total_chars": total,
        "offset": 0,
        "returned_chars": total,
        "next_offset": total,
        "more_available": False,
        "snapshot_complete": True,
        "excerpt": content,
    }


def test_cited_snapshot_page_metadata_distinguishes_full_from_partial_observation() -> None:
    content = "abcdefghij"
    ledger, source = _ledger_with_historical_read(content)
    handle = f"receipt:{source.receipt_id}"

    _request, first = _execute(ledger, handle, span=4)
    assert first["total_chars"] == 10
    assert first["returned_chars"] == 4
    assert first["next_offset"] == 4
    assert first["more_available"] is True
    assert first["snapshot_complete"] is False

    _request, tail = _execute(ledger, handle, offset=4, span=20)
    assert tail["returned_chars"] == 6
    assert tail["next_offset"] == 10
    assert tail["more_available"] is False
    # A final page alone does not establish that the whole snapshot was observed.
    assert tail["snapshot_complete"] is False

    _request, full = _execute(ledger, handle, span=20)
    assert full["returned_chars"] == 10
    assert full["more_available"] is False
    assert full["snapshot_complete"] is True


def test_provider_removes_only_fully_observed_cited_snapshot_handle() -> None:
    handle = "receipt:step-1:old"
    messages = _packet_message([_cited_row("step-1:old")])
    messages.append(_runtime_result_message(_complete_cited_result(handle)))
    assert _pcr_verifier_completed_cited_receipt_handles_from_input(
        messages, eligible_handles=(handle,),
    ) == (handle,)
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    schema = tool["parameters"]
    assert "pcr_cited_receipt_request" not in schema["$defs"]
    assert schema["$defs"]["direct_inspection_request"] == {
        "$ref": "#/$defs/pcr_direct_locator_request",
    }


def test_provider_keeps_partial_cited_snapshot_actionable() -> None:
    handle = "receipt:step-1:old"
    messages = _packet_message([_cited_row("step-1:old")])
    partial = _complete_cited_result(handle, "abcdefghij")
    partial.update({
        "excerpt": "abcd", "returned_chars": 4, "next_offset": 4,
        "more_available": True, "snapshot_complete": False,
    })
    messages.append(_runtime_result_message(partial))
    assert _pcr_verifier_completed_cited_receipt_handles_from_input(
        messages, eligible_handles=(handle,),
    ) == ()
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    cited = tool["parameters"]["$defs"]["pcr_cited_receipt_request"]
    assert cited["properties"]["locator"] == {"type": "string", "enum": [handle]}


def test_assistant_authored_completion_cannot_hide_cited_snapshot_tool() -> None:
    handle = "receipt:step-1:old"
    messages = _packet_message([_cited_row("step-1:old")])
    messages.append({
        "role": "assistant",
        "content": json.dumps({"verifier_inspection_results": [_complete_cited_result(handle)]}),
    })
    assert _pcr_verifier_completed_cited_receipt_handles_from_input(
        messages, eligible_handles=(handle,),
    ) == ()
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    assert "pcr_cited_receipt_request" in tool["parameters"]["$defs"]


def test_provider_consumes_completed_handle_without_hiding_other_historical_receipts() -> None:
    first = "receipt:step-1:first"
    second = "receipt:step-2:second"
    messages = _packet_message([_cited_row("step-1:first"), _cited_row("step-2:second")])
    messages.append(_runtime_result_message(_complete_cited_result(first)))
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    cited = tool["parameters"]["$defs"]["pcr_cited_receipt_request"]
    assert cited["properties"]["locator"] == {"type": "string", "enum": [second]}


def test_registry_rejects_forged_complete_flag_on_partial_cited_page() -> None:
    ledger, source = _ledger_with_historical_read("abcdefghij")
    request, result = _execute(ledger, f"receipt:{source.receipt_id}", span=4)
    forged = dict(result)
    forged.update({"snapshot_complete": True, "more_available": False, "next_offset": 10})
    enriched = register_inspection_results(
        (request,), (forged,), ledger=ledger, step=4, requester="model_verifier",
        executor=_Executor(), overlay=_Executor(), packet_signature="packet",
    )[0]
    assert enriched["observation_valid"] is False
    assert enriched["admissibility"] == "exploratory"
    assert "paging truth" in enriched["observation_failure"]


def _provider_cited_request(locator: str, *, offset: int | None = 0, span: int | None = 8192) -> dict:
    return {
        "kind": "read_cited_receipt", "locator": locator, "offset": offset, "span": span,
        "clause_ids": ["task:raw"], "proof_ids": None,
    }

def test_f93_equivalent_cited_requests_collapse_inside_one_provider_turn() -> None:
    row = _provider_cited_request("receipt:step-1:old")
    wrapper = {"turn": {"kind": "inspect", "requests": [dict(row) for _ in range(12)]}}
    canonical, receipt = unwrap_verifier_direct_turn(json.dumps(wrapper))
    requests = json.loads(canonical)["requests"]
    assert len(requests) == 1
    assert requests[0]["kind"] == "read_output"
    assert requests[0]["handle"] == "receipt:step-1:old"
    assert "request_id" not in requests[0]
    mappings = receipt["provider_pcr_verifier_compact_locator_mapping"]
    assert len(mappings) == 12
    assert mappings[0]["provider_duplicate_equivalent"] is False
    assert all(row["canonical_request_ordinal"] == 0 for row in mappings)
    assert sum(int(row["provider_duplicate_equivalent"]) for row in mappings) == 11
    assert mappings[-1]["duplicate_equivalent_count"] == 12

def test_f93_cited_paging_variants_are_not_collapsed() -> None:
    a = _provider_cited_request("receipt:step-1:old", offset=0, span=4)
    b = _provider_cited_request("receipt:step-1:old", offset=4, span=4)
    canonical, receipt = unwrap_verifier_direct_turn(json.dumps({"turn": {"kind": "inspect", "requests": [a, b]}}))
    assert len(json.loads(canonical)["requests"]) == 2
    assert not any(row["provider_duplicate_equivalent"] for row in receipt["provider_pcr_verifier_compact_locator_mapping"])

def test_f93_live_direct_repeats_are_not_collapsed() -> None:
    row = {"kind": "read_file", "locator": "out.txt", "limit": None, "offset": 0, "span": 10, "clause_ids": None, "proof_ids": None}
    canonical, receipt = unwrap_verifier_direct_turn(json.dumps({"turn": {"kind": "inspect", "requests": [dict(row), dict(row)]}}))
    assert len(json.loads(canonical)["requests"]) == 2
    assert len(receipt["provider_pcr_verifier_compact_locator_mapping"]) == 2




def test_s5c3_provider_does_not_offer_unreplayable_cited_read_snapshot() -> None:
    """A cited read_file without a captured content hash must not be advertised."""
    row = _cited_row("step-1:large-read")
    row["current_payload_projection"] = {
        "path": "text.gcode",
        "bytes": 1661422,
        # Large Solver read was paged/truncated and carried no content_hash.
    }
    messages = _packet_message([row])

    assert _pcr_verifier_cited_receipt_handles_from_input(messages) == ()
    tool, _ids = _pcr_verifier_native_tool_for_input(messages)
    schema = tool["parameters"]
    assert "pcr_cited_receipt_request" not in schema["$defs"]
