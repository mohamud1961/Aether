from __future__ import annotations

import time

import pytest

from aether.run_deadline import (
    KernelRunTimeout,
    raise_if_run_deadline_exceeded,
    remaining_run_s,
    run_deadline,
    run_deadline_cleanup_authority,
    run_deadline_excluded_wait,
    run_deadline_wait_exclusion_active,
)


def test_run_deadline_scope_reports_remaining_and_resets() -> None:
    assert remaining_run_s() is None
    with run_deadline(time.monotonic() + 1.0):
        remaining = remaining_run_s()
        assert remaining is not None
        assert 0.0 < remaining <= 1.0
        raise_if_run_deadline_exceeded()
    assert remaining_run_s() is None


def test_expired_run_deadline_fails_closed() -> None:
    with run_deadline(time.monotonic() - 1.0):
        assert remaining_run_s() == 0.0
        with pytest.raises(KernelRunTimeout, match="task run deadline exceeded"):
            raise_if_run_deadline_exceeded()



def test_expired_run_deadline_allows_only_explicit_cleanup_scope() -> None:
    with run_deadline(time.monotonic() - 1.0):
        with pytest.raises(KernelRunTimeout):
            raise_if_run_deadline_exceeded()
        with run_deadline_cleanup_authority():
            raise_if_run_deadline_exceeded()
        with pytest.raises(KernelRunTimeout):
            raise_if_run_deadline_exceeded()


def test_excluded_wait_shifts_only_bound_task_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    import aether.run_deadline as deadline_module

    now = [100.0]
    monkeypatch.setattr(deadline_module.time, "monotonic", lambda: now[0])
    with run_deadline(110.0):
        assert remaining_run_s() == pytest.approx(10.0)
        with run_deadline_excluded_wait():
            assert run_deadline_wait_exclusion_active()
            now[0] += 7.0
            # The clock still observes elapsed wall time inside the lexical
            # exclusion; only the final scientific deadline is compensated.
            assert remaining_run_s() == pytest.approx(3.0)
        assert not run_deadline_wait_exclusion_active()
        assert remaining_run_s() == pytest.approx(10.0)
        now[0] += 10.1
        with pytest.raises(KernelRunTimeout):
            raise_if_run_deadline_exceeded()


def test_excluded_wait_refuses_to_revive_expired_task(monkeypatch: pytest.MonkeyPatch) -> None:
    import aether.run_deadline as deadline_module

    now = [100.0]
    monkeypatch.setattr(deadline_module.time, "monotonic", lambda: now[0])
    with run_deadline(99.0):
        with pytest.raises(KernelRunTimeout, match="before excluded infrastructure wait"):
            with run_deadline_excluded_wait():
                raise AssertionError("unreachable")
