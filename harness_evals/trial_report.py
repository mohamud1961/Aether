"""Scoreboard markdown from trial rows.

Rates use valid trials only. Invalid trials are excluded from every rate and counted by reason.
Each rate carries a Wilson 95% interval. Overall rates pool trials across tasks, which treats
trials as independent; per-task rows are the unit to read first. pass@k and pass^k use the
unbiased estimators in harness_evals.stats, with k equal to the largest attempt number in the
file; they are shown only where a task has at least k valid attempts for an arm.

Trajectory figures use valid trials only. Idle waits come from trace sidecars, and the report
states how many valid trials had one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from harness_evals.stats import pass_all_k, pass_at_k, summarize_rate
from harness_evals.trajectory import Distribution, TrialMeasure, idle_waits, summarize
from harness_evals.trials import TrialKey, TrialRow, TrialTrace

_NA = "n/a"


@dataclass(frozen=True)
class _Cell:
    valid: int
    passed: int


def render_report(
    rows: Sequence[TrialRow], traces: Mapping[TrialKey, TrialTrace], source: str
) -> str:
    if not rows:
        return f"# Scoreboard: {source}\n\nNo trial rows.\n"
    arms = _unique(row.arm for row in rows)
    tasks = _unique(row.task_id for row in rows)
    k = max(row.attempt for row in rows)
    valid_rows = [row for row in rows if row.valid]
    lines = [
        f"# Scoreboard: {source}",
        "",
        f"- Run ids: {', '.join(sorted({row.run_id for row in rows}))}",
        f"- Trials: {len(rows)} ({len(valid_rows)} valid, {len(rows) - len(valid_rows)} invalid)",
        f"- Arms: {', '.join(arms)}; tasks: {len(tasks)}; attempts per task: up to {k}",
        "",
        "## Overall by arm",
        "",
        "| arm | valid trials | passed | pass rate | 95% CI | invalid |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in arms:
        cell = _cell(valid_rows, arm)
        invalid = sum(1 for row in rows if row.arm == arm and not row.valid)
        lines.append(
            f"| {arm} | {cell.valid} | {cell.passed} | {_rate(cell)} | {_interval(cell)} | {invalid} |"
        )
    lines += [
        "",
        "## Per task",
        "",
        f"| task | arm | valid | passed | pass rate | 95% CI | pass@{k} | pass^{k} |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for task_id in tasks:
        for arm in arms:
            lines.append(_task_line(rows, valid_rows, arm, task_id, k))
    lines += ["", "## Invalid trials by reason", ""]
    lines += _invalid_section(rows, arms)
    lines += ["", "## Trajectory (valid trials)", ""]
    lines += [
        "",
        "Cost caution: CLI-agent usage is unavailable; unpriced model runs record cost_known=false in their traces. Zero is not proof that a provider run was free.",
        "",
    ]
    lines += _trajectory_section(valid_rows, traces, arms)
    lines.append("")
    return "\n".join(lines)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _cell(rows: Sequence[TrialRow], arm: str, task_id: str | None = None) -> _Cell:
    selected = [
        row
        for row in rows
        if row.arm == arm and (task_id is None or row.task_id == task_id)
    ]
    return _Cell(valid=len(selected), passed=sum(1 for row in selected if row.passed))


def _rate(cell: _Cell) -> str:
    summary = summarize_rate(cell.passed, cell.valid)
    return _NA if summary.rate is None else f"{summary.rate:.1%}"


def _interval(cell: _Cell) -> str:
    if cell.valid == 0:
        return _NA
    summary = summarize_rate(cell.passed, cell.valid)
    return f"[{summary.low:.1%}, {summary.high:.1%}]"


def _task_line(
    rows: Sequence[TrialRow],
    valid_rows: Sequence[TrialRow],
    arm: str,
    task_id: str,
    k: int,
) -> str:
    if not any(row.arm == arm and row.task_id == task_id for row in rows):
        return f"| {task_id} | {arm} | {_NA} | {_NA} | {_NA} | {_NA} | {_NA} | {_NA} |"
    cell = _cell(valid_rows, arm, task_id)
    at_k = all_k = _NA
    if cell.valid >= k:
        at_k = f"{pass_at_k(cell.valid, cell.passed, k):.3f}"
        all_k = f"{pass_all_k(cell.valid, cell.passed, k):.3f}"
    return (
        f"| {task_id} | {arm} | {cell.valid} | {cell.passed} | {_rate(cell)} | {_interval(cell)} "
        f"| {at_k} | {all_k} |"
    )


def _invalid_section(rows: Sequence[TrialRow], arms: Sequence[str]) -> list[str]:
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        if not row.valid:
            reason = row.invalid_reason or "unknown"
            counts[(row.arm, reason)] = counts.get((row.arm, reason), 0) + 1
    if not counts:
        return ["None."]
    lines = ["| arm | reason | count |", "|---|---|---:|"]
    for (arm, reason), count in sorted(
        counts.items(), key=lambda item: (arms.index(item[0][0]), item[0][1])
    ):
        lines.append(f"| {arm} | {reason} | {count} |")
    return lines


def _trajectory_section(
    valid_rows: Sequence[TrialRow],
    traces: Mapping[TrialKey, TrialTrace],
    arms: Sequence[str],
) -> list[str]:
    table = [
        "| arm | metric | total | mean | median | min | max |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    coverage: list[str] = []
    for arm in arms:
        selected = [row for row in valid_rows if row.arm == arm]
        if not selected:
            continue
        measures = [_measure(row, traces.get(row.key)) for row in selected]
        with_trace = sum(1 for row in selected if row.key in traces)
        coverage.append(
            f"- {arm}: {with_trace}/{len(selected)} valid trials have a trace file"
        )
        for name, dist in summarize(measures).metrics():
            table.append(_metric_line(arm, name, dist))
    if len(table) == 2:
        return ["No valid trials."]
    return table + [""] + coverage


def _measure(row: TrialRow, trace: TrialTrace | None) -> TrialMeasure:
    waits, waited_s = idle_waits(trace.actions) if trace is not None else (0, 0.0)
    return TrialMeasure(
        tokens_in=row.tokens_in,
        tokens_out=row.tokens_out,
        cost=row.cost,
        wall_s=row.wall_s,
        tool_calls=row.tool_calls,
        repeated_actions=row.repeated_actions,
        idle_waits=waits,
        idle_wait_s=waited_s,
    )


def _metric_line(arm: str, name: str, dist: Distribution) -> str:
    if dist.count == 0:
        return f"| {arm} | {name} | {_NA} | {_NA} | {_NA} | {_NA} | {_NA} |"
    return (
        f"| {arm} | {name} | {dist.total:g} | {_num(dist.mean)} | {_num(dist.median)} "
        f"| {_num(dist.minimum)} | {_num(dist.maximum)} |"
    )


def _num(value: float | None) -> str:
    return _NA if value is None else f"{value:.4g}"
