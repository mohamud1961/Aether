"""Run a single-task TerminalBench failure-pressure diagnostic."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from runner.agent import run_reference_baseline
from runner.model_client import make_azure_gpt53_codex_route_from_env
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE5_HARD_GAUNTLET_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)

MISSION_ID = "terminalbench_failure_probe_extract_moves_from_video"
CONTROL = "spb_01"
CANDIDATE = "spb_tooling_seed_plus_receipt_and_completion_01"
VARIANTS = (CONTROL, CANDIDATE)
TASK_ID = "extract-moves-from-video"
TERMINALBENCH_ROOT = Path("/Users/mohamud/Downloads/terminalbench")
TASK_DIR = TERMINALBENCH_ROOT / "official_tasks" / TASK_ID
CASE_STUDY = Path(
    "tracking/collab/stage_02_synthesis/trajectory_case_studies/"
    "extract_moves_from_video.md"
)
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-05_terminalbench_failure_probe_extract_moves_from_video"
)
PRICE = {"input": 1.75 / 1_000_000, "cached_input": 0.175 / 1_000_000, "output": 14.0 / 1_000_000}
TASK_META = tomllib.loads((TASK_DIR / "task.toml").read_text(encoding="utf-8"))
TASK_INSTRUCTION = (TASK_DIR / "instruction.md").read_text(encoding="utf-8").strip()
AGENT_TIMEOUT_SEC = int(TASK_META["agent"]["timeout_sec"])
DOCKER_IMAGE = str(TASK_META["environment"]["docker_image"])
TASK_STEP_BUDGET = 60


def launch_probe(*, output_dir: str | Path, execute: bool = True) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    preflight = _preflight()
    route_matrix = _route_matrix()
    _write_text(out / "terminalbench_failure_probe_plan.md", _plan(out, preflight, route_matrix))
    if not execute or preflight["status"] != "pass" or route_matrix["status"] != "pass":
        return _write_blocked(out, preflight, route_matrix, execute=execute)

    records: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    model_backed_runs = 0
    for variant in VARIANTS:
        attempt = 0
        while True:
            attempt += 1
            model_backed_runs += 1
            record, trace = _run_variant(out, variant, attempt)
            records.append(record)
            traces.append(trace)
            if not record["invalid_infrastructure_failure"] or attempt >= 2:
                break
            if model_backed_runs >= 4:
                break

    reports = _reports(records, traces, preflight, route_matrix)
    _write_jsonl(out / "terminalbench_failure_probe_result_records.jsonl", records)
    for name, payload in reports.items():
        _write_json(out / name, payload)
    _write_text(out / "terminalbench_failure_probe_handoff.md", _handoff(out, reports["terminalbench_failure_probe_score_envelope.json"], reports))
    ledger = _ledger_update(out, reports["terminalbench_failure_probe_score_envelope.json"])
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE.txt", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": model_backed_runs,
        "selected_recommendation": reports["terminalbench_failure_probe_score_envelope.json"]["selected_recommendation"],
    }


def _preflight() -> dict[str, Any]:
    docker = _run(["docker", "info"], cwd=Path.cwd(), timeout=60)
    blockers: list[str] = []
    if docker["returncode"] != 0 or "Server:" not in docker["stdout"]:
        blockers.append("docker_info_failed")
    if not TERMINALBENCH_ROOT.exists():
        blockers.append("terminalbench_root_missing")
    if not TASK_DIR.exists():
        blockers.append("locked_task_missing")
    if not CASE_STUDY.exists():
        blockers.append("task_choice_evidence_missing")
    return {
        "mission_id": MISSION_ID,
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "docker_info_live_server": not blockers or "docker_info_failed" not in blockers,
        "terminalbench_root": str(TERMINALBENCH_ROOT),
        "task_toml": str(TASK_DIR / "task.toml"),
        "task_choice_evidence": str(CASE_STUDY.resolve()),
        "docker_image": DOCKER_IMAGE,
        "difficulty": TASK_META["metadata"]["difficulty"],
        "agent_timeout_sec": AGENT_TIMEOUT_SEC,
        "verifier_timeout_sec": TASK_META["verifier"]["timeout_sec"],
        "authority": _authority(),
    }


def _route_matrix() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE)
    routes = []
    blockers = []
    for variant in VARIANTS:
        try:
            manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            routes.append({
                "variant_id": variant,
                "route_valid": True,
                "route_scope": manifest["route_scope"],
                "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                "changed_runtime_keys": [r["runtime_key"] for r in manifest["routed_modules"] if r.get("claimed_changed_surface")],
            })
        except Exception as exc:
            blockers.append({"variant_id": variant, "error": str(exc)})
            routes.append({"variant_id": variant, "route_valid": False, "error": str(exc)})
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "routes": routes, "blockers": blockers}


def _run_variant(out: Path, variant: str, attempt: int) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id = f"{MISSION_ID}__{TASK_ID}__{variant}__r{attempt - 1}"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _materialize_workspace(workspace)
    prompt = _task_prompt()
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=TASK_ID,
        task_prompt=prompt,
        benchmark_family="terminalbench",
        case_id=f"terminalbench_{TASK_ID}",
        seed_id=variant,
        model_route=make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": 300, "max_retries": 1},
        orientation_env_overrides={"step_budget_hint": TASK_STEP_BUDGET},
        max_steps=TASK_STEP_BUDGET,
        timeout_sec=AGENT_TIMEOUT_SEC,
        sandbox_type="docker",
        sandbox_image=DOCKER_IMAGE,
        cwd=workspace,
        route_manifest=build_packet04_route_manifest(variant, scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE),
        enforce_packet04_route_contract=True,
    )
    verifier = _run_official_verifier(workspace, run_dir)
    failure_mode = _classify_failure(result, verifier, workspace)
    usage = _usage(result)
    verdict = "pass" if verifier["status"] == "pass" else "fail"
    if verifier["invalid_infrastructure_failure"]:
        verdict = "unresolved"
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "benchmark_class": "terminalbench",
        "eval_id": f"terminalbench_{TASK_ID}",
        "task_id": TASK_ID,
        "variant_id": variant,
        "attempt": attempt,
        "model_route": result["run_header"]["model_route"],
        "run_dir": str(run_dir),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "score_summary": {"final_verdict": verdict, "official_verifier": verifier},
        "token_and_cost_summary": usage,
        "governed_terminal_status": "invalid" if verifier["invalid_infrastructure_failure"] else "valid",
        "invalid_infrastructure_failure": verifier["invalid_infrastructure_failure"],
        "reason_codes": [] if verdict == "pass" else failure_mode["reason_codes"],
        "failure_mode": failure_mode,
        "authority": _authority(),
    }
    _patch_score(run_dir, verdict, verifier, failure_mode)
    trace = _trace_row(result, record, verifier, workspace)
    return record, trace


def _materialize_workspace(workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "instruction.md").write_text(TASK_INSTRUCTION + "\n", encoding="utf-8")


def _task_prompt() -> str:
    return "\n".join([
        "You are running the real public TerminalBench task `extract-moves-from-video` inside the official task Docker image.",
        "Current working directory is your writable task workspace. Anything you write there will later be mounted as `/app` for the official verifier.",
        "You may use the network, install tools, download the video, inspect frames, run OCR, and create temporary files in the workspace as needed.",
        "Do the task itself, not a plan-only diagnostic.",
        "Required deliverable: create `solution.txt` in the current working directory with one extracted Zork move per line.",
        "Do not claim completion unless `solution.txt` exists and you have done at least one concrete quality check on its contents.",
        "Do not read or modify verifier tests. Do not submit to any leaderboard.",
        "",
        "Official task instruction:",
        TASK_INSTRUCTION,
    ])


def _run_official_verifier(workspace: Path, run_dir: Path) -> dict[str, Any]:
    logs = run_dir / "verifier_logs"
    logs.mkdir(parents=True, exist_ok=True)
    tests = TASK_DIR / "tests"
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{workspace}:/app",
        "-v", f"{tests}:/tests:ro",
        "-v", f"{logs}:/logs",
        "-w", "/app",
        DOCKER_IMAGE,
        "bash", "/tests/test.sh",
    ]
    result = _run(cmd, cwd=Path.cwd(), timeout=int(TASK_META["verifier"]["timeout_sec"]) + 120)
    reward_path = logs / "verifier" / "reward.txt"
    reward = reward_path.read_text(encoding="utf-8").strip() if reward_path.exists() else None
    invalid = _looks_like_docker_infra_failure(result) and reward is None
    status = "pass" if reward == "1" and result["returncode"] == 0 else "fail"
    if invalid:
        status = "invalid_infrastructure"
    payload = {
        "status": status,
        "docker_image": DOCKER_IMAGE,
        "command": result["cmd"],
        "returncode": result["returncode"],
        "timed_out": result["timed_out"],
        "reward": reward,
        "reward_path": str(reward_path),
        "stdout_tail": result["stdout"][-4000:],
        "stderr_tail": result["stderr"][-4000:],
        "invalid_infrastructure_failure": invalid,
        "logs_dir": str(logs),
    }
    _write_json(run_dir / "official_verifier_result.json", payload)
    return payload


def _classify_failure(result: dict[str, Any], verifier: dict[str, Any], workspace: Path) -> dict[str, Any]:
    text = json.dumps(result.get("execution", {}), sort_keys=True).lower()
    tool_results = [tool for step in result.get("execution", {}).get("steps", []) for tool in step.get("results", [])]
    timed_out = any(bool(tool.get("timed_out")) for tool in tool_results)
    contract = any(tool.get("result_class") == "contract_error" for tool in tool_results)
    solution = workspace / "solution.txt"
    reason_codes: list[str] = []
    primary = None
    if verifier["invalid_infrastructure_failure"]:
        primary = "invalid_infrastructure"
        reason_codes.append("docker_verifier_infrastructure_failure")
    elif verifier["status"] == "pass":
        primary = "none"
    elif contract:
        primary = "tool-gateway / command-contract failure"
        reason_codes.append("tool_gateway_or_command_contract_failure")
    elif timed_out:
        primary = "runtime timeout / long-horizon degradation"
        reason_codes.append("runtime_timeout_or_long_horizon_degradation")
    elif not solution.exists():
        primary = "false completion / unsupported completion claim"
        reason_codes.append("missing_solution_file_after_model_completion")
    elif "not sure" in text or "uncertain" in text or "cannot fully" in text:
        primary = "perception / extraction ambiguity"
        reason_codes.append("model_reported_extraction_uncertainty")
    else:
        primary = "verifier-finalization failure"
        reason_codes.append("official_verifier_failed_final_similarity")
    return {
        "primary": primary,
        "reason_codes": reason_codes,
        "solution_file_exists": solution.exists(),
        "solution_line_count": _line_count(solution) if solution.exists() else 0,
        "model_claimed_done": result.get("execution", {}).get("status") == "completed",
        "tool_contract_error_count": sum(1 for tool in tool_results if tool.get("result_class") == "contract_error"),
        "tool_timeout_count": sum(1 for tool in tool_results if tool.get("timed_out")),
    }


def _trace_row(result: dict[str, Any], record: dict[str, Any], verifier: dict[str, Any], workspace: Path) -> dict[str, Any]:
    events = result.get("run_events", [])
    return {
        "mission_id": MISSION_ID,
        "run_id": record["run_id"],
        "variant_id": record["variant_id"],
        "trace_ref": record["trace_ref"],
        "raw_bash_events": json.dumps(events, sort_keys=True).count("raw_bash_result"),
        "tool_contract_error_count": record["failure_mode"]["tool_contract_error_count"],
        "tool_timeout_count": record["failure_mode"]["tool_timeout_count"],
        "solution_file_exists": (workspace / "solution.txt").exists(),
        "solution_line_count": record["failure_mode"]["solution_line_count"],
        "official_verifier_status": verifier["status"],
        "official_verifier_reward": verifier["reward"],
        "failure_mode": record["failure_mode"]["primary"],
    }


def _patch_score(run_dir: Path, verdict: str, verifier: dict[str, Any], failure_mode: dict[str, Any]) -> None:
    score_path = run_dir / "score_envelope.json"
    score = json.loads(score_path.read_text(encoding="utf-8"))
    final = "pass" if verdict == "pass" else "fail"
    score["aggregate"]["final_verdict"] = final
    score["aggregate"]["terminalbench_failure_probe"] = {"official_verifier": verifier, "failure_mode": failure_mode}
    score["layers"]["L1_verifier_artifact"]["artifact_ref"] = str(run_dir / "official_verifier_result.json")
    score["layers"]["L1_verifier_artifact"]["score"] = {"kind": "boolean", "value": verifier["status"] == "pass"}
    score["layers"]["L4_final_acceptance"]["status"] = "pass" if verifier["status"] == "pass" else "fail"
    score["layers"]["L4_final_acceptance"]["score"] = {"kind": "boolean", "value": verifier["status"] == "pass"}
    score_path.write_text(json.dumps(score, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _reports(records: list[dict[str, Any]], traces: list[dict[str, Any]], preflight: dict[str, Any], route_matrix: dict[str, Any]) -> dict[str, Any]:
    score = _score(records, preflight, route_matrix)
    analysis = _failure_analysis(records)
    score["selected_recommendation"] = _recommendation(records, analysis)
    return {
        "terminalbench_failure_probe_score_envelope.json": score,
        "terminalbench_failure_probe_trace_report.json": {"mission_id": MISSION_ID, "run_count": len(traces), "traces": traces},
        "terminalbench_failure_probe_failure_analysis.json": analysis,
        "terminalbench_failure_probe_cost_report.json": _cost(records),
    }


def _score(records: list[dict[str, Any]], preflight: dict[str, Any], route_matrix: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "task_id": TASK_ID,
        "run_count": len(records),
        "model_backed_runs": len(records),
        "invalid_run_count": sum(1 for r in records if r["invalid_infrastructure_failure"]),
        "final_verdict_counts": _counts(r["score_summary"]["final_verdict"] for r in records),
        "variant_summary": _summary(records),
        "preflight": preflight,
        "route_matrix": route_matrix,
        "authority": _authority(),
    }


def _failure_analysis(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant = {
        r["variant_id"]: {
            "verdict": r["score_summary"]["final_verdict"],
            "official_verifier_status": r["score_summary"]["official_verifier"]["status"],
            "reward": r["score_summary"]["official_verifier"]["reward"],
            "failure_mode": r["failure_mode"],
        }
        for r in records
    }
    c = by_variant.get(CANDIDATE, {})
    b = by_variant.get(CONTROL, {})
    return {
        "mission_id": MISSION_ID,
        "task_id": TASK_ID,
        "candidate_vs_control": _compare(c.get("verdict"), b.get("verdict")),
        "defended_verifier_closure": {
            CONTROL: b.get("official_verifier_status") == "pass",
            CANDIDATE: c.get("official_verifier_status") == "pass",
        },
        "by_variant": by_variant,
        "repair_implication": _repair_implication(by_variant),
    }


def _recommendation(records: list[dict[str, Any]], analysis: dict[str, Any]) -> str:
    if any(r["invalid_infrastructure_failure"] for r in records):
        return "task_exposes_long_horizon_or_tool_contract_repair_need"
    relation = analysis["candidate_vs_control"]
    if relation == "candidate_beats_control":
        return "candidate_handles_failed_agent_tb_task"
    if relation == "candidate_regresses_against_control":
        return "candidate_regresses_on_failed_agent_tb_task"
    modes = [v["failure_mode"]["primary"] for v in analysis["by_variant"].values()]
    if any("false completion" in str(mode) for mode in modes):
        return "task_exposes_false_completion_risk"
    if any("timeout" in str(mode) or "tool-gateway" in str(mode) for mode in modes):
        return "task_exposes_long_horizon_or_tool_contract_repair_need"
    return "candidate_ties_control_on_failed_agent_tb_task"


def _compare(candidate: str | None, control: str | None) -> str:
    score = {"pass": 1, "fail": 0, "unresolved": -1, None: -1}
    if score.get(candidate, -1) > score.get(control, -1):
        return "candidate_beats_control"
    if score.get(candidate, -1) < score.get(control, -1):
        return "candidate_regresses_against_control"
    return "candidate_ties_control"


def _repair_implication(by_variant: dict[str, Any]) -> str:
    modes = " ".join(str(v.get("failure_mode", {}).get("primary", "")) for v in by_variant.values())
    if "tool-gateway" in modes or "timeout" in modes:
        return "tool-contract or long-horizon workflow repair"
    if "false completion" in modes:
        return "completion repair"
    if "perception" in modes or "verifier-finalization" in modes:
        return "long-horizon multimodal extraction and verifier-finalization repair"
    return "none"


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


def _cost(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"total_tokens": 0, "usd": 0.0}
    by_variant: dict[str, Any] = {}
    for row in records:
        cost = row["token_and_cost_summary"]
        total["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        total["usd"] += float(cost.get("usd", 0.0) or 0.0)
        bucket = by_variant.setdefault(row["variant_id"], {"run_count": 0, "total_tokens": 0, "usd": 0.0})
        bucket["run_count"] += 1
        bucket["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        bucket["usd"] += float(cost.get("usd", 0.0) or 0.0)
    cap = "below_soft_cap" if total["usd"] <= 20 else "below_hard_cap" if total["usd"] <= 50 else "hard_cap_exceeded"
    return {"mission_id": MISSION_ID, "budget_caps": {"target_model_backed_runs": 2, "hard_model_backed_cap": 4, "soft_cost_cap_usd": 20.0, "hard_cost_cap_usd": 50.0}, "cap_status": cap, "total": total, "by_variant": by_variant}


def _plan(out: Path, preflight: dict[str, Any], route_matrix: dict[str, Any]) -> str:
    return "\n".join([
        "# TerminalBench Failure Probe Plan",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- comparison: `{CONTROL}` vs `{CANDIDATE}`",
        f"- locked_task: `{TASK_ID}`",
        f"- task_difficulty: `{preflight.get('difficulty')}`",
        f"- docker_image: `{preflight.get('docker_image')}`",
        f"- preflight_status: `{preflight['status']}`",
        f"- route_status: `{route_matrix['status']}`",
        "- execution: each variant exactly once unless invalid infrastructure requires one bounded rerun.",
        "- authority: diagnostic only; no Packet 07 movement, benchmark-authority widening, leaderboard submission, transfer movement, protected holdouts, task-id routing, RHv1 unfreeze, or full RHv1 revival.",
        "",
    ])


def _handoff(out: Path, score: dict[str, Any], reports: dict[str, Any]) -> str:
    analysis = reports["terminalbench_failure_probe_failure_analysis.json"]
    return "\n".join([
        "# TerminalBench Failure Probe Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- locked_task: `{TASK_ID}`",
        f"- run_count: `{score['run_count']}`",
        f"- model_backed_runs: `{score['model_backed_runs']}`",
        f"- invalid_run_count: `{score['invalid_run_count']}`",
        f"- candidate_vs_control: `{analysis['candidate_vs_control']}`",
        f"- repair_implication: `{analysis['repair_implication']}`",
        f"- final_recommendation: `{score['selected_recommendation']}`",
        "- authority: diagnostic only; no Packet 07 movement or benchmark authority movement occurred.",
        "",
    ])


def _ledger_update(out: Path, score: dict[str, Any]) -> str:
    return "\n".join([
        "RAW_LEDGER_UPDATE",
        "- actor: codex",
        "- task: bounded TerminalBench failure-pressure diagnostic on extract-moves-from-video",
        "- event_type: experiment",
        f"- summary: Ran `{TASK_ID}` for `{CONTROL}` and `{CANDIDATE}` with official Docker verifier closure; recommendation `{score['selected_recommendation']}`.",
        f"- observations: Produced {score['run_count']} records; invalid infrastructure count {score['invalid_run_count']}; verdict counts {score.get('final_verdict_counts', {})}.",
        "- inference: This is diagnostic stress evidence only and does not move Packet07 or benchmark authority.",
        f"- evidence_paths: {out / 'terminalbench_failure_probe_result_records.jsonl'}; {out / 'terminalbench_failure_probe_score_envelope.json'}; {out / 'terminalbench_failure_probe_failure_analysis.json'}; {out / 'terminalbench_failure_probe_handoff.md'}",
        "- affected_components: pre-Packet07 external diagnostic probe; TerminalBench hard-task failure pressure; Packet06 successor comparison",
        "- decision_change: NONE - diagnostic evidence only; no Packet07 movement authorized",
        "- unresolved_questions: Whether this single hard public TerminalBench result should alter the context/completion/tool-contract repair queue before readiness review resumes.",
        "- confidence: medium",
        "- commit_message: HOLD - TerminalBench failure probe artifacts generated for review",
    ])


def _write_blocked(out: Path, preflight: dict[str, Any], route_matrix: dict[str, Any], *, execute: bool) -> dict[str, Any]:
    score = {"mission_id": MISSION_ID, "run_count": 0, "model_backed_runs": 0, "invalid_run_count": 0, "selected_recommendation": "task_exposes_long_horizon_or_tool_contract_repair_need", "preflight": preflight, "route_matrix": route_matrix}
    _write_jsonl(out / "terminalbench_failure_probe_result_records.jsonl", [])
    _write_json(out / "terminalbench_failure_probe_score_envelope.json", score)
    _write_json(out / "terminalbench_failure_probe_trace_report.json", {"mission_id": MISSION_ID, "blocked": True, "execute": execute, "preflight": preflight, "route_matrix": route_matrix})
    _write_json(out / "terminalbench_failure_probe_failure_analysis.json", {"mission_id": MISSION_ID, "blocked": True, "preflight": preflight, "route_matrix": route_matrix})
    _write_json(out / "terminalbench_failure_probe_cost_report.json", {"mission_id": MISSION_ID, "blocked": True, "total": {"total_tokens": 0, "usd": 0.0}})
    _write_text(out / "terminalbench_failure_probe_handoff.md", _handoff(out, score, {"terminalbench_failure_probe_failure_analysis.json": {"candidate_vs_control": "blocked", "repair_implication": "measurement blocker"}}))
    ledger = _ledger_update(out, score)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE.txt", ledger)
    return {"output_dir": str(out), "run_count": 0, "selected_recommendation": score["selected_recommendation"]}


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in records:
        bucket = out.setdefault(row["variant_id"], {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        verdict = row["score_summary"]["final_verdict"]
        bucket["run_count"] += 1
        bucket[verdict if verdict in bucket else "unresolved"] += 1
    return out


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _line_count(path: Path) -> int:
    return len([line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()])


def _looks_like_docker_infra_failure(result: dict[str, Any]) -> bool:
    text = f"{result['stdout']}\n{result['stderr']}".lower()
    markers = ("pull access denied", "manifest unknown", "error response from daemon", "cannot connect to the docker daemon", "network is unreachable", "temporary failure", "no such host")
    return result["returncode"] != 0 and any(marker in text for marker in markers)


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)
        return {"cmd": " ".join(cmd), "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {"cmd": " ".join(cmd), "returncode": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "", "timed_out": True}


def _record_ledger(raw: str) -> None:
    proc = subprocess.run([sys.executable, "tracking/ledger/tools/record_update.py"], input=raw, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ledger update failed: {proc.stderr}")


def _authority() -> dict[str, bool]:
    return {"packet07_movement": False, "benchmark_authority_widening": False, "leaderboard_submission": False, "transfer_movement": False, "protected_holdouts": False, "task_id_routing": False, "rhv1_unfreeze": False, "full_rhv1_revival": False}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(launch_probe(output_dir=args.output_dir, execute=not args.no_execute), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
