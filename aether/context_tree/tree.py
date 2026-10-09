"""Strictly binary summary tree and ordered background builder [OptChat §3–4]."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import Context, copy_context
from dataclasses import dataclass
import math
import threading
import time
from typing import Any, Mapping, Sequence

from .compactor import NODE, Compactor
from ..run_deadline import remaining_run_s
from .store import RunStore
from .view import TreeView, ViewPart

JOBS = 8
RETRY = 10.0


@dataclass(frozen=True)
class NodeAddress:
    level: int
    index: int

    def __post_init__(self) -> None:
        if self.level < 0 or self.index < 0:
            raise ValueError("node coordinates must be non-negative")

    @property
    def span(self) -> int:
        return 1 << self.level

    @property
    def start(self) -> int:
        return self.index * self.span

    @property
    def end(self) -> int:
        return self.start + self.span

    @property
    def identifier(self) -> str:
        return f"{self.start}+{self.span}"


@dataclass(frozen=True)
class TreeNode:
    address: NodeAddress
    text: str
    event_count: int
    phase: str
    source: str


def covers(level: int, index: int) -> tuple[int, int]:
    address = NodeAddress(level, index)
    return address.start, address.end


def node_identifier(level: int, index: int) -> str:
    return NodeAddress(level, index).identifier


def _safe_exception_detail(exc: BaseException) -> dict[str, Any]:
    """Project only bounded exception metadata; never persist its message/body."""
    detail: dict[str, Any] = {"error_type": type(exc).__name__[:80]}
    current: BaseException | None = exc
    for _ in range(6):
        if current is None:
            break
        try:
            status = getattr(current, "status_code", None)
            status_code = int(status) if status is not None else None
        except (TypeError, ValueError):
            status_code = None
        if status_code is None:
            try:
                response = getattr(current, "response", None)
                status = getattr(response, "status_code", None)
                status_code = int(status) if status is not None else None
            except (TypeError, ValueError):
                status_code = None
        if status_code is not None and 100 <= status_code <= 599:
            detail["http_status"] = status_code
            detail["error_code"] = f"http_{status_code}"

        request_id: Any = None
        for name in ("_request_id", "request_id"):
            try:
                request_id = getattr(current, name, None)
            except Exception:  # noqa: BLE001 - never let diagnostics escape.
                request_id = None
            if _valid_request_id(request_id):
                break
            request_id = None
        if request_id is None:
            try:
                response = getattr(current, "response", None)
                headers = getattr(response, "headers", None)
                get_header = getattr(headers, "get", None)
                request_id = get_header("x-request-id") if callable(get_header) else None
            except Exception:  # noqa: BLE001 - read only the scalar correlation header.
                request_id = None
        if _valid_request_id(request_id):
            detail["provider_request_id"] = request_id.strip()
            break
        current = current.__cause__
    return detail


def _valid_request_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= 512
        and all(ord(char) >= 32 and ord(char) != 127 for char in value)
    )


class ContextTree:
    """Own one run's events, binary nodes, view and compactor workers."""

    def __init__(self, store: RunStore, compactor: Compactor | None = None, *,
                 node_bytes: int = NODE, view_bytes: int = 128_000,
                 jobs: int = JOBS, retry_s: float = RETRY,
                 on_failure: Any = None,
                 abort_event: threading.Event | None = None) -> None:
        if jobs < 1 or retry_s < 0:
            raise ValueError("invalid tree worker settings")
        self.store = store
        self.compactor = compactor
        self.node_bytes = int(node_bytes)
        self.jobs = int(jobs)
        self.retry_s = float(retry_s)
        self.on_failure = on_failure
        self.abort_event = abort_event
        self._worker_context: Context = copy_context()
        self.events: list[dict[str, Any]] = store.read_events()
        self._nodes: dict[tuple[int, int], TreeNode] = {}
        self._records: list[dict[str, Any]] = []
        self._active: set[tuple[int, int]] = set()
        self._timeline_count: int | None = None
        self._lock = threading.RLock()
        self._changed = threading.Condition(self._lock)
        self._executor = ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="m-tree")
        self._closed = False
        self._futures: dict[tuple[int, int], Future[Any]] = {}
        self._retrying: dict[tuple[int, int], threading.Timer] = {}
        self._reported_failures: set[tuple[int, int]] = set()
        self._failure_details: list[dict[str, Any]] = []
        self.node_failure_attempts = 0
        self.node_retry_attempts = 0
        self.view = TreeView(self, budget=view_bytes)
        for row in store.read_nodes():
            addr = NodeAddress(int(row["l"]), int(row["i"]))
            key = (addr.level, addr.index)
            if key in self._nodes:
                raise ValueError(f"duplicate append-only tree node {addr.identifier}")
            node = TreeNode(addr, str(row["text"]), int(row.get("event_count", len(self.events))),
                            str(row.get("phase", "node_complete")), str(row.get("source", "loaded")))
            self._nodes[key] = node
            self._records.append(row)
        self._repair_missing_free_nodes()
        self._rebuild_view()
        self.pump()

    @property
    def event_count(self) -> int:
        return self._timeline_count if self._timeline_count is not None else len(self.events)

    @property
    def failure_details(self) -> list[dict[str, Any]]:
        return list(self._failure_details)

    def get_event(self, index: int) -> dict[str, Any]:
        return self.events[index]

    def get_node(self, level: int, index: int) -> TreeNode | None:
        key = (int(level), int(index))
        if key not in self._active:
            return None
        return self._nodes.get(key)

    def append(self, kind: str, text: str) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("context tree is closed")
        event = self.store.append_event(kind, text)
        with self._lock:
            if event["i"] != len(self.events):
                raise ValueError("event stream is not contiguous")
            self.events.append(event)
            self._timeline_count = None
            self._create_free_closure(event_index=event["i"], phase="event_append")
            self.view.append(event["i"])
            self.pump()
            self._changed.notify_all()
        return event

    def first_unbuilt(self) -> int:
        for part in self.view.parts:
            if not self.view.is_built(part):
                return part.start
        return self.event_count

    def settle(self, *, timeout: float | None = None,
               abort_event: threading.Event | None = None) -> bool:
        abort_event = abort_event or self.abort_event
        deadline = None if timeout is None else time.monotonic() + timeout
        if abort_event is not None and abort_event.is_set():
            return False
        if deadline is not None and deadline <= time.monotonic():
            return False
        self.pump()
        with self._changed:
            while not self.view.settled:
                if abort_event is not None and abort_event.is_set():
                    return False
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._changed.wait(min(remaining, 0.05 if abort_event else remaining))
                else:
                    self._changed.wait(0.05 if abort_event else None)
                if abort_event is not None and abort_event.is_set():
                    return False
                if deadline is not None and deadline <= time.monotonic():
                    return False
                self.pump()
            if abort_event is not None and abort_event.is_set():
                return False
            if deadline is not None and deadline <= time.monotonic():
                return False
            return True

    def pump(self) -> None:
        with self._lock:
            if self._stop_requested():
                return
            if self.compactor is None and self.event_count:
                return
            while len(self._futures) < self.jobs:
                if self._stop_requested():
                    return
                total = self.event_count
                if not total:
                    return
                first = self.first_unbuilt()
                candidate: NodeAddress | None = None
                free_text: str | None = None
                for level in range(total.bit_length()):
                    span = 1 << level
                    for index in range(total // span):
                        address = NodeAddress(level, index)
                        key = (level, index)
                        end = index if level == 0 else address.end
                        if key in self._nodes or key in self._futures or key in self._retrying:
                            continue
                        if end > first or not self._sources_exist(address):
                            continue
                        free_text = self._free_text(address)
                        candidate = address
                        break
                    if candidate is not None:
                        break
                if candidate is None:
                    return
                if free_text is not None:
                    self._persist_node(candidate, free_text, phase="node_complete", source="free")
                    self.view.fit()
                    self._create_free_closure(event_index=None, phase="node_complete")
                    self.view.fit()
                    self._changed.notify_all()
                    continue
                if self.compactor is None:
                    return
                context_lines = self._compactor_context(candidate)
                event = self.events[candidate.index] if candidate.level == 0 else None
                children = (
                    () if candidate.level == 0 else
                    tuple(self._nodes[(candidate.level - 1, child_index)].text
                          for child_index in (candidate.index * 2, candidate.index * 2 + 1))
                )
                worker_context = self._worker_context.copy()
                future = self._executor.submit(
                    worker_context.run, self.compactor.summarize,
                    level=candidate.level, event=event, children=children,
                    context_lines=context_lines,
                )
                self._futures[(candidate.level, candidate.index)] = future
                if key in self._reported_failures:
                    self.node_retry_attempts += 1
                future.add_done_callback(
                    lambda finished, addr=candidate: self._finish_node(addr, finished)
                )

    def _sources_exist(self, address: NodeAddress) -> bool:
        if address.level == 0:
            return address.index < len(self.events)
        return ((address.level - 1, address.index * 2) in self._active
                and (address.level - 1, address.index * 2 + 1) in self._active)

    def _free_text(self, address: NodeAddress) -> str | None:
        if address.level == 0:
            event = self.events[address.index]
            text = f"{event['kind']}: {event['text']}"
        else:
            left = self._nodes.get((address.level - 1, address.index * 2))
            right = self._nodes.get((address.level - 1, address.index * 2 + 1))
            if left is None or right is None:
                return None
            text = left.text + "\n" + right.text
        return text if len(text.encode("utf-8")) <= self.node_bytes else None

    def _persist_node(self, address: NodeAddress, text: str, *, phase: str, source: str) -> TreeNode:
        if len(text.encode("utf-8")) > self.node_bytes and source == "free":
            raise ValueError("free node source exceeds NODE")
        event_count = self.event_count
        row = self.store.append_node(address.level, address.index, text,
                                     event_count=event_count, phase=phase, source=source)
        node = TreeNode(address, text, event_count, phase, source)
        key = (address.level, address.index)
        self._nodes[key] = node
        self._active.add(key)
        self._records.append(row)
        return node

    def _create_free_closure(self, *, event_index: int | None, phase: str) -> None:
        if event_index is not None:
            leaf = NodeAddress(0, event_index)
            if (leaf.level, leaf.index) not in self._nodes:
                text = self._free_text(leaf)
                if text is not None:
                    self._persist_node(leaf, text, phase=phase, source="free")
        changed = True
        while changed:
            changed = False
            max_level = max(1, len(self.events).bit_length())
            for level in range(1, max_level):
                for index in range(len(self.events) // (1 << level)):
                    key = (level, index)
                    if key in self._nodes:
                        continue
                    address = NodeAddress(level, index)
                    if not self._sources_exist(address):
                        continue
                    text = self._free_text(address)
                    if text is None:
                        continue
                    self._persist_node(address, text, phase=phase, source="free")
                    changed = True

    def _compactor_context(self, address: NodeAddress) -> list[str]:
        cutoff = address.start if address.level == 0 else address.end
        rows = []
        for part in self.view.parts:
            if part.end > cutoff:
                continue
            node = self.get_node(part.level, part.index)
            if node is not None:
                rows.append(node.text.replace("\n", " "))
        return rows

    def _finish_node(self, address: NodeAddress, future: Future[Any]) -> None:
        key = (address.level, address.index)
        with self._lock:
            self._futures.pop(key, None)
            if self._stop_requested():
                self._changed.notify_all()
                return
            try:
                result = future.result()
            except Exception as exc:
                detail = {"node": address.identifier, **_safe_exception_detail(exc)}
                self.node_failure_attempts += 1
                if key not in self._reported_failures:
                    self._reported_failures.add(key)
                    self._failure_details.append(detail)
                    if self.on_failure is not None:
                        self.on_failure(dict(detail))
                timer = threading.Timer(self.retry_s, self._retry_node, args=(address,))
                timer.daemon = True
                self._retrying[key] = timer
                timer.start()
            else:
                if self._stop_requested():
                    self._changed.notify_all()
                    return
                text = result.text if hasattr(result, "text") else str(result)
                self._persist_node(address, text, phase="node_complete", source="compactor")
                self.view.fit()
                self._create_free_closure(event_index=None, phase="node_complete")
                self.view.fit()
            self._changed.notify_all()
        self.pump()

    def _retry_node(self, address: NodeAddress) -> None:
        with self._lock:
            self._retrying.pop((address.level, address.index), None)
            self._changed.notify_all()
            if self._stop_requested():
                return
        self.pump()

    def _stop_requested(self) -> bool:
        if self._closed or (self.abort_event is not None and self.abort_event.is_set()):
            return True
        remaining = self._worker_context.copy().run(remaining_run_s)
        return remaining is not None and remaining <= 0.0

    def _repair_missing_free_nodes(self) -> None:
        """Recover deterministic free nodes without rewriting existing records."""
        if self._nodes:
            self._active = set(self._nodes)
            return
        self._active = set()
        for index in range(len(self.events)):
            self._timeline_count = index + 1
            self._create_free_closure(event_index=index, phase="event_append")
        self._timeline_count = None

    def _rebuild_view(self) -> None:
        """Replay append and node-completion order, then restore the live view."""
        old_active = set(self._active)
        self._active = set()
        self.view = TreeView(self, budget=self.view.budget)
        records_by_t: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for row in self._records:
            event_count = int(row.get("event_count", len(self.events)))
            phase = str(row.get("phase", "node_complete"))
            records_by_t.setdefault((event_count, phase), []).append(row)
        for index in range(len(self.events)):
            t = index + 1
            self._timeline_count = t
            for row in records_by_t.get((t, "event_append"), ()):
                self._active.add((int(row["l"]), int(row["i"])))
            self.view.append(index)
            for row in records_by_t.get((t, "node_complete"), ()):
                self._active.add((int(row["l"]), int(row["i"])))
                self.view.fit()
        self._timeline_count = None
        self._active = old_active

    def refold_view(self) -> TreeView:
        self._rebuild_view()
        return self.view

    def wait_for_idle(self, *, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        with self._changed:
            while self._futures or self._retrying:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._changed.wait(remaining)
            return True

    def close(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for timer in self._retrying.values():
                timer.cancel()
            self._retrying.clear()
            for future in tuple(self._futures.values()):
                future.cancel()
            self._changed.notify_all()
        self._executor.shutdown(wait=wait, cancel_futures=True)
