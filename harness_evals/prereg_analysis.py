"""Analyse trial rows against a sealed plan and return a mechanical verdict.

Rows are JSON objects, one per line. validate_rows refuses rows that do not match the seal: wrong
prereg_hash, task_hash or grader_hash, an arm or task the plan does not name, an attempt outside 1..k,
a repeated attempt, or a cell (arm, task) without exactly k rows. Invalid rows (valid is false) are
excluded from every rate and counted by invalid_reason.

Metrics: the primary metric is the pass rate over valid trials pooled across tasks. Its Wilson interval
comes from harness_evals.stats. The baseline-to-candidate difference has a percentile bootstrap interval
from harness_evals.stats with a fixed seed. That bootstrap is unpaired: each arm is resampled on its own.

Verdict, evaluated in this order:
  FALSIFIED     the falsifier expression holds, or a sentinel task's candidate rate is below its baseline rate
  SUPPORTED     the promotion bar holds and neither of the above applies
  INCONCLUSIVE  the promotion bar does not hold, or an arm or sentinel has no valid trials
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_evals.prereg import PlanError
from harness_evals.prereg_expr import ClauseResult, evaluate
from harness_evals.stats import bootstrap_rate_difference, summarize_rate

ROW_KEYS = (
    "arm",
    "task_id",
    "attempt",
    "passed",
    "valid",
    "prereg_hash",
    "task_hash",
    "grader_hash",
)
BOOTSTRAP_SEED = 0
BOOTSTRAP_ITERATIONS = 10_000
CONFIDENCE = 0.95
VERDICTS = ("SUPPORTED", "FALSIFIED", "INCONCLUSIVE")

Row = dict[str, Any]


@dataclass(frozen=True)
class ArmStats:
    name: str
    passes: int
    valid: int
    invalid: int
    rate: float | None
    low: float
    high: float
    invalid_reasons: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class SentinelRow:
    task_id: str
    baseline_rate: float | None
    candidate_rate: float | None
    regressed: bool | None


@dataclass(frozen=True)
class Analysis:
    verdict: str
    reasons: tuple[str, ...]
    baseline: ArmStats
    candidate: ArmStats
    diff: float | None
    diff_low: float | None
    diff_high: float | None
    sentinels: tuple[SentinelRow, ...]
    falsifier: tuple[ClauseResult, ...]
    promotion: tuple[ClauseResult, ...]


def load_rows(path: Path) -> tuple[list[tuple[int, Row]], list[str]]:
    """Read JSONL trial rows as (line number, row) pairs. Lines that are not JSON objects are problems."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise PlanError(f"cannot read trials {path}: {exc}") from exc
    rows: list[tuple[int, Row]] = []
    problems: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {lineno}: not JSON ({exc.msg})")
            continue
        if not isinstance(value, dict):
            problems.append(f"line {lineno}: not a JSON object")
            continue
        rows.append((lineno, value))
    return rows, problems


def validate_rows(seal: dict[str, Any], rows: Sequence[tuple[int, Row]]) -> list[str]:
    """Every reason the rows cannot be analysed against the seal. An empty list means they can."""
    settings = seal["settings"]
    k = settings["k"]
    arms = set(seal["arms"])
    tasks = seal["tasks"]
    problems: list[str] = []
    seen: set[tuple[Any, Any, Any]] = set()
    per_cell: Counter[tuple[Any, Any]] = Counter()
    for lineno, row in rows:
        missing = [key for key in ROW_KEYS if key not in row]
        if missing:
            problems.append(f"line {lineno}: missing fields {missing}")
            continue
        arm, task_id, attempt = row["arm"], row["task_id"], row["attempt"]
        if row["prereg_hash"] != seal["prereg_hash"]:
            problems.append(f"line {lineno}: prereg_hash is not the sealed hash")
        if not isinstance(arm, str) or not isinstance(task_id, str):
            problems.append(f"line {lineno}: arm and task_id must be strings")
            continue
        if arm not in arms:
            problems.append(f"line {lineno}: arm {arm!r} is not in the plan")
        if task_id not in tasks:
            problems.append(f"line {lineno}: task {task_id!r} is not in the plan")
        else:
            if row["task_hash"] != tasks[task_id]["task_hash"]:
                problems.append(
                    f"line {lineno}: task_hash for {task_id!r} differs from the seal"
                )
            if row["grader_hash"] != tasks[task_id]["grader_hash"]:
                problems.append(
                    f"line {lineno}: grader_hash for {task_id!r} differs from the seal"
                )
        if not _is_int(attempt) or not 1 <= attempt <= k:
            problems.append(f"line {lineno}: attempt {attempt!r} is outside 1..{k}")
            continue
        if not isinstance(row["passed"], bool) or not isinstance(row["valid"], bool):
            problems.append(f"line {lineno}: passed and valid must be booleans")
        if (arm, task_id, attempt) in seen:
            problems.append(
                f"line {lineno}: attempt {attempt!r} of {arm!r} on {task_id!r} repeats"
            )
        seen.add((arm, task_id, attempt))
        per_cell[(arm, task_id)] += 1
    for arm in sorted(arms):
        for task_id in sorted(tasks):
            count = per_cell[(arm, task_id)]
            if count != k:
                problems.append(
                    f"arm {arm!r} task {task_id!r}: {count} rows, expected exactly {k}"
                )
    return problems


def analyze(seal: dict[str, Any], rows: Sequence[tuple[int, Row]]) -> Analysis:
    """Compute the metrics and the verdict. Call validate_rows first; this assumes the rows are sound."""
    flat = [row for _, row in rows]
    settings = seal["settings"]
    baseline_name, candidate_name = settings["baseline"], settings["candidate"]
    baseline = _arm_stats(flat, baseline_name, None)
    candidate = _arm_stats(flat, candidate_name, None)
    sentinels = tuple(
        _sentinel(flat, baseline_name, candidate_name, task_id)
        for task_id in settings["sentinels"]
    )
    undecided = _undecided_reasons(baseline, candidate, sentinels)
    if undecided or baseline.rate is None or candidate.rate is None:
        return Analysis(
            "INCONCLUSIVE",
            undecided,
            baseline,
            candidate,
            None,
            None,
            None,
            sentinels,
            (),
            (),
        )
    diff_low, diff_high = bootstrap_rate_difference(
        _outcomes(flat, candidate_name, None),
        _outcomes(flat, baseline_name, None),
        iterations=BOOTSTRAP_ITERATIONS,
        confidence=CONFIDENCE,
        seed=BOOTSTRAP_SEED,
    )
    regressions = [row.task_id for row in sentinels if row.regressed]
    values = {
        "baseline_rate": baseline.rate,
        "candidate_rate": candidate.rate,
        "diff": candidate.rate - baseline.rate,
        "diff_ci_low": diff_low,
        "diff_ci_high": diff_high,
        "sentinel_regressions": float(len(regressions)),
    }
    falsifier_holds, falsifier = evaluate(settings["falsifier"], values)
    promotion_holds, promotion = evaluate(settings["promotion_bar"], values)
    if falsifier_holds:
        verdict, reasons = "FALSIFIED", (f"falsifier holds: {settings['falsifier']}",)
    elif regressions:
        verdict, reasons = (
            "FALSIFIED",
            (f"sentinel task(s) regressed: {', '.join(regressions)}",),
        )
    elif promotion_holds:
        verdict, reasons = (
            "SUPPORTED",
            (f"promotion bar met: {settings['promotion_bar']}",),
        )
    else:
        verdict, reasons = (
            "INCONCLUSIVE",
            (f"promotion bar not met: {settings['promotion_bar']}",),
        )
    return Analysis(
        verdict=verdict,
        reasons=reasons,
        baseline=baseline,
        candidate=candidate,
        diff=values["diff"],
        diff_low=diff_low,
        diff_high=diff_high,
        sentinels=sentinels,
        falsifier=falsifier,
        promotion=promotion,
    )


def render(analysis: Analysis, seal: dict[str, Any]) -> str:
    settings = seal["settings"]
    lines = [
        analysis.verdict,
        f"question: {seal['question']}",
        f"prereg_hash: {seal['prereg_hash']}",
        "",
        f"primary metric: {settings['primary_metric']} over valid trials, pooled across tasks",
        _arm_line("baseline", analysis.baseline),
        _arm_line("candidate", analysis.candidate),
        (
            f"difference (candidate - baseline): {_num(analysis.diff)}, "
            f"95% bootstrap interval [{_num(analysis.diff_low)}, {_num(analysis.diff_high)}] "
            f"(unpaired, seed {BOOTSTRAP_SEED})"
        ),
        "",
        f"falsifier: {settings['falsifier']}",
        *_clause_lines(analysis.falsifier),
        f"promotion bar: {settings['promotion_bar']}",
        *_clause_lines(analysis.promotion),
        "sentinels (must not regress):",
        *[_sentinel_line(row) for row in analysis.sentinels],
        "reasons:",
        *[f"  - {reason}" for reason in analysis.reasons],
    ]
    return "\n".join(lines)


def _valid_rows(rows: Sequence[Row], arm: str, task_id: str | None) -> list[Row]:
    return [
        row
        for row in rows
        if row["arm"] == arm
        and row["valid"]
        and (task_id is None or row["task_id"] == task_id)
    ]


def _arm_stats(rows: Sequence[Row], arm: str, task_id: str | None) -> ArmStats:
    selected = [
        row
        for row in rows
        if row["arm"] == arm and (task_id is None or row["task_id"] == task_id)
    ]
    valid = _valid_rows(rows, arm, task_id)
    invalid = [row for row in selected if not row["valid"]]
    passes = sum(1 for row in valid if row["passed"])
    summary = summarize_rate(passes, len(valid))
    reasons = Counter(
        str(row.get("invalid_reason") or "unspecified") for row in invalid
    )
    return ArmStats(
        name=arm,
        passes=passes,
        valid=len(valid),
        invalid=len(invalid),
        rate=summary.rate,
        low=summary.low,
        high=summary.high,
        invalid_reasons=tuple(sorted(reasons.items())),
    )


def _outcomes(rows: Sequence[Row], arm: str, task_id: str | None) -> list[bool]:
    return [bool(row["passed"]) for row in _valid_rows(rows, arm, task_id)]


def _sentinel(
    rows: Sequence[Row], baseline: str, candidate: str, task_id: str
) -> SentinelRow:
    base = _arm_stats(rows, baseline, task_id)
    cand = _arm_stats(rows, candidate, task_id)
    if base.rate is None or cand.rate is None:
        return SentinelRow(task_id, base.rate, cand.rate, None)
    return SentinelRow(task_id, base.rate, cand.rate, cand.rate < base.rate)


def _undecided_reasons(
    baseline: ArmStats, candidate: ArmStats, sentinels: Sequence[SentinelRow]
) -> tuple[str, ...]:
    reasons: list[str] = []
    for stats in (baseline, candidate):
        if stats.valid == 0:
            reasons.append(f"arm {stats.name!r} has no valid trials")
    for row in sentinels:
        if row.regressed is None:
            reasons.append(f"sentinel {row.task_id!r} has no valid trials in one arm")
    return tuple(reasons)


def _clause_lines(clauses: Sequence[ClauseResult]) -> list[str]:
    if not clauses:
        return ["  not evaluated"]
    return [
        f"  {clause.text}: {clause.lhs_value:.4f} vs {clause.rhs_value:.4f} -> {'holds' if clause.truth else 'does not hold'}"
        for clause in clauses
    ]


def _arm_line(label: str, stats: ArmStats) -> str:
    reasons = (
        ", ".join(f"{name}={count}" for name, count in stats.invalid_reasons) or "none"
    )
    return (
        f"  {label} {stats.name}: {stats.passes}/{stats.valid} = {_num(stats.rate)} "
        f"(Wilson 95% [{stats.low:.4f}, {stats.high:.4f}]); invalid rows excluded: {stats.invalid} ({reasons})"
    )


def _sentinel_line(row: SentinelRow) -> str:
    if row.regressed is None:
        status = "undefined"
    else:
        status = "REGRESSED" if row.regressed else "ok"
    return f"  {row.task_id}: baseline {_num(row.baseline_rate)} candidate {_num(row.candidate_rate)} -> {status}"


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
