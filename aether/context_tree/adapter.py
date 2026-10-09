"""Production M-TREE adapter for the shared Thin execution loop."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import time
from typing import Any, Mapping

from .compactor import COMPACTOR_DEPLOYMENT, COMPACTOR_REQUEST_TIMEOUT_S, Compactor, VIEW_DOC
from .epoch import EPOCH_STEPS, EPOCH_TOKENS, EpochPolicy, MTreeEpochOverflow
from .store import RunStore, cap_tool_result
from .tree import ContextTree
from .zoom_tool import zoom
from ..ledger import ExecutionLedger, Receipt
from ..run_cancellation import raise_if_run_cancelled
from ..run_deadline import (
    KernelRunTimeout, raise_if_run_deadline_exceeded, remaining_run_s,
)
from ..runtime_ir import CapabilityDescriptor, CompiledRuntime, SolverTurn


class ContextTreeContinuityError(RuntimeError):
    """The native Solver transcript could not be reset at an M-TREE epoch."""


class ContextTreeAdapter:
    """Adapt M-TREE fresh epochs to Thin's existing ModelHooks/action seam.

    The adapter owns only its run-local event tree and request boundary. Public
    Aether actions still pass through ``run_act_turn``; only ``zoom`` is handled
    here as context-tree navigation.
    """

    # thin_loop contract shared with the context-file adapter.
    owned_actions = frozenset({"zoom"})
    continuity_reset_hook = "reset_solver_continuity_for_recovery"

    def __init__(
        self,
        *,
        raw_task: str,
        evidence_root: str | Path,
        run_id: str,
        compactor_provider: Any,
        compactor_route: str = COMPACTOR_DEPLOYMENT,
        compactor_limiter_path: str | Path,
        epoch_tokens: int = EPOCH_TOKENS,
        epoch_steps: int = EPOCH_STEPS,
        request_limit: int = 200_000,
        view_bytes: int = 128_000,
        jobs: int = 8,
        retry_s: float = 10.0,
        request_timeout_s: float = COMPACTOR_REQUEST_TIMEOUT_S,
        request_estimator: Any | None = None,
    ) -> None:
        self.raw_task = str(raw_task)
        self.evidence_root = Path(evidence_root)
        self.run_id = str(run_id)
        self.compactor_provider = compactor_provider
        self.compactor_route = str(compactor_route)
        self.compactor_limiter_path = Path(compactor_limiter_path)
        self.epoch_tokens = int(epoch_tokens)
        self.epoch_steps = int(epoch_steps)
        self.request_limit = int(request_limit)
        self.view_bytes = int(view_bytes)
        self.jobs = int(jobs)
        self.retry_s = float(retry_s)
        self.request_timeout_s = float(request_timeout_s)
        self.request_estimator = request_estimator or _tree_request_estimate
        if not self.raw_task or not self.run_id:
            raise ValueError("M-TREE requires a raw task and run id")
        if not callable(self.compactor_provider):
            raise TypeError("M-TREE compactor provider must be callable")
        self._store: RunStore | None = None
        self._tree: ContextTree | None = None
        self._compactor: Compactor | None = Compactor(
            self.compactor_provider,
            route=self.compactor_route,
            limiter=str(self.compactor_limiter_path),
            request_timeout_s=self.request_timeout_s,
        )
        self._policy = EpochPolicy(token_limit=self.epoch_tokens, step_limit=self.epoch_steps)
        self._epoch_prefix: list[dict[str, Any]] | None = None
        self._epoch_record: dict[str, Any] | None = None
        self._epoch_reset_pending = False
        self._latest_action: str | None = None
        self._latest_result: str | None = None
        self._latest_action_is_zoom = False
        self._epochs: list[dict[str, Any]] = []
        self._view_bytes_per_epoch_start: list[int] = []
        self._zoom_calls: list[dict[str, int]] = []
        self._requests_seen = 0
        self._total_estimated_tokens = 0
        self._epoch_overflow_count = 0
        self._pending_notes: list[str] = []
        self._closed = False

    @property
    def active(self) -> bool:
        return self._tree is not None

    def solver_compiled(self, compiled: CompiledRuntime) -> CompiledRuntime:
        """Expose only the adapter-owned zoom action to this run's Solver."""
        schema = tuple(compiled.action_schema)
        if not any(name == "zoom" for name, _args in schema):
            schema = (*schema, ("zoom", ("id", "n")))
        capabilities = tuple(compiled.selected_capabilities)
        if not any(item.capability_id == "context_tree" for item in capabilities):
            capabilities = (*capabilities, CapabilityDescriptor(
                capability_id="context_tree",
                summary="Open a line of task-local context history",
                available=True,
                tool_names=("zoom",),
                cost_hint="cheap",
            ))
        if schema == tuple(compiled.action_schema) and capabilities == tuple(compiled.selected_capabilities):
            return compiled
        return replace(compiled, action_schema=schema, selected_capabilities=capabilities)

    def prepare_messages(
        self,
        base_messages: list[dict[str, Any]],
        *,
        compiled: CompiledRuntime,
        task_workspace: str | Path,
        cancellation_event: Any | None = None,
        settle_timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        raise_if_run_cancelled(cancellation_event)
        raise_if_run_deadline_exceeded()
        timeout_candidates = [
            float(value) for value in (settle_timeout, remaining_run_s())
            if value is not None
        ]
        effective_timeout = min(timeout_candidates) if timeout_candidates else None
        if effective_timeout is not None and effective_timeout <= 0:
            raise KernelRunTimeout("task run deadline exceeded before M-TREE settle")
        if self.raw_task != compiled.task_prompt:
            raise ValueError("M-TREE task instruction does not match the compiled task")
        bind_cancellation = getattr(self.compactor_provider, "bind_run_cancellation", None)
        if callable(bind_cancellation):
            bind_cancellation(cancellation_event)
        self._ensure_started(
            Path(task_workspace), cancellation_event=cancellation_event,
        )
        packet_message = next((
            deepcopy(dict(row)) for row in reversed(base_messages)
            if str(row.get("role") or "") == "system"
            and str(row.get("content") or "").startswith("[context_packet]\n")
        ), None)
        if packet_message is None:
            raise ValueError("M-TREE requires Thin's current context packet")

        fresh_epoch = self._epoch_prefix is None
        if fresh_epoch:
            assert self._tree is not None
            settle_deadline = (
                None if effective_timeout is None
                else time.monotonic() + effective_timeout
            )
            if not self._tree.settle(
                timeout=effective_timeout,
                abort_event=cancellation_event,
            ):
                raise_if_run_cancelled(cancellation_event)
                raise_if_run_deadline_exceeded()
                if settle_deadline is not None and time.monotonic() >= settle_deadline:
                    raise KernelRunTimeout("task run deadline exceeded while settling M-TREE")
                raise RuntimeError("M-TREE settle was aborted")
            raise_if_run_cancelled(cancellation_event)
            raise_if_run_deadline_exceeded()
            if settle_deadline is not None and time.monotonic() >= settle_deadline:
                raise KernelRunTimeout("task run deadline exceeded while settling M-TREE")
            view_text = self._tree.view.render()
            stable = [
                deepcopy(dict(row)) for row in base_messages
                if not (
                    str(row.get("role") or "") == "system"
                    and (
                        str(row.get("content") or "").startswith("[raw_user_task]\n")
                        or str(row.get("content") or "").startswith("[context_packet]\n")
                    )
                )
            ]
            stable.append({"role": "system", "content": VIEW_DOC})
            self._epoch_prefix = [
                *stable,
                {"role": "user", "content": self.raw_task},
                {"role": "user", "content": view_text},
            ]
            view_bytes = len(view_text.encode("utf-8"))
            self._epoch_record = {
                "epoch": self._policy.current.index,
                "view_bytes": view_bytes,
                "start_event_count": self._tree.event_count,
            }
            self._epochs.append(self._epoch_record)
            self._view_bytes_per_epoch_start.append(view_bytes)

        packet_text = str(packet_message.get("content") or "")
        if fresh_epoch or self._latest_action_is_zoom:
            packet_text += self._latest_exchange_text()
        packet_message["content"] = packet_text
        return [*deepcopy(self._epoch_prefix or ()), packet_message]

    def note_request(self, messages: list[dict[str, Any]]) -> None:
        estimated = int(self.request_estimator({"messages": messages}))
        try:
            self._policy.note_request(estimated, request_limit=self.request_limit)
        except MTreeEpochOverflow:
            self._epoch_overflow_count += 1
            raise
        self._requests_seen += 1
        self._total_estimated_tokens += max(0, estimated)

    def record_note(self, text: str) -> dict[str, Any] | None:
        """Append one public note verbatim, or queue it until this run starts.

        CHALLENGER and other optional public mechanisms can use this hook when M-TREE
        is enabled without exposing private ledger state to the adapter.
        """
        if not isinstance(text, str):
            raise TypeError("M-TREE note text must be a string")
        if self._closed:
            raise RuntimeError("M-TREE adapter is closed")
        if self._tree is None:
            self._pending_notes.append(text)
            return None
        return self._tree.append("note", text)

    def request_metadata(self) -> dict[str, Any]:
        current = self._epochs[-1] if self._epochs else {}
        return {
            "epoch_index": int(self._policy.current.index),
            "view_bytes": int(current.get("view_bytes", 0)),
        }

    def consume_epoch_reset(self) -> bool:
        pending = self._epoch_reset_pending
        self._epoch_reset_pending = False
        return pending

    def record_solver_turn(self, turn: SolverTurn, *, step: int) -> None:
        """Log only the accepted visible Solver text; reasoning is never stored."""
        text = str(turn.summary or "")
        if text:
            self._tree_required().append("talk", text)
        if turn.kind in {"submit_outcome", "finish_intent", "finish_outcome"}:
            completion = str(turn.claim or turn.summary or "")
            if completion:
                self.record_note(completion)

    def dispatch_owned_action(self, turn: SolverTurn, *, step: int, ledger: ExecutionLedger) -> str:
        return self.dispatch_zoom(turn, step=step, ledger=ledger)

    def dispatch_zoom(self, turn: SolverTurn, *, step: int, ledger: ExecutionLedger) -> str:
        action = turn.actions[0]
        event_id = action.arguments.get("id")
        span = action.arguments.get("n")
        if not isinstance(event_id, int) or isinstance(event_id, bool):
            event_id = -1
        if not isinstance(span, int) or isinstance(span, bool):
            span = 0
        action_text = _tree_action_text("zoom", action.arguments)
        result = zoom(self._tree_required(), event_id, span)
        capped = cap_tool_result(result)
        self._tree_required().append("tool", action_text)
        self._tree_required().append("echo", capped)
        success = not result.startswith("No line ")
        ledger.record(Receipt(
            receipt_id=f"step-{step}:{action.action_id}:m_tree_zoom",
            step=step,
            kind="m_tree_zoom",
            success=success,
            summary="M-TREE zoom returned a history line" if success else result,
            failure_class="" if success else "invalid_zoom",
            payload={"action_id": action.action_id, "id": event_id, "n": span, "result": capped},
        ))
        self._latest_action = action_text
        self._latest_result = capped
        self._latest_action_is_zoom = True
        self._zoom_calls.append({
            "id": event_id, "n": span,
            "depth": 0 if span <= 1 else span.bit_length() - 1,
        })
        self._finish_accepted_action(step=step)
        return capped

    def record_public_action_result(
        self,
        turn: SolverTurn,
        *,
        step: int,
        receipts: list[Receipt],
    ) -> bool:
        """Log a public action only when the existing dispatcher produced results."""
        action = turn.actions[0]
        index = next((
            receipt for receipt in reversed(receipts)
            if receipt.kind == "primary_action_result_index"
            and (receipt.payload or {}).get("action_id") == action.action_id
        ), None)
        if index is None or (index.payload or {}).get("status") == "missing":
            return False
        result_ids = set((index.payload or {}).get("outcome_receipt_ids") or ())
        outcomes = [receipt for receipt in receipts if receipt.receipt_id in result_ids]
        if not outcomes:
            return False
        action_text = _tree_action_text(action.kind, action.arguments)
        result_text = json.dumps(
            [_tree_receipt_payload(receipt) for receipt in outcomes],
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
        )
        capped = cap_tool_result(result_text)
        self._tree_required().append("tool", action_text)
        self._tree_required().append("echo", capped)
        self._latest_action = action_text
        self._latest_result = capped
        self._latest_action_is_zoom = False
        self._finish_accepted_action(step=step)
        return True

    def telemetry(self) -> dict[str, Any]:
        return {
            "epochs": deepcopy(self._epochs),
            "view_bytes_per_epoch_start": list(self._view_bytes_per_epoch_start),
            "zoom_calls": deepcopy(self._zoom_calls),
            "epoch_boundaries": deepcopy(self._policy.boundaries),
            "solver_requests": self._requests_seen,
            "estimated_solver_tokens": self._total_estimated_tokens,
            "m_tree_epoch_overflow": self._epoch_overflow_count,
            "compactor": {} if self._compactor is None else deepcopy(self._compactor.metrics),
        }

    def close(self) -> None:
        tree, store = self._tree, self._store
        self._tree = None
        self._store = None
        self._closed = True
        self._pending_notes.clear()
        if tree is not None:
            tree.close(wait=True)
        if store is not None:
            store.close()

    def _ensure_started(
        self,
        task_workspace: Path,
        *,
        cancellation_event: Any | None = None,
    ) -> None:
        if self._tree is not None:
            return
        if self._closed:
            raise RuntimeError("M-TREE adapter is closed")
        self._store = RunStore.create(
            self.evidence_root, self.run_id, self.raw_task,
            task_workspace=task_workspace,
        )
        self._tree = ContextTree(
            self._store, self._compactor, view_bytes=self.view_bytes,
            jobs=self.jobs, retry_s=self.retry_s,
            abort_event=cancellation_event,
        )
        pending_notes, self._pending_notes = self._pending_notes, []
        for note in pending_notes:
            self._tree.append("note", note)

    def _tree_required(self) -> ContextTree:
        if self._tree is None:
            raise RuntimeError("M-TREE adapter has not been started")
        return self._tree

    def _latest_exchange_text(self) -> str:
        if self._latest_action is None or self._latest_result is None:
            return ""
        return f"\n\nLatest action: {self._latest_action}\nFull result:\n{self._latest_result}"

    def _finish_accepted_action(self, *, step: int) -> None:
        reason = self._policy.accepted_action()
        if reason is None:
            return
        if self._epoch_record is not None:
            self._epoch_record["boundary_reason"] = reason
            self._epoch_record["end_event_count"] = self._tree_required().event_count
        self._epoch_record = None
        self._epoch_prefix = None
        self._epoch_reset_pending = True


def _tree_action_text(kind: str, arguments: Mapping[str, Any]) -> str:
    return f"{kind} {json.dumps(dict(arguments), ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)}"


def _tree_receipt_payload(receipt: Receipt) -> dict[str, Any]:
    return {
        "kind": receipt.kind,
        "success": receipt.success,
        "summary": receipt.summary,
        "state_change": receipt.state_change,
        "failure_class": receipt.failure_class,
        "payload": deepcopy(receipt.payload),
    }


def _tree_request_estimate(request: Mapping[str, Any]) -> int:
    raw = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return max(1, (len(raw.encode("utf-8")) + 3) // 4)
