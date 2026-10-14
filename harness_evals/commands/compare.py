"""compare: pass rates, intervals and paired McNemar test for two arms of trial rows.

Input is trial JSONL (one trial per line, the TrialRow schema). Either give one file that holds two
arms, or two files that each hold one arm. Only rows with valid == true enter the rates and tests;
the invalid rows are counted and reported, never dropped silently.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from harness_evals.stats import (
    RateSummary,
    bootstrap_rate_difference,
    fisher_exact_two_sided,
    mcnemar_exact_p,
    pass_all_k,
    pass_at_k,
    summarize_rate,
)


class TrialFileError(ValueError):
    """Raised for unreadable or malformed trial input, and for selections that cannot be compared."""


@dataclass(frozen=True)
class Trial:
    arm: str
    task_id: str
    attempt: int
    valid: bool
    passed: bool


@dataclass(frozen=True)
class Side:
    label: str
    trials: tuple[Trial, ...]

    def valid_trials(self) -> list[Trial]:
        return [trial for trial in self.trials if trial.valid]


@dataclass(frozen=True)
class ArmSummary:
    label: str
    rows: int
    valid: int
    rate: RateSummary
    pass_at_k: float | None
    pass_all_k: float | None
    tasks_scored: int
    tasks_skipped: int


@dataclass(frozen=True)
class PairedSummary:
    pairs: int
    both_pass: int
    both_fail: int
    only_a: int
    only_b: int
    mcnemar_p: float


@dataclass(frozen=True)
class Comparison:
    a: ArmSummary
    b: ArmSummary
    k: int
    alpha: float
    iterations: int
    seed: int
    difference: float | None
    difference_ci: tuple[float, float] | None
    fisher_p: float | None
    paired: PairedSummary | None
    verdict: str


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "compare",
        help="compare the pass rates of two arms with CIs and a paired McNemar test",
        description=(
            "Give one trial JSONL file that holds two arms (or name them with --arm-a and --arm-b), "
            "or two files that each hold one arm. Pairs are matched on task_id and attempt."
        ),
    )
    parser.add_argument(
        "trials",
        nargs="+",
        type=Path,
        help="one file with two arms, or two single-arm files",
    )
    parser.add_argument("--arm-a", help="arm label to use as side A")
    parser.add_argument("--arm-b", help="arm label to use as side B")
    parser.add_argument(
        "--k",
        type=int,
        default=1,
        help="draw size for pass@k and pass^k per task (default 1)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="significance level for the verdict (default 0.05)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10_000,
        help="bootstrap resamples (default 10000)",
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="bootstrap seed (default 0)"
    )
    parser.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    try:
        side_a, side_b = load_sides(args.trials, args.arm_a, args.arm_b)
        comparison = compare_sides(
            side_a,
            side_b,
            k=args.k,
            alpha=args.alpha,
            iterations=args.iterations,
            seed=args.seed,
        )
    except (TrialFileError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(render_comparison(comparison))
    return 0


def read_trials(path: Path) -> list[Trial]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise TrialFileError(
            f"cannot read {path}: {error.strerror or error}"
        ) from error
    trials: list[Trial] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise TrialFileError(
                f"{path}:{line_number}: invalid JSON ({error.msg})"
            ) from error
        if not isinstance(row, dict):
            raise TrialFileError(
                f"{path}:{line_number}: trial row must be a JSON object"
            )
        trials.append(_trial_from_row(row, path, line_number))
    if not trials:
        raise TrialFileError(f"{path} has no trial rows")
    return trials


def _trial_from_row(row: dict[str, object], path: Path, line_number: int) -> Trial:
    where = f"{path}:{line_number}"
    for key in ("arm", "task_id", "attempt", "valid"):
        if key not in row:
            raise TrialFileError(f"{where}: missing field {key!r}")
    arm, task_id, attempt, valid = (
        row["arm"],
        row["task_id"],
        row["attempt"],
        row["valid"],
    )
    if not isinstance(arm, str) or not isinstance(task_id, str):
        raise TrialFileError(f"{where}: arm and task_id must be strings")
    if not isinstance(attempt, int) or isinstance(attempt, bool):
        raise TrialFileError(f"{where}: attempt must be an integer")
    if not isinstance(valid, bool):
        raise TrialFileError(f"{where}: valid must be true or false")
    passed = row.get("passed")
    if valid and not isinstance(passed, bool):
        raise TrialFileError(
            f"{where}: a valid trial needs passed set to true or false"
        )
    return Trial(
        arm=arm, task_id=task_id, attempt=attempt, valid=valid, passed=passed is True
    )


def load_sides(
    paths: Sequence[Path], arm_a: str | None, arm_b: str | None
) -> tuple[Side, Side]:
    if len(paths) == 1:
        return _sides_from_one_file(paths[0], arm_a, arm_b)
    if len(paths) == 2:
        return _sides_from_two_files(paths[0], paths[1], arm_a, arm_b)
    raise TrialFileError(
        "give one trial file with two arms, or two single-arm trial files"
    )


def _sides_from_one_file(
    path: Path, arm_a: str | None, arm_b: str | None
) -> tuple[Side, Side]:
    trials = read_trials(path)
    arms = sorted({trial.arm for trial in trials})
    if arm_a is None and arm_b is None:
        if len(arms) != 2:
            raise TrialFileError(
                f"{path} holds arms {arms}; pass --arm-a and --arm-b to choose two"
            )
        arm_a, arm_b = arms
    if arm_a is None or arm_b is None:
        raise TrialFileError("give both --arm-a and --arm-b, or neither")
    if arm_a == arm_b:
        raise TrialFileError("--arm-a and --arm-b must name different arms")
    side_a = _select_arm(trials, arm_a, path)
    side_b = _select_arm(trials, arm_b, path)
    return side_a, side_b


def _sides_from_two_files(
    first: Path, second: Path, arm_a: str | None, arm_b: str | None
) -> tuple[Side, Side]:
    side_a = _single_arm_side(first, arm_a)
    side_b = _single_arm_side(second, arm_b)
    if side_a.label == side_b.label:
        side_a = Side(label=f"{side_a.label} ({first.name})", trials=side_a.trials)
        side_b = Side(label=f"{side_b.label} ({second.name})", trials=side_b.trials)
    return side_a, side_b


def _single_arm_side(path: Path, arm: str | None) -> Side:
    trials = read_trials(path)
    arms = sorted({trial.arm for trial in trials})
    if arm is None:
        if len(arms) != 1:
            raise TrialFileError(
                f"{path} holds arms {arms}; pass --arm-a or --arm-b to choose one"
            )
        arm = arms[0]
    return _select_arm(trials, arm, path)


def _select_arm(trials: Sequence[Trial], arm: str, path: Path) -> Side:
    selected = tuple(trial for trial in trials if trial.arm == arm)
    if not selected:
        raise TrialFileError(f"arm {arm!r} not found in {path}")
    seen: set[tuple[str, int]] = set()
    for trial in selected:
        key = (trial.task_id, trial.attempt)
        if key in seen:
            raise TrialFileError(
                f"duplicate trial for arm {arm!r}: task {trial.task_id!r} attempt {trial.attempt}"
            )
        seen.add(key)
    return Side(label=arm, trials=selected)


def compare_sides(
    side_a: Side,
    side_b: Side,
    *,
    k: int = 1,
    alpha: float = 0.05,
    iterations: int = 10_000,
    seed: int = 0,
) -> Comparison:
    if k < 1:
        raise TrialFileError("--k must be at least 1")
    if not 0 < alpha < 1:
        raise TrialFileError("--alpha must be strictly between 0 and 1")
    arm_a = _summarize_arm(side_a, k)
    arm_b = _summarize_arm(side_b, k)
    difference: float | None = None
    difference_ci: tuple[float, float] | None = None
    fisher_p: float | None = None
    if arm_a.rate.rate is not None and arm_b.rate.rate is not None:
        difference = arm_a.rate.rate - arm_b.rate.rate
        difference_ci = bootstrap_rate_difference(
            [trial.passed for trial in side_a.valid_trials()],
            [trial.passed for trial in side_b.valid_trials()],
            iterations=iterations,
            seed=seed,
        )
        fisher_p = fisher_exact_two_sided(
            arm_a.rate.successes,
            arm_a.rate.trials - arm_a.rate.successes,
            arm_b.rate.successes,
            arm_b.rate.trials - arm_b.rate.successes,
        )
    paired = _pair(side_a, side_b)
    return Comparison(
        a=arm_a,
        b=arm_b,
        k=k,
        alpha=alpha,
        iterations=iterations,
        seed=seed,
        difference=difference,
        difference_ci=difference_ci,
        fisher_p=fisher_p,
        paired=paired,
        verdict=_verdict(arm_a, arm_b, paired, alpha),
    )


def _summarize_arm(side: Side, k: int) -> ArmSummary:
    valid = side.valid_trials()
    passes = sum(trial.passed for trial in valid)
    per_task: dict[str, list[bool]] = {}
    for trial in valid:
        per_task.setdefault(trial.task_id, []).append(trial.passed)
    scored = [
        (len(outcomes), sum(outcomes))
        for outcomes in per_task.values()
        if len(outcomes) >= k
    ]
    estimates = [pass_at_k(n, c, k) for n, c in scored]
    all_estimates = [pass_all_k(n, c, k) for n, c in scored]
    return ArmSummary(
        label=side.label,
        rows=len(side.trials),
        valid=len(valid),
        rate=summarize_rate(passes, len(valid)),
        pass_at_k=_mean(estimates),
        pass_all_k=_mean(all_estimates),
        tasks_scored=len(scored),
        tasks_skipped=len(per_task) - len(scored),
    )


def _pair(side_a: Side, side_b: Side) -> PairedSummary | None:
    by_key_b = {
        (trial.task_id, trial.attempt): trial.passed for trial in side_b.valid_trials()
    }
    pairs = [
        (trial.passed, by_key_b[(trial.task_id, trial.attempt)])
        for trial in side_a.valid_trials()
        if (trial.task_id, trial.attempt) in by_key_b
    ]
    if not pairs:
        return None
    only_a = sum(1 for a_pass, b_pass in pairs if a_pass and not b_pass)
    only_b = sum(1 for a_pass, b_pass in pairs if b_pass and not a_pass)
    return PairedSummary(
        pairs=len(pairs),
        both_pass=sum(1 for a_pass, b_pass in pairs if a_pass and b_pass),
        both_fail=sum(1 for a_pass, b_pass in pairs if not a_pass and not b_pass),
        only_a=only_a,
        only_b=only_b,
        mcnemar_p=mcnemar_exact_p(only_a, only_b),
    )


def _verdict(
    arm_a: ArmSummary, arm_b: ArmSummary, paired: PairedSummary | None, alpha: float
) -> str:
    if arm_a.valid == 0 or arm_b.valid == 0:
        return "INCONCLUSIVE: one arm has no valid trials."
    if paired is None:
        return (
            "INCONCLUSIVE: no task and attempt has valid trials in both arms, "
            "so the paired McNemar test cannot run."
        )
    p_text = _format_p(paired.mcnemar_p)
    if paired.mcnemar_p < alpha:
        leader = arm_a.label if paired.only_a > paired.only_b else arm_b.label
        return f"DIFFERENCE: {leader} passes more often (paired exact McNemar p={p_text}, alpha={alpha})."
    return (
        f"NO DETECTABLE DIFFERENCE: paired exact McNemar p={p_text} is not below alpha={alpha}. "
        "This does not show that the arms are equal."
    )


def render_comparison(comparison: Comparison) -> str:
    lines: list[str] = []
    for arm in (comparison.a, comparison.b):
        lines.extend(_render_arm(arm, comparison.k))
    if comparison.difference is not None and comparison.difference_ci is not None:
        low, high = comparison.difference_ci
        lines.append(
            f"rate difference (A - B): {comparison.difference:+.3f} "
            f"(95% bootstrap CI {low:+.3f} to {high:+.3f}; {comparison.iterations} resamples, seed {comparison.seed})"
        )
    if comparison.fisher_p is not None:
        lines.append(
            f"unpaired Fisher exact, two-sided p = {_format_p(comparison.fisher_p)}"
        )
    if comparison.paired is None:
        lines.append("paired trials (same task and attempt, valid in both arms): 0")
    else:
        paired = comparison.paired
        lines.append(
            f"paired trials (same task and attempt, valid in both arms): {paired.pairs}"
        )
        lines.append(
            f"  both pass {paired.both_pass}, both fail {paired.both_fail}, "
            f"A only {paired.only_a}, B only {paired.only_b}"
        )
        lines.append(
            f"paired exact McNemar, two-sided p = {_format_p(paired.mcnemar_p)}"
        )
    lines.append("")
    lines.append(f"verdict: {comparison.verdict}")
    return "\n".join(lines)


def _render_arm(arm: ArmSummary, k: int) -> list[str]:
    excluded = arm.rows - arm.valid
    lines = [
        f"arm {arm.label}",
        f"  rows {arm.rows}, valid {arm.valid}, excluded {excluded} (invalid or not valid)",
    ]
    if arm.rate.rate is None:
        lines.append("  pass rate: n/a (no valid trials)")
    else:
        lines.append(
            f"  pass rate: {arm.rate.rate:.3f} ({arm.rate.successes}/{arm.rate.trials}), "
            f"95% Wilson CI {arm.rate.low:.3f} to {arm.rate.high:.3f}"
        )
    if arm.pass_at_k is None or arm.pass_all_k is None:
        lines.append(
            f"  pass@{k} / pass^{k}: n/a (no task has {k} valid attempt{'' if k == 1 else 's'})"
        )
    else:
        lines.append(
            f"  pass@{k} {arm.pass_at_k:.3f}, pass^{k} {arm.pass_all_k:.3f} "
            f"(mean over {arm.tasks_scored} tasks; {arm.tasks_skipped} task{'' if arm.tasks_skipped == 1 else 's'} skipped, "
            f"each needs {k} valid attempt{'' if k == 1 else 's'})"
        )
    return lines


def _format_p(p: float) -> str:
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


__all__ = [
    "Comparison",
    "Side",
    "Trial",
    "TrialFileError",
    "compare_sides",
    "load_sides",
    "render_comparison",
]
