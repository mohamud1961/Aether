"""Kernel-owned action handlers kept outside kernel.py for LOC discipline."""
from __future__ import annotations

from .ledger import ExecutionLedger, Receipt
from .history_query import query_history
from .memory_events import artifact_history, diff_summary_for_path
from .runtime_ir import ActionRequest, CompiledRuntime, EnvMap, normalize_relpath

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .execution import Executor


def _history_path(action: ActionRequest, envmap: EnvMap) -> tuple[str, str]:
    """Return raw and canonical paths for exact history lookups.

    History is receipt-backed and exact-match by design.  Canonicalize the
    request at the kernel boundary so relative, virtual ``/app``, and declared
    physical-root aliases address the same receipt path without widening an
    empty request into a query over every receipt.
    """
    requested = str(action.arguments.get("path", "")).strip()
    if not requested:
        raise ValueError("artifact history requires a non-empty path")
    return requested, normalize_relpath(requested, envmap.workspace_root)


def _history_unavailable_receipt(
    *,
    action: ActionRequest,
    step: int,
    kind: str,
    requested_path: str,
    normalized_path: str,
    failure_class: str,
    error: str,
) -> Receipt:
    operation = "artifact history" if kind == "query_artifact_history" else "recorded diff history"
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:{kind}",
        step=step,
        kind=kind,
        success=False,
        summary=f"{operation} unavailable for {requested_path!r}: {error}",
        failure_class=failure_class,
        payload={
            "path": normalized_path,
            "requested_path": requested_path,
            "normalized_path": normalized_path,
            "history_status": "unavailable" if failure_class == "history_unavailable" else "invalid_path",
            "history_available": False,
            "total_events": 0,
            "returned_events": 0,
            "event_count": 0,
            "history": [],
            "events": [],
            "error": error,
        },
    )


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
        try:
            requested_path, path = _history_path(action, envmap)
        except ValueError as exc:
            return _history_unavailable_receipt(
                action=action, step=step, kind=action.kind,
                requested_path=str(action.arguments.get("path", "")).strip(),
                normalized_path="", failure_class=(
                    "workspace_path_escape"
                    if "outside" in str(exc) or "escapes" in str(exc)
                    else "invalid_workspace_path"
                ), error=str(exc),
            )
        try:
            receipts = tuple(ledger.all_receipts())
            def normalizer(value: str) -> str:
                return normalize_relpath(value, envmap.workspace_root)

            all_rows = artifact_history(
                receipts, path=path, limit=None, path_normalizer=normalizer,
            )
        except Exception as exc:  # noqa: BLE001 - preserve unavailable history as evidence
            return _history_unavailable_receipt(
                action=action, step=step, kind=action.kind,
                requested_path=requested_path, normalized_path=path,
                failure_class="history_unavailable",
                error=f"{type(exc).__name__}: {exc}",
            )
        rows = all_rows[-12:]
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:artifact_history", step=step,
            kind="query_artifact_history", success=True,
            summary=f"artifact history {path}: returned {len(rows)}/{len(all_rows)} events",
            payload={
                "path": path, "requested_path": requested_path,
                "normalized_path": path,
                "history_status": "matched" if all_rows else "empty",
                "history_available": True,
                "ordering": "oldest_to_newest_within_returned_window",
                "total_events": len(all_rows), "returned_events": len(rows),
                "event_cap": 12, "more_available": len(rows) < len(all_rows),
                "events": rows,
            },
        )
    if action.kind == "inspect_diff":
        try:
            requested_path, path = _history_path(action, envmap)
        except ValueError as exc:
            return _history_unavailable_receipt(
                action=action, step=step, kind=action.kind,
                requested_path=str(action.arguments.get("path", "")).strip(),
                normalized_path="", failure_class=(
                    "workspace_path_escape"
                    if "outside" in str(exc) or "escapes" in str(exc)
                    else "invalid_workspace_path"
                ), error=str(exc),
            )
        try:
            receipts = tuple(ledger.all_receipts())
            def normalizer(value: str) -> str:
                return normalize_relpath(value, envmap.workspace_root)

            summary = diff_summary_for_path(
                receipts, path=path, path_normalizer=normalizer,
            )
        except Exception as exc:  # noqa: BLE001 - preserve unavailable history as evidence
            return _history_unavailable_receipt(
                action=action, step=step, kind=action.kind,
                requested_path=requested_path, normalized_path=path,
                failure_class="history_unavailable",
                error=f"{type(exc).__name__}: {exc}",
            )
        summary = {
            **summary,
            "requested_path": requested_path,
            "normalized_path": path,
            "history_status": "matched" if summary["event_count"] else "empty",
            "history_available": True,
        }
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
