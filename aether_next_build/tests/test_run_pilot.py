from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import run_pilot


def test_run_pilot_persists_in_progress_row_before_task_runner_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_dir = tmp_path / "tasks"
    task_dir = tasks_dir / "demo-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text('docker_image = "demo:latest"\n', encoding="utf-8")
    out_path = tmp_path / "results.json"

    monkeypatch.setattr(run_pilot, "make_azure_callable", lambda **_kwargs: (lambda *_a, **_k: "{}"))
    monkeypatch.setattr(run_pilot, "_read_docker_image", lambda _task_dir: "demo:latest")

    def fake_run_tbench_task(**kwargs):
        rows = json.loads(out_path.read_text(encoding="utf-8"))
        assert rows == [
            {
                "task": "demo-task",
                "image": "demo:latest",
                "architect_mode": "workbench",
                "reference_architect_mode": False,
                "reward": 0.0,
                "status": "running",
                "kernel_status": "running",
                "error": "attempt_in_progress",
                "error_detail": "task attempt started but no terminal result row has been written yet",
                "classifier_label": "attempt_in_progress",
                "classifier_confidence": "high",
                "classifier_detail": "non-terminal launch receipt; replace with completed/error row when run_tbench_task returns",
                "step": 0,
                "reconfigurations": 0,
                "model_parse_errors": [],
                "grader_exit": -1,
                "grader_stdout_tail": "",
                "grader_stderr_tail": "",
                "receipt_summary": [],
            }
        ]
        return {
            "task": "demo-task",
            "image": "demo:latest",
            "architect_mode": "workbench",
            "reference_architect_mode": False,
            "reward": 1.0,
            "status": "completed",
            "kernel_status": "completed",
            "classifier_label": "none",
            "classifier_confidence": "high",
            "classifier_detail": "completed",
            "step": 1,
            "reconfigurations": 0,
            "model_parse_errors": [],
            "grader_exit": 0,
            "grader_stdout_tail": "",
            "grader_stderr_tail": "",
            "receipt_summary": [],
        }

    monkeypatch.setattr(run_pilot, "run_tbench_task", fake_run_tbench_task)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pilot.py",
            "--tasks-dir",
            str(tasks_dir),
            "--tasks",
            "demo-task",
            "--out",
            str(out_path),
        ],
    )

    assert run_pilot.main() == 0

    rows = json.loads(out_path.read_text(encoding="utf-8"))
    assert rows[0]["status"] == "completed"
    assert rows[0]["reward"] == 1.0
