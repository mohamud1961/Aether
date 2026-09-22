from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
import time

import pytest

import aether.provider_pacing as pacing_module
from aether.provider_pacing import (
    ProviderThroughputError,
    SerialTokenPacer,
    SharedDeploymentTokenPacer,
)
from aether.run_deadline import KernelRunTimeout, run_deadline, run_deadline_excluded_wait


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class ProcessSharedFakeClock:
    """Advance quota time only during pacer sleeps across spawned workers."""

    def __init__(self, ctx) -> None:
        self._now = ctx.Value("d", 0.0)

    def clock(self) -> float:
        with self._now.get_lock():
            return float(self._now.value)

    def sleep(self, seconds: float) -> None:
        with self._now.get_lock():
            self._now.value += seconds
        time.sleep(seconds)


def _shared_pacer_process(role, state_path, first_admitted, result_queue, shared_clock):
    pacer = SharedDeploymentTokenPacer(
        state_path=Path(state_path),
        deployment="https://provider.example/deployments/shared",
        token_limit=100,
        request_limit=600,
        window_s=0.6,
        clock=shared_clock.clock,
        sleep=shared_clock.sleep,
    )
    admission = pacer.admit(estimated_tokens=80)
    if role == "first":
        first_admitted.set()
        time.sleep(0.15)
        pacer.reconcile_observed_usage(
            reservation_id=admission["throughput_reservation_id"],
            input_tokens=50,
            output_tokens=30,
            requested_output_tokens=80,
        )
    result_queue.put({"role": role, "admission": admission})


def test_serial_token_pacer_smooths_and_enforces_rolling_window() -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000, window_s=60.0, clock=fake.clock, sleep=fake.sleep,
    )

    first = pacer.admit(estimated_tokens=50_000)
    second = pacer.admit(estimated_tokens=25_000)
    third = pacer.admit(estimated_tokens=30_000)

    assert first["throughput_wait_s"] == 0
    assert first["throughput_spacing_s"] == 30
    assert second["throughput_wait_s"] == 30
    # At t=45 the three reservations would total 105K, so the third create
    # must wait for the t=0 reservation to leave the 60-second window.
    assert third["throughput_wait_s"] == 30
    assert third["throughput_rolling_wait_s"] == 15
    assert fake.now == 60


def test_success_usage_can_extend_rolling_reservation() -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000, window_s=60.0, clock=fake.clock, sleep=fake.sleep,
    )

    pacer.admit(estimated_tokens=20_000)
    reconciled = pacer.reconcile_success(input_tokens=70_000, requested_output_tokens=20_000)
    next_row = pacer.admit(estimated_tokens=20_000)

    assert reconciled["throughput_reconciled_tokens"] == 90_000
    assert next_row["throughput_wait_s"] == 60
    assert next_row["throughput_rolling_wait_s"] == 6
    assert fake.now == 60


def test_serial_pacer_default_keeps_requested_output_cap_with_observed_usage() -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000, window_s=60.0, clock=fake.clock, sleep=fake.sleep,
    )

    pacer.admit(estimated_tokens=17_384)
    reconciled = pacer.reconcile_success(
        input_tokens=1_000,
        requested_output_tokens=16_384,
        output_tokens=200,
    )

    assert reconciled["throughput_reconciled_tokens"] == 17_384


def test_serial_pacer_observed_output_challenger_uses_valid_usage() -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000,
        window_s=60.0,
        settlement_mode="observed_output",
        clock=fake.clock,
        sleep=fake.sleep,
    )

    pacer.admit(estimated_tokens=17_384)
    reconciled = pacer.reconcile_success(
        input_tokens=1_000,
        requested_output_tokens=16_384,
        output_tokens=200,
    )

    assert reconciled["throughput_reconciled_tokens"] == 1_200


@pytest.mark.parametrize("output_tokens", [None, -1, True, "unknown"])
def test_serial_pacer_observed_output_challenger_falls_back_to_cap_for_invalid_usage(
    output_tokens: object,
) -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000,
        window_s=60.0,
        settlement_mode="observed_output",
        clock=fake.clock,
        sleep=fake.sleep,
    )

    pacer.admit(estimated_tokens=17_384)
    reconciled = pacer.reconcile_success(
        input_tokens=1_000,
        requested_output_tokens=16_384,
        output_tokens=output_tokens,
    )

    assert reconciled["throughput_reconciled_tokens"] == 17_384


def test_trace_shaped_growing_loads_do_not_overflow_rolling_100k() -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000, window_s=60.0, clock=fake.clock, sleep=fake.sleep,
    )
    actual = (24_019, 24_968, 27_578, 30_617, 33_679, 36_245)
    dispatches: list[tuple[float, int]] = []
    for load in actual:
        row = pacer.admit(estimated_tokens=load)
        dispatches.append((fake.now, load))
        pacer.reconcile_success(input_tokens=load - 16_000, requested_output_tokens=16_000)
        # The currently live rolling window must remain within quota.
        assert row["throughput_active_reserved_tokens"] <= 100_000

    for now, _ in dispatches:
        live = sum(load for sent, load in dispatches if sent <= now and sent > now - 60.0)
        assert live <= 100_000


def test_pacing_refuses_wait_that_would_cross_task_deadline() -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000, window_s=60.0, clock=fake.clock, sleep=fake.sleep,
    )
    pacer.admit(estimated_tokens=100_000)

    with run_deadline(time.monotonic() + 0.1):
        with pytest.raises(KernelRunTimeout, match="throughput pacing"):
            pacer.admit(estimated_tokens=1)

    assert fake.sleeps == []


def test_explicit_rate_limit_forces_one_full_window_before_next_create() -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000, window_s=60.0, clock=fake.clock, sleep=fake.sleep,
    )
    pacer.note_rate_limit()
    row = pacer.admit(estimated_tokens=1)
    assert row["throughput_wait_s"] == 60
    assert fake.sleeps == [60]


def test_saturated_usage_waits_full_window_after_response_settlement() -> None:
    fake = FakeClock()
    pacer = SerialTokenPacer(
        token_limit=100_000, window_s=62.0, clock=fake.clock, sleep=fake.sleep,
    )

    pacer.admit(estimated_tokens=100_000)
    fake.now += 15.0  # Simulate provider generation/response latency.
    reconciled = pacer.reconcile_success(
        input_tokens=101_000, requested_output_tokens=32_768,
    )
    second = pacer.admit(estimated_tokens=100_000)

    assert reconciled["throughput_window_anchor"] == "response_settlement"
    assert second["throughput_wait_s"] == 62.0
    assert fake.now == 77.0


def test_shared_pacer_accounts_actual_wait_and_separates_spacing_from_quota(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = SharedDeploymentTokenPacer(
        state_path=tmp_path / "shared.json",
        deployment="deployment-a",
        token_limit=100,
        request_limit=1000,
        window_s=0.6,
        clock=fake.clock,
        sleep=fake.sleep,
    )
    first = pacer.admit(estimated_tokens=80)
    fake.now = 0.2
    pacer.reconcile_observed_usage(
        reservation_id=first["throughput_reservation_id"],
        input_tokens=50,
        output_tokens=30,
        requested_output_tokens=80,
    )

    next_request = pacer.admit(estimated_tokens=20)

    # No dispatch-spacing wait; 80 tokens were settled at 0.2 s, 20 more fit.
    assert next_request["throughput_wait_s"] == 0
    assert next_request["throughput_wait_by_reason_s"]["dispatch_spacing"] == 0.0
    assert next_request["throughput_rolling_wait_s"] == 0


def test_shared_pacer_dispatch_anchor_expires_quota_from_dispatch_time(tmp_path: Path) -> None:
    def next_wait(window_anchor: str) -> tuple[float, dict[str, object], dict[str, object]]:
        fake = FakeClock()
        pacer = SharedDeploymentTokenPacer(
            state_path=tmp_path / f"{window_anchor}.json",
            deployment="deployment-a",
            token_limit=100,
            request_limit=600,
            window_s=60,
            window_anchor=window_anchor,
            clock=fake.clock,
            sleep=fake.sleep,
        )
        first = pacer.admit(estimated_tokens=100)
        fake.now += 15.0  # Simulate provider latency after dispatch.
        settlement = pacer.reconcile_observed_usage(
            reservation_id=first["throughput_reservation_id"],
            input_tokens=100,
            output_tokens=0,
            requested_output_tokens=100,
        )
        second = pacer.admit(estimated_tokens=100)
        return second["throughput_wait_s"], settlement, second

    settlement_wait, settlement_info, _ = next_wait("settlement")
    dispatch_wait, dispatch_info, _ = next_wait("dispatch")

    assert settlement_info["throughput_window_anchor"] == "response_settlement"
    assert settlement_wait == pytest.approx(60.0)
    assert dispatch_info["throughput_window_anchor"] == "dispatch"
    assert dispatch_wait == pytest.approx(45.0)
    assert settlement_wait - dispatch_wait == pytest.approx(15.0)


def test_shared_pacer_fails_closed_when_window_anchor_changes(tmp_path: Path) -> None:
    path = tmp_path / "shared-anchor.json"
    settlement = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=600,
        window_s=60,
        window_anchor="settlement",
    )
    settlement.admit(estimated_tokens=20)

    dispatch = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=600,
        window_s=60,
        window_anchor="dispatch",
    )
    with pytest.raises(ProviderThroughputError, match="window_anchor"):
        dispatch.admit(estimated_tokens=20)


def test_dispatch_anchor_keeps_dead_owner_reservation_for_full_window(
    tmp_path: Path,
) -> None:
    fake = FakeClock()
    pacer = SharedDeploymentTokenPacer(
        state_path=tmp_path / "dead-owner.json",
        deployment="deployment-a",
        token_limit=100,
        request_limit=600,
        window_s=60,
        window_anchor="dispatch",
        clock=fake.clock,
        sleep=fake.sleep,
    )
    pacer.admit(estimated_tokens=100)
    fake.now = 120.0
    state_path = tmp_path / "dead-owner.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["reservations"][0]["owner_pid"] = 999_999_999
    state_path.write_text(json.dumps(state), encoding="utf-8")
    pacer._pid_alive = lambda pid: pid != 999_999_999  # noqa: SLF001 - model a crashed owner

    next_request = pacer.admit(estimated_tokens=100)

    assert next_request["throughput_wait_s"] == pytest.approx(60.0)
    assert fake.now == pytest.approx(180.0)


def test_shared_pacer_is_one_fifo_quota_across_two_processes(tmp_path: Path) -> None:
    ctx = multiprocessing.get_context("spawn")
    state_path = tmp_path / "shared-limiter.json"
    first_admitted = ctx.Event()
    results = ctx.Queue()
    shared_clock = ProcessSharedFakeClock(ctx)
    first = ctx.Process(
        target=_shared_pacer_process,
        args=("first", str(state_path), first_admitted, results, shared_clock),
    )
    second = ctx.Process(
        target=_shared_pacer_process,
        args=("second", str(state_path), first_admitted, results, shared_clock),
    )
    first.start()
    assert first_admitted.wait(5), "first process failed to reserve shared capacity"
    second.start()
    first.join(5)
    second.join(5)

    assert first.exitcode == 0
    assert second.exitcode == 0
    records = [results.get(timeout=2), results.get(timeout=2)]
    by_role = {item["role"]: item["admission"] for item in records}
    assert by_role["first"]["throughput_wait_s"] < 0.1
    second_admission = by_role["second"]
    assert second_admission["throughput_wait_by_reason_s"]["rolling_quota"] >= 0.35
    assert second_admission["throughput_wait_s"] >= 0.35
    assert second_admission["throughput_active_reserved_tokens"] == 80


def test_shared_pacer_fails_closed_on_corrupt_state(tmp_path: Path) -> None:
    state_path = tmp_path / "shared-limiter.json"
    state_path.write_text("{truncated", encoding="utf-8")
    state_path.chmod(0o600)
    pacer = SharedDeploymentTokenPacer(
        state_path=state_path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=600,
        window_s=60,
    )

    with pytest.raises(ProviderThroughputError, match="corrupt"):
        pacer.admit(estimated_tokens=20)


def test_shared_pacer_fails_closed_on_existing_empty_state_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "shared.json"
    before_restart = FakeClock()
    before_restart.now = 1000.0
    old = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=1,
        window_s=60,
        clock=before_restart.clock,
        sleep=before_restart.sleep,
        boot_id="boot-a",
    )
    old.admit(estimated_tokens=80)

    # Model a crash after the old in-place writer truncated the durable ledger.
    path.write_bytes(b"")
    after_restart = FakeClock()
    restarted = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=1,
        window_s=60,
        clock=after_restart.clock,
        sleep=after_restart.sleep,
        boot_id="boot-b",
    )

    with pytest.raises(ProviderThroughputError, match="empty|corrupt"):
        restarted.admit(estimated_tokens=80)


def test_shared_pacer_partial_state_write_keeps_old_reservation_usable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "shared.json"
    before_restart = FakeClock()
    before_restart.now = 1000.0
    old = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=600,
        window_s=60,
        clock=before_restart.clock,
        sleep=before_restart.sleep,
        boot_id="boot-a",
    )
    old.admit(estimated_tokens=80)
    old_state = path.read_bytes()

    real_write = os.write
    failed = False

    def partial_then_fail(fd: int, data: bytes | memoryview) -> int:
        nonlocal failed
        if not failed:
            failed = True
            prefix = data[: max(1, len(data) // 2)]
            real_write(fd, prefix)
            raise OSError("simulated partial state write")
        return real_write(fd, data)

    monkeypatch.setattr(pacing_module.os, "write", partial_then_fail)
    with pytest.raises(OSError, match="simulated partial state write"):
        old.admit(estimated_tokens=20)
    monkeypatch.undo()

    assert failed
    assert path.read_bytes() == old_state
    assert sum(row["tokens"] for row in json.loads(old_state)["reservations"]) == 80

    after_restart = FakeClock()
    restarted = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=600,
        window_s=60,
        clock=after_restart.clock,
        sleep=after_restart.sleep,
        boot_id="boot-b",
    )
    next_admission = restarted.admit(estimated_tokens=30)

    assert next_admission["throughput_wait_s"] == pytest.approx(60.0)
    assert next_admission["throughput_active_reserved_tokens"] == 30


def test_shared_pacer_enforces_request_rate_below_tpm_capacity(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = SharedDeploymentTokenPacer(
        state_path=tmp_path / "shared.json",
        deployment="deployment-a",
        token_limit=300_000,
        request_limit=300,
        window_s=60,
        clock=fake.clock,
        sleep=fake.sleep,
    )

    first = pacer.admit(estimated_tokens=100)
    second = pacer.admit(estimated_tokens=100)

    assert first["throughput_request_limit"] == 300
    assert first["throughput_spacing_s"] == 0.0
    assert second["throughput_wait_by_reason_s"]["dispatch_spacing"] == 0.0
    assert second["throughput_wait_s"] == 0
    assert second["throughput_wait_by_reason_s"]["request_rate"] == 0


def test_shared_pacer_rebases_live_reservations_after_monotonic_restart(tmp_path: Path) -> None:
    path = tmp_path / "shared.json"
    before_restart = FakeClock()
    before_restart.now = 1000.0
    old = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=600,
        window_s=60,
        clock=before_restart.clock,
        sleep=before_restart.sleep,
        boot_id="boot-a",
    )
    first = old.admit(estimated_tokens=80)
    old.reconcile_observed_usage(
        reservation_id=first["throughput_reservation_id"],
        input_tokens=50,
        output_tokens=30,
        requested_output_tokens=80,
    )

    after_restart = FakeClock()
    new = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100,
        request_limit=600,
        window_s=60,
        clock=after_restart.clock,
        sleep=after_restart.sleep,
        boot_id="boot-b",
    )
    second = new.admit(estimated_tokens=30)

    assert second["throughput_wait_s"] == pytest.approx(60.0)
    assert second["throughput_wait_s"] < 1000
    assert second["throughput_active_reserved_tokens"] == 30


def test_shared_pacer_rebases_rpm_reservation_age_after_monotonic_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "shared-rpm.json"
    before_restart = FakeClock()
    before_restart.now = 1000.0
    old = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100_000,
        request_limit=1,
        window_s=60,
        clock=before_restart.clock,
        sleep=before_restart.sleep,
        boot_id="boot-a",
    )
    first = old.admit(estimated_tokens=10)
    old.reconcile_observed_usage(
        reservation_id=first["throughput_reservation_id"],
        input_tokens=8,
        output_tokens=2,
        requested_output_tokens=10,
    )

    after_restart = FakeClock()
    new = SharedDeploymentTokenPacer(
        state_path=path,
        deployment="deployment-a",
        token_limit=100_000,
        request_limit=1,
        window_s=60,
        clock=after_restart.clock,
        sleep=after_restart.sleep,
        boot_id="boot-b",
    )
    second = new.admit(estimated_tokens=10)

    assert second["throughput_wait_s"] == pytest.approx(60.0)
    assert sum(after_restart.sleeps) == pytest.approx(60.0)
    assert second["throughput_wait_s"] < 1060.0


def test_shared_pacer_can_exclude_cross_row_queue_wait_from_task_deadline(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = SharedDeploymentTokenPacer(
        state_path=tmp_path / "shared-excluded.json",
        deployment="deployment-a",
        token_limit=100,
        request_limit=1000,
        window_s=0.6,
        clock=fake.clock,
        sleep=fake.sleep,
    )
    first = pacer.admit(estimated_tokens=80)
    pacer.reconcile_observed_usage(
        reservation_id=first["throughput_reservation_id"],
        input_tokens=80,
        output_tokens=0,
        requested_output_tokens=80,
    )

    with run_deadline(time.monotonic() + 0.1):
        with pytest.raises(KernelRunTimeout, match="shared provider limiter wait"):
            pacer.admit(estimated_tokens=80)

    with run_deadline(time.monotonic() + 0.1):
        with run_deadline_excluded_wait():
            admitted = pacer.admit(estimated_tokens=80)

    assert admitted["throughput_wait_s"] > 0
