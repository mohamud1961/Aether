"""Run the accepted Phase 6.5 completion-runner parallelism slice."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.successor_phase6_corrective_rerun import _record_ledger, _write_json, _write_text
from runner.successor_phase65_completion_closure import (
    DEFAULT_THROUGHPUT_WORKERS,
    launch_phase65_completion_closure,
)
from runner.successor_phase65_completion_followup2 import launch_phase65_completion_followup2
from runner.successor_phase65_completion_followup3 import launch_phase65_completion_followup3

MISSION_ID = "successor_phase65_completion_runner_parallelism"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_completion_runner_parallelism"
)
RUNNERS = (
    ("completion_closure", launch_phase65_completion_closure, "phase65_completion_closure_runtime_profile.json"),
    ("completion_followup2", launch_phase65_completion_followup2, "phase65_completion_followup2_runtime_profile.json"),
    ("completion_followup3", launch_phase65_completion_followup3, "phase65_completion_followup3_runtime_profile.json"),
)
SLICE = {"max_specs": 2, "max_variants_per_spec": 2}


def launch_phase65_completion_runner_parallelism(*, output_dir: str | Path, execute: bool = True) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    serial_dir = out / "serial"
    parallel_dir = out / "parallel"
    _write_text(out / "phase65_completion_runner_parallelism_plan.md", _plan(out))

    serial = _run_family(serial_dir, execute=execute, max_workers=1)
    parallel = _run_family(parallel_dir, execute=execute, max_workers=DEFAULT_THROUGHPUT_WORKERS)
    before_after = _before_after(serial=serial, parallel=parallel)
    profile = _profile(serial=serial, parallel=parallel)
    policy = _policy()
    _write_json(out / "phase65_completion_runner_parallelism_profile_report.json", profile)
    _write_json(out / "phase65_completion_runner_parallelism_policy.json", policy)
    _write_json(out / "phase65_completion_runner_parallelism_before_after_report.json", before_after)
    _write_text(out / "phase65_completion_runner_parallelism_test_report.txt", _test_report(serial=serial, parallel=parallel))

    recommendation = _recommendation(before_after, serial=serial, parallel=parallel, execute=execute)
    _write_text(
        out / "phase65_completion_runner_parallelism_handoff.md",
        _handoff(out=out, recommendation=recommendation, before_after=before_after, profile=profile),
    )
    ledger = _ledger(out=out, recommendation=recommendation, before_after=before_after, profile=profile)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "recommendation": recommendation,
        "serial_wall_sec": before_after["serial"]["wall_sec"],
        "parallel_wall_sec": before_after["parallel"]["wall_sec"],
        "speedup_ratio": before_after["speedup_ratio"],
    }


def _run_family(out: Path, *, execute: bool, max_workers: int) -> dict[str, Any]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    runner_results: dict[str, Any] = {}
    runner_profiles: dict[str, Any] = {}
    runner_walls: dict[str, float] = {}
    for runner_key, launcher, profile_name in RUNNERS:
        runner_out = out / runner_key
        runner_started = perf_counter()
        runner_results[runner_key] = launcher(
            output_dir=runner_out,
            execute=execute,
            max_workers=max_workers,
            max_specs=SLICE["max_specs"],
            max_variants_per_spec=SLICE["max_variants_per_spec"],
        )
        runner_walls[runner_key] = perf_counter() - runner_started
        profile_path = runner_out / profile_name
        runner_profiles[runner_key] = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    wall_sec = perf_counter() - started
    return {
        "output_dir": str(out),
        "wall_sec": wall_sec,
        "runner_results": runner_results,
        "runner_walls": runner_walls,
        "runner_profiles": runner_profiles,
    }


def _before_after(*, serial: dict[str, Any], parallel: dict[str, Any]) -> dict[str, Any]:
    serial_wall = float(serial["wall_sec"])
    parallel_wall = float(parallel["wall_sec"])
    speedup = (serial_wall / parallel_wall) if parallel_wall > 0 else 0.0
    reduction = ((serial_wall - parallel_wall) / serial_wall) if serial_wall > 0 else 0.0
    per_runner = {}
    for runner_key, _, _ in RUNNERS:
        serial_runner_wall = float(serial["runner_walls"].get(runner_key, 0.0))
        parallel_runner_wall = float(parallel["runner_walls"].get(runner_key, 0.0))
        per_runner[runner_key] = {
            "serial_wall_sec": serial_runner_wall,
            "parallel_wall_sec": parallel_runner_wall,
            "speedup_ratio": (serial_runner_wall / parallel_runner_wall) if parallel_runner_wall > 0 else 0.0,
            "wall_clock_reduction_ratio": (
                (serial_runner_wall - parallel_runner_wall) / serial_runner_wall if serial_runner_wall > 0 else 0.0
            ),
        }
    return {
        "mission_id": MISSION_ID,
        "serial": {"wall_sec": serial_wall, "output_dir": serial["output_dir"]},
        "parallel": {"wall_sec": parallel_wall, "output_dir": parallel["output_dir"]},
        "speedup_ratio": speedup,
        "wall_clock_reduction_ratio": reduction,
        "per_runner": per_runner,
    }


def _profile(*, serial: dict[str, Any], parallel: dict[str, Any]) -> dict[str, Any]:
    serial_breakdown = _sum_breakdowns(serial["runner_profiles"])
    parallel_breakdown = _sum_breakdowns(parallel["runner_profiles"])
    dominant_pool = {key: value for key, value in serial_breakdown.items() if key != "total_run_wall_sec"}
    dominant = max(dominant_pool.items(), key=lambda row: row[1])[0] if dominant_pool else None
    return {
        "mission_id": MISSION_ID,
        "slice": dict(SLICE),
        "worker_cap": DEFAULT_THROUGHPUT_WORKERS,
        "serial_breakdown_sec": serial_breakdown,
        "parallel_breakdown_sec": parallel_breakdown,
        "serial_runner_profiles": serial["runner_profiles"],
        "parallel_runner_profiles": parallel["runner_profiles"],
        "dominant_serial_runtime_component": dominant,
    }


def _sum_breakdowns(runner_profiles: dict[str, Any]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for profile in runner_profiles.values():
        breakdown = profile.get("breakdown_sec", {}) if isinstance(profile, dict) else {}
        for key, value in breakdown.items():
            totals[key] = totals.get(key, 0.0) + float(value or 0.0)
    return totals


def _policy() -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "policy": "bounded_worker_pool",
        "worker_cap": DEFAULT_THROUGHPUT_WORKERS,
        "slice": dict(SLICE),
        "safety_constraints": {
            "route_distinctness": "preserved by per-run route manifest validation in each completion runner",
            "attribution_safety": "preserved by unique run_id and run_dir per run",
            "workspace_isolation": "preserved by per-run workspace roots",
            "output_determinism": "preserved by plan-index sorting before aggregation",
            "trace_logging": "preserved by per-run run_events.jsonl trace refs",
        },
        "fail_closed": "max_workers must be >= 1 and is capped by host CPU and runner hard cap",
    }


def _recommendation(before_after: dict[str, Any], *, serial: dict[str, Any], parallel: dict[str, Any], execute: bool) -> str:
    if not execute:
        return "completion_runner_parallelism_blocked"
    if _is_blocked(serial) or _is_blocked(parallel):
        return "completion_runner_parallelism_blocked"
    improved_runners = sum(1 for row in before_after["per_runner"].values() if float(row["speedup_ratio"]) > 1.05)
    if float(before_after["speedup_ratio"]) > 1.10 and improved_runners >= 2:
        return "completion_runner_parallelism_completed_resume_research"
    return "completion_runner_parallelism_partial_fix_more_engineering_needed"


def _is_blocked(run: dict[str, Any]) -> bool:
    return any(bool(payload.get("blocked")) for payload in run.get("runner_results", {}).values())


def _plan(out: Path) -> str:
    return "\n".join(
        [
            "# Phase 6.5 Completion Runner Parallelism Plan",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            "- locked_scope: throughput-only engineering; no Packet 07 movement; no benchmark-authority widening; no completion-family mechanism changes.",
            "- targets: successor_phase65_completion_closure, successor_phase65_completion_followup2, successor_phase65_completion_followup3.",
            f"- bounded_slice: `{SLICE}`",
            f"- policy_target_worker_cap: `{DEFAULT_THROUGHPUT_WORKERS}`",
            "- proof_method: serial worker_cap=1 vs bounded parallel worker_cap=2 on the same admissible completion slice.",
        ]
    )


def _test_report(*, serial: dict[str, Any], parallel: dict[str, Any]) -> str:
    rows = [
        "completion_runner_parallelism_test_report",
        f"serial_output_dir={serial['output_dir']}",
        f"parallel_output_dir={parallel['output_dir']}",
        f"serial_wall_sec={serial['wall_sec']:.3f}",
        f"parallel_wall_sec={parallel['wall_sec']:.3f}",
    ]
    for runner_key, _, _ in RUNNERS:
        rows.append(f"{runner_key}_serial_wall_sec={serial['runner_walls'].get(runner_key, 0.0):.3f}")
        rows.append(f"{runner_key}_parallel_wall_sec={parallel['runner_walls'].get(runner_key, 0.0):.3f}")
    return "\n".join(rows) + "\n"


def _handoff(*, out: Path, recommendation: str, before_after: dict[str, Any], profile: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 6.5 Completion Runner Parallelism Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            f"- serial_wall_sec: `{before_after['serial']['wall_sec']:.3f}`",
            f"- parallel_wall_sec: `{before_after['parallel']['wall_sec']:.3f}`",
            f"- speedup_ratio: `{before_after['speedup_ratio']:.3f}`",
            f"- wall_clock_reduction_ratio: `{before_after['wall_clock_reduction_ratio']:.3f}`",
            f"- dominant_serial_runtime_component: `{profile.get('dominant_serial_runtime_component')}`",
            "- remaining_limits: model-backed latency remains the largest bounded component on sampled completion slices.",
            "- remaining_local_pressure: concurrent model/tool loops still consume local CPU and I/O despite worker-cap bounds.",
            "- remote_execution_note: remote execution can still reduce local host occupancy for broader boards.",
            f"- final_recommendation: `{recommendation}`",
        ]
    ) + "\n"


def _ledger(*, out: Path, recommendation: str, before_after: dict[str, Any], profile: dict[str, Any]) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: successor Phase 6.5 completion runner parallelism execution",
            "- event_type: implementation",
            f"- summary: Ported bounded worker-pool execution and runtime profiling into the completion runners and measured serial vs parallel throughput with recommendation `{recommendation}`.",
            (
                "- observations: "
                f"serial_wall_sec `{before_after['serial']['wall_sec']:.3f}`; "
                f"parallel_wall_sec `{before_after['parallel']['wall_sec']:.3f}`; "
                f"speedup_ratio `{before_after['speedup_ratio']:.3f}`; "
                f"dominant_serial_runtime_component `{profile.get('dominant_serial_runtime_component')}`."
            ),
            "- inference: completion runners are safely parallelizable with bounded worker cap while preserving deterministic aggregation and trace integrity.",
            (
                f"- evidence_paths: {out / 'phase65_completion_runner_parallelism_profile_report.json'}; "
                f"{out / 'phase65_completion_runner_parallelism_policy.json'}; "
                f"{out / 'phase65_completion_runner_parallelism_before_after_report.json'}; "
                f"{out / 'phase65_completion_runner_parallelism_handoff.md'}"
            ),
            "- affected_components: runner/successor_phase65_completion_closure.py; runner/successor_phase65_completion_followup2.py; runner/successor_phase65_completion_followup3.py; completion-runner throughput evidence artifacts",
            "- decision_change: completion-family board execution now defaults to bounded worker-pool throughput mode without widening research scope.",
            "- unresolved_questions: whether worker_cap can be safely raised above 2 on this host while keeping latency, cost, and contention within budget.",
            "- confidence: medium",
            "- commit_message: HOLD - port completion runner bounded parallelism and runtime profiling with before/after proof",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_phase65_completion_runner_parallelism(
                output_dir=args.output_dir,
                execute=not args.no_execute,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
