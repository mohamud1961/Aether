"""Behavioral controls for exact action-keyed terminal observation sequences."""

import importlib.util
import json
from pathlib import Path


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _replay_module():
    source = Path(__file__).resolve().parents[1] / "qa" / "replay_corpus.py"
    return _module("aether_core_replay_corpus_sequences", source)


def _sequence_qa_module():
    source = Path(__file__).resolve().parents[1] / "qa" / "replay_terminal_sequences.py"
    return _module("aether_core_terminal_sequences", source)


def test_core_loop_sequence_playback_preserves_duplicate_results_and_mismatch_does_not_consume(
    monkeypatch,
):
    replay = _replay_module()
    action = "synthetic harmless command"
    mutated = action + " __changed__"
    observations = ["first distinct result\u0085continuation\n", "second distinct result\n"]
    blocked = "[playback blocked: no exact recorded observation; action not executed]"
    script = [
        replay.scripted_call("terminal", {"input": mutated}, "mutation"),
        replay.scripted_call("terminal", {"input": action}, "action-1"),
        replay.scripted_call("terminal", {"input": action}, "action-2"),
        replay.scripted_call("terminal", {"input": action}, "action-exhausted"),
        replay.scripted_call("finish", {"summary": "scripted"}, "finish"),
    ]

    process_calls = {"shell": 0, "exec": 0}

    def forbidden(kind):
        def fail(*_args, **_kwargs):
            process_calls[kind] += 1
            raise AssertionError("replay attempted process creation")

        return fail

    monkeypatch.setattr(replay.asyncio, "create_subprocess_shell", forbidden("shell"))
    monkeypatch.setattr(replay.asyncio, "create_subprocess_exec", forbidden("exec"))
    run = replay.run_scripted(
        script,
        "Synthetic replay test.",
        playback_sequences={action: observations},
        capture_provider_requests=True,
    )

    terminal_rows = [
        row for row in run["trace"] if row.get("event") == "tool" and row.get("name") == "terminal"
    ]
    assert run["result"].status == "finished"
    assert [row["result"] for row in terminal_rows] == [blocked, *observations, blocked]
    assert [hit["sequence_index"] for hit in run["env"].playback_sequence_hits] == [0, 1]
    assert all(value == 0 for value in run["env"].remaining_playback_sequences().values())
    assert len(run["env"].blocked_actions) == 2
    assert process_calls == {"shell": 0, "exec": 0}
    assert run["temporary_workdirs_removed"]

    expected_by_call = {
        "mutation": blocked,
        "action-1": observations[0],
        "action-2": observations[1],
        "action-exhausted": blocked,
    }
    for request_index, call_id in enumerate(expected_by_call, start=1):
        messages = run["provider_requests"][request_index]["messages"]
        tool_message = next(
            message
            for message in messages
            if message.get("role") == "tool" and message.get("tool_call_id") == call_id
        )
        assert tool_message["content"].startswith(expected_by_call[call_id])


def test_known_bad_scalar_playback_is_detected_as_duplicate_result_collapse():
    replay = _replay_module()
    action = "synthetic repeated action"
    expected = ["observation one", "observation two"]
    run = replay.run_scripted(
        [
            replay.scripted_call("terminal", {"input": action}, "scalar-1"),
            replay.scripted_call("terminal", {"input": action}, "scalar-2"),
            replay.scripted_call("finish", {"summary": "scripted"}, "scalar-finish"),
        ],
        "Synthetic scalar negative control.",
        playback={action: expected[0]},
    )
    observed = [
        row["result"]
        for row in run["trace"]
        if row.get("event") == "tool" and row.get("name") == "terminal"
    ]
    assert observed == [expected[0], expected[0]]
    assert observed != expected


def test_terminal_sequence_qa_reports_known_bad_queue_detection():
    sequence_qa = _sequence_qa_module()
    replay = sequence_qa._module()
    result = sequence_qa._synthetic_queue_control(replay)
    assert result["status"] == "PASS", result
    assert result["checks"]["blocked_queue_collapse_was_detected"]
    assert result["checks"]["duplicate_action_got_distinct_results"]
    assert result["checks"]["mutation_did_not_consume_original_queue"]


def test_protected_case_preflight_runs_before_any_archive_resolution(tmp_path, monkeypatch):
    sequence_qa = _sequence_qa_module()
    case = {
        "archive_case": "extract-elf__protected",
        "case_key": "cohort:extract-elf__protected:protected",
        "source_symbol": "$DENIED/path/core_trace.jsonl",
        "expected": {"client_capture_present": True},
        "requests": [{"selected_action_names": ["terminal"]}],
    }
    cases = [case] + [
        {
            "archive_case": f"safe-case-{index}",
            "case_key": f"cohort:safe-case-{index}:fixture",
            "source_symbol": "$SAFE/path/core_trace.jsonl",
            "expected": {"client_capture_present": True},
            "requests": [{"selected_action_names": ["terminal"]}],
        }
        for index in range(14)
    ]
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(
        json.dumps(
            {"schema": "aether.core.replay_corpus.v1", "cases": cases}, separators=(",", ":")
        )
    )
    monkeypatch.setattr(sequence_qa, "CORPUS_SHA256", sequence_qa._sha256(corpus_path.read_bytes()))
    monkeypatch.setattr(sequence_qa, "EXPECTED_CASES", 15)
    monkeypatch.setattr(sequence_qa, "_module", lambda: (_ for _ in ()).throw(AssertionError("resolver module loaded")))

    try:
        sequence_qa.run_qualification(corpus_path, tmp_path / "missing-root-map.json")
    except PermissionError as exc:
        assert "PROTECTED_CASE_DENIED_BEFORE_SOURCE_RESOLUTION" in str(exc)
    else:
        raise AssertionError("protected metadata did not fail closed")
