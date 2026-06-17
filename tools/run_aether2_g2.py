#!/usr/bin/env python3
"""Run the five G2 local-homolog task shapes against a live model client.

Usage:
    python3 tools/run_aether2_g2.py

For each homolog directory under tracking/collab/aether2_g2_homologs/g2_*,
this script:
  - builds a TaskSpec from instruction.md + task.json
  - constructs the GPT-5.4 mini model client
  - runs the Aether-2 continuity loop against a local workspace
  - runs verifier.sh AFTER the loop returns (post-exit check for g2_02)
  - writes one row to result_rows.jsonl and prints a scoreboard

Output is written under:
    tracking/collab/aether2_g2_homologs/runs/<timestamp>/
"""

from __future__ import annotations

import errno
import ast
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import NamedTuple
import types

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _parse_toml_value(raw: str) -> object:
    value = raw.strip()
    if value.startswith(("'", '"')):
        return ast.literal_eval(value)
    if value in {"true", "false"}:
        return value == "true"
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def _install_tomllib_fallback() -> None:
    try:
        import tomllib as tomllib_module  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        try:
            import tomli as tomllib_module  # type: ignore[import-not-found]
        except ModuleNotFoundError:
            tomllib_module = types.ModuleType("tomllib")

            def loads(text: str) -> dict[str, object]:
                data: dict[str, object] = {}
                current: dict[str, object] = data
                for raw_line in text.splitlines():
                    line = raw_line.split("#", 1)[0].strip()
                    if not line:
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        path = [part.strip() for part in line[1:-1].split(".") if part.strip()]
                        current = data
                        for part in path:
                            next_value = current.get(part)
                            if not isinstance(next_value, dict):
                                next_value = {}
                                current[part] = next_value
                            current = next_value
                        continue
                    if "=" not in line:
                        continue
                    key, value = [part.strip() for part in line.split("=", 1)]
                    current[key] = _parse_toml_value(value)
                return data

            def load(fp) -> dict[str, object]:
                return loads(fp.read())

            tomllib_module.loads = loads  # type: ignore[attr-defined]
            tomllib_module.load = load  # type: ignore[attr-defined]
    sys.modules["tomllib"] = tomllib_module


_install_tomllib_fallback()

from runner.aether2.bridge_harbor import TaskSpec, _build_runtime  # noqa: E402
from runner.aether2.loop import run_aether2_loop  # noqa: E402
from runner.aether2.metrics import build_scorecard  # noqa: E402
from tools.run_phase_journal import (  # noqa: E402
    PHASE_AGENT_RUN_COMPLETED,
    PHASE_AGENT_RUN_STARTED,
    PHASE_GRADER_RUN_COMPLETED,
    PHASE_GRADER_RUN_STARTED,
    PHASE_INITIALIZED,
    RunClassificationContext,
    RunJournal,
    build_phase_row,
    build_result_row,
    classify_run_status,
    summarize_result_rows,
)
from tools.aether2_launch_integrity import run_launch_integrity_preflight, write_launch_integrity_report  # noqa: E402

HOMOLOGS_DIR = REPO_ROOT / "tracking" / "collab" / "aether2_g2_homologs"
HOMOLOG_IDS = [
    "g2_01_file_artifact",
    "g2_02_service_survives_exit",
    "g2_03_interactive_session",
    "g2_04_package_install",
    "g2_05_long_running_job",
]

_RESULT_PASSTHROUGH_FIELDS = (
    "persistent_blockers",
    "verifier_suppression_metrics",
    "verifier_suppression",
    "environment_contract_version",
    "environment_contract_digest",
    "environment_contract_ref",
)


# Ports used by homolog tasks (read from instruction.md/verifier.sh): used by
# pre-run cleanup (H2b) to find and kill leftover listeners from PRIOR G2 runs.
HOMOLOG_PORTS: dict[str, list[int]] = {
    "g2_02_service_survives_exit": [8123],
}

# Subprocess-spawn EAGAIN retry parameters (H1), matching
# ContainerExecutor._run_subprocess's retry armor (5 attempts, 0.2s exponential
# backoff) so verifier.sh invocations survive transient host fork pressure.
_SPAWN_RETRY_MAX = 5
_SPAWN_RETRY_BASE_SEC = 0.2


class CleanupOutcome(NamedTuple):
    log_lines: list[str]
    blocked_homologs: dict[str, str]


def _is_eagain_spawn_failure(exc: BaseException) -> bool:
    if isinstance(exc, BlockingIOError):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.EAGAIN:
        return True
    return False


def _run_with_eagain_retry(
    args: list[str], **kwargs: object
) -> tuple["subprocess.CompletedProcess[str] | None", str | None]:
    """Run `subprocess.run(args, **kwargs)` with EAGAIN/fork-pressure retry.

    Returns (completed_process, None) on success, or (None, reason) if every
    attempt failed due to host fork pressure (`fork: Resource temporarily
    unavailable` / EAGAIN / BlockingIOError on spawn). Any other exception is
    re-raised.
    """
    last_reason: str | None = None
    for attempt in range(_SPAWN_RETRY_MAX):
        try:
            proc = subprocess.run(args, **kwargs)  # type: ignore[arg-type]
        except BaseException as exc:  # noqa: BLE001
            if _is_eagain_spawn_failure(exc):
                last_reason = f"{type(exc).__name__}: {exc}"
                time.sleep(_SPAWN_RETRY_BASE_SEC * (2**attempt))
                continue
            raise
        if proc.returncode == 128 and "fork: Resource temporarily unavailable" in (proc.stderr or ""):
            last_reason = proc.stderr.strip()
            time.sleep(_SPAWN_RETRY_BASE_SEC * (2**attempt))
            continue
        return proc, None
    return None, last_reason or "fork: Resource temporarily unavailable (retries exhausted)"


def _read_text_if_exists(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _pid_cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_text(encoding="utf-8", errors="replace").replace("\x00", " ").strip()
    except OSError:
        return ""


def _homolog_id_from_path(path: Path) -> str | None:
    for part in path.parts:
        if part in HOMOLOG_IDS:
            return part
    return None


def _record_blocker(blocked_homologs: dict[str, str], homolog_id: str, message: str) -> None:
    existing = blocked_homologs.get(homolog_id)
    blocked_homologs[homolog_id] = f"{existing}; {message}" if existing else message


def _signal_and_wait_for_exit(pid: int, log: list[str], note: str) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
        log.append(f"killed pid {pid} ({note})")
    except ProcessLookupError:
        return True
    except OSError as exc:
        log.append(f"failed to kill pid {pid} ({note}): {exc}")
        return False
    for _ in range(20):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            return True
        time.sleep(0.1)
    log.append(f"pid {pid} still alive after SIGTERM ({note})")
    return False


def _load_task(homolog_dir: Path, run_dir: Path) -> tuple[TaskSpec, int]:
    instruction = (homolog_dir / "instruction.md").read_text(encoding="utf-8")
    config = json.loads((homolog_dir / "task.json").read_text(encoding="utf-8"))

    # H2(a): each run gets a FRESH, isolated workspace under
    # runs/<ts>/workspaces/<homolog_id>/ rather than reusing the shared
    # workspace/ dir in the homolog directory across runs. If the homolog
    # ships a pristine fixture workspace (workspace_fixture/), seed from that;
    # otherwise start empty (matching the previous rmtree+mkdir behavior).
    workspace_root = run_dir / "workspaces" / homolog_dir.name / config["workspace_root"]
    if workspace_root.exists():
        shutil.rmtree(workspace_root)
    fixture_dir = homolog_dir / "workspace_fixture"
    if fixture_dir.exists():
        shutil.copytree(fixture_dir, workspace_root)
    else:
        workspace_root.mkdir(parents=True, exist_ok=True)

    task_run_dir = run_dir / "task_dirs" / homolog_dir.name
    if task_run_dir.exists():
        shutil.rmtree(task_run_dir)
    shutil.copytree(
        homolog_dir,
        task_run_dir,
        ignore=shutil.ignore_patterns(".aether2", "artifacts", "workspace", "workspace_fixture"),
    )

    artifacts_dir = run_dir / "artifacts" / homolog_dir.name
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    task = TaskSpec(
        task_id=config["task_id"],
        instruction=instruction,
        task_dir=task_run_dir,
        workspace_root=workspace_root,
        artifacts_dir=artifacts_dir,
    )
    return task, int(config.get("time_budget_sec", 180))


def _load_attempt_metadata(homolog_dir: Path) -> dict[str, object]:
    try:
        config = json.loads((homolog_dir / "task.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    metadata: dict[str, object] = {}
    for key in ("attempt", "attempt_label", "attempt_source", "attempt_provenance"):
        if key in config:
            value = config[key]
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                metadata[key] = value
    return metadata


def _collect_result_passthrough_fields(result: object | None) -> dict[str, object]:
    if result is None:
        return {}
    passthrough: dict[str, object] = {}
    for field in _RESULT_PASSTHROUGH_FIELDS:
        value = getattr(result, field, None)
        if value is not None:
            passthrough[field] = value
    return passthrough


def _iter_prior_run_dirs(run_dir: Path) -> list[Path]:
    runs_root = run_dir.parent
    return sorted(p for p in runs_root.iterdir() if p.is_dir() and p != run_dir)


def _port_listener_pids(port: int) -> list[int]:
    try:
        proc = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    pids: list[int] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return pids


def _cleanup_prior_runs(run_dir: Path) -> CleanupOutcome:
    """H2(b): kill leftover processes from PRIOR G2 runs before starting.

    Two sources of evidence are used, and ONLY pids attributable to prior G2
    runs (via pidfile path or matching cmdline) are killed -- never arbitrary
    port holders:

    1. Job pidfiles under previous runs' `workspaces/<homolog_id>/.aether2/state/jobs/*/job.pid`.
    2. `lsof -i :<port>` for each port a homolog task is known to use (e.g.
       8123 for g2_02), cross-checked against the job pidfiles / cmdline so we
       only kill processes whose cmdline matches the known job launch command
       recorded in that job's meta.json `cmd`.
    """
    log: list[str] = []
    known_pids: set[int] = set()
    known_job_commands: dict[str, set[str]] = {key: set() for key in HOMOLOG_PORTS}
    blocked_homologs: dict[str, str] = {}

    for prior in _iter_prior_run_dirs(run_dir):
        for jobs_dir in prior.glob("workspaces/*/*/.aether2/state/jobs/*"):
            pidfile = jobs_dir / "job.pid"
            meta_cmd = _read_text_if_exists(jobs_dir / "meta.json")
            if meta_cmd:
                try:
                    cmd = json.loads(meta_cmd).get("cmd")
                except json.JSONDecodeError:
                    cmd = None
                if isinstance(cmd, str):
                    homolog_id = _homolog_id_from_path(jobs_dir)
                    if homolog_id in known_job_commands:
                        known_job_commands[homolog_id].add(cmd)
            if not pidfile.exists():
                continue
            try:
                pid = int(pidfile.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                continue
            if pid <= 0:
                continue
            known_pids.add(pid)
            _signal_and_wait_for_exit(pid, log, f"pidfile {pidfile}")

    # Also check legacy shared workspace/.aether2/state/jobs (pre-H2 layout).
    for jobs_dir in HOMOLOGS_DIR.glob("g2_*/workspace/.aether2/state/jobs/*"):
        pidfile = jobs_dir / "job.pid"
        meta_cmd = _read_text_if_exists(jobs_dir / "meta.json")
        if meta_cmd:
            try:
                cmd = json.loads(meta_cmd).get("cmd")
            except json.JSONDecodeError:
                cmd = None
            if isinstance(cmd, str):
                homolog_id = _homolog_id_from_path(jobs_dir)
                if homolog_id in known_job_commands:
                    known_job_commands[homolog_id].add(cmd)
        if not pidfile.exists():
            continue
        try:
            pid = int(pidfile.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            continue
        if pid <= 0 or pid in known_pids:
            continue
        known_pids.add(pid)
        _signal_and_wait_for_exit(pid, log, f"legacy pidfile {pidfile}")

    # Port-based cleanup: for each known homolog port, find listeners via lsof
    # and kill only those attributable to prior G2 runs (pidfile or cmdline
    # match against prior-run job metadata). If a listener remains that we
    # cannot attribute, block that homolog honestly instead of contaminating
    # the run with a reused service from somewhere else.
    for homolog_id, ports in HOMOLOG_PORTS.items():
        for port in ports:
            for pid in _port_listener_pids(port):
                if pid in known_pids:
                    _signal_and_wait_for_exit(pid, log, f"port {port} listener from prior {homolog_id} run")
                    continue
                cmdline = _pid_cmdline(pid)
                matched_cmd = next(
                    (cmd for cmd in known_job_commands.get(homolog_id, set()) if cmd and cmd in cmdline),
                    None,
                )
                if matched_cmd is not None:
                    _signal_and_wait_for_exit(
                        pid,
                        log,
                        f"port {port} listener matched prior {homolog_id} job cmd {matched_cmd!r}",
                    )
                else:
                    _record_blocker(
                        blocked_homologs,
                        homolog_id,
                        f"port {port} already occupied by unattributable pid {pid}"
                        + (f" cmdline={cmdline!r}" if cmdline else ""),
                    )
                    log.append(
                        f"blocking {homolog_id}: port {port} has listener pid {pid} not attributable to a prior G2 run"
                    )
            remaining = _port_listener_pids(port)
            if remaining and homolog_id not in blocked_homologs:
                _record_blocker(
                    blocked_homologs,
                    homolog_id,
                    f"port {port} still occupied after attributable cleanup by pid(s) {remaining}",
                )
                log.append(
                    f"blocking {homolog_id}: port {port} still occupied after cleanup by pid(s) {remaining}"
                )

    return CleanupOutcome(log, blocked_homologs)


def _run_one(homolog_id: str, run_dir: Path, *, blocked_reason: str | None = None) -> dict:
    homolog_dir = HOMOLOGS_DIR / homolog_id
    attempt_metadata = _load_attempt_metadata(homolog_dir)
    phase_rows_path = run_dir / "phase_rows.jsonl"
    phase_journal = RunJournal(
        phase_rows_path,
        metadata={"run_id": f"{run_dir.name}:{homolog_id}", "homolog_id": homolog_id, **attempt_metadata},
    )
    phase_journal.append(
        build_phase_row(
            PHASE_INITIALIZED,
            attempt=attempt_metadata.get("attempt"),
            attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
            details={"homolog_id": homolog_id},
        )
    )

    if blocked_reason is not None:
        row = build_result_row(
            row_status="invalid_environment",
            classification_stage="launch",
            attempt=attempt_metadata.get("attempt"),
            attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
            details={
                "homolog_id": homolog_id,
                "phase_rows_path": str(phase_rows_path),
                "wall_time_sec": 0.0,
                "verifier_exit_code": None,
                "verifier_stdout": "",
                "verifier_stderr": blocked_reason,
                "loop_error": None,
            },
        )
        return row

    try:
        task, time_budget = _load_task(homolog_dir, run_dir)
    except Exception as exc:  # noqa: BLE001
        row_status = classify_run_status(RunClassificationContext(stage="launch", error=exc))
        return build_result_row(
            row_status=row_status,
            classification_stage="launch",
            attempt=attempt_metadata.get("attempt"),
            attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
            details={
                "homolog_id": homolog_id,
                "phase_rows_path": str(phase_rows_path),
                "wall_time_sec": 0.0,
                "verifier_exit_code": None,
                "verifier_stdout": "",
                "verifier_stderr": f"{type(exc).__name__}: {exc}",
                "loop_error": None,
            },
        )

    try:
        runtime_handle = _build_runtime(task)
    except Exception as exc:  # noqa: BLE001
        row_status = classify_run_status(RunClassificationContext(stage="launch", error=exc))
        return build_result_row(
            row_status=row_status,
            classification_stage="launch",
            attempt=attempt_metadata.get("attempt"),
            attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
            details={
                "homolog_id": homolog_id,
                "phase_rows_path": str(phase_rows_path),
                "wall_time_sec": 0.0,
                "verifier_exit_code": None,
                "verifier_stdout": "",
                "verifier_stderr": f"runtime_unavailable: {type(exc).__name__}: {exc}",
                "loop_error": None,
            },
        )
    runtime = runtime_handle.__enter__()
    verifier_proc = None
    eagain_reason: str | None = None
    start = time.time()
    deadline_ts = start + time_budget
    error: str | None = None
    result = None
    verifier_context_path = run_dir / "verifier_context" / f"{homolog_id}.json"
    try:
        phase_journal.append(build_phase_row(PHASE_AGENT_RUN_STARTED, attempt=attempt_metadata.get("attempt"), attempt_label=str(attempt_metadata.get("attempt_label") or "") or None))
        try:
            result = run_aether2_loop(task, runtime.model_client, runtime.executor, deadline_ts=deadline_ts)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            agent_status = classify_run_status(RunClassificationContext(stage="agent", error=exc))
            phase_journal.append(
                build_phase_row(
                    PHASE_AGENT_RUN_COMPLETED,
                    phase_result=agent_status,
                    attempt=attempt_metadata.get("attempt"),
                    attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
                    details={"loop_error": error},
                )
            )
            wall_time = time.time() - start
            row = build_result_row(
                row_status=agent_status,
                classification_stage="agent",
                attempt=attempt_metadata.get("attempt"),
                attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
                details={
                    "homolog_id": homolog_id,
                    "phase_rows_path": str(phase_rows_path),
                    "wall_time_sec": wall_time,
                    "verifier_exit_code": None,
                    "verifier_stdout": "",
                    "verifier_stderr": "",
                    "loop_error": error,
                },
            )
            return row
        else:
            phase_journal.append(
                build_phase_row(
                    PHASE_AGENT_RUN_COMPLETED,
                    phase_result="completed",
                    attempt=attempt_metadata.get("attempt"),
                    attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
                    details={"loop_error": None},
                )
            )
        wall_time = time.time() - start

        verifier_context_path.parent.mkdir(parents=True, exist_ok=True)
        verifier_context_path.write_text(
            json.dumps(_build_verifier_context(task, result, error), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        # Run the verifier AFTER the loop has returned (and the agent process
        # tree has exited), per spec. For g2_02 this is the post-exit liveness
        # check on the still-running background service.
        verifier_path = homolog_dir / "verifier.sh"
        verifier_cmd = (
            f"{shlex.quote(str(verifier_path))} "
            f"{shlex.quote(str(task.workspace_root))} "
            f"{shlex.quote(str(verifier_context_path))}"
        )
        phase_journal.append(
            build_phase_row(
                PHASE_GRADER_RUN_STARTED,
                attempt=attempt_metadata.get("attempt"),
                attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
                details={"verifier_context_path": str(verifier_context_path)},
            )
        )
        try:
            verifier_proc, eagain_reason = _run_with_eagain_retry(
                ["/bin/sh", "-lc", verifier_cmd],
                cwd=str(task.workspace_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired as exc:
            eagain_reason = f"{type(exc).__name__}: {exc}"
            grader_status = classify_run_status(
                RunClassificationContext(stage="grader", error=exc, timed_out=True, stderr=str(exc))
            )
            phase_journal.append(
                build_phase_row(
                    PHASE_GRADER_RUN_COMPLETED,
                    phase_result=grader_status,
                    attempt=attempt_metadata.get("attempt"),
                    attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
                    details={"verifier_error": eagain_reason},
                )
            )
            verifier_proc = None
        except Exception as exc:  # noqa: BLE001
            eagain_reason = f"{type(exc).__name__}: {exc}"
            grader_status = classify_run_status(RunClassificationContext(stage="grader", error=exc, stderr=str(exc)))
            phase_journal.append(
                build_phase_row(
                    PHASE_GRADER_RUN_COMPLETED,
                    phase_result=grader_status,
                    attempt=attempt_metadata.get("attempt"),
                    attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
                    details={"verifier_error": eagain_reason},
                )
            )
            verifier_proc = None
        else:
            if verifier_proc is None:
                grader_status = classify_run_status(
                    RunClassificationContext(stage="grader", blocked_reason=eagain_reason, stderr=eagain_reason or "")
                )
            else:
                grader_status = classify_run_status(
                    RunClassificationContext(
                        stage="grader",
                        exit_code=verifier_proc.returncode,
                        stderr=f"{verifier_proc.stdout or ''}\n{verifier_proc.stderr or ''}",
                    )
                )
            phase_journal.append(
                build_phase_row(
                    PHASE_GRADER_RUN_COMPLETED,
                    phase_result=grader_status,
                    attempt=attempt_metadata.get("attempt"),
                    attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
                    details={
                        "verifier_exit_code": None if verifier_proc is None else verifier_proc.returncode,
                        "verifier_error": eagain_reason,
                    },
                )
            )
    finally:
        runtime_handle.__exit__(None, None, None)
        _cleanup_runtime_container(getattr(runtime_handle, "container_id", None))

    scorecard = None
    if result is not None:
        scorecard = build_scorecard(result)

    if verifier_proc is None:
        verifier_exit = None
        verifier_stdout = ""
        verifier_stderr = eagain_reason or ""
        row_status = classify_run_status(
            RunClassificationContext(stage="grader", blocked_reason=eagain_reason, stderr=verifier_stderr)
        )
        classification_stage = "grader"
    else:
        verifier_exit = verifier_proc.returncode
        verifier_stdout = verifier_proc.stdout.strip()
        verifier_stderr = verifier_proc.stderr.strip()
        row_status = classify_run_status(
            RunClassificationContext(
                stage="grader",
                exit_code=verifier_exit,
                stderr=f"{verifier_stdout}\n{verifier_stderr}",
            )
        )
        classification_stage = "grader"
    row = build_result_row(
        row_status=row_status,
        classification_stage=classification_stage,
        attempt=attempt_metadata.get("attempt"),
        attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
        details={
            "homolog_id": homolog_id,
            "phase_rows_path": str(phase_rows_path),
            "wall_time_sec": wall_time,
            "verifier_exit_code": verifier_exit,
            "verifier_stdout": verifier_stdout,
            "verifier_stderr": verifier_stderr,
            "loop_error": error,
        },
    )
    passthrough_fields = _collect_result_passthrough_fields(result)
    if passthrough_fields:
        row.update(passthrough_fields)
    if scorecard is not None:
        row["scorecard"] = scorecard.as_dict()
    if result is not None:
        row["run_result"] = {
            "verifier_clean": result.verifier_clean,
            "finalize_reason": result.finalize_reason,
            "summary": result.summary,
            "steps": result.steps,
            "model_calls": result.model_calls,
            "tokens_cached": result.tokens_cached,
            "tokens_fresh": result.tokens_fresh,
            "cost": result.cost,
            "wall_time": result.wall_time,
            "no_delta_streaks": result.no_delta_streaks,
            "verification_rounds": result.verification_rounds,
            "recoveries": result.recoveries,
            "compaction_count": result.compaction_count,
            "job_survival": result.job_survival,
            "session_survival": result.session_survival,
            "grader_reward": result.grader_reward,
            "discrepancy_reports": [asdict(report) for report in result.discrepancy_reports],
            **passthrough_fields,
        }

    return row


def _invalid_launch_row_for_homolog(
    homolog_id: str,
    run_dir: Path,
    *,
    reason: str,
    details: dict[str, object],
) -> dict:
    homolog_dir = HOMOLOGS_DIR / homolog_id
    attempt_metadata = _load_attempt_metadata(homolog_dir)
    phase_rows_path = run_dir / "phase_rows.jsonl"
    phase_journal = RunJournal(
        phase_rows_path,
        metadata={"run_id": f"{run_dir.name}:{homolog_id}", "homolog_id": homolog_id, **attempt_metadata},
    )
    phase_journal.append(
        build_phase_row(
            PHASE_INITIALIZED,
            phase_result="invalid_launch",
            attempt=attempt_metadata.get("attempt"),
            attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
            details={"homolog_id": homolog_id, "launch_integrity": details},
        )
    )
    return build_result_row(
        row_status="invalid_launch",
        classification_stage="launch",
        attempt=attempt_metadata.get("attempt"),
        attempt_label=str(attempt_metadata.get("attempt_label") or "") or None,
        details={
            "homolog_id": homolog_id,
            "phase_rows_path": str(phase_rows_path),
            "wall_time_sec": 0.0,
            "verifier_exit_code": None,
            "verifier_stdout": "",
            "verifier_stderr": reason,
            "loop_error": reason,
            "launch_integrity": details,
        },
    )


def _cleanup_runtime_container(container_id: str | None) -> None:
    if not container_id:
        return
    try:
        subprocess.run(
            ["docker", "rm", "-f", container_id],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except OSError:
        return


def _build_verifier_context(task: TaskSpec, result: object | None, loop_error: str | None) -> dict[str, object]:
    tool_invocations: list[dict[str, object]] = []
    passthrough_fields = _collect_result_passthrough_fields(result)
    if result is not None:
        for record in getattr(result, "tool_invocations", []) or []:
            envelope = getattr(record, "envelope", None)
            tool_invocations.append(
                {
                    "step": getattr(record, "step", None),
                    "tool_name": getattr(record, "tool_name", ""),
                    "arguments": getattr(record, "arguments", {}),
                    "envelope": {
                        "tool": getattr(envelope, "tool", None),
                        "exit_code": getattr(envelope, "exit_code", None),
                        "cwd": getattr(envelope, "cwd", None),
                        "stdout_head": getattr(envelope, "stdout_head", ""),
                        "stdout_tail": getattr(envelope, "stdout_tail", ""),
                        "stderr_head": getattr(envelope, "stderr_head", ""),
                        "stderr_tail": getattr(envelope, "stderr_tail", ""),
                        "raw_log_path": getattr(envelope, "raw_log_path", None),
                    },
                }
            )
    return {
        "task_id": task.task_id,
        "workspace_root": str(task.workspace_root),
        "loop_error": loop_error,
        "run_result": None
        if result is None
        else {
            "verifier_clean": getattr(result, "verifier_clean", None),
            "finalize_reason": getattr(result, "finalize_reason", None),
            "summary": getattr(result, "summary", None),
            "verification_rounds": getattr(result, "verification_rounds", None),
            "job_survival": getattr(result, "job_survival", None),
            "session_survival": getattr(result, "session_survival", None),
            **passthrough_fields,
        },
        "tool_invocations": tool_invocations,
        **passthrough_fields,
    }


def main() -> int:
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = HOMOLOGS_DIR / "runs" / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    rows_path = run_dir / "result_rows.jsonl"
    scoreboard_path = run_dir / "scoreboard.md"
    cleanup_log_path = run_dir / "pre_run_cleanup.log"
    launch_report_path = run_dir / "launch_integrity.json"

    launch_report = run_launch_integrity_preflight(repo_root=REPO_ROOT)
    write_launch_integrity_report(launch_report_path, launch_report)
    if not launch_report.ok:
        reason = "launch_integrity_preflight_failed: " + ",".join(launch_report.reason_codes)
        rows = [
            _invalid_launch_row_for_homolog(
                homolog_id,
                run_dir,
                reason=reason,
                details={"launch_integrity_ref": str(launch_report_path), **launch_report.as_dict()},
            )
            for homolog_id in HOMOLOG_IDS
        ]
        rows_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        scoreboard_path.write_text(_render_scoreboard(timestamp, rows), encoding="utf-8")
        print(reason, flush=True)
        print(f"Wrote {rows_path}")
        print(f"Wrote {scoreboard_path}")
        return 1

    cleanup_outcome = _cleanup_prior_runs(run_dir)
    cleanup_log_path.write_text(
        ("\n".join(cleanup_outcome.log_lines) + "\n") if cleanup_outcome.log_lines else "(no leftover processes found)\n",
        encoding="utf-8",
    )
    for line in cleanup_outcome.log_lines:
        print(f"[cleanup] {line}", flush=True)

    rows = []
    with rows_path.open("w", encoding="utf-8") as fh:
        for homolog_id in HOMOLOG_IDS:
            print(f"=== running {homolog_id} ===", flush=True)
            row = _run_one(
                homolog_id,
                run_dir,
                blocked_reason=cleanup_outcome.blocked_homologs.get(homolog_id),
            )
            rows.append(row)
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(json.dumps(row, indent=2), flush=True)

    scoreboard_path.write_text(_render_scoreboard(timestamp, rows), encoding="utf-8")
    print(f"\nWrote {rows_path}")
    print(f"Wrote {scoreboard_path}")
    return 0


def _render_scoreboard(timestamp: str, rows: list[dict]) -> str:
    lines = [
        "# G2 local-homolog scoreboard",
        "",
        f"Run timestamp: {timestamp}",
        "",
        "| homolog | row_status | classification_stage | scoreable | verifier_exit | verifier_clean | steps | model_calls | tokens_cached | tokens_fresh | wall_time_sec | loop_error |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        rr = row.get("run_result", {})
        lines.append(
            "| {homolog} | {status} | {stage} | {scoreable} | {vexit} | {vclean} | {steps} | {calls} | {cached} | {fresh} | {wt:.1f} | {err} |".format(
                homolog=row["homolog_id"],
                status=row.get("row_status"),
                stage=row.get("classification_stage"),
                scoreable=row.get("scoreable"),
                vexit=row["verifier_exit_code"],
                vclean=rr.get("verifier_clean"),
                steps=rr.get("steps"),
                calls=rr.get("model_calls"),
                cached=rr.get("tokens_cached"),
                fresh=rr.get("tokens_fresh"),
                wt=row["wall_time_sec"],
                err=row["loop_error"] or "",
            )
        )

    summary = summarize_result_rows(rows)
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- total_rows: {summary['total_rows']}",
            f"- scorable_rows: {summary['scorable_rows']}",
            f"- score_numerator: {summary['score_numerator']}",
            f"- score_denominator: {summary['score_denominator']}",
            f"- score: {summary['score'] if summary['score'] is not None else 'n/a'}",
            "",
            "| row_status | count |",
            "|---|---|",
        ]
    )
    for status in (
        "pass",
        "fail",
        "invalid_launch",
        "invalid_environment",
        "invalid_provider",
        "invalid_resource_killed",
        "invalid_grader",
    ):
        lines.append(f"| {status} | {summary['status_counts'][status]} |")
    if summary["by_attempt"]:
        lines.extend(["", "## By Attempt", "", "| attempt | pass | fail | invalid | total |", "|---|---|---|---|---|"])
        for attempt_name in sorted(summary["by_attempt"]):
            attempt_counts = summary["by_attempt"][attempt_name]
            invalid_total = attempt_counts["invalid_launch"] + attempt_counts["invalid_environment"] + attempt_counts["invalid_provider"] + attempt_counts["invalid_resource_killed"] + attempt_counts["invalid_grader"]
            lines.append(
                f"| {attempt_name} | {attempt_counts['pass']} | {attempt_counts['fail']} | {invalid_total} | {attempt_counts['total']} |"
            )

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
