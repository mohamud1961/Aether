from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether.kernel_actions import handle_kernel_owned_action
from aether.ledger import ExecutionLedger, Receipt
from aether.runtime_ir import ActionRequest, EnvMap


ROOT = "/tmp/aether-history-workspace"


def _action(kind: str, path: str) -> ActionRequest:
    return ActionRequest(
        action_id=f"{kind}-{path or 'empty'}",
        kind=kind,
        capability_id="history",
        arguments={"path": path},
        intent="inspect recorded path history",
        expected_observation="exact receipt history for the requested path",
        if_fail_next="report the observation boundary",
    )


def _handle(ledger: object, kind: str, path: str):
    return handle_kernel_owned_action(
        _action(kind, path),
        step=4,
        compiled=SimpleNamespace(),
        executor=SimpleNamespace(),
        envmap=EnvMap(task_prompt="history", workspace_root=ROOT),
        ledger=ledger,  # type: ignore[arg-type]
    )


def _ledger_with_alias_receipts() -> ExecutionLedger:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        "r-relative", 1, "read_file", True, "read target",
        payload={"path": "reports/output.txt", "content_hash": "a" * 16},
    ))
    ledger.record(Receipt(
        "r-app", 2, "write_file", True, "write target",
        state_change=True,
        payload={
            "path": "/app/reports/output.txt",
            "before_content_hash": "a" * 16,
            "after_content_hash": "b" * 16,
        },
    ))
    ledger.record(Receipt(
        "r-physical", 3, "read_file", True, "read target",
        payload={
            "path": f"{ROOT}/reports/output.txt",
            "content_hash": "b" * 16,
        },
    ))
    ledger.record(Receipt(
        "r-other", 3, "read_file", True, "read unrelated",
        payload={"path": "other.txt", "content_hash": "c" * 16},
    ))
    return ledger


@pytest.mark.parametrize("path", [
    "reports/output.txt",
    "/app/reports/output.txt",
    f"{ROOT}/reports/output.txt",
])
def test_artifact_history_aliases_match_one_canonical_exact_path(path: str) -> None:
    receipt = _handle(_ledger_with_alias_receipts(), "query_artifact_history", path)

    assert receipt is not None and receipt.success is True
    assert receipt.payload["path"] == "reports/output.txt"
    assert receipt.payload["requested_path"] == path
    assert receipt.payload["history_status"] == "matched"
    assert receipt.payload["history_available"] is True
    assert receipt.payload["total_events"] == 3
    assert {row["event_id"] for row in receipt.payload["events"]} == {
        "r-relative", "r-app", "r-physical",
    }
    assert all(
        row["matched_paths"] == ["reports/output.txt"]
        for row in receipt.payload["events"]
    )


@pytest.mark.parametrize("path", [
    "reports/output.txt",
    "/app/reports/output.txt",
    f"{ROOT}/reports/output.txt",
])
def test_inspect_diff_aliases_use_same_recorded_history(path: str) -> None:
    receipt = _handle(_ledger_with_alias_receipts(), "inspect_diff", path)

    assert receipt is not None and receipt.success is True
    assert receipt.payload["path"] == "reports/output.txt"
    assert receipt.payload["requested_path"] == path
    assert receipt.payload["history_status"] == "matched"
    assert receipt.payload["history_available"] is True
    assert receipt.payload["event_count"] == 3
    assert receipt.payload["write_count"] == 1
    assert receipt.payload["read_count"] == 2
    assert receipt.payload["filesystem_diff"] is False


@pytest.mark.parametrize("path", ["../outside.txt", "/etc/passwd"])
@pytest.mark.parametrize("kind", ["query_artifact_history", "inspect_diff"])
def test_history_rejects_traversal_and_unrelated_absolute_paths(kind: str, path: str) -> None:
    receipt = _handle(_ledger_with_alias_receipts(), kind, path)

    assert receipt is not None and receipt.success is False
    assert receipt.failure_class == "workspace_path_escape"
    assert receipt.payload["history_status"] == "invalid_path"
    assert receipt.payload["history_available"] is False
    assert receipt.payload["events"] == []


@pytest.mark.parametrize("kind", ["query_artifact_history", "inspect_diff"])
def test_empty_history_path_is_invalid_instead_of_querying_every_receipt(kind: str) -> None:
    receipt = _handle(_ledger_with_alias_receipts(), kind, "")

    assert receipt is not None and receipt.success is False
    assert receipt.failure_class == "invalid_workspace_path"
    assert receipt.payload["history_status"] == "invalid_path"
    assert receipt.payload["history_available"] is False
    assert receipt.payload["events"] == []


@pytest.mark.parametrize("kind", ["query_artifact_history", "inspect_diff"])
def test_empty_matching_history_is_distinct_from_unavailable_history(kind: str) -> None:
    empty = _handle(_ledger_with_alias_receipts(), kind, "missing.txt")

    assert empty is not None and empty.success is True
    assert empty.payload["history_status"] == "empty"
    assert empty.payload["history_available"] is True
    assert empty.payload.get("events", empty.payload.get("history", [])) == []

    class UnavailableLedger:
        def all_receipts(self):
            raise RuntimeError("ledger store offline")

    unavailable = _handle(UnavailableLedger(), kind, "missing.txt")

    assert unavailable is not None and unavailable.success is False
    assert unavailable.failure_class == "history_unavailable"
    assert unavailable.payload["history_status"] == "unavailable"
    assert unavailable.payload["history_available"] is False
    assert unavailable.payload["events"] == []
    assert "ledger store offline" in unavailable.payload["error"]
