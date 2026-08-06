from __future__ import annotations

import json
from hashlib import sha256
from types import SimpleNamespace

from aether.verifier_budget import VerifierPhaseBudget, VerifierPhaseState
from aether.verifier_inspector import (
    RECENT_RECEIPTS_PACKET_TARGET_BYTES,
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
)


def _receipt(index: int, *, summary: str) -> SimpleNamespace:
    return SimpleNamespace(
        receipt_id=f"step-{index}:receipt",
        step=index,
        kind="run_command",
        success=True,
        summary=summary,
        failure_class="",
        payload={},
    )


def _inspect(receipts: list[SimpleNamespace], *, limit: int = 30) -> dict:
    request = VerifierInspectionRequest(
        request_id="recent",
        kind="inspect_recent_receipts",
        limit=limit,
    )
    rows = execute_verifier_inspection_requests(
        (request,),
        compiled=SimpleNamespace(planned_checks=lambda: ()),
        ledger=SimpleNamespace(all_receipts=lambda: tuple(receipts)),
        executor=SimpleNamespace(),
        envmap=SimpleNamespace(workspace_root="/app"),
    )
    assert len(rows) == 1
    return rows[0]


def test_recent_receipts_compact_long_summaries_and_preserve_identity() -> None:
    full = "python3 - <<'PY'\n" + ("print('large historical command')\n" * 200) + "PY"
    result = _inspect([_receipt(1, summary=full)], limit=1)

    assert result["returned_count"] == 1
    row = result["rows"][0]
    assert row["receipt_id"] == "step-1:receipt"
    assert row["summary"] != full
    assert row["summary_truncated"] is True
    assert row["summary_bytes"] == len(full.encode("utf-8"))
    assert row["summary_sha256"] == sha256(full.encode("utf-8")).hexdigest()
    assert full not in json.dumps(result, sort_keys=True)


def test_recent_receipts_keep_newest_rows_within_packet_target() -> None:
    receipts = [
        _receipt(index, summary=f"command-{index}:" + ("x" * 1500))
        for index in range(30)
    ]
    result = _inspect(receipts, limit=30)
    encoded = json.dumps(result, sort_keys=True, default=str).encode("utf-8")

    assert len(encoded) <= RECENT_RECEIPTS_PACKET_TARGET_BYTES
    assert result["matching_count"] == 30
    assert result["requested_limit"] == 30
    assert result["returned_count"] < 30
    assert result["omitted_count"] == 30 - result["returned_count"]
    assert result["rows"][-1]["receipt_id"] == "step-29:receipt"
    assert [row["step"] for row in result["rows"]] == sorted(row["step"] for row in result["rows"])


def test_compacted_receipts_do_not_invalidate_successful_mixed_observations() -> None:
    receipts = [
        _receipt(index, summary=f"historical-command-{index}:" + ("y" * 1800))
        for index in range(30)
    ]
    recent = _inspect(receipts, limit=30)
    perception = {
        "request_id": "probe-image",
        "kind": "perceive_artifact",
        "path": "/app/probe.jpg",
        "bytes": 413_767,
        "transcription": "independent semantic observation " * 45,
        "extraction_authority": "model_transcription_not_ground_truth",
        "read_only": True,
    }
    script_tail = {
        "request_id": "script-tail",
        "kind": "read_file",
        "path": "/app/script.py",
        "bytes": 5_158,
        "excerpt": "return takeoff, landing\n" * 45,
        "read_only": True,
    }

    state = VerifierPhaseState(VerifierPhaseBudget())
    state.validate_results((recent, perception, script_tail), elapsed_s=0.1)
    assert len(json.dumps(recent, sort_keys=True).encode("utf-8")) < 8_192
