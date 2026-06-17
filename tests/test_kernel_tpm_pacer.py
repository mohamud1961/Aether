"""Tests for runner.kernel_tpm_pacer (RollingTPMPacer / RollingTokenWindow)."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from runner.kernel_tpm_pacer import (
    RollingTokenWindow,
    RollingTPMPacer,
    _extract_output_tokens,
    make_paced_client,
)
from runner.model_client import make_model_client_from_route, make_model_route


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_route() -> dict[str, Any]:
    return {
        "model_client_id": "local_stub",
        "provider_route": "local_stub",
        "model_name": "stub",
        "adapter_id": "local_stub",
        "auth_mode": "none",
        "provider_scope": "local_dev",
        "api_base": None,
        "request_settings": {},
        "request_settings_fingerprint": "",
    }


def _make_stub_client(output_tokens: int = 10) -> MagicMock:
    client = MagicMock()
    client.route = _stub_route()
    client.complete.return_value = {
        "text": "ok",
        "tool_calls": [],
        "usage": {"output_tokens": output_tokens},
        "status": "completed",
        "model_route": _stub_route(),
    }
    return client


# ---------------------------------------------------------------------------
# RollingTokenWindow tests
# ---------------------------------------------------------------------------


class TestRollingTokenWindow:
    def test_empty_window_returns_zero(self) -> None:
        w = RollingTokenWindow(window_sec=60.0)
        assert w.rolling_total() == 0

    def test_single_record(self) -> None:
        w = RollingTokenWindow(window_sec=60.0)
        now = time.monotonic()
        w.record(500, ts=now)
        assert w.rolling_total(ts=now) == 500

    def test_accumulates_within_window(self) -> None:
        w = RollingTokenWindow(window_sec=60.0)
        now = time.monotonic()
        w.record(100, ts=now - 10)
        w.record(200, ts=now - 5)
        w.record(300, ts=now)
        assert w.rolling_total(ts=now) == 600

    def test_evicts_expired_events(self) -> None:
        w = RollingTokenWindow(window_sec=60.0)
        now = time.monotonic()
        w.record(999, ts=now - 61)   # too old → evicted
        w.record(100, ts=now - 30)   # within window
        assert w.rolling_total(ts=now) == 100

    def test_zero_tokens_not_recorded(self) -> None:
        w = RollingTokenWindow(window_sec=60.0)
        w.record(0)
        w.record(-5)
        assert w.rolling_total() == 0

    def test_boundary_event_at_exactly_window_edge_is_evicted(self) -> None:
        """Events at exactly (now - window_sec) are evicted (strict cutoff < ts)."""
        w = RollingTokenWindow(window_sec=60.0)
        now = time.monotonic()
        # Place event at exactly the cutoff boundary
        w.record(100, ts=now - 60.0)
        # Should be evicted because cutoff = now - 60.0 and event.ts < cutoff is False
        # (ts == cutoff, so it's NOT less-than → kept)
        total = w.rolling_total(ts=now)
        # Window evicts events where ts < (now - window_sec);
        # exactly at boundary ts == cutoff so it should be kept.
        assert total == 100

    def test_window_respects_configured_duration(self) -> None:
        w = RollingTokenWindow(window_sec=30.0)
        now = time.monotonic()
        w.record(100, ts=now - 31)   # outside 30 s window
        w.record(200, ts=now - 10)   # inside 30 s window
        assert w.rolling_total(ts=now) == 200


# ---------------------------------------------------------------------------
# _extract_output_tokens tests
# ---------------------------------------------------------------------------


class TestExtractOutputTokens:
    def test_output_tokens_key(self) -> None:
        result = {"usage": {"output_tokens": 42}}
        assert _extract_output_tokens(result) == 42

    def test_completion_tokens_key(self) -> None:
        result = {"usage": {"completion_tokens": 77}}
        assert _extract_output_tokens(result) == 77

    def test_output_tokens_preferred_over_completion_tokens(self) -> None:
        result = {"usage": {"output_tokens": 50, "completion_tokens": 30}}
        assert _extract_output_tokens(result) == 50

    def test_fallback_total_minus_prompt(self) -> None:
        result = {"usage": {"total_tokens": 100, "prompt_tokens": 60}}
        assert _extract_output_tokens(result) == 40

    def test_fallback_with_input_tokens_key(self) -> None:
        result = {"usage": {"total_tokens": 120, "input_tokens": 80}}
        assert _extract_output_tokens(result) == 40

    def test_missing_usage_returns_zero(self) -> None:
        assert _extract_output_tokens({}) == 0

    def test_non_dict_returns_zero(self) -> None:
        assert _extract_output_tokens("bad") == 0  # type: ignore[arg-type]

    def test_usage_not_dict_returns_zero(self) -> None:
        assert _extract_output_tokens({"usage": "bad"}) == 0

    def test_zero_output_tokens_returns_zero(self) -> None:
        assert _extract_output_tokens({"usage": {"output_tokens": 0}}) == 0


# ---------------------------------------------------------------------------
# RollingTPMPacer construction tests
# ---------------------------------------------------------------------------


class TestRollingTPMPacerConstruction:
    def test_default_construction(self) -> None:
        client = _make_stub_client()
        pacer = RollingTPMPacer(client=client)
        assert pacer.tpm_limit == 100_000
        assert pacer.window_sec == 60.0
        assert pacer.throttle_fraction == 0.85
        assert pacer.pause_sec == 4.0
        assert pacer.enabled is True

    def test_invalid_tpm_limit(self) -> None:
        client = _make_stub_client()
        with pytest.raises(ValueError, match="tpm_limit"):
            RollingTPMPacer(client=client, tpm_limit=0)

    def test_invalid_throttle_fraction_zero(self) -> None:
        client = _make_stub_client()
        with pytest.raises(ValueError, match="throttle_fraction"):
            RollingTPMPacer(client=client, throttle_fraction=0.0)

    def test_invalid_throttle_fraction_over_one(self) -> None:
        client = _make_stub_client()
        with pytest.raises(ValueError, match="throttle_fraction"):
            RollingTPMPacer(client=client, throttle_fraction=1.1)

    def test_invalid_pause_sec_negative(self) -> None:
        client = _make_stub_client()
        with pytest.raises(ValueError, match="pause_sec"):
            RollingTPMPacer(client=client, pause_sec=-1.0)

    def test_route_delegates_to_inner_client(self) -> None:
        client = _make_stub_client()
        pacer = RollingTPMPacer(client=client)
        assert pacer.route is client.route


# ---------------------------------------------------------------------------
# RollingTPMPacer.complete — no throttle expected
# ---------------------------------------------------------------------------


class TestRollingTPMPacerNoThrottle:
    def test_delegates_complete_call(self) -> None:
        client = _make_stub_client(output_tokens=50)
        pacer = RollingTPMPacer(client=client, tpm_limit=10_000)
        messages = [{"role": "user", "content": "hello"}]
        result = pacer.complete(messages)
        client.complete.assert_called_once_with(messages)
        assert result["text"] == "ok"

    def test_records_output_tokens_in_window(self) -> None:
        client = _make_stub_client(output_tokens=200)
        pacer = RollingTPMPacer(client=client, tpm_limit=10_000)
        pacer.complete([{"role": "user", "content": "x"}])
        assert pacer.rolling_total() == 200

    def test_accumulates_across_calls(self) -> None:
        client = _make_stub_client(output_tokens=100)
        pacer = RollingTPMPacer(client=client, tpm_limit=10_000)
        pacer.complete([])
        pacer.complete([])
        pacer.complete([])
        assert pacer.rolling_total() == 300

    def test_disabled_pacer_does_not_record(self) -> None:
        client = _make_stub_client(output_tokens=500)
        pacer = RollingTPMPacer(client=client, tpm_limit=10_000, enabled=False)
        pacer.complete([])
        assert pacer.rolling_total() == 0

    def test_disabled_pacer_still_delegates(self) -> None:
        client = _make_stub_client(output_tokens=10)
        pacer = RollingTPMPacer(client=client, tpm_limit=10_000, enabled=False)
        result = pacer.complete([])
        client.complete.assert_called_once()
        assert result["text"] == "ok"


# ---------------------------------------------------------------------------
# RollingTPMPacer.complete — throttle triggered (time.sleep mocked)
# ---------------------------------------------------------------------------


class TestRollingTPMPacerThrottle:
    def _pacer_near_limit(self, tpm_limit: int = 1000, throttle_fraction: float = 0.85) -> RollingTPMPacer:
        client = _make_stub_client(output_tokens=10)
        pacer = RollingTPMPacer(
            client=client,
            tpm_limit=tpm_limit,
            throttle_fraction=throttle_fraction,
            pause_sec=4.0,
        )
        # Manually seed the window above threshold
        threshold = int(tpm_limit * throttle_fraction)
        pacer._window.record(threshold + 1)
        return pacer

    def test_sleep_called_when_above_threshold(self) -> None:
        pacer = self._pacer_near_limit(tpm_limit=1000, throttle_fraction=0.85)
        with patch("runner.kernel_tpm_pacer.time.sleep") as mock_sleep:
            pacer.complete([])
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args.args[0] >= 4.0

    def test_sleep_not_called_when_below_threshold(self) -> None:
        client = _make_stub_client(output_tokens=10)
        pacer = RollingTPMPacer(client=client, tpm_limit=10_000)
        # Only 50 tokens in window — well below 85 % of 10 000
        pacer._window.record(50)
        with patch("runner.kernel_tpm_pacer.time.sleep") as mock_sleep:
            pacer.complete([])
        mock_sleep.assert_not_called()

    def test_sleep_not_called_when_disabled(self) -> None:
        client = _make_stub_client(output_tokens=10)
        pacer = RollingTPMPacer(client=client, tpm_limit=1000, enabled=False)
        pacer._window.record(950)  # would exceed 85 % if enabled
        with patch("runner.kernel_tpm_pacer.time.sleep") as mock_sleep:
            pacer.complete([])
        mock_sleep.assert_not_called()

    def test_custom_pause_sec(self) -> None:
        pacer = self._pacer_near_limit(tpm_limit=1000)
        pacer.pause_sec = 7.5
        with patch("runner.kernel_tpm_pacer.time.sleep") as mock_sleep:
            pacer.complete([])
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args.args[0] >= 7.5

    def test_complete_still_returns_result_after_sleep(self) -> None:
        pacer = self._pacer_near_limit()
        with patch("runner.kernel_tpm_pacer.time.sleep"):
            result = pacer.complete([])
        assert result["text"] == "ok"


# ---------------------------------------------------------------------------
# snapshot() helper
# ---------------------------------------------------------------------------


class TestSnapshot:
    def test_snapshot_fields(self) -> None:
        client = _make_stub_client()
        pacer = RollingTPMPacer(client=client, tpm_limit=10_000, throttle_fraction=0.8)
        snap = pacer.snapshot()
        assert snap["enabled"] is True
        assert snap["tpm_limit"] == 10_000
        assert snap["throttle_fraction"] == 0.8
        assert snap["threshold"] == 8_000
        assert snap["rolling_total"] == 0
        assert snap["headroom"] == 8_000
        assert snap["is_throttled"] is False

    def test_snapshot_throttled_state(self) -> None:
        client = _make_stub_client()
        pacer = RollingTPMPacer(client=client, tpm_limit=1_000, throttle_fraction=0.5)
        pacer._window.record(600)  # above 50 % of 1000
        snap = pacer.snapshot()
        assert snap["is_throttled"] is True
        assert snap["headroom"] == 0


# ---------------------------------------------------------------------------
# make_paced_client factory
# ---------------------------------------------------------------------------


class TestMakePacedClient:
    def test_returns_rolling_tpm_pacer(self) -> None:
        client = _make_stub_client()
        pacer = make_paced_client(client, tpm_limit=50_000)
        assert isinstance(pacer, RollingTPMPacer)
        assert pacer.tpm_limit == 50_000

    def test_disabled_factory(self) -> None:
        client = _make_stub_client()
        pacer = make_paced_client(client, tpm_limit=50_000, enabled=False)
        assert pacer.enabled is False

    def test_custom_params(self) -> None:
        client = _make_stub_client()
        pacer = make_paced_client(
            client,
            tpm_limit=200_000,
            window_sec=30.0,
            throttle_fraction=0.9,
            pause_sec=6.0,
        )
        assert pacer.window_sec == 30.0
        assert pacer.throttle_fraction == 0.9
        assert pacer.pause_sec == 6.0

    def test_model_client_factory_wraps_enabled_provider_route_and_strips_transport_settings(self) -> None:
        route = make_model_route(
            model_client_id="openai_api_key",
            provider_route="openai_api",
            model_name="gpt-test",
            adapter_id="openai_chat_completions_api_key",
            auth_mode="api_key",
            provider_scope="certified_eval",
            api_base="https://api.openai.com/v1/chat/completions",
            request_settings={
                "temperature": 0,
                "api_key_env_var": "OPENAI_API_KEY",
                "tpm_pacer_enabled": True,
                "tpm_limit": 12345,
            },
        )

        client = make_model_client_from_route(route, tpm_pause_sec=0)

        assert isinstance(client, RollingTPMPacer)
        assert client.tpm_limit == 12345
        assert client.client.route["request_settings"] == {
            "temperature": 0,
            "api_key_env_var": "OPENAI_API_KEY",
        }
