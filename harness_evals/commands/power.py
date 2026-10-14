"""power: trials needed per arm to detect a difference between two pass probabilities."""

from __future__ import annotations

import argparse
import sys

from harness_evals.stats import (
    power_two_proportions,
    sample_size_two_proportions,
    simulated_power_fisher,
)


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "power",
        help="trials per arm needed to detect a pass-rate difference",
        description=(
            "Two-sided two-proportion sample size (normal approximation), the power it gives at that size, "
            "and a simulated power check using Fisher's exact test."
        ),
    )
    parser.add_argument(
        "--p1",
        type=float,
        required=True,
        help="expected pass probability of arm 1, in [0, 1]",
    )
    parser.add_argument(
        "--p2",
        type=float,
        required=True,
        help="expected pass probability of arm 2, in [0, 1]",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="two-sided significance level (default 0.05)",
    )
    parser.add_argument(
        "--power", type=float, default=0.8, help="target power (default 0.8)"
    )
    parser.add_argument(
        "--sims",
        type=int,
        default=2000,
        help="simulated experiments for the check (default 2000)",
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="seed for the simulation (default 0)"
    )
    parser.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    try:
        n = sample_size_two_proportions(
            args.p1, args.p2, alpha=args.alpha, power=args.power
        )
        normal_power = power_two_proportions(n, args.p1, args.p2, alpha=args.alpha)
        simulated = simulated_power_fisher(
            args.p1, args.p2, n, alpha=args.alpha, sims=args.sims, seed=args.seed
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(
        f"target: detect p1={args.p1:.3f} vs p2={args.p2:.3f} at alpha={args.alpha}, power={args.power:.2f}"
    )
    print(f"trials per arm (normal approximation): {n}")
    print(f"normal-approximation power at {n} per arm: {normal_power:.3f}")
    print(
        f"simulated power at {n} per arm (Fisher exact, two-sided, {args.sims} runs, seed {args.seed}): "
        f"{simulated:.3f}"
    )
    return 0
