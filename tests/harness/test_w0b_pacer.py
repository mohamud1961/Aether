"""W0-B pacer: no spacing wait, p95 output estimate, header authority, 429 tightening."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from aether.provider_pacing import ProviderThroughputError, SharedDeploymentTokenPacer


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def make(tmp_path: Path, fake: FakeClock, *, token_limit: int = 300_000, cls=SharedDeploymentTokenPacer):
    return cls(
        state_path=tmp_path / "shared.json",
        deployment="deployment-a",
        token_limit=token_limit,
        request_limit=100_000,
        window_s=60,
        clock=fake.clock,
        sleep=fake.sleep,
    )


def settle(pacer, admitted, *, input_tokens=1000, output_tokens=100):
    pacer.reconcile_observed_usage(
        reservation_id=admitted["throughput_reservation_id"],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        requested_output_tokens=16384,
    )


def test_back_to_back_admissions_have_no_spacing_wait(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = make(tmp_path, fake)
    results = [pacer.admit(estimated_tokens=50_000) for _ in range(4)]
    assert fake.now == 1000.0
    for row in results:
        assert row["throughput_wait_s"] == 0
        assert row["throughput_wait_by_reason_s"]["dispatch_spacing"] == 0.0
        assert row["throughput_spacing_s"] == 0.0


def test_expected_output_is_p95_of_observed_and_capped(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = make(tmp_path, fake)
    # Initial: 4096, never above the requested cap.
    assert pacer.expected_output_tokens(16384) == 4096
    assert pacer.expected_output_tokens(1000) == 1000
    assert pacer.approximate_request_tokens(4000, 16384) == 1000 + 4096
    outputs = [100] * 19 + [900]
    for out in outputs:
        settle(pacer, pacer.admit(estimated_tokens=5000), output_tokens=out)
    # nearest-rank p95 of 20 samples is the 19th value.
    assert pacer.expected_output_tokens(16384) == 100
    for _ in range(5):
        settle(pacer, pacer.admit(estimated_tokens=5000), output_tokens=8000)
    assert pacer.expected_output_tokens(16384) == 8000
    assert pacer.expected_output_tokens(2000) == 2000
    assert pacer.approximate_request_tokens(4000, 16384) == 1000 + 8000
    # A second instance on the same state file sees the same distribution.
    other = make(tmp_path, fake)
    assert other.expected_output_tokens(16384) == 8000


def test_header_report_admits_with_headroom_even_when_local_ledger_is_full(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = make(tmp_path, fake, token_limit=100_000)
    first = pacer.admit(estimated_tokens=90_000)
    settle(pacer, first, input_tokens=60_000, output_tokens=30_000)
    # Local accounting would hold the next 60 s window (90k + 50k > 100k).
    pacer.report_rate_limit_headers(
        remaining_tokens=95_000, remaining_requests=500,
        reservation_id=first["throughput_reservation_id"],
    )
    second = pacer.admit(estimated_tokens=80_000)  # 80k <= 95k * 0.9
    assert second["throughput_admission_basis"] == "provider_headers"
    assert second["throughput_wait_s"] == 0
    assert fake.now == 1000.0


def test_header_report_waits_when_remaining_is_low_then_falls_back_when_stale(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = make(tmp_path, fake)
    pacer.report_rate_limit_headers(remaining_tokens=10_000)
    row = pacer.admit(estimated_tokens=20_000)
    # Waited until the report went stale, then used local accounting.
    assert row["throughput_wait_s"] >= SharedDeploymentTokenPacer.HEADER_FRESH_S
    assert row["throughput_wait_by_reason_s"]["rolling_quota"] >= SharedDeploymentTokenPacer.HEADER_FRESH_S
    assert row["throughput_admission_basis"] == "local_accounting"


def test_header_report_subtracts_requests_admitted_after_report(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = make(tmp_path, fake)
    pacer.report_rate_limit_headers(remaining_tokens=100_000, observed_at=fake.now)
    fake.now += 1
    a = pacer.admit(estimated_tokens=50_000)
    assert a["throughput_admission_basis"] == "provider_headers"
    b = pacer.admit(estimated_tokens=50_000)  # 50k + 50k > 90k
    assert b["throughput_wait_s"] >= SharedDeploymentTokenPacer.HEADER_FRESH_S - 1.001
    assert b["throughput_admission_basis"] == "local_accounting"


def test_header_remaining_requests_zero_blocks(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = make(tmp_path, fake)
    pacer.report_rate_limit_headers(remaining_tokens=200_000, remaining_requests=0)
    row = pacer.admit(estimated_tokens=1000)
    assert row["throughput_wait_s"] >= SharedDeploymentTokenPacer.HEADER_FRESH_S


def test_two_pacers_on_one_state_file_cannot_spend_same_remaining_quota(tmp_path: Path) -> None:
    class QuickStale(SharedDeploymentTokenPacer):
        HEADER_FRESH_S = 1.0
        _POLL_S = 0.05

    path = tmp_path / "shared.json"

    def build():
        return QuickStale(
            state_path=path, deployment="deployment-a", token_limit=1_000_000,
            request_limit=100_000, window_s=60,
        )

    build().report_rate_limit_headers(remaining_tokens=100_000, remaining_requests=1000)
    results: list[dict] = []
    guard = threading.Lock()
    barrier = threading.Barrier(8)

    def worker() -> None:
        pacer = build()
        barrier.wait()
        row = pacer.admit(estimated_tokens=30_000)
        with guard:
            results.append(row)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert len(results) == 8
    by_header = [r for r in results if r["throughput_admission_basis"] == "provider_headers"]
    # 100k * 0.9 = 90k of header headroom => at most three 30k requests.
    assert len(by_header) == 3
    assert sum(r["throughput_estimated_tokens"] for r in by_header) <= 90_000


def test_429_blocks_until_retry_after_halves_limit_then_restores(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = make(tmp_path, fake, token_limit=100_000)
    t0 = fake.now
    pacer.note_rate_limit_response(retry_after_s=5)
    row = pacer.admit(estimated_tokens=40_000)
    assert row["throughput_wait_by_reason_s"]["rate_limit_backoff"] == pytest.approx(5.0)
    settle(pacer, row, input_tokens=30_000, output_tokens=10_000)
    # Halved limit (50k) while tightened: another 40k must wait for the 40k to age out.
    second = pacer.admit(estimated_tokens=40_000)
    assert second["throughput_wait_by_reason_s"]["rolling_quota"] > 0
    # After tightening ends the full limit applies: 40k + 40k + 20k fits with no wait
    # (it would not under the halved 50k limit).
    fake.now = t0 + 61 + 61
    settle(pacer, second, input_tokens=30_000, output_tokens=10_000)
    third = pacer.admit(estimated_tokens=40_000)
    fourth = pacer.admit(estimated_tokens=20_000)
    assert third["throughput_wait_s"] == 0
    assert fourth["throughput_wait_s"] == 0


def test_429_default_retry_after_and_header_report_discarded(tmp_path: Path) -> None:
    fake = FakeClock()
    pacer = make(tmp_path, fake)
    pacer.report_rate_limit_headers(remaining_tokens=250_000)
    pacer.note_rate_limit_response()
    row = pacer.admit(estimated_tokens=1000)
    assert row["throughput_wait_by_reason_s"]["rate_limit_backoff"] == pytest.approx(10.0)
    assert row["throughput_admission_basis"] == "local_accounting"


def test_single_request_above_configured_tpm_is_still_rejected(tmp_path: Path) -> None:
    pacer = make(tmp_path, FakeClock(), token_limit=100_000)
    with pytest.raises(ProviderThroughputError, match="exceeds the declared deployment TPM"):
        pacer.admit(estimated_tokens=100_001)
