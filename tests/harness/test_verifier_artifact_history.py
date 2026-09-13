from __future__ import annotations

from types import SimpleNamespace

from aether.ledger import Receipt
from aether.verifier_inspector import (
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
)


def _inspect(receipts: list[Receipt], *, path: str, limit: int = 5) -> dict:
    request = VerifierInspectionRequest(
        request_id="history",
        kind="inspect_artifact_history",
        path=path,
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


def _preservation_receipts() -> list[Receipt]:
    original = '[{"id":1,"phone":"020 7123-4567","nickname":"A-B","extra":{"keep":true}}]'
    final = '[{"id":1,"phone":"02071234567","nickname":"A-B","extra":{"keep":true}}]'
    receipts = [
        Receipt(
            receipt_id="step-0:read",
            step=0,
            kind="read_file",
            success=True,
            summary="read profiles.json",
            payload={
                "path": "profiles.json",
                "content_hash": "before-hash",
                "bytes": len(original),
                "content": original,
                "excerpt": original,
            },
        ),
        Receipt(
            receipt_id="step-1:write",
            step=1,
            kind="write_file",
            success=True,
            summary="wrote profiles.json",
            state_change=True,
            payload={
                "path": "profiles.json",
                "modified_paths": ("profiles.json",),
                "artifact_paths": ("profiles.json",),
                "before_content_hash": "before-hash",
                "after_content_hash": "after-hash",
                "bytes": len(final),
                "content": final,
                "excerpt": final,
            },
        ),
    ]
    # Reproduce the live failure shape: enough unrelated later receipts to
    # push the original observation out of a globally limited history view.
    receipts.extend(
        Receipt(
            receipt_id=f"later-{index}",
            step=2 + index,
            kind="runtime_accounting",
            success=True,
            summary=f"later bookkeeping {index}",
            payload={"counter": "provider_calls", "value": index},
        )
        for index in range(40)
    )
    return receipts


def test_artifact_history_filters_requested_path_before_limit() -> None:
    result = _inspect(_preservation_receipts(), path="profiles.json", limit=5)

    assert [row["event_id"] for row in result["rows"]] == [
        "step-0:read",
        "step-1:write",
    ]
    assert result["rows"][0]["receipt_kind"] == "read_file"
    assert result["rows"][0]["excerpt"].startswith('[{"id":1')
    assert result["rows"][1]["receipt_kind"] == "write_file"
    assert result["observation_origin"] == "ledger_artifact_history"
    assert result["read_only"] is True


def test_artifact_history_normalizes_workspace_absolute_path() -> None:
    relative = _inspect(_preservation_receipts(), path="profiles.json", limit=5)
    absolute = _inspect(_preservation_receipts(), path="/app/profiles.json", limit=5)

    assert absolute["normalized_path"] == "profiles.json"
    assert absolute["rows"] == relative["rows"]


def test_artifact_history_does_not_turn_command_claim_into_file_history() -> None:
    receipts = _preservation_receipts()
    receipts.append(
        Receipt(
            receipt_id="solver-claim",
            step=50,
            kind="run_command",
            success=True,
            summary="solver says original profile was preserved",
            payload={
                "command": "python3 -c 'print(\"original preserved\")'",
                "stdout_tail": "original preserved",
            },
        )
    )

    result = _inspect(receipts, path="profiles.json", limit=5)

    assert [row["event_id"] for row in result["rows"]] == [
        "step-0:read",
        "step-1:write",
    ]
    assert all(row["receipt_kind"] != "run_command" for row in result["rows"])
