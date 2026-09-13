"""Thread-local wall-clock budget shared by verifier provider turns."""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_deadline_monotonic: ContextVar[float | None] = ContextVar(
    "aether_verifier_deadline_monotonic", default=None,
)


@contextmanager
def verifier_generation_deadline(deadline_monotonic: float) -> Iterator[None]:
    """Expose one verifier generation's absolute deadline to nested calls."""
    token = _deadline_monotonic.set(float(deadline_monotonic))
    try:
        yield
    finally:
        _deadline_monotonic.reset(token)


def remaining_verifier_generation_s() -> float | None:
    """Return remaining wall-clock time for this verifier generation, if bound."""
    deadline = _deadline_monotonic.get()
    if deadline is None:
        return None
    return max(0.0, deadline - time.monotonic())
