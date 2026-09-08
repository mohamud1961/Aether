"""Kernel-owned action handlers kept outside kernel.py for LOC discipline."""
from __future__ import annotations

from .ledger import ExecutionLedger, Receipt
from .history_query import query_history
from .memory_events import artifact_history, diff_summary_for_path
from .runtime_ir import ActionRequest, CompiledRuntime, EnvMap

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .execution import Executor


def handle_kernel_owned_action(
    action: ActionRequest,
    step: int,
    compiled: CompiledRuntime,
    executor: "Executor",
    envmap: EnvMap,
    ledger: ExecutionLedger,
) -> Receipt | None:
    if action.kind == "query_history":
        query = str(action.arguments.get("query", ""))
        offset = max(0, int(action.arguments.get("offset", 0) or 0))
        limit = max(1, min(20, int(action.arguments.get("limit", 8) or 8)))
        result = query_history(ledger.all_receipts(), query, offset=offset, limit=limit)
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:history", step=step,
            kind="query_history", success=True,
            summary=(
                f"literal history query {query!r}: "
                f"{len(result['results'])}/{result['total_matches']} matches"
            ),
            payload=result,
        )
    if action.kind == "query_artifact_history":
        path = str(action.arguments.get("path", "")).strip()
        all_rows = artifact_history(ledger.all_receipts(), path=path, limit=None)
        rows = all_rows[-12:]
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:artifact_history", step=step,
            kind="query_artifact_history", success=True,
            summary=f"artifact history {path}: returned {len(rows)}/{len(all_rows)} events",
            payload={
                "path": path, "ordering": "oldest_to_newest_within_returned_window",
                "total_events": len(all_rows), "returned_events": len(rows),
                "event_cap": 12, "more_available": len(rows) < len(all_rows),
                "events": rows,
            },
        )
    if action.kind == "inspect_diff":
        path = str(action.arguments.get("path", "")).strip()
        summary = diff_summary_for_path(ledger.all_receipts(), path=path)
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:diff", step=step,
            kind="inspect_diff", success=True,
            summary=(
                f"recorded exact-path history {path}: {summary['event_count']} events; "
                "not a filesystem diff"
            ),
            payload=summary,
        )
    return None
