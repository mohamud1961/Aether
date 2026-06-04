from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace


ENV = importlib.import_module("harness.aether2.traces.envelope")
ENV_COMPAT = importlib.import_module("runner.aether2.envelope")

assert ENV_COMPAT is ENV


def test_collapse_cr_ansi_keeps_final_visible_state():
    text = "progress 10%\rprogress 20%\rdone\x1b[31m!\x1b[0m\nline two\rfinal two"
    assert ENV.collapse_cr_ansi(text) == "done!\nfinal two"


def test_build_envelope_bounds_and_raw_log(tmp_path):
    stdout = "A" * 2048 + "M" * 1000 + "B" * 2048
    stderr = "C" * 2048 + "N" * 1000 + "D" * 2048
    raw = SimpleNamespace(
        tool="run_command",
        exit_code=0,
        duration_sec=1.25,
        cwd="/tmp/work",
        stdout=stdout,
        stderr=stderr,
    )

    envelope = ENV.build_envelope(raw, raw_log_dir=tmp_path)

    assert envelope.tool == "run_command"
    assert envelope.exit_code == 0
    assert envelope.duration_sec == 1.25
    assert envelope.cwd == "/tmp/work"
    assert envelope.stdout_head == "A" * 2048
    assert envelope.stdout_tail == "B" * 2048
    assert envelope.stderr_head == "C" * 2048
    assert envelope.stderr_tail == "D" * 2048
    assert envelope.truncated is True
    assert envelope.raw_log_path
    assert envelope.truncation_digest is not None
    assert envelope.truncation_digest.raw_log_path == envelope.raw_log_path

    raw_log_path = Path(envelope.raw_log_path)
    assert raw_log_path.exists()
    raw_log = json.loads(raw_log_path.read_text(encoding="utf-8"))
    assert raw_log["stdout"] == stdout
    assert raw_log["stderr"] == stderr
    assert raw_log["truncation_digest"]["raw_log_path"] == envelope.raw_log_path


def test_build_envelope_exact_boundary_is_not_truncated(tmp_path):
    stdout = "x" * 4096
    stderr = "y" * 4096
    raw = SimpleNamespace(
        tool="session_read",
        exit_code=None,
        duration_sec=0.0,
        cwd="/tmp/work",
        stdout=stdout,
        stderr=stderr,
    )

    envelope = ENV.build_envelope(raw, raw_log_dir=tmp_path)

    assert envelope.truncated is False
    assert envelope.truncation_digest is None
    assert envelope.stdout_head == "x" * 2048
    assert envelope.stdout_tail == "x" * 2048
    assert envelope.stderr_head == "y" * 2048
    assert envelope.stderr_tail == "y" * 2048
    assert envelope.stdout_head + envelope.stdout_tail == stdout
    assert envelope.stderr_head + envelope.stderr_tail == stderr


def test_build_envelope_coerces_process_and_error_metadata(tmp_path):
    raw = SimpleNamespace(
        tool="run_command",
        exit_code=1,
        duration_sec=2.0,
        cwd="/tmp/work",
        stdout="ok",
        stderr="bad",
        process_delta={
            "started": ["proc-1"],
            "exited": ["proc-2"],
            "log_growth": {"proc.log": 10},
            "jobs_started": ["job-1"],
            "jobs_exited": ["job-2"],
            "sessions_started": ["session-1"],
            "sessions_exited": ["session-2"],
            "services_started": ["service-1"],
            "services_exited": ["service-2"],
            "job_log_growth": {"job.log": 11},
            "session_log_growth": {"session.log": 12},
            "service_log_growth": {"service.log": 13},
        },
        error={
            "kind": "refusal",
            "message": "already failed",
            "reason_code": "blind_retry_blocked_same_failed_command",
            "failure_class": "retry_guard",
            "details": "same command",
            "tool_name": "run_command",
            "command": "echo bad",
            "exit_code": 1,
            "timed_out": False,
        },
    )

    envelope = ENV.build_envelope(raw, raw_log_dir=tmp_path)

    assert envelope.blind_retry_blocked is True
    assert envelope.process_delta.started == ["proc-1"]
    assert envelope.process_delta.exited == ["proc-2"]
    assert envelope.process_delta.log_growth == {"proc.log": 10}
    assert envelope.process_delta.jobs_started == ["job-1"]
    assert envelope.process_delta.jobs_exited == ["job-2"]
    assert envelope.process_delta.sessions_started == ["session-1"]
    assert envelope.process_delta.sessions_exited == ["session-2"]
    assert envelope.process_delta.services_started == ["service-1"]
    assert envelope.process_delta.services_exited == ["service-2"]
    assert envelope.process_delta.job_log_growth == {"job.log": 11}
    assert envelope.process_delta.session_log_growth == {"session.log": 12}
    assert envelope.process_delta.service_log_growth == {"service.log": 13}
    assert envelope.error is not None
    assert envelope.error.reason_code == "blind_retry_blocked_same_failed_command"
    assert envelope.error.failure_class == "retry_guard"
    assert envelope.error.command == "echo bad"
    assert envelope.error.exit_code == 1
    assert envelope.error.timed_out is False
    assert envelope.truncation_digest is None

    raw_log = json.loads(Path(envelope.raw_log_path).read_text(encoding="utf-8"))
    assert raw_log["process_delta"]["jobs_started"] == ["job-1"]
    assert raw_log["process_delta"]["session_log_growth"] == {"session.log": 12}
    assert raw_log["error"]["reason_code"] == "blind_retry_blocked_same_failed_command"
    assert raw_log["error"]["command"] == "echo bad"


def test_build_envelope_truncation_digest_captures_middle_traceback_and_salient_lines(tmp_path):
    prefix = "A" * 2100
    suffix = "B" * 2100
    stderr = "\n".join(
        [
            prefix,
            "\x1b[31mFAILED tests/test_math.py::test_addition - AssertionError: expected 4\x1b[0m",
            "Traceback (most recent call last):",
            '  File "/tmp/test_math.py", line 12, in test_addition',
            '  File "/tmp/helpers.py", line 5, in add',
            "AssertionError: expected 4",
            "fatal error: linker command failed with exit code 1",
            "ModuleNotFoundError: No module named 'pkg'",
            "Killed",
            suffix,
        ]
    )
    raw = SimpleNamespace(
        tool="run_command",
        exit_code=1,
        duration_sec=1.5,
        cwd="/tmp/work",
        stdout="",
        stderr=stderr,
    )

    first = ENV.build_envelope(raw, raw_log_dir=tmp_path)
    second = ENV.build_envelope(raw, raw_log_dir=tmp_path)

    assert first.truncated is True
    assert first.stderr_head == "A" * 2048
    assert first.stderr_tail == "B" * 2048
    assert first.truncation_digest is not None
    assert second.truncation_digest is not None
    assert first.truncation_digest.raw_log_path == first.raw_log_path
    assert second.truncation_digest.raw_log_path == second.raw_log_path

    first_entries = [
        (entry.source, entry.line_number, tuple(entry.kinds), entry.text)
        for entry in first.truncation_digest.entries
    ]
    second_entries = [
        (entry.source, entry.line_number, tuple(entry.kinds), entry.text)
        for entry in second.truncation_digest.entries
    ]
    assert first_entries == second_entries
    assert first_entries == [
        (
            "stderr",
            2,
            ("failed_test", "assertion_summary"),
            "FAILED tests/test_math.py::test_addition - AssertionError: expected 4",
        ),
        (
            "stderr",
            4,
            ("traceback_frame",),
            'File "/tmp/test_math.py", line 12, in test_addition',
        ),
        (
            "stderr",
            5,
            ("traceback_frame",),
            'File "/tmp/helpers.py", line 5, in add',
        ),
        (
            "stderr",
            6,
            ("traceback_exception", "assertion_summary"),
            "AssertionError: expected 4",
        ),
        (
            "stderr",
            7,
            ("compiler_or_linker",),
            "fatal error: linker command failed with exit code 1",
        ),
        (
            "stderr",
            8,
            ("missing_reference",),
            "ModuleNotFoundError: No module named 'pkg'",
        ),
        ("stderr", 9, ("timeout_or_kill",), "Killed"),
    ]

    raw_log = json.loads(Path(first.raw_log_path).read_text(encoding="utf-8"))
    assert raw_log["truncation_digest"]["entries"] == [
        {
            "source": source,
            "line_number": line_number,
            "kinds": list(kinds),
            "text": text,
        }
        for source, line_number, kinds, text in first_entries
    ]


def test_build_envelope_truncation_digest_uses_timeout_metadata_when_middle_is_omitted(tmp_path):
    raw = SimpleNamespace(
        tool="run_command",
        exit_code=124,
        duration_sec=120.0,
        cwd="/tmp/work",
        stdout="A" * 2100 + "\n" + "B" * 2100,
        stderr="",
        error={
            "kind": "timeout",
            "message": "command timed out",
            "reason_code": "command_timeout",
            "timed_out": True,
            "exit_code": 124,
        },
    )

    envelope = ENV.build_envelope(raw, raw_log_dir=tmp_path)

    assert envelope.truncated is True
    assert envelope.truncation_digest is not None
    assert [
        (entry.source, tuple(entry.kinds), entry.text)
        for entry in envelope.truncation_digest.entries
    ] == [
        (
            "meta",
            ("timeout_or_kill",),
            "tool metadata indicates timeout; tool metadata reason_code=command_timeout; tool exited with code 124",
        )
    ]
