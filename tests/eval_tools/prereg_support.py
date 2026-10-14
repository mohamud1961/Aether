"""Builders shared by the pre-registration tests: a plan project on disk and trial rows for it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval_support import write_task
from harness_evals import prereg

SEALED_AT = "2026-10-13T09:00:00+00:00"
ARM_LINES = ('  - "name=baseline agent=noop"', '  - "name=candidate agent=minimal"')


def plan_yaml(
    *,
    k: int = 10,
    tasks: tuple[str, ...] = ("alpha", "beta", "gamma"),
    sentinels: tuple[str, ...] = ("gamma",),
    arms: tuple[str, ...] = ARM_LINES,
    baseline: str = "baseline",
    candidate: str = "candidate",
    falsifier: str = "candidate_rate <= baseline_rate",
    promotion: str = "diff_ci_low > 0",
    primary: str = "pass_rate",
) -> str:
    lines = [
        'question: "Does the candidate arm pass more tasks than the baseline arm?"',
        "arms:",
        *arms,
        f"baseline: {baseline}",
        f"candidate: {candidate}",
        "tasks:",
        *[f'  - "../tasks/{task}"' for task in tasks],
        "sentinels:",
        *[f"  - {sentinel}" for sentinel in sentinels],
        f"k: {k}",
        f"primary_metric: {primary}",
        f'falsifier: "{falsifier}"',
        f'promotion_bar: "{promotion}"',
    ]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class Project:
    plan: Path
    seal: Path
    trials: Path
    tasks_dir: Path


def make_project(
    tmp_path: Path,
    *,
    k: int = 10,
    task_ids: tuple[str, ...] = ("alpha", "beta", "gamma"),
    sentinels: tuple[str, ...] = ("gamma",),
    **plan_options: Any,
) -> Project:
    """Write task directories and a plan under tmp_path, then seal the plan."""
    tasks_dir = tmp_path / "tasks"
    for task_id in task_ids:
        write_task(tasks_dir, task_id=task_id)
    plans = tmp_path / "plans"
    plans.mkdir()
    plan = plans / "plan.yaml"
    plan.write_text(plan_yaml(k=k, tasks=task_ids, sentinels=sentinels, **plan_options), encoding="utf-8")
    seal_path = plans / prereg.SEAL_FILE
    prereg.seal(plan, at=SEALED_AT, seal_path=seal_path)
    return Project(plan=plan, seal=seal_path, trials=plans / "trials.jsonl", tasks_dir=tasks_dir)


def read_seal(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def trial_rows(seal: dict[str, Any], outcomes: dict[tuple[str, str], list[bool | None]]) -> list[dict[str, Any]]:
    """One trial row per entry. True and False are valid outcomes; None is an invalid row."""
    rows: list[dict[str, Any]] = []
    for (arm, task_id), entries in outcomes.items():
        for attempt, entry in enumerate(entries, start=1):
            valid = entry is not None
            rows.append(
                {
                    "run_id": "run-test",
                    "arm": arm,
                    "task_id": task_id,
                    "attempt": attempt,
                    "started_at": "2026-10-13T10:00:00+00:00",
                    "wall_s": 1.0,
                    "passed": bool(entry),
                    "score": 1.0 if entry else 0.0,
                    "reasons": [],
                    "valid": valid,
                    "invalid_reason": None if valid else "provider_error",
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost": 0.0,
                    "tool_calls": 1,
                    "repeated_actions": 0,
                    "agent_version": "test",
                    "grader_hash": seal["tasks"][task_id]["grader_hash"],
                    "task_hash": seal["tasks"][task_id]["task_hash"],
                    "prereg_hash": seal["prereg_hash"],
                }
            )
    return rows


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def numbered(rows: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    return list(enumerate(rows, start=1))


def uniform(outcome: bool | None, k: int) -> list[bool | None]:
    return [outcome] * k
