"""Context-file adapter for the shared Thin loop.

Duck-types the same seam as ``ContextTreeAdapter`` (it occupies the same
``ThinLoopConfig.context_tree_adapter`` slot, so the two mechanisms cannot be
combined) and adds a per-turn tool-surface restriction while over budget.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Mapping

from ..context_tree.epoch import MTreeEpochOverflow
from ..context_tree.store import cap_tool_result
from ..ledger import ExecutionLedger, Receipt
from ..run_cancellation import raise_if_run_cancelled
from ..run_deadline import raise_if_run_deadline_exceeded
from ..runtime_ir import CapabilityDescriptor, CompiledRuntime, SolverTurn
from .config import (
    MANAGED_CONTEXT_OVERFLOW_CODE, CONTEXT_FILE_BUDGET_DEFAULT, FORCED_TRIM_TARGET_FRACTION,
    OVER_BUDGET_TRIM_AFTER_TURNS, validate_budget,
)
from .file import ContextFile
from .tools import CONTEXT_FILE_CAPABILITY, EDIT_CONTEXT_ACTION

PACKET_PREFIX = "[context_packet]\n"
RESULT_CAP = 6_000
ARGS_CAP = 2_000
NOTE_CAP = 4_000
SUMMARY_CAP = 300
CONTEXT_FILE_DOC = (
    "Your working context is the file shown below. After each action the system "
    "appends the action and a bounded copy of its result to the file. You may "
    "rewrite the file with edit_context to keep what matters and drop what does "
    "not; the task statement above is fixed and is not part of the file. The file "
    "has a byte budget; when it is exceeded only edit_context and finish are available."
)


class ClmContextOverflow(MTreeEpochOverflow):
    """A request still exceeds the declared limit; the arm has no capacity reanchor."""

    code = MANAGED_CONTEXT_OVERFLOW_CODE

    def __init__(self, estimated_tokens: int, request_limit: int) -> None:
        RuntimeError.__init__(
            self, f"{MANAGED_CONTEXT_OVERFLOW_CODE}: estimated request {estimated_tokens} exceeds {request_limit}",
        )
        self.estimated_tokens = int(estimated_tokens)
        self.request_limit = int(request_limit)


class ContextFileAdapter:
    # thin_loop contract: which public action kinds this adapter dispatches itself,
    # and which provider hook drops chat continuity without touching other scope modes.
    owned_actions = frozenset({EDIT_CONTEXT_ACTION})
    continuity_reset_hook = "reset_solver_continuity_state_only"

    def __init__(
        self, *, evidence_root: str | Path, run_id: str,
        budget_bytes: int = CONTEXT_FILE_BUDGET_DEFAULT, request_limit: int = 200_000,
        request_estimator: Any | None = None,
    ) -> None:
        if not str(run_id):
            raise ValueError("context file arm requires a run id")
        self.budget = validate_budget(budget_bytes)
        self.request_limit = int(request_limit)
        self.request_estimator = request_estimator or _estimate_tokens
        self.run_id = str(run_id)
        self._file = ContextFile(Path(evidence_root) / self.run_id / "context_file")
        self._closed = False
        self.restricted = False
        self._step = 0
        self._reset_pending = False
        self._failed_turns = 0
        self._last_over_size: int | None = None
        self._summary = ""
        self._facts: list[str] = []
        self._events: list[dict[str, Any]] = []
        self._edits: list[dict[str, Any]] = []
        self._trims: list[dict[str, Any]] = []
        self._requests = 0
        self._overflow_count = 0
        self._peak_bytes = 0
        self._over_budget_turns = 0

    @property
    def active(self) -> bool:
        return not self._closed

    @property
    def file(self) -> ContextFile:
        return self._file

    def solver_compiled(self, compiled: CompiledRuntime) -> CompiledRuntime:
        schema = tuple(compiled.action_schema)
        if not any(name == EDIT_CONTEXT_ACTION for name, _args in schema):
            schema = (*schema, (EDIT_CONTEXT_ACTION, ()))
        capabilities = tuple(compiled.selected_capabilities)
        if not any(item.capability_id == CONTEXT_FILE_CAPABILITY for item in capabilities):
            capabilities = (*capabilities, CapabilityDescriptor(
                capability_id=CONTEXT_FILE_CAPABILITY,
                summary="Edit the task-local working context file",
                available=True, tool_names=(EDIT_CONTEXT_ACTION,), cost_hint="cheap",
            ))
        return replace(compiled, action_schema=schema, selected_capabilities=capabilities)

    def turn_compiled(self, compiled: CompiledRuntime) -> CompiledRuntime:
        """Restrict this turn's accepted action kinds while the file is over budget."""
        if not self.restricted:
            return compiled
        return replace(compiled, action_schema=tuple(
            item for item in compiled.action_schema if item[0] == EDIT_CONTEXT_ACTION
        ))

    def prepare_messages(
        self, base_messages: list[dict[str, Any]], *, compiled: CompiledRuntime,
        task_workspace: str | Path, cancellation_event: Any | None = None,
        settle_timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        raise_if_run_cancelled(cancellation_event)
        raise_if_run_deadline_exceeded()
        index = next((
            i for i in range(len(base_messages) - 1, -1, -1)
            if str(base_messages[i].get("role") or "") == "system"
            and str(base_messages[i].get("content") or "").startswith(PACKET_PREFIX)
        ), None)
        if index is None:
            raise ValueError("context file arm requires Thin's current context packet")
        self._evaluate_budget()
        size = self.file.size
        self._peak_bytes = max(self._peak_bytes, size)
        facts = [f"context_file_bytes: {size}/{self.budget}", *self._facts]
        self._facts = []
        messages = deepcopy(base_messages)
        packet = messages[index]
        packet["content"] = str(packet.get("content") or "") + "\n\n" + "\n".join(facts)
        messages.insert(index, {
            "role": "user",
            "content": f"{CONTEXT_FILE_DOC}\n<context_file>\n{self.file.text}</context_file>",
        })
        self._reset_pending = True
        return messages

    def note_request(self, messages: list[dict[str, Any]]) -> None:
        estimated = int(self.request_estimator({"messages": messages}))
        if estimated > self.request_limit:
            self._overflow_count += 1
            raise ClmContextOverflow(estimated, self.request_limit)
        self._requests += 1

    def record_note(self, text: str) -> None:
        if self._closed:
            raise RuntimeError("context file adapter is closed")
        if not isinstance(text, str):
            raise TypeError("context file note text must be a string")
        self.file.append("note", cap_tool_result(text, NOTE_CAP), step=self._step)

    def request_metadata(self) -> dict[str, Any]:
        return {
            "context_file_bytes": self.file.size, "context_file_budget": self.budget,
            "context_file_restricted": self.restricted,
        }

    def consume_epoch_reset(self) -> bool:
        pending, self._reset_pending = self._reset_pending, False
        return pending

    def record_solver_turn(self, turn: SolverTurn, *, step: int) -> None:
        self._step = int(step)
        self._summary = str(turn.summary or "")[:SUMMARY_CAP]
        if turn.kind in {"submit_outcome", "finish_intent", "finish_outcome"} and (turn.claim or turn.summary):
            self.record_note(str(turn.claim or turn.summary))

    def dispatch_owned_action(self, turn: SolverTurn, *, step: int, ledger: ExecutionLedger) -> str:
        """Apply one edit_context action to the harness-side file; log before/after hashes."""
        action = turn.actions[0]
        result = self.file.apply_edit(action.arguments, step=step)
        row = {
            "step": step, "ok": result.ok, "mode": result.mode, "error": result.error,
            "before_sha256": result.before_sha256, "after_sha256": result.after_sha256,
            "before_bytes": result.before_bytes, "after_bytes": result.after_bytes,
        }
        self._edits.append(row)
        ledger.record(Receipt(
            receipt_id=f"step-{step}:{action.action_id}:managed_context_edit_context",
            step=step, kind="managed_context_edit_context", success=result.ok, summary=result.fact(),
            failure_class="" if result.ok else "invalid_context_edit",
            payload={"action_id": action.action_id, **row},
        ))
        self._facts.append(result.fact())
        return result.fact()

    def record_public_action_result(
        self, turn: SolverTurn, *, step: int, receipts: list[Receipt],
    ) -> bool:
        action = turn.actions[0]
        index = next((
            r for r in reversed(receipts) if r.kind == "primary_action_result_index"
            and (r.payload or {}).get("action_id") == action.action_id
        ), None)
        if index is None or (index.payload or {}).get("status") == "missing":
            return False
        ids = set((index.payload or {}).get("outcome_receipt_ids") or ())
        outcomes = [r for r in receipts if r.receipt_id in ids]
        if not outcomes:
            return False
        args = cap_tool_result(_json(dict(action.arguments)), ARGS_CAP)
        result = cap_tool_result(_json([_receipt_row(r) for r in outcomes]), RESULT_CAP)
        summary = f"summary: {self._summary}\n" if self._summary else ""
        self.file.append("action", f"{summary}action: {action.kind} {args}\nresult: {result}", step=step)
        return True

    def drain_events(self) -> list[dict[str, Any]]:
        events, self._events = self._events, []
        return events

    def telemetry(self) -> dict[str, Any]:
        return {
            "context_file_budget": self.budget, "context_file_bytes": self.file.size,
            "context_file_peak_bytes": self._peak_bytes, "over_budget_turns": self._over_budget_turns,
            "edits": deepcopy(self._edits), "forced_trims": deepcopy(self._trims),
            "solver_requests": self._requests, "managed_context_context_overflow": self._overflow_count,
        }

    def close(self) -> None:
        self._closed = True  # evidence stays on disk; telemetry remains readable

    def _evaluate_budget(self) -> None:
        size = self.file.size
        if size <= self.budget:
            self.restricted, self._failed_turns, self._last_over_size = False, 0, None
            return
        self._over_budget_turns += 1
        if self._last_over_size is not None:
            self._failed_turns = self._failed_turns + 1 if size >= self._last_over_size else 0
        if self._failed_turns >= OVER_BUDGET_TRIM_AFTER_TURNS:
            result = self.file.forced_trim(int(self.budget * FORCED_TRIM_TARGET_FRACTION))
            row = {
                "step": self._step, "removed_entry_ids": list(result.removed_entry_ids),
                "before_bytes": result.before_bytes, "after_bytes": result.after_bytes,
                "target_bytes": result.target_bytes, "reached_target": result.reached_target,
            }
            self._trims.append(row)
            self._events.append({"kind": "managed_context_forced_trim", **row})
            self._facts.append(
                f"managed_context_forced_trim: removed {len(result.removed_entry_ids)} oldest system-appended "
                f"entries, {result.before_bytes} -> {result.after_bytes} bytes (target {result.target_bytes})"
            )
            self._failed_turns, size = 0, self.file.size
        self.restricted = size > self.budget
        self._last_over_size = size if self.restricted else None
        if self.restricted:
            self._facts.append(f"context_file_over_budget: {size}/{self.budget}")


def apply_turn_surface(
    adapter: Any, hooks: Any, solver_compiled: CompiledRuntime, *, ledger: ExecutionLedger, step: int,
) -> CompiledRuntime:
    """Per-turn hook for thin_loop: record trim receipts, set provider tools, restrict actions."""
    if not isinstance(adapter, ContextFileAdapter):
        return solver_compiled
    for event in adapter.drain_events():
        ledger.record(Receipt(
            receipt_id=f"step-{step}:{event['kind']}", step=step, kind=str(event["kind"]), success=True,
            summary=f"{event['kind']}: {event['before_bytes']} -> {event['after_bytes']} bytes",
            payload={k: v for k, v in event.items() if k != "kind"},
        ))
    configure = getattr(hooks, "configure_context_file_mode", None)
    if callable(configure):
        configure("restricted" if adapter.restricted else "on")
    return adapter.turn_compiled(solver_compiled)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _receipt_row(receipt: Receipt) -> dict[str, Any]:
    return {
        "kind": receipt.kind, "success": receipt.success, "summary": receipt.summary,
        "state_change": receipt.state_change, "failure_class": receipt.failure_class,
        "payload": deepcopy(receipt.payload),
    }


def _estimate_tokens(request: Mapping[str, Any]) -> int:
    return max(1, (len(_json(request).encode("utf-8")) + 3) // 4)
