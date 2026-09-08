from __future__ import annotations

import json
from pathlib import Path

import pytest

from aether import request_anatomy


def _request(turn: int = 1) -> dict:
    return {
        "instructions": f"stable instructions v{turn // 100}",
        "input": [{"role": "user", "content": f"boundary {turn}"}],
        "reasoning": {"effort": "low", "context": "current_turn"},
        "tools": [{"name": "run_command"}],
        "tool_choice": "required",
        "max_output_tokens": 12000,
        "previous_response_id": None if turn == 1 else "resp_abc",
        "store": False,
    }


def test_recorder_is_disabled_by_default(tmp_path: Path) -> None:
    out = tmp_path / "anatomy.jsonl"
    request_anatomy.observe_request(role="primary", request=_request())
    assert not out.exists()


def test_enabled_recorder_requires_output_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY", "1")
    monkeypatch.delenv("AETHER_REQUEST_ANATOMY_PATH", raising=False)
    with pytest.raises(RuntimeError, match="AETHER_REQUEST_ANATOMY_PATH"):
        request_anatomy.observe_request(role="primary", request=_request())


def test_rows_are_deterministic_and_plane_separated(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "nested" / "anatomy.jsonl"
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY", "1")
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY_PATH", str(out))

    request_anatomy.observe_request(role="primary", request=_request(1), turn_index=1)
    request_anatomy.observe_request(role="primary", request=_request(2), turn_index=2)
    first, second = (json.loads(line) for line in out.read_text().splitlines())

    assert first["schema_version"] == request_anatomy.SCHEMA
    assert first["role"] == "primary"
    planes = first["planes"]
    assert set(planes) == {"instructions", "input", "reasoning", "tools", "tool_choice", "max_output_tokens", "residual"}
    # stable instructions identical across turns -> identical digest
    assert planes["instructions"] == second["planes"]["instructions"]
    # boundary items legitimately change -> different digest + per-item digests
    assert planes["input"] != second["planes"]["input"]
    assert len(first["input_item_digests"]) == 1
    assert first["continuity"]["previous_response_id_present"] is False
    assert second["continuity"]["previous_response_id_present"] is True
    assert first["continuity"]["store"] is False

    # determinism: replaying the same request appends an identical row body
    request_anatomy.observe_request(role="primary", request=_request(1), turn_index=3)
    lines = out.read_text().splitlines()
    third = json.loads(lines[2])
    third.pop("turn_index")
    replay_first = json.loads(lines[0])
    replay_first.pop("turn_index")
    assert third == replay_first


def test_reasoning_treatment_change_is_visible_in_its_own_plane(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    out = tmp_path / "anatomy.jsonl"
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY", "1")
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY_PATH", str(out))
    current = _request(1)
    all_turns = dict(current)
    all_turns["reasoning"] = {"effort": "low", "context": "all_turns"}
    request_anatomy.observe_request(role="primary", request=current)
    request_anatomy.observe_request(role="primary", request=all_turns)
    first, second = (json.loads(line)["planes"] for line in out.read_text().splitlines())
    # ONLY the reasoning plane differs: everything else byte-identical inputs.
    assert first["reasoning"] != second["reasoning"]
    for key in ("instructions", "tools", "tool_choice"):
        assert first[key] == second[key]


def test_residual_plane_binds_every_unnamed_request_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    out = tmp_path / "anatomy.jsonl"
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY", "1")
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY_PATH", str(out))
    base = _request(1)
    smuggled = dict(base)
    smuggled["reasoning"] = dict(base["reasoning"], summary="auto")
    request_anatomy.observe_request(role="primary", request=base)
    request_anatomy.observe_request(role="primary", request=dict(base, background=True))
    request_anatomy.observe_request(role="primary", request=smuggled)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows[1]["planes"]["residual"] != rows[0]["planes"]["residual"]
    assert "background" in rows[1]["residual_request_keys"]
    # a new key inside the reasoning plane must NOT hide in residual
    assert rows[2]["planes"]["reasoning"] != rows[0]["planes"]["reasoning"]
    assert rows[2]["residual_request_keys"] == rows[0]["residual_request_keys"]


def test_correlation_ids_are_recorded_but_never_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    out = tmp_path / "anatomy.jsonl"
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY", "1")
    monkeypatch.setenv("AETHER_REQUEST_ANATOMY_PATH", str(out))
    request_anatomy.observe_request(role="verifier", request=_request(1), run_id="run-9", task_id="t-1")
    row = json.loads(out.read_text().splitlines()[0])
    assert row["run_id"] == "run-9" and row["task_id"] == "t-1"
