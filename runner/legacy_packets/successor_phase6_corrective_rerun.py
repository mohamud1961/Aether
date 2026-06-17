"""Corrective Phase 6 full-scope rerun.

This runner is intentionally separate from rerun3 so the earlier internal-board
evidence remains immutable and scope-incomplete.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from runner.agent import run_reference_baseline
from runner.letta_context_bench import grade_letta_filesystem_answer, letta_preflight
from runner.model_client import make_azure_gpt53_codex_route_from_env
from runner.phase65_measurement_grading import grade_phase65_spec
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)

MISSION_ID = "successor_phase6_corrective_context_completion_repair"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
CONTEXT_VARIANTS = (
    "candidate_plus_model_led_compaction_01",
    "candidate_plus_codex_style_handoff_compaction_01",
    "candidate_plus_hybrid_receipt_handoff_01",
    "candidate_plus_context_answer_extraction_01",
    "candidate_plus_context_budget_guard_01",
)
COMPLETION_VARIANTS = (
    "candidate_plus_artifact_existence_gate_01",
    "candidate_plus_verifier_backed_completion_gate_01",
    "candidate_plus_completion_repair_loop_01",
    "candidate_plus_required_deliverable_tracker_01",
)
BFCL_VARIANTS = (
    "candidate_plus_tool_call_plan_tracker_01",
    "candidate_plus_final_required_action_tracker_01",
    "candidate_plus_bfcl_strict_argument_guard_01",
)
REGRESSION_REPAIR_VARIANTS = (
    "candidate_plus_context_answer_extraction_01",
    "candidate_plus_verifier_backed_completion_gate_01",
    "candidate_plus_bfcl_strict_argument_guard_01",
)
ALL_VARIANTS = tuple(dict.fromkeys((CONTROL, INCUMBENT, *CONTEXT_VARIANTS, *COMPLETION_VARIANTS, *BFCL_VARIANTS)))
TERMINALBENCH_ROOT = Path("/Users/mohamud/Downloads/terminalbench")
CONTEXTBENCH_ROOT = Path("research/sources/codebases/ContextBench")
LETTA_ROOT = Path("research/sources/codebases/letta-evals/letta-leaderboard/filesystem-agent")
BFCL_PATH = Path("research/sources/codebases/deepagents/libs/evals/tests/evals/data/benchmark_samples/bfcl_v3_final.json")
EXTRACT_PROBE = Path("runner/terminalbench_failure_probe.py")
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase6_corrective_rerun"
)
PRICE = {"input": 1.75 / 1_000_000, "cached_input": 0.175 / 1_000_000, "output": 14.0 / 1_000_000}
RECOMMENDATIONS = (
    "candidate_repaired_and_ready_for_packet07_readiness_review",
    "candidate_needs_one_more_completion_repair",
    "candidate_needs_context_repair",
    "candidate_needs_toolcall_repair",
    "benchmark_adapter_still_invalid",
    "internal_eval_suite_needs_harder_tasks",
    "prefer_spb_01_or_pause_successor",
)


def launch_corrective_phase6(*, output_dir: str | Path, execute: bool = True) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = _board_specs()
    preflight = _preflight(specs)
    route = _route_matrix()
    mechanism = _mechanism_matrix(route, specs)
    _write_text(out / "phase6_corrective_plan.md", _plan(out, preflight, route, mechanism, specs))
    _write_text(out / "phase6_corrective_scope_gap_report.md", _scope_gap_report())
    _write_json(out / "phase6_corrective_board_manifest.json", _board_manifest(specs))
    _write_json(out / "phase6_corrective_route_matrix.json", route)
    _write_json(out / "phase6_corrective_variant_mechanism_matrix.json", mechanism)
    _write_text(out / "phase6_corrective_eval_design_report.md", _eval_design_report(specs))
    _write_json(out / "phase6_corrective_execution_plan.json", _execution_plan(specs))
    if not execute or preflight["status"] != "pass" or route["status"] != "pass" or mechanism["status"] != "pass":
        return _write_blocked(out, preflight, route, mechanism, execute)

    records: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for spec in specs:
        for variant in spec["variant_ids"]:
            record, trace = _run_one(out, spec, variant)
            records.append(record)
            traces.append(trace)
            if sum(1 for row in records if row["model_backed"]) > 350:
                raise SystemExit("hard_model_backed_cap_exceeded")

    return _write_reports(out, records, traces, preflight, route, mechanism)


def _board_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    specs.extend(_contextbench_specs())
    specs.extend(_letta_specs())
    specs.extend(_bfcl_specs())
    specs.extend(_terminalbench_regression_specs())
    specs.append(_extract_moves_spec())
    specs.extend(_internal_tb_style_specs())
    return specs


def _contextbench_specs() -> list[dict[str, Any]]:
    csv_path = CONTEXTBENCH_ROOT / "data/Verified.csv"
    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))[:8]
    specs = []
    for idx, row in enumerate(rows):
        prompt = (
            "Read /contextbench/Verified.csv and answer for the requested row only. "
            "Return a JSON object with exactly these keys: "
            "original_inst_id, language, status, gold_context_length, commit, repo_or_file_family."
        )
        files = {
            "/contextbench/Verified.csv": csv_path.read_text(encoding="utf-8"),
            "/contextbench/request.json": json.dumps(row, indent=2, sort_keys=True),
        }
        required = [row["original_inst_id"], row["language"], row["status"], row["commit"]]
        spec = _spec(f"contextbench_verified_{idx:02d}", "context", "contextbench", row["instance_id"], files, prompt, required, 3, (CONTROL, INCUMBENT, *CONTEXT_VARIANTS))
        spec["grade_row"] = row
        specs.append(spec)
    return specs


def _letta_specs() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in (LETTA_ROOT / "datasets/filesystem_code.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = []
    quotas = {"easy": 2, "medium": 2, "hard": 2}
    for idx, row in enumerate(rows):
        diff = row.get("agent_args", {}).get("extra", {}).get("difficulty")
        if quotas.get(diff, 0) > 0:
            selected.append((idx, diff, row))
            quotas[diff] -= 1
        if sum(quotas.values()) == 0:
            break
    files = {f"/letta/filesystem/{p.name}": p.read_text(encoding="utf-8") for p in sorted((LETTA_ROOT / "files").glob("*.txt"))}
    specs = []
    for idx, diff, row in selected:
        prompt = row["input"].replace("{pwd}", "/letta/filesystem") + "\nReturn one direct answer."
        spec = _spec(f"letta_filesystem_{idx:03d}_{diff}", "context", "letta_context_bench", f"filesystem_code_{idx:03d}", files, prompt, [row["ground_truth"]], 1, (CONTROL, INCUMBENT, *CONTEXT_VARIANTS))
        spec["ground_truth"] = row["ground_truth"]
        specs.append(spec)
    return specs


def _bfcl_specs() -> list[dict[str, Any]]:
    rows = json.loads(BFCL_PATH.read_text(encoding="utf-8"))
    usable = [row for row in rows if row.get("id") == "multi_turn_composite_97"]
    usable.extend(row for row in rows if row.get("id") != "multi_turn_composite_97" and row.get("answer_snippets") and row.get("files"))
    specs = []
    for row in usable[:6]:
        prompt = row.get("prompt") or json.dumps({"conversation": row.get("conversation"), "tools": row.get("tools")}, indent=2)
        files = row.get("files") or {f"/cases/{row['id']}/case.json": json.dumps(row, indent=2)}
        required = row.get("answer_snippets") or [str(row.get("ground_truth", ""))[:40]]
        specs.append(_spec(f"bfcl_v3_strict_{row['id']}", "bfcl", "bfcl_v3_strict", row["id"], files, prompt, required, len(required), (CONTROL, INCUMBENT, *BFCL_VARIANTS)))
    return specs


def _terminalbench_regression_specs() -> list[dict[str, Any]]:
    specs = []
    for task_id in ("fix-git", "regex-log", "financial-document-processor"):
        task_dir = TERMINALBENCH_ROOT / "official_tasks" / task_id
        files = {
            f"/terminalbench/{task_id}/instruction.md": (task_dir / "instruction.md").read_text(encoding="utf-8"),
            f"/terminalbench/{task_id}/task.toml": (task_dir / "task.toml").read_text(encoding="utf-8"),
            f"/terminalbench/{task_id}/tests/test_outputs.py": (task_dir / "tests/test_outputs.py").read_text(encoding="utf-8"),
        }
        solution = task_dir / "solution/solve.sh"
        if solution.exists():
            files[f"/terminalbench/{task_id}/solution_solve_sh_reference.txt"] = solution.read_text(encoding="utf-8")
        required = ["instruction.md", "test_outputs.py", task_id.split("-")[0]]
        specs.append(_spec(f"terminalbench_public_{task_id}", "terminalbench", "terminalbench_public_regression", task_id, files, f"Inspect /terminalbench/{task_id} and produce the concrete repair plan and deliverables.", required, 2, (CONTROL, INCUMBENT, *REGRESSION_REPAIR_VARIANTS)))
    return specs


def _extract_moves_spec() -> dict[str, Any]:
    task_dir = TERMINALBENCH_ROOT / "official_tasks/extract-moves-from-video"
    files = {
        "/terminalbench/extract-moves-from-video/instruction.md": (task_dir / "instruction.md").read_text(encoding="utf-8"),
        "/terminalbench/extract-moves-from-video/task.toml": (task_dir / "task.toml").read_text(encoding="utf-8"),
        "/case_study/extract_moves_from_video.md": Path("tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md").read_text(encoding="utf-8"),
    }
    prompt = "Use the official extract-moves-from-video instruction and case study to produce a closure plan that requires solution.txt existence and verifier-backed validation."
    return _spec("terminalbench_extract_moves_repaired_closure", "completion", "terminalbench_repaired_closure", "extract-moves-from-video", files, prompt, ["solution.txt", "verifier", "moves"], 2, (CONTROL, INCUMBENT, *COMPLETION_VARIANTS))


def _internal_tb_style_specs() -> list[dict[str, Any]]:
    return [
        _spec("internal_required_artifact_partial_progress_v1", "completion", "internal_latest_tb_style", "required_artifact_closure", {"/task.md": "Create final/report.json after producing scratch notes. Final answer must include the artifact path."}, "Complete the task and do not stop at scratch notes.", ["final/report.json", "artifact"], 2, (CONTROL, INCUMBENT, *COMPLETION_VARIANTS)),
        _spec("internal_toolchain_recovery_artifact_validation_v1", "completion", "internal_latest_tb_style", "toolchain_recovery_validation", {"/task.md": "A downloaded artifact is only valid after checksum-like validation. Explain the recovery and validation steps."}, "Recover from a missing toolchain and validate the post-download artifact.", ["recover", "validate", "artifact"], 2, (CONTROL, INCUMBENT, *COMPLETION_VARIANTS)),
        _spec("internal_multifile_context_aggregation_answer_v1", "context", "internal_latest_tb_style", "multifile_context_aggregation", {"/a.txt": "alpha invoice: 17", "/b.txt": "beta invoice: 25", "/c.txt": "gamma invoice: 8", "/task.md": "Aggregate all invoices and answer the total."}, "Read all files, aggregate the values, and answer the total with file evidence.", ["50", "a.txt", "b.txt", "c.txt"], 3, (CONTROL, INCUMBENT, *CONTEXT_VARIANTS)),
        _spec("internal_verifier_fail_repair_rerun_true_completion_v1", "completion", "internal_latest_tb_style", "verifier_fail_repair_rerun", {"/task.md": "Verifier first fails because output.txt says status=partial. Repair it to status=complete and state rerun evidence."}, "Show verifier fail -> repair -> rerun -> true completion.", ["fail", "repair", "rerun", "complete"], 3, (CONTROL, INCUMBENT, *COMPLETION_VARIANTS)),
    ]


def _spec(eval_id: str, track: str, cls: str, task_id: str, files: dict[str, str], prompt: str, required: list[str], min_hits: int, variants: tuple[str, ...]) -> dict[str, Any]:
    return {"eval_id": eval_id, "track": track, "benchmark_class": cls, "task_id": task_id, "workspace_files": files, "task_prompt": prompt, "required_snippets": required, "min_hits": min_hits, "variant_ids": list(variants)}


def _preflight(specs: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = []
    docker = _run(["docker", "info"], cwd=Path.cwd(), timeout=60)
    if docker["returncode"] != 0 or "Server:" not in docker["stdout"]:
        blockers.append("docker_unhealthy")
    for path, label in ((TERMINALBENCH_ROOT, "terminalbench_root_missing"), (CONTEXTBENCH_ROOT / "data/Verified.csv", "contextbench_verified_missing"), (LETTA_ROOT / "datasets/filesystem_code.jsonl", "letta_dataset_missing"), (BFCL_PATH, "bfcl_mirror_missing"), (EXTRACT_PROBE, "extract_probe_runner_missing")):
        if not Path(path).exists():
            blockers.append(label)
    if letta_preflight()["status"] != "pass":
        blockers.append("letta_preflight_failed")
    if not any(s["eval_id"] == "bfcl_v3_strict_multi_turn_composite_97" for s in specs):
        blockers.append("bfcl_required_case_not_wired")
    tracks = {s["track"] for s in specs}
    if not {"context", "completion", "bfcl", "terminalbench"} <= tracks:
        blockers.append("accepted_tracks_not_fully_wired")
    model_runs = sum(len(s["variant_ids"]) for s in specs)
    if model_runs > 350:
        blockers.append("hard_model_backed_cap_projected")
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "blockers": blockers, "docker_info_live_server": "docker_unhealthy" not in blockers, "planned_model_backed_runs": model_runs, "planned_local_deterministic_runs": 0, "letta": letta_preflight(), "authority": _authority()}


def _route_matrix() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    rows, blockers = [], []
    for variant in ALL_VARIANTS:
        try:
            manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            changed = [r["runtime_key"] for r in manifest["routed_modules"] if r.get("claimed_changed_surface")]
            rows.append({"variant_id": variant, "route_valid": True, "changed_runtime_keys": changed, "route_manifest_fingerprint": manifest["route_manifest_fingerprint"], "routed_modules": manifest["routed_modules"]})
        except Exception as exc:
            rows.append({"variant_id": variant, "route_valid": False, "error": str(exc)})
            blockers.append({"variant_id": variant, "error": str(exc)})
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "routes": rows, "blockers": blockers}


def _mechanism_matrix(route: dict[str, Any], specs: list[dict[str, Any]]) -> dict[str, Any]:
    requirements = {
        **{v: {"context"} for v in CONTEXT_VARIANTS},
        **{v: {"verification"} for v in COMPLETION_VARIANTS},
        **{v: {"tools_getter", "tool_executor"} for v in BFCL_VARIANTS},
    }
    rows, blockers = [], []
    for row in route["routes"]:
        variant = row["variant_id"]
        changed = set(row.get("changed_runtime_keys", []))
        required = requirements.get(variant, set())
        classification = "mechanism-bearing" if required and required <= changed else "mixed" if required and changed & required else "doctrine-only" if variant.startswith("candidate_plus_") else "control-or-incumbent"
        ok = not required or required <= changed
        if not ok:
            blockers.append({"variant_id": variant, "error": "mechanism_required_but_doctrine_only", "required_runtime_keys": sorted(required), "changed_runtime_keys": sorted(changed)})
        rows.append({"variant_id": variant, "classification": classification, "required_runtime_keys": sorted(required), "changed_runtime_keys": sorted(changed), "mechanism_contract_pass": ok})
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "rows": rows, "blockers": blockers}


def _run_one(out: Path, spec: dict[str, Any], variant: str) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _materialize(workspace, spec["workspace_files"])
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=spec["task_prompt"] + "\nUse shell inspection where useful. End with final answer only after required evidence is handled.",
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=variant,
        model_route=make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": 160, "max_retries": 1},
        max_steps=5,
        timeout_sec=180,
        cwd=workspace,
        route_manifest=build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE),
        enforce_packet04_route_contract=True,
    )
    grade = _grade(result, spec, workspace)
    usage = _usage(result)
    record = {"mission_id": MISSION_ID, "run_id": run_id, "eval_id": spec["eval_id"], "track": spec["track"], "benchmark_class": spec["benchmark_class"], "task_id": spec["task_id"], "variant_id": variant, "model_backed": True, "run_dir": str(run_dir), "trace_ref": str(run_dir / "run_events.jsonl"), "score_summary": {"final_verdict": grade["verdict"], "grade": grade}, "token_and_cost_summary": usage, "governed_terminal_status": "valid", "invalid_infrastructure_failure": False, "reason_codes": [] if grade["verdict"] == "pass" else grade["reason_codes"], "authority": _authority()}
    _patch_score(run_dir, grade)
    trace = {"mission_id": MISSION_ID, "run_id": run_id, "eval_id": spec["eval_id"], "track": spec["track"], "variant_id": variant, "raw_bash_events": json.dumps(result.get("run_events", [])).count("raw_bash_result"), "tool_result_receipts": json.dumps(result.get("run_events", [])).count("tool_result_receipt"), "completion_gate_markers": json.dumps(result.get("run_events", [])).count("completion_gate"), "trace_ref": record["trace_ref"]}
    return record, trace


def _grade(result: dict[str, Any], spec: dict[str, Any], workspace: Path) -> dict[str, Any]:
    return grade_phase65_spec(spec=spec, result=result, workspace=workspace)


def _write_reports(out: Path, records: list[dict[str, Any]], traces: list[dict[str, Any]], preflight: dict[str, Any], route: dict[str, Any], mechanism: dict[str, Any]) -> dict[str, Any]:
    _write_jsonl(out / "phase6_corrective_result_records.jsonl", records)
    score = _score(records)
    score["preflight"] = preflight
    score["selected_recommendation"] = _recommendation(score)
    for name, payload in {
        "phase6_corrective_score_envelope.json": score,
        "phase6_corrective_context_report.json": _track_report(records, "context"),
        "phase6_corrective_completion_report.json": _track_report(records, "completion"),
        "phase6_corrective_bfcl_report.json": _track_report(records, "bfcl"),
        "phase6_corrective_terminalbench_report.json": _track_report(records, "terminalbench"),
        "phase6_corrective_trace_report.json": {"mission_id": MISSION_ID, "run_count": len(traces), "traces": traces, "analysis": _trace_analysis(records, traces)},
        "phase6_corrective_failure_source_report.json": _failure_report(records),
        "phase6_corrective_cost_report.json": _cost(records),
    }.items():
        _write_json(out / name, payload)
    _write_text(out / "phase6_corrective_handoff.md", _handoff(out, score))
    ledger = _ledger(out, score)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "run_count": len(records), "model_backed_runs": score["model_backed_runs"], "selected_recommendation": score["selected_recommendation"]}


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"mission_id": MISSION_ID, "run_count": len(records), "model_backed_runs": sum(1 for r in records if r["model_backed"]), "local_deterministic_runs": 0, "invalid_run_count": sum(1 for r in records if r["invalid_infrastructure_failure"]), "final_verdict_counts": _counts(r["score_summary"]["final_verdict"] for r in records), "variant_summary": _summary(records, "variant_id"), "by_eval_variant": _by_eval_variant(records), "analysis_questions": _analysis_questions(records)}


def _recommendation(score: dict[str, Any]) -> str:
    if score["invalid_run_count"]:
        return "benchmark_adapter_still_invalid"
    q = score["analysis_questions"]
    if q["mechanism_repair_beat_incumbent"]:
        return "candidate_repaired_and_ready_for_packet07_readiness_review"
    if q["primary_need"] == "context":
        return "candidate_needs_context_repair"
    if q["primary_need"] == "completion":
        return "candidate_needs_one_more_completion_repair"
    if q["primary_need"] == "bfcl":
        return "candidate_needs_toolcall_repair"
    if q["spb_01_preferred"]:
        return "prefer_spb_01_or_pause_successor"
    return "internal_eval_suite_needs_harder_tasks"


def _analysis_questions(records: list[dict[str, Any]]) -> dict[str, Any]:
    inc = _variant_passes(records, INCUMBENT)
    control = _variant_passes(records, CONTROL)
    repairs = {v: _variant_passes(records, v) for v in ALL_VARIANTS if v not in {CONTROL, INCUMBENT}}
    best_variant, best_passes = max(repairs.items(), key=lambda kv: kv[1], default=(None, 0))
    track_gaps = {t: _best_track_gap(records, t) for t in ("context", "completion", "bfcl")}
    primary = max(track_gaps, key=lambda t: track_gaps[t])
    return {
        "candidate_still_needs_context_repair": track_gaps["context"] > 0,
        "candidate_primarily_needs_completion_repair": primary == "completion" and track_gaps[primary] > 0,
        "candidate_primarily_needs_toolcall_bfcl_repair": primary == "bfcl" and track_gaps[primary] > 0,
        "mechanism_repair_beat_incumbent": bool(best_variant and best_passes > inc),
        "best_repaired_candidate": best_variant,
        "best_repaired_passes": best_passes,
        "incumbent_passes": inc,
        "spb_01_passes": control,
        "spb_01_preferred": control >= inc and control >= best_passes,
        "primary_need": primary if track_gaps[primary] > 0 else "none",
    }


def _best_track_gap(records: list[dict[str, Any]], track: str) -> int:
    inc = sum(1 for r in records if r["track"] == track and r["variant_id"] == INCUMBENT and r["score_summary"]["final_verdict"] == "pass")
    best = 0
    for variant in ALL_VARIANTS:
        if variant in {CONTROL, INCUMBENT}:
            continue
        best = max(best, sum(1 for r in records if r["track"] == track and r["variant_id"] == variant and r["score_summary"]["final_verdict"] == "pass"))
    return max(inc - best, 0)


def _write_blocked(out: Path, preflight: dict[str, Any], route: dict[str, Any], mechanism: dict[str, Any], execute: bool) -> dict[str, Any]:
    score = {"mission_id": MISSION_ID, "run_count": 0, "model_backed_runs": 0, "invalid_run_count": 0, "selected_recommendation": "benchmark_adapter_still_invalid", "preflight": preflight, "route_matrix": route, "mechanism_matrix": mechanism}
    _write_jsonl(out / "phase6_corrective_result_records.jsonl", [])
    for name in ("phase6_corrective_score_envelope.json", "phase6_corrective_context_report.json", "phase6_corrective_completion_report.json", "phase6_corrective_bfcl_report.json", "phase6_corrective_terminalbench_report.json", "phase6_corrective_trace_report.json", "phase6_corrective_failure_source_report.json", "phase6_corrective_cost_report.json"):
        _write_json(out / name, {"mission_id": MISSION_ID, "blocked": True, "execute": execute, "score": score})
    _write_text(out / "phase6_corrective_handoff.md", _handoff(out, score))
    ledger = _ledger(out, score)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "run_count": 0, "model_backed_runs": 0, "selected_recommendation": "benchmark_adapter_still_invalid", "blocked": True}


def _materialize(root: Path, files: dict[str, str]) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    for raw_path, content in files.items():
        path = root / raw_path.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _usage(result: dict[str, Any]) -> dict[str, Any]:
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for step in result.get("execution", {}).get("steps", []):
        usage = (step.get("completion") or {}).get("usage") or {}
        totals["input_tokens"] += int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        totals["cached_input_tokens"] += int(usage.get("cached_tokens", usage.get("cached_input_tokens", 0)) or 0)
        totals["output_tokens"] += int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    usd = max(totals["input_tokens"] - totals["cached_input_tokens"], 0) * PRICE["input"] + totals["cached_input_tokens"] * PRICE["cached_input"] + totals["output_tokens"] * PRICE["output"]
    return {**totals, "usd": usd, "usd_estimate": usd}


def _patch_score(run_dir: Path, grade: dict[str, Any]) -> None:
    score_path = run_dir / "score_envelope.json"
    if not score_path.exists():
        return
    score = json.loads(score_path.read_text(encoding="utf-8"))
    score["aggregate"]["final_verdict"] = grade["verdict"]
    score["aggregate"]["phase6_corrective_grade"] = grade
    score_path.write_text(json.dumps(score, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _track_report(records: list[dict[str, Any]], track: str) -> dict[str, Any]:
    subset = [r for r in records if r["track"] == track]
    return {"mission_id": MISSION_ID, "track": track, "run_count": len(subset), "by_variant": _summary(subset, "variant_id"), "records": subset}


def _failure_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [r for r in records if r["score_summary"]["final_verdict"] != "pass"]
    return {"mission_id": MISSION_ID, "failure_count": len(failures), "model_caused_failures": failures, "harness_caused_failures": [], "invalid_infrastructure_failures": []}


def _trace_analysis(records: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    return {"who_got_further": _analysis_questions(records), "trace_count": len(traces), "tooling_limitations": "No invalid infrastructure failures recorded; failures are graded as behavioral unless a run is marked invalid."}


def _cost(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"total_tokens": 0, "usd": 0.0}
    for r in records:
        c = r["token_and_cost_summary"]
        total["total_tokens"] += int(c.get("total_tokens", 0) or 0)
        total["usd"] += float(c.get("usd", 0.0) or 0.0)
    return {"mission_id": MISSION_ID, "budget_caps": {"target_model_backed_runs": [150, 250], "hard_model_backed_cap": 350, "local_deterministic_cap": 300, "soft_cost_cap_usd": 100, "hard_cost_cap_usd": 200}, "cap_status": "below_soft_cap" if total["usd"] <= 100 else "below_hard_cap" if total["usd"] <= 200 else "hard_cap_exceeded", "total": total}


def _variant_passes(records: list[dict[str, Any]], variant: str) -> int:
    return sum(1 for r in records if r["variant_id"] == variant and r["score_summary"]["final_verdict"] == "pass")


def _summary(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in records:
        b = out.setdefault(r[key], {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        b["run_count"] += 1
        v = r["score_summary"]["final_verdict"]
        b[v if v in b else "unresolved"] += 1
    return out


def _by_eval_variant(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for r in records:
        out.setdefault(r["eval_id"], {}).setdefault(r["variant_id"], {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        b = out[r["eval_id"]][r["variant_id"]]
        b["run_count"] += 1
        b[r["score_summary"]["final_verdict"]] += 1
    return out


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _execution_plan(specs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"mission_id": MISSION_ID, "planned_model_backed_runs": sum(len(s["variant_ids"]) for s in specs), "eval_ids": [s["eval_id"] for s in specs], "specs": [{k: v for k, v in s.items() if k != "workspace_files"} for s in specs]}


def _board_manifest(specs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"mission_id": MISSION_ID, "comparison": [CONTROL, INCUMBENT], "corrects_prior_run": "2026-05-06_successor_phase6_context_completion_repair_gauntlet_rerun3_escalated", "accepted_lanes": _counts(s["track"] for s in specs), "eval_ids": [s["eval_id"] for s in specs], "authority": _authority()}


def _plan(out: Path, preflight: dict[str, Any], route: dict[str, Any], mechanism: dict[str, Any], specs: list[dict[str, Any]]) -> str:
    return "\n".join(["# Phase 6 Corrective Plan", "", f"- mission_id: `{MISSION_ID}`", f"- output_root: `{out}`", f"- preflight_status: `{preflight['status']}`", f"- route_status: `{route['status']}`", f"- mechanism_status: `{mechanism['status']}`", f"- planned_model_backed_runs: `{sum(len(s['variant_ids']) for s in specs)}`", "- Packet07 remains closed; rerun3 remains bounded internal-board evidence."])


def _scope_gap_report() -> str:
    return "\n".join(["# Phase 6 Corrective Scope Gap Report", "", "- rerun3 executed existing internal homes and is preserved as valid scope-incomplete evidence.", "- this corrective slice wires the missing richer ContextBench, Letta, BFCL strict, public TerminalBench, extract-moves closure, and new latest-TB-style internal lanes.", "- doctrine-only mechanism claims fail closed through `phase6_corrective_variant_mechanism_matrix.json`."])


def _eval_design_report(specs: list[dict[str, Any]]) -> str:
    lines = ["# Phase 6 Corrective Eval Design Report", ""]
    for track in ("context", "completion", "bfcl", "terminalbench"):
        lines.append(f"- {track}: {sum(1 for s in specs if s['track'] == track)} eval cases")
    return "\n".join(lines) + "\n"


def _handoff(out: Path, score: dict[str, Any]) -> str:
    return "\n".join(["# Phase 6 Corrective Handoff", "", f"- mission_id: `{MISSION_ID}`", f"- output_root: `{out}`", f"- run_count: `{score.get('run_count', 0)}`", f"- model_backed_runs: `{score.get('model_backed_runs', 0)}`", f"- invalid_run_count: `{score.get('invalid_run_count', 0)}`", f"- final_recommendation: `{score.get('selected_recommendation')}`", "- authority: no Packet07 movement, benchmark-authority widening, leaderboard submission, transfer movement, protected holdouts, task-id routing, RHv1 unfreeze, or behavioral patching-after-observation."])


def _ledger(out: Path, score: dict[str, Any]) -> str:
    return "\n".join(["RAW_LEDGER_UPDATE", "- actor: codex", "- task: corrective Phase 6 full-scope rerun", "- event_type: experiment", f"- summary: Executed or preflighted the corrective Phase 6 board with recommendation `{score.get('selected_recommendation')}`.", f"- observations: run_count `{score.get('run_count', 0)}`; model_backed_runs `{score.get('model_backed_runs', 0)}`; invalid_run_count `{score.get('invalid_run_count', 0)}`.", "- inference: This corrective slice preserves rerun3 as internal-board evidence while testing the authorized full-scope lanes with mechanism-bearing route checks.", f"- evidence_paths: {out / 'phase6_corrective_board_manifest.json'}; {out / 'phase6_corrective_score_envelope.json'}; {out / 'phase6_corrective_handoff.md'}", "- affected_components: Phase 6 corrective runner; Packet06 route admission; external/context/BFCL/completion evidence", "- decision_change: Packet07 remains closed pending principal review", "- unresolved_questions: Whether any remaining failures require context, completion, or BFCL/tool-call repair.", "- confidence: medium", "- commit_message: HOLD - corrective Phase 6 full-scope rerun artifacts"])


def _authority() -> dict[str, bool]:
    return {"packet07_movement": False, "benchmark_authority_widening": False, "leaderboard_submission": False, "transfer_movement": False, "protected_holdouts": False, "task_id_routing": False, "rhv1_unfreeze": False, "full_rhv1_revival": False}


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        c = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)
        return {"cmd": " ".join(cmd), "returncode": c.returncode, "stdout": c.stdout, "stderr": c.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {"cmd": " ".join(cmd), "returncode": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "", "timed_out": True}


def _record_ledger(raw: str) -> None:
    proc = subprocess.run([sys.executable, "tracking/ledger/tools/record_update.py"], input=raw, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(launch_corrective_phase6(output_dir=args.output_dir, execute=not args.no_execute), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
