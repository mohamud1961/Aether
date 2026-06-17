from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import spawn_with_retry


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "run_aether2_g2.py"
    spec = importlib.util.spec_from_file_location("run_aether2_g2_test_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_journal_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "run_phase_journal.py"
    spec = importlib.util.spec_from_file_location("run_phase_journal_test_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_entrypoint_module_load_works_from_foreign_cwd_without_pythonpath() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    script_path = Path(__file__).resolve().parents[1] / "tools" / "run_aether2_g2.py"
    code = (
        "import importlib.util, pathlib, sys\n"
        f"script = pathlib.Path({str(script_path)!r})\n"
        'spec = importlib.util.spec_from_file_location("run_aether2_g2_import_smoke", script)\n'
        "assert spec is not None and spec.loader is not None\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n"
        "print(module.run_aether2_loop.__module__)\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = spawn_with_retry(
            subprocess.run,
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
            cwd=tmpdir,
            env=env,
        )

    assert proc.returncode == 0
    assert "harness.aether2.control.loop" in proc.stdout
    assert "module named 'runner'" not in (proc.stdout + proc.stderr).lower()


def test_cleanup_blocks_unattributable_port_listener(tmp_path, monkeypatch) -> None:
    mod = _load_module()
    run_dir = tmp_path / "runs" / "current"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "_iter_prior_run_dirs", lambda _run_dir: [])
    monkeypatch.setattr(mod, "_port_listener_pids", lambda port: [4444] if port == 8123 else [])
    monkeypatch.setattr(mod, "_pid_cmdline", lambda pid: "python3 -m http.server 8123")

    outcome = mod._cleanup_prior_runs(run_dir)

    assert outcome.blocked_homologs == {
        "g2_02_service_survives_exit": "port 8123 already occupied by unattributable pid 4444 cmdline='python3 -m http.server 8123'"
    }
    assert any("blocking g2_02_service_survives_exit" in line for line in outcome.log_lines)


def test_cleanup_kills_attributable_listener_from_prior_run(tmp_path, monkeypatch) -> None:
    mod = _load_module()
    run_dir = tmp_path / "runs" / "current"
    prior_jobs = (
        tmp_path
        / "runs"
        / "prior"
        / "workspaces"
        / "g2_02_service_survives_exit"
        / "workspace"
        / ".aether2"
        / "state"
        / "jobs"
        / "http8123"
    )
    prior_jobs.mkdir(parents=True)
    (prior_jobs / "job.pid").write_text("1234\n", encoding="utf-8")
    (prior_jobs / "meta.json").write_text('{"cmd": "python3 server.py"}\n', encoding="utf-8")

    killed: list[tuple[int, str]] = []

    monkeypatch.setattr(mod, "_iter_prior_run_dirs", lambda _run_dir: [tmp_path / "runs" / "prior"])
    monkeypatch.setattr(mod, "HOMOLOGS_DIR", tmp_path / "homologs")
    monkeypatch.setattr(
        mod,
        "_signal_and_wait_for_exit",
        lambda pid, log, note: killed.append((pid, note)) or log.append(f"killed {pid} {note}") or True,
    )
    listener_calls = {"count": 0}

    def fake_port_listener_pids(port: int) -> list[int]:
        if port != 8123:
            return []
        listener_calls["count"] += 1
        return [1234] if listener_calls["count"] == 1 else []

    monkeypatch.setattr(mod, "_port_listener_pids", fake_port_listener_pids)
    monkeypatch.setattr(mod, "_pid_cmdline", lambda pid: "python3 server.py")

    outcome = mod._cleanup_prior_runs(run_dir)

    assert outcome.blocked_homologs == {}
    assert killed == [
        (1234, f"pidfile {prior_jobs / 'job.pid'}"),
        (1234, "port 8123 listener from prior g2_02_service_survives_exit run"),
    ]


def test_run_one_returns_invalid_environment_row_without_running(monkeypatch, tmp_path) -> None:
    mod = _load_module()

    row = mod._run_one(
        "g2_02_service_survives_exit",
        tmp_path,
        blocked_reason="port 8123 already occupied by unattributable pid 4444",
    )

    assert row["row_status"] == "invalid_environment"
    assert row["classification_stage"] == "launch"
    assert row["scoreable"] is False
    assert row["verifier_exit_code"] is None
    assert row["verifier_stderr"] == "port 8123 already occupied by unattributable pid 4444"
    assert "run_result" not in row
    phase_rows = Path(row["phase_rows_path"])
    assert phase_rows.exists()
    phase_row = json.loads(phase_rows.read_text(encoding="utf-8").strip())
    assert phase_row["phase"] == "initialized"


def test_invalid_launch_row_for_homolog_emits_explicit_phase_and_result(monkeypatch, tmp_path) -> None:
    mod = _load_module()
    homologs_dir = tmp_path / "homologs"
    homolog_dir = homologs_dir / "g2_01_file_artifact"
    homolog_dir.mkdir(parents=True)
    (homolog_dir / "task.json").write_text(
        json.dumps(
            {
                "task_id": "g2_01_file_artifact",
                "workspace_root": "workspace",
                "attempt": 7,
                "attempt_label": "launch-preflight",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "HOMOLOGS_DIR", homologs_dir)

    run_dir = tmp_path / "runs" / "current"
    row = mod._invalid_launch_row_for_homolog(  # noqa: SLF001
        "g2_01_file_artifact",
        run_dir,
        reason="launch_integrity_preflight_failed: launch_import_failed",
        details={"ok": False, "reason_codes": ["launch_import_failed"]},
    )

    assert row["row_status"] == "invalid_launch"
    assert row["classification_stage"] == "launch"
    assert row["scoreable"] is False
    assert row["attempt"] == 7
    assert row["attempt_label"] == "launch-preflight"
    assert row["verifier_stderr"] == "launch_integrity_preflight_failed: launch_import_failed"
    assert row["launch_integrity"] == {"ok": False, "reason_codes": ["launch_import_failed"]}

    phase_row = json.loads(Path(row["phase_rows_path"]).read_text(encoding="utf-8").strip())
    assert phase_row["phase"] == "initialized"
    assert phase_row["phase_result"] == "invalid_launch"
    assert phase_row["launch_integrity"]["reason_codes"] == ["launch_import_failed"]


def test_build_verifier_context_records_session_tool_evidence(tmp_path) -> None:
    mod = _load_module()
    from runner.aether2.envelope import ObservationEnvelope, ProcessDelta
    from runner.aether2.loop import RunResult, ToolInvocationRecord

    session_start = ToolInvocationRecord(
        step=1,
        tool_name="session_start",
        arguments={"session_id": "py", "command": "python3"},
        envelope=ObservationEnvelope(
            tool="session_start",
            exit_code=0,
            duration_sec=0.01,
            cwd=str(tmp_path),
            stdout_head="started session py",
            stdout_tail="",
            stderr_head="",
            stderr_tail="",
            truncated=False,
            raw_log_path=str(tmp_path / "start.json"),
            files_changed=[],
            process_delta=ProcessDelta(),
            blind_retry_blocked=False,
            error=None,
            truncation_digest=None,
        ),
    )
    session_read = ToolInvocationRecord(
        step=2,
        tool_name="session_read",
        arguments={"session_id": "py"},
        envelope=ObservationEnvelope(
            tool="session_read",
            exit_code=None,
            duration_sec=0.01,
            cwd=str(tmp_path),
            stdout_head=">>> x = 21\n>>> x * 2\n42\n",
            stdout_tail="",
            stderr_head="",
            stderr_tail="",
            truncated=False,
            raw_log_path=str(tmp_path / "read.json"),
            files_changed=[],
            process_delta=ProcessDelta(),
            blind_retry_blocked=False,
            error=None,
            truncation_digest=None,
        ),
    )
    result = RunResult(
        verifier_clean=True,
        finalize_reason="task_done",
        summary="done",
        steps=2,
        model_calls=2,
        tokens_cached=0,
        tokens_fresh=0,
        cost=0.0,
        wall_time=1.0,
        no_delta_streaks=0,
        verification_rounds=1,
        recoveries=0,
        compaction_count=0,
        job_survival=True,
        session_survival=True,
        suppressed_verifier_calls=0,
        completion_precheck_rejections=0,
        tool_invocations=[session_start, session_read],
        mirror_notes=[],
        discrepancy_reports=[],
    )
    task = mod.TaskSpec(
        task_id="g2_03_interactive_session",
        instruction="do it",
        task_dir=tmp_path,
        workspace_root=tmp_path / "workspace",
        artifacts_dir=tmp_path / "artifacts",
    )

    payload = mod._build_verifier_context(task, result, None)

    assert payload["run_result"]["session_survival"] is True
    assert payload["tool_invocations"][0]["tool_name"] == "session_start"
    assert payload["tool_invocations"][1]["envelope"]["stdout_head"].endswith("42\n")


def test_run_one_passes_verifier_context_and_cleans_up_container(monkeypatch, tmp_path) -> None:
    mod = _load_module()
    homolog_dir = tmp_path / "g2_03_interactive_session"
    homolog_dir.mkdir()
    verifier = homolog_dir / "verifier.sh"
    verifier.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    verifier.chmod(0o755)
    (homolog_dir / "instruction.md").write_text("do it\n", encoding="utf-8")
    (homolog_dir / "task.json").write_text(
        '{"task_id":"g2_03_interactive_session","workspace_root":"workspace","time_budget_sec":30}\n',
        encoding="utf-8",
    )

    workspace = tmp_path / "run" / "workspaces" / "g2_03_interactive_session" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "result.txt").write_text("42\n", encoding="utf-8")

    class _RuntimeHandle:
        container_id = "cid-123"

        def __init__(self) -> None:
            self.runtime = type(
                "Runtime",
                (),
                {"model_client": object(), "executor": object()},
            )()

        def __enter__(self):
            return self.runtime

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Result:
        verifier_clean = True
        finalize_reason = "task_done"
        summary = "done"
        steps = 3
        model_calls = 3
        tokens_cached = 0
        tokens_fresh = 0
        cost = 0.0
        wall_time = 1.0
        no_delta_streaks = 0
        verification_rounds = 1
        recoveries = 0
        compaction_count = 0
        job_survival = True
        session_survival = True
        grader_reward = None
        discrepancy_reports = []
        tool_invocations = []

    verifier_calls: list[list[str]] = []
    cleanup_calls: list[list[str]] = []

    monkeypatch.setattr(mod, "HOMOLOGS_DIR", tmp_path)
    monkeypatch.setattr(mod, "_build_runtime", lambda task: _RuntimeHandle())
    monkeypatch.setattr(mod, "run_aether2_loop", lambda *args, **kwargs: _Result())
    monkeypatch.setattr(mod, "build_scorecard", lambda result: type("Score", (), {"as_dict": lambda self: {"pass": True}})())

    def fake_retry(args, **kwargs):
        verifier_calls.append(list(args))
        context_path = Path(args[-1].split()[-1]) if len(args) == 1 else None
        return subprocess.CompletedProcess(args, 0, stdout="PASS\n", stderr=""), None

    monkeypatch.setattr(mod, "_run_with_eagain_retry", fake_retry)

    def fake_run(cmd, **kwargs):
        cleanup_calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    row = mod._run_one("g2_03_interactive_session", tmp_path / "run")

    context_path = tmp_path / "run" / "verifier_context" / "g2_03_interactive_session.json"
    assert row["row_status"] == "pass"
    assert context_path.exists()
    context = json.loads(context_path.read_text(encoding="utf-8"))
    assert context["run_result"]["session_survival"] is True
    assert verifier_calls and str(context_path) in verifier_calls[0][2]
    assert cleanup_calls == [["docker", "rm", "-f", "cid-123"]]
    phase_rows = Path(row["phase_rows_path"])
    assert phase_rows.exists()
    phase_entries = [json.loads(line) for line in phase_rows.read_text(encoding="utf-8").splitlines() if line]
    assert phase_entries[-1]["phase"] == "grader_run_completed"
    assert phase_entries[-1]["phase_result"] == "pass"


def test_run_one_reports_runtime_unavailable_as_invalid_environment(monkeypatch, tmp_path) -> None:
    mod = _load_module()
    homolog_dir = tmp_path / "g2_03_interactive_session"
    homolog_dir.mkdir()
    (homolog_dir / "instruction.md").write_text("do it\n", encoding="utf-8")
    (homolog_dir / "task.json").write_text(
        '{"task_id":"g2_03_interactive_session","workspace_root":"workspace","time_budget_sec":30}\n',
        encoding="utf-8",
    )
    (homolog_dir / "verifier.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    monkeypatch.setattr(mod, "HOMOLOGS_DIR", tmp_path)
    monkeypatch.setattr(mod, "_build_runtime", lambda task: (_ for _ in ()).throw(RuntimeError("docker unavailable")))

    row = mod._run_one("g2_03_interactive_session", tmp_path / "run")

    assert row["row_status"] == "invalid_environment"
    assert row["classification_stage"] == "launch"
    assert row["scoreable"] is False
    assert row["verifier_exit_code"] is None
    assert row["verifier_stderr"] == "runtime_unavailable: RuntimeError: docker unavailable"
    phase_rows = Path(row["phase_rows_path"])
    assert phase_rows.exists()
    phase_entries = [json.loads(line) for line in phase_rows.read_text(encoding="utf-8").splitlines() if line]
    assert phase_entries[-1]["phase"] == "initialized"


def test_run_one_reports_provider_400_as_invalid_provider(monkeypatch, tmp_path) -> None:
    mod = _load_module()
    from runner.model_client import ModelClientError

    homolog_dir = tmp_path / "g2_03_interactive_session"
    homolog_dir.mkdir()
    (homolog_dir / "instruction.md").write_text("do it\n", encoding="utf-8")
    (homolog_dir / "task.json").write_text(
        '{"task_id":"g2_03_interactive_session","workspace_root":"workspace","time_budget_sec":30}\n',
        encoding="utf-8",
    )
    (homolog_dir / "verifier.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    workspace = tmp_path / "run" / "workspaces" / "g2_03_interactive_session" / "workspace"
    workspace.mkdir(parents=True)

    class _RuntimeHandle:
        container_id = "cid-123"

        def __init__(self) -> None:
            self.runtime = type(
                "Runtime",
                (),
                {"model_client": object(), "executor": object()},
            )()

        def __enter__(self):
            return self.runtime

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mod, "HOMOLOGS_DIR", tmp_path)
    monkeypatch.setattr(mod, "_build_runtime", lambda task: _RuntimeHandle())
    monkeypatch.setattr(
        mod,
        "run_aether2_loop",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ModelClientError("bad request", status_code=400, error_kind="provider_bad_request")
        ),
    )

    def unexpected_verifier(*args, **kwargs):
        raise AssertionError("verifier should not run after provider failure")

    monkeypatch.setattr(mod, "_run_with_eagain_retry", unexpected_verifier)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
    )

    row = mod._run_one("g2_03_interactive_session", tmp_path / "run")

    assert row["row_status"] == "invalid_provider"
    assert row["classification_stage"] == "agent"
    assert row["scoreable"] is False
    phase_rows = Path(row["phase_rows_path"])
    assert phase_rows.exists()
    phase_entries = [json.loads(line) for line in phase_rows.read_text(encoding="utf-8").splitlines() if line]
    assert phase_entries[-1]["phase"] == "agent_run_completed"
    assert phase_entries[-1]["phase_result"] == "invalid_provider"


def test_phase_journal_retains_last_row_and_attempt_provenance(tmp_path) -> None:
    mod = _load_journal_module()
    journal = mod.RunJournal(
        tmp_path / "phase_rows.jsonl",
        metadata={"run_id": "run-1", "attempt": 1, "attempt_label": "Attempt 1"},
    )

    journal.append(
        mod.build_phase_row(
            mod.PHASE_INITIALIZED,
            attempt=1,
            attempt_label="Attempt 1",
            details={"run_id": "run-1"},
        )
    )
    journal.append(
        mod.build_phase_row(
            mod.PHASE_AGENT_RUN_STARTED,
            attempt=1,
            attempt_label="Attempt 1",
            details={"run_id": "run-1"},
        )
    )

    rows = journal.rows()
    assert len(rows) == 2
    assert journal.last_row()["phase"] == "agent_run_started"
    assert journal.last_row()["attempt"] == 1
    assert journal.last_row()["attempt_label"] == "Attempt 1"


@pytest.mark.parametrize(
    ("context_kwargs", "expected"),
    [
        (
            {"stage": "launch", "error_message": "ModuleNotFoundError: No module named 'runner'"},
            "invalid_launch",
        ),
        (
            {"stage": "launch", "error_message": "RuntimeError: docker unavailable"},
            "invalid_environment",
        ),
        (
            {
                "stage": "agent",
                "status_code": 400,
                "error_kind": "provider_bad_request",
                "error_message": "bad request",
            },
            "invalid_provider",
        ),
        (
            {"stage": "grader", "exit_code": 127, "error_message": "/bin/sh: pytest: command not found"},
            "invalid_grader",
        ),
        (
            {"stage": "grader", "exit_code": 137, "killed": True, "error_message": "Killed"},
            "invalid_resource_killed",
        ),
        (
            {"stage": "grader", "timed_out": True, "error_message": "command timed out"},
            "invalid_resource_killed",
        ),
        ({"stage": "grader", "exit_code": 1}, "fail"),
        ({"stage": "grader", "exit_code": 0}, "pass"),
        # W9.2: a clean grader exit (0 or 1) with a real test-runner summary is
        # authoritative -- pass/fail, never invalid -- even if the output also
        # contains words that would otherwise look like kill/toolchain signals.
        (
            {
                "stage": "grader",
                "exit_code": 1,
                "stderr": "collected 4 items\nFAILED test_x.py::test_answer - AssertionError\n1 failed, 3 passed in 2.10s",
            },
            "fail",
        ),
        (
            {
                "stage": "grader",
                "exit_code": 0,
                "stderr": "collected 2 items\n2 passed in 0.45s",
            },
            "pass",
        ),
        (
            {
                "stage": "grader",
                "exit_code": 137,
                "killed": True,
                "stderr": "Killed",
            },
            "invalid_resource_killed",
        ),
        (
            {
                "stage": "grader",
                "status_code": 400,
                "error_kind": "provider_bad_request",
                "error_message": "ModelClientError azure 400 bad request",
            },
            "invalid_provider",
        ),
        (
            {
                "stage": "grader",
                "exit_code": 2,
                "stderr": "ERROR: file or directory not found: tests/\ncollection failed",
            },
            "invalid_grader",
        ),
    ],
)
def test_classify_run_status_matrix(context_kwargs, expected) -> None:
    mod = _load_journal_module()
    context = mod.RunClassificationContext(**context_kwargs)
    assert mod.classify_run_status(context) == expected


def test_summarize_result_rows_excludes_invalid_populations_from_denominator() -> None:
    mod = _load_journal_module()
    rows = [
        mod.build_result_row(
            row_status="pass",
            classification_stage="grader",
            attempt=1,
            attempt_label="Attempt 1",
        ),
        mod.build_result_row(
            row_status="fail",
            classification_stage="grader",
            attempt=1,
            attempt_label="Attempt 1",
        ),
        mod.build_result_row(
            row_status="invalid_provider",
            classification_stage="agent",
            attempt=2,
            attempt_label="Attempt 2",
        ),
        mod.build_result_row(
            row_status="invalid_grader",
            classification_stage="grader",
            attempt=2,
            attempt_label="Attempt 2",
        ),
    ]

    summary = mod.summarize_result_rows(rows)

    assert summary["total_rows"] == 4
    assert summary["status_counts"]["pass"] == 1
    assert summary["status_counts"]["fail"] == 1
    assert summary["status_counts"]["invalid_provider"] == 1
    assert summary["status_counts"]["invalid_grader"] == 1
    assert summary["score_denominator"] == 2
    assert summary["score"] == 0.5
    assert summary["by_attempt"]["Attempt 1"]["total"] == 2
    assert summary["by_attempt"]["Attempt 2"]["total"] == 2


def test_g2_03_verifier_requires_real_interactive_session(tmp_path, retrying_subprocess) -> None:
    retrying_subprocess(sys.modules[__name__])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "result.txt").write_text("42\n", encoding="utf-8")
    context_path = tmp_path / "context.json"
    context_path.write_text(
        json.dumps(
            {
                "run_result": {"session_survival": True},
                "tool_invocations": [
                    {
                        "tool_name": "session_start",
                        "arguments": {"session_id": "py", "command": "python3"},
                        "envelope": {"exit_code": 0, "stdout_head": "started session py", "stdout_tail": ""},
                    },
                    {
                        "tool_name": "session_send",
                        "arguments": {"session_id": "py", "keys": "x = 21"},
                        "envelope": {"exit_code": 0, "stdout_head": "", "stdout_tail": ""},
                    },
                    {
                        "tool_name": "session_read",
                        "arguments": {"session_id": "py"},
                        "envelope": {"exit_code": None, "stdout_head": ">>> x * 2\n42\n", "stdout_tail": ""},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    verifier = (
        Path(__file__).resolve().parents[1]
        / "tracking"
        / "collab"
        / "aether2_g2_homologs"
        / "g2_03_interactive_session"
        / "verifier.sh"
    )

    passed = subprocess.run(
        [str(verifier), str(workspace), str(context_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert passed.returncode == 0
    assert "interactive session evidence is present" in passed.stdout

    context_path.write_text(
        json.dumps(
            {
                "run_result": {"session_survival": False},
                "tool_invocations": [],
            }
        ),
        encoding="utf-8",
    )
    failed = subprocess.run(
        [str(verifier), str(workspace), str(context_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode == 1
    assert "session_survival was not true" in failed.stdout

def test_g2_load_task_copies_workspace_fixture_for_service_task(tmp_path, monkeypatch):
    mod = _load_module()

    homolog_dir = tmp_path / "g2_02_service_survives_exit"
    homolog_dir.mkdir()
    (homolog_dir / "instruction.md").write_text("start service\n", encoding="utf-8")
    (homolog_dir / "task.json").write_text(
        '{"task_id": "g2_02_service_survives_exit", "workspace_root": "workspace", "time_budget_sec": 180}\n',
        encoding="utf-8",
    )

    fixture = homolog_dir / "workspace_fixture"
    fixture.mkdir()
    (fixture / "server_ok.py").write_text("print('ok server')\n", encoding="utf-8")

    run_dir = tmp_path / "runs" / "current"
    run_dir.mkdir(parents=True)

    task, budget = mod._load_task(homolog_dir, run_dir)

    assert budget == 180
    assert (task.workspace_root / "server_ok.py").read_text(encoding="utf-8") == "print('ok server')\n"
    assert task.workspace_root == run_dir / "workspaces" / "g2_02_service_survives_exit" / "workspace"
    assert task.task_dir == run_dir / "task_dirs" / "g2_02_service_survives_exit"
    assert task.artifacts_dir == run_dir / "artifacts" / "g2_02_service_survives_exit"
    assert (task.task_dir / "instruction.md").read_text(encoding="utf-8") == "start service\n"
    assert not (task.task_dir / "workspace_fixture").exists()
