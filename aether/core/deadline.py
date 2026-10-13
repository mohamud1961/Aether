"""Task-scoped monotonic wall-clock authority shared across Aether layers.

The deadline is deliberately observational/pre-dispatch authority. Callers may
refuse to start new work or abort provider waits when it expires. Mutating
remote operations that are already in flight retain their existing lifecycle
and cleanup semantics; this module does not manufacture replay/cancellation
authority for ambiguous mutations.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_deadline_monotonic: ContextVar[float | None] = ContextVar(
    "aether_run_deadline_monotonic",
    default=None,
)
_cleanup_authority_depth: ContextVar[int] = ContextVar(
    "aether_run_deadline_cleanup_authority_depth",
    default=0,
)
_excluded_wait_depth: ContextVar[int] = ContextVar(
    "aether_run_deadline_excluded_wait_depth",
    default=0,
)


class KernelRunTimeout(TimeoutError):
    """The task-owned monotonic deadline expired on the current critical path."""


@contextmanager
def run_deadline(deadline_monotonic: float | None) -> Iterator[None]:
    """Bind one task deadline for nested provider/executor boundaries."""
    normalized = None if deadline_monotonic is None else float(deadline_monotonic)
    token = _deadline_monotonic.set(normalized)
    try:
        yield
    finally:
        _deadline_monotonic.reset(token)


def run_deadline_wait_exclusion_active() -> bool:
    """Return whether the current lexical scope excludes infrastructure wait.

    This is deliberately narrow research authority.  It is used only around
    shared cross-row provider admission, never around provider generation,
    model reasoning, tool execution, or local task work.
    """
    return int(_excluded_wait_depth.get()) > 0


@contextmanager
def run_deadline_excluded_wait() -> Iterator[None]:
    """Exclude one bounded infrastructure wait from the scientific task clock.

    The scope refuses to revive an already-expired task.  For the outermost
    exclusion, the bound task deadline is shifted forward by exactly the
    monotonic time spent inside the scope.  Nested exclusions do not
    double-count elapsed time.  Any independent outer process/wave deadline is
    unaffected.
    """
    deadline = _deadline_monotonic.get()
    if deadline is None:
        yield
        return
    started = time.monotonic()
    if deadline <= started:
        raise KernelRunTimeout(
            "task run deadline exceeded before excluded infrastructure wait"
        )
    depth = int(_excluded_wait_depth.get())
    token = _excluded_wait_depth.set(depth + 1)
    try:
        yield
    finally:
        try:
            if depth == 0:
                current = _deadline_monotonic.get()
                if current is not None:
                    _deadline_monotonic.set(
                        float(current) + max(0.0, time.monotonic() - started)
                    )
        finally:
            _excluded_wait_depth.reset(token)


def remaining_run_s() -> float | None:
    """Return remaining task wall time, or None when no task deadline is bound."""
    deadline = _deadline_monotonic.get()
    if deadline is None:
        return None
    return max(0.0, deadline - time.monotonic())


@contextmanager
def run_deadline_cleanup_authority() -> Iterator[None]:
    """Permit bounded teardown/observation after task execution authority expires.

    This authority is intentionally lexical and non-transitive across task code:
    callers must opt in around cleanup they already own. It does not restore
    permission to launch new task mutations after the deadline.
    """
    depth = int(_cleanup_authority_depth.get())
    token = _cleanup_authority_depth.set(depth + 1)
    try:
        yield
    finally:
        _cleanup_authority_depth.reset(token)


def raise_if_run_deadline_exceeded() -> None:
    """Fail before new task work unless the current scope is bounded cleanup."""
    if int(_cleanup_authority_depth.get()) > 0:
        return
    remaining = remaining_run_s()
    if remaining is not None and remaining <= 0.0:
        raise KernelRunTimeout("task run deadline exceeded")
