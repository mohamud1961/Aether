from __future__ import annotations

import hashlib
import json

from aether.completion_record import (
    MAX_RECORD_BYTES,
    canonical_task_hash,
    current_revision,
    ensure_initial_nonadherence_receipt,
    project_completion_record_context,
    record_finish_metadata,
    update_completion_record_receipt,
)
from aether.ledger import ExecutionLedger, Receipt
from aether.model_parse import parse_solver_turn
from aether.persistent_context import evidence_alias
from aether.persistent_provider_protocol import (
    PERSISTENT_ACTION_ARGUMENT_VARIANTS,
    canonicalize_persistent_direct_tool_call,
    persistent_direct_provider_tools,
)
from aether.runtime_ir import ACTION_SCHEMA


def _evidence(ledger: ExecutionLedger, *, receipt_id: str = "r:read") -> tuple[str, str]:
    digest = hashlib.sha256(b"observed bytes").hexdigest()
    ledger.record(Receipt(
        receipt_id=receipt_id,
        step=0,
        kind="read_file",
        success=True,
        summary="read artifact",
        payload={"path": "workspace/out.txt", "content_sha256": digest},
    ))
    return receipt_id, digest


def _record(task: str, *, revision: int = 1, conditions: list[dict] | None = None) -> dict:
    task_hash = canonical_task_hash(task)
    if conditions is None:
        conditions = [{
            "id": "c1",
            "outcome": "Deliver the requested output",
            "source_refs": [{"task_hash": task_hash, "start_byte": 0, "end_byte": len(task.encode())}],
            "kind": "explicit",
            "proof_needed": "Inspect the delivered output",
            "evidence_refs": [],
            "assessment": "open",
            "uncertainty": "Not yet checked",
            "retirement_reason": None,
        }]
    return {
        "schema_version": 1,
        "revision": revision,
        "task_hash": task_hash,
        "conditions": conditions,
        "revision_reason": "Current Frontier assessment",
    }


def test_completion_record_action_is_common_provider_surface() -> None:
    assert any(kind == "update_completion_record" for kind, _ in ACTION_SCHEMA)
    assert "update_completion_record" in PERSISTENT_ACTION_ARGUMENT_VARIANTS
    tool_names = {tool["name"] for tool in persistent_direct_provider_tools()}
    assert "update_completion_record" in tool_names


def test_valid_revision_is_append_only_and_stale_update_is_rejected() -> None:
    task = "Produce output.txt exactly."
    ledger = ExecutionLedger()
    receipt_id, digest = _evidence(ledger)
    record = _record(task)
    record["conditions"][0]["evidence_refs"] = [{"receipt_id": receipt_id, "artifact_hash": f"sha256:{digest}"}]
    accepted = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=record,
        task_text=task, step=1, action_id="a1",
    )
    assert accepted.success
    ledger.record(accepted)
    assert current_revision(ledger) == 1

    stale = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record={**record, "revision": 1},
        task_text=task, step=2, action_id="a2",
    )
    assert not stale.success
    assert "stale expected_revision" in stale.summary
    assert stale.payload["prior_record_unchanged"] is True
    assert current_revision(ledger) == 1


def test_prior_condition_cannot_silently_disappear_but_can_be_retired() -> None:
    task = "Produce output.txt exactly."
    ledger = ExecutionLedger()
    first = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=_record(task),
        task_text=task, step=1, action_id="a1",
    )
    ledger.record(first)

    vanished = _record(task, revision=2, conditions=[])
    rejected = update_completion_record_receipt(
        ledger=ledger, expected_revision=1, replacement_record=vanished,
        task_text=task, step=2, action_id="a2",
    )
    assert not rejected.success
    assert "retire them with a reason" in rejected.summary

    retired = _record(task, revision=2)
    retired["conditions"][0]["assessment"] = "retired"
    retired["conditions"][0]["retirement_reason"] = "Frontier no longer asserts this interpretation"
    accepted = update_completion_record_receipt(
        ledger=ledger, expected_revision=1, replacement_record=retired,
        task_text=task, step=2, action_id="a3",
    )
    assert accepted.success


def test_record_size_limit_is_fail_closed_without_truncation() -> None:
    task = "Produce output.txt exactly."
    ledger = ExecutionLedger()
    record = _record(task)
    record["conditions"][0]["outcome"] = "x" * (MAX_RECORD_BYTES + 100)
    rejected = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=record,
        task_text=task, step=1, action_id="oversize",
    )
    assert not rejected.success
    assert "record byte limit exceeded" in rejected.summary
    assert current_revision(ledger) == 0


def test_projection_differs_by_instruction_not_tool_surface() -> None:
    task = "Produce output.txt exactly."
    ledger = ExecutionLedger()
    assert project_completion_record_context(ledger, mode="off", task_text=task) is None
    treatment = project_completion_record_context(ledger, mode="v1", task_text=task)
    assert treatment is not None
    assert treatment["mode"] == "v1"
    assert "treatment_instruction" in treatment

    accepted = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=_record(task),
        task_text=task, step=1, action_id="a1",
    )
    ledger.record(accepted)
    control = project_completion_record_context(ledger, mode="off", task_text=task)
    assert control is not None
    assert control["active_record"]["revision"] == 1
    assert "treatment_instruction" not in control


def test_treatment_nonadherence_is_one_factual_nonblocking_receipt() -> None:
    ledger = ExecutionLedger()
    ensure_initial_nonadherence_receipt(ledger, step=0, mode="v1")
    assert not ledger.all_receipts()
    ensure_initial_nonadherence_receipt(ledger, step=1, mode="v1")
    ensure_initial_nonadherence_receipt(ledger, step=2, mode="v1")
    rows = [r for r in ledger.all_receipts() if r.kind == "completion_record_initial_nonadherence"]
    assert len(rows) == 1
    assert rows[0].success
    assert rows[0].payload["submission_blocked"] is False


def test_finish_metadata_is_optional_and_mismatch_never_vetoes() -> None:
    task = "Produce output.txt exactly."
    ledger = ExecutionLedger()
    first = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=_record(task),
        task_text=task, step=1, action_id="a1",
    )
    ledger.record(first)
    record_finish_metadata(
        ledger,
        finish_metadata={
            "reviewed_revision": 0,
            "remaining_uncertainties": ["One residual concern"],
            "completion_basis": "Frontier chooses to submit on current evidence",
        },
        mode="v1",
        step=2,
    )
    row = ledger.latest_receipt("completion_record_finish_metadata")
    assert row is not None and row.success
    assert row.payload["review_mismatch"] is True
    assert row.payload["submission_blocked"] is False


def test_direct_finish_accepts_optional_finish_metadata_and_parser_preserves_it() -> None:
    args = {
        "claim": "Complete",
        "evidence_refs": ["evidence:0123456789abcdef"],
        "finish_metadata": {
            "reviewed_revision": 1,
            "remaining_uncertainties": [],
            "completion_basis": "Reviewed current task evidence",
        },
    }
    canonical, _receipt = canonicalize_persistent_direct_tool_call("finish", json.dumps(args))
    turn = parse_solver_turn(canonical)
    assert turn.kind == "finish_outcome"
    assert turn.finish_metadata is not None
    assert turn.finish_metadata["reviewed_revision"] == 1


def test_evidence_freshness_distinguishes_superseded_from_unknown() -> None:
    task = "Produce output.txt exactly."
    # Known same-path mutation => superseded.
    ledger = ExecutionLedger()
    receipt_id, digest = _evidence(ledger)
    record = _record(task)
    record["conditions"][0]["evidence_refs"] = [{"receipt_id": receipt_id, "artifact_hash": digest}]
    accepted = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=record,
        task_text=task, step=1, action_id="a1",
    )
    ledger.record(accepted)
    ledger.record(Receipt(
        receipt_id="r:write", step=2, kind="write_file", success=True,
        summary="changed same artifact", state_change=True,
        payload={"path": "workspace/out.txt", "modified_paths": ["workspace/out.txt"]},
    ))
    projection = project_completion_record_context(ledger, mode="v1", task_text=task)
    assert projection is not None
    assert projection["evidence_freshness"][0]["freshness"] == "superseded"

    # Opaque mutation with no known same-path target => unknown_since_mutation.
    ledger2 = ExecutionLedger()
    receipt_id2, digest2 = _evidence(ledger2, receipt_id="r:read2")
    record2 = _record(task)
    record2["conditions"][0]["evidence_refs"] = [{"receipt_id": receipt_id2, "artifact_hash": digest2}]
    accepted2 = update_completion_record_receipt(
        ledger=ledger2, expected_revision=0, replacement_record=record2,
        task_text=task, step=1, action_id="a2",
    )
    ledger2.record(accepted2)
    ledger2.record(Receipt(
        receipt_id="r:opaque", step=2, kind="run_command", success=True,
        summary="opaque task-world mutation", state_change=True,
        payload={"state_delta": {"mutation_detection_status": "coarse"}},
    ))
    projection2 = project_completion_record_context(ledger2, mode="v1", task_text=task)
    assert projection2 is not None
    assert projection2["evidence_freshness"][0]["freshness"] == "unknown_since_mutation"



def _assert_strict_object_tree(schema: dict, *, path: str = "root") -> None:
    if not isinstance(schema, dict):
        return
    if schema.get("type") == "object":
        properties = schema.get("properties") or {}
        assert set(schema.get("required") or []) == set(properties), path
        assert schema.get("additionalProperties") is False, path
        for name, child in properties.items():
            _assert_strict_object_tree(child, path=f"{path}/properties/{name}")
    for key in ("items",):
        child = schema.get(key)
        if isinstance(child, dict):
            _assert_strict_object_tree(child, path=f"{path}/{key}")
    for key in ("anyOf", "oneOf", "allOf"):
        for index, child in enumerate(schema.get(key) or []):
            if isinstance(child, dict):
                _assert_strict_object_tree(child, path=f"{path}/{key}/{index}")


def test_completion_record_native_tool_schema_is_recursively_strict() -> None:
    tool = next(
        item for item in persistent_direct_provider_tools()
        if item["name"] == "update_completion_record"
    )
    _assert_strict_object_tree(tool["parameters"], path="parameters")


# ---------------------------------------------------------------------------
# F05 F03 hash-domain sentinel: receipt/projection hashes are not artifact
# hashes and must be rejected; content_sha256 is accepted.
# ---------------------------------------------------------------------------


def test_receipt_hash_rejected_as_artifact_hash() -> None:
    """A non-artifact hash (record_sha256) in the evidence_ref is rejected."""
    task = "Produce output.txt exactly."
    ledger = ExecutionLedger()
    digest = hashlib.sha256(b"observed bytes").hexdigest()
    ledger.record(Receipt(
        receipt_id="r:record", step=0, kind="completion_record_revision", success=True,
        summary="record revision",
        payload={"revision": 1, "record_sha256": digest},
    ))
    record = _record(task)
    record["conditions"][0]["evidence_refs"] = [
        {"receipt_id": "r:record", "artifact_hash": f"sha256:{digest}"},
    ]
    rejected = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=record,
        task_text=task, step=1, action_id="a1",
    )
    assert not rejected.success
    assert "does not resolve to an artifact-content hash" in rejected.summary
    assert "receipt/projection hash is not an artifact hash" in rejected.payload["detail"]


def test_content_sha256_accepted_as_artifact_hash() -> None:
    """A genuine content_sha256 artifact hash passes validation."""
    task = "Produce output.txt exactly."
    ledger = ExecutionLedger()
    digest = hashlib.sha256(b"observed bytes").hexdigest()
    ledger.record(Receipt(
        receipt_id="r:read", step=0, kind="read_file", success=True,
        summary="read artifact",
        payload={"path": "workspace/out.txt", "content_sha256": digest},
    ))
    record = _record(task)
    record["conditions"][0]["evidence_refs"] = [
        {"receipt_id": "r:read", "artifact_hash": f"sha256:{digest}"},
    ]
    accepted = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=record,
        task_text=task, step=1, action_id="a1",
    )
    assert accepted.success


# ---------------------------------------------------------------------------
# F05 F04 render-layer sentinel: completion-record tool presence follows
# include_completion_record flag; set_job_disposition always present.
# ---------------------------------------------------------------------------


def test_completion_record_tool_hidden_when_rendering_excludes_completion_record() -> None:
    full_tools = {tool["name"] for tool in persistent_direct_provider_tools()}
    no_cr_tools = {
        tool["name"]
        for tool in persistent_direct_provider_tools(include_completion_record=False)
    }
    assert "update_completion_record" in full_tools
    assert "update_completion_record" not in no_cr_tools
    assert "set_job_disposition" in full_tools
    assert "set_job_disposition" in no_cr_tools


def test_completion_record_projection_exposes_submission_alias_for_record_evidence() -> None:
    task = "Produce output.txt exactly."
    ledger = ExecutionLedger()
    receipt_id, digest = _evidence(ledger, receipt_id="step-11:persistent-demo:cmd")
    record = _record(task)
    record["conditions"][0]["evidence_refs"] = [{
        "receipt_id": receipt_id,
        "artifact_hash": f"sha256:{digest}",
    }]
    accepted = update_completion_record_receipt(
        ledger=ledger, expected_revision=0, replacement_record=record,
        task_text=task, step=1, action_id="a1",
    )
    assert accepted.success
    ledger.record(accepted)

    projection = project_completion_record_context(ledger, mode="v1", task_text=task)
    assert projection is not None
    row = projection["evidence_freshness"][0]
    assert row["receipt_id"] == receipt_id
    assert row["evidence_ref"] == evidence_alias(receipt_id)
    assert row["evidence_ref"] != receipt_id


def test_finish_provider_tools_require_canonical_evidence_aliases() -> None:
    tools = {tool["name"]: tool for tool in persistent_direct_provider_tools()}
    for name in ("finish_intent", "finish"):
        schema = tools[name]["parameters"]["properties"]["evidence_refs"]
        assert schema["items"]["pattern"] == r"^evidence:[0-9a-f]{16}$"
        assert "never receipt_id" in tools[name]["description"]
