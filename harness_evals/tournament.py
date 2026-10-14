"""Round-robin sealed paired study. No retries; budget must cover the declared board."""

import json
from pathlib import Path

from .agents.base import get_agent
from .prereg import load_plan, verify
from .prereg_analysis import analyze, load_rows, render, validate_rows
from .task import load_task
from .trial_report import render_report
from .trials import (
    Arm,
    existing_run_id,
    new_run_id,
    read_rows,
    read_traces,
    run_trials,
    trace_path_for,
)


def run(plan_path, seal_path, out, max_rows, sandbox_kind="docker"):
    plan_path, out = Path(plan_path), Path(out)
    plan, _ = load_plan(plan_path)
    checked = verify(plan_path, Path(seal_path))
    if checked.changes:
        raise ValueError("seal drift: " + "; ".join(checked.changes))
    tasks = [load_task(plan_path.parent / p) for p in plan.tasks]
    if any(t.admission != "capability" for t in tasks):
        raise ValueError("smoke cannot enter capability study")
    expected = len(tasks) * len(plan.arms) * plan.k
    if max_rows < expected:
        raise ValueError(f"budget {max_rows} cannot cover {expected} rows")
    arms = []
    for name, config in plan.arms.items():
        opts = {k: v for k, v in config.items() if k not in {"name", "agent"}}
        arms.append(
            Arm(
                name,
                get_agent(config["agent"], **opts),
                json.dumps(config, sort_keys=True),
            )
        )
    run_id = existing_run_id(out) or new_run_id()
    for attempt in range(1, plan.k + 1):
        for task in tasks:
            for arm in arms:
                checked = verify(plan_path, Path(seal_path))
                if checked.changes:
                    raise ValueError("source changed during frozen run")
                run_trials(
                    [task],
                    [arm],
                    attempt,
                    sandbox_kind,
                    out,
                    run_id,
                    resume=out.exists(),
                    prereg_hash=checked.seal["prereg_hash"],
                )
    numbered, errors = load_rows(out)
    errors += validate_rows(checked.seal, numbered)
    if errors:
        raise ValueError("study contract: " + "; ".join(errors))
    result = analyze(checked.seal, numbered)
    report = render(result, checked.seal)
    out.with_suffix(".analysis.md").write_text(report)
    out.with_suffix(".report.md").write_text(
        render_report(read_rows(out), read_traces(trace_path_for(out)), out.name)
    )
    return report
