from __future__ import annotations

import threading
from pathlib import Path

import pytest

import aether.research_glm_harbor_agent as mod
from aether.trace_aware_judge_advice import TraceAwareJudgeAdvice


def _clear(monkeypatch) -> None:
    for name in (
        mod.G4_JUDGE_ADVICE_ENV,
        mod.G4_JUDGE_ADVICE_MODEL_ENV,
        mod.G4_JUDGE_ADVICE_BROKER_DIR_ENV,
        mod.G4_JUDGE_ADVICE_JOURNAL_ENV,
        mod.G4_JUDGE_ADVICE_CAP_GBP_ENV,
        "AETHER_CHAT_TELEMETRY_JOURNAL",
        "AETHER_JUDGE_API_KEY",
        "AETHER_JUDGE_CALLS_ALLOWED",
    ):
        monkeypatch.delenv(name, raising=False)


def test_g4_js_defaults_off_without_any_judge_configuration(monkeypatch) -> None:
    _clear(monkeypatch)
    assert mod.g4_judge_advice_mode() == mod.G4_JUDGE_ADVICE_CONTROL
    assert mod.build_g4_trace_aware_judge_assistance(
        cancellation_event=threading.Event()
    ) is None


def test_g4_js_rejects_unknown_mode(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_ENV, "mystery")
    with pytest.raises(RuntimeError, match=mod.G4_JUDGE_ADVICE_ENV):
        mod.g4_judge_advice_mode()


def test_g4_js_builds_credential_free_file_broker_assistance(
    monkeypatch, tmp_path: Path
) -> None:
    _clear(monkeypatch)
    chat = tmp_path / "chat_attempts.jsonl"
    broker = tmp_path / "broker"
    journal = tmp_path / "judge.jsonl"
    monkeypatch.setenv(
        mod.G4_JUDGE_ADVICE_ENV, mod.G4_JUDGE_ADVICE_HARD_STUCK_TRACE_V1
    )
    monkeypatch.setenv(
        mod.G4_JUDGE_ADVICE_MODEL_ENV, mod.G4_JUDGE_ADVICE_FROZEN_MODEL
    )
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_BROKER_DIR_ENV, str(broker))
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_JOURNAL_ENV, str(journal))
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_CAP_GBP_ENV, "0.02")
    monkeypatch.setenv("AETHER_CHAT_TELEMETRY_JOURNAL", str(chat))

    assistance = mod.build_g4_trace_aware_judge_assistance(
        cancellation_event=threading.Event()
    )
    assert isinstance(assistance, TraceAwareJudgeAdvice)
    assert assistance.model == "judge-1.13.0"
    assert assistance.telemetry_journal == chat
    transport = assistance.evaluate
    assert transport.expected_result_model == "judge-1.13.0"
    assert transport.max_calls == 1
    assert transport.broker_dir == broker
    assert journal.is_file()
    assert "AETHER_JUDGE_API_KEY" not in __import__("os").environ


def test_g4_js_requires_exact_frozen_model(monkeypatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv(
        mod.G4_JUDGE_ADVICE_ENV, mod.G4_JUDGE_ADVICE_HARD_STUCK_TRACE_V1
    )
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_MODEL_ENV, "judge-latest")
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_BROKER_DIR_ENV, str(tmp_path / "broker"))
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_JOURNAL_ENV, str(tmp_path / "judge.jsonl"))
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_CAP_GBP_ENV, "0.02")
    monkeypatch.setenv("AETHER_CHAT_TELEMETRY_JOURNAL", str(tmp_path / "chat.jsonl"))
    with pytest.raises(RuntimeError, match=mod.G4_JUDGE_ADVICE_MODEL_ENV):
        mod.build_g4_trace_aware_judge_assistance(
            cancellation_event=threading.Event()
        )


def test_g4_js_requires_chat_journal(monkeypatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv(
        mod.G4_JUDGE_ADVICE_ENV, mod.G4_JUDGE_ADVICE_HARD_STUCK_TRACE_V1
    )
    monkeypatch.setenv(
        mod.G4_JUDGE_ADVICE_MODEL_ENV, mod.G4_JUDGE_ADVICE_FROZEN_MODEL
    )
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_BROKER_DIR_ENV, str(tmp_path / "broker"))
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_JOURNAL_ENV, str(tmp_path / "judge.jsonl"))
    monkeypatch.setenv(mod.G4_JUDGE_ADVICE_CAP_GBP_ENV, "0.02")
    with pytest.raises(RuntimeError, match="AETHER_CHAT_TELEMETRY_JOURNAL"):
        mod.build_g4_trace_aware_judge_assistance(
            cancellation_event=threading.Event()
        )
