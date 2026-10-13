"""Task-run cancellation shared by Harbor, kernel and provider boundaries.

Cancellation is control flow, not a model/provider failure. Harbor may revoke an
agent's authority while Aether is executing its synchronous kernel in a worker
thread. A thread-safe event lets every boundary stop admitting new work while
the async Harbor adapter waits for that worker to relinquish the task world
before returning cancellation to Harbor's grader lifecycle.
"""
from __future__ import annotations

from typing import Any


class RunCancellationRequested(Exception):
    """Raised when the external task lifecycle has revoked run authority."""


def cancellation_requested(event: Any | None) -> bool:
    is_set = getattr(event, "is_set", None)
    return bool(callable(is_set) and is_set())


def raise_if_run_cancelled(event: Any | None) -> None:
    if cancellation_requested(event):
        raise RunCancellationRequested("task run cancellation requested")


__all__ = [
    "RunCancellationRequested",
    "cancellation_requested",
    "raise_if_run_cancelled",
]
