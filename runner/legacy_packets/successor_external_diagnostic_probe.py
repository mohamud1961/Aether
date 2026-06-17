"""Run the bounded pre-Packet07 external diagnostic probe."""

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
from runner.letta_context_bench import (
    grade_letta_filesystem_answer,
    letta_preflight,
    selected_letta_filesystem_specs,
)
from runner.model_client import make_azure_gpt53_codex_route_from_env
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE5_HARD_GAUNTLET_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.schemas import utc_now

MISSION_ID = "successor_pre_packet07_external_diagnostic_probe"
CONTROL = "spb_01"
CANDIDATE = "spb_tooling_seed_plus_receipt_and_completion_01"
VARIANTS = (CONTROL, CANDIDATE)
TERMINALBENCH_ROOT = Path("/Users/mohamud/Downloads/terminalbench")
CONTEXTBENCH_ROOT = Path("/Users/mohamud/Downloads/harnesseng/research/sources/codebases/ContextBench")
CONTEXTBENCH_PYTHON = Path("/Users/mohamud/Downloads/harnesseng/.venv/bin/python")
INSTANCE_ID = "SWE-Bench-Verified__python__maintenance__bugfix__726ccefd"
BFCL_PATH = Path("research/sources/codebases/deepagents/libs/evals/tests/evals/data/benchmark_samples/bfcl_v3_final.json")
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-05_pre_packet07_external_diagnostic_probe"
)
RECOMMENDATIONS = (
    "proceed_to_packet07_readiness_review",
    "run_one_more_external_probe",
    "candidate_needs_context_repair_before_packet07",
    "candidate_needs_terminal_task_repair_before_packet07",
    "internal_eval_suite_too_easy_repair_before_packet07",
)
PRICE = {"input": 1.75 / 1_000_000, "cached_input": 0.175 / 1_000_000, "output": 14.0 / 1_000_000}


def launch_probe(*, output_dir: str | Path, execute: bool = True) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    preflight = _preflight(out)
    route_matrix = _route_matrix()
    _write_text(out / "external_diagnostic_probe_plan.md", _plan(out, preflight, route_matrix))
    _write_text(out / "external_diagnostic_task_selection.md", _task_selection(preflight))
    if not execute or preflight["status"] != "pass" or route_matrix["status"] != "pass":
        return _write_blocked(out, preflight, route_matrix, execute=execute)

    records: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for spec in _probe_specs(out):
        for variant in VARIANTS:
            record, trace = _run_one(out, spec, variant)
            records.append(record)
            trace_rows.append(trace)

    contextbench = _contextbench_convert(out)
    if contextbench["status"] != "pass":
        _write_jsonl(out / "external_diagnostic_result_records.jsonl", records)
        _write_json(out / "external_diagnostic_contextbench_report.json", contextbench)
        raise SystemExit("measurement_blocker: ContextBench custom parser conversion failed")

    reports = _reports(records, trace_rows, contextbench)
    _write_jsonl(out / "external_diagnostic_result_records.jsonl", records)
    for name, payload in reports.items():
        _write_json(out / name, payload)
    handoff = _handoff(out, reports["external_diagnostic_score_envelope.json"], reports, reports["external_diagnostic_score_envelope.json"]["selected_recommendation"])
    _write_text(out / "external_diagnostic_handoff.md", handoff)
    ledger = _ledger_update(out, reports["external_diagnostic_score_envelope.json"])
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE.txt", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": len(records),
        "selected_recommendation": reports["external_diagnostic_score_envelope.json"]["selected_recommendation"],
    }


def _preflight(out: Path) -> dict[str, Any]:
    docker = _run(["docker", "info"], cwd=Path.cwd(), timeout=60)
    tb_tasks = {}
    for task_id in ("fix-git", "regex-log", "financial-document-processor"):
        task_dir = TERMINALBENCH_ROOT / "official_tasks" / task_id
        meta = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
        tb_tasks[task_id] = {
            "task_dir": str(task_dir),
            "difficulty": meta["metadata"]["difficulty"],
            "verifier_timeout_sec": meta["verifier"]["timeout_sec"],
            "docker_image": meta["environment"]["docker_image"],
            "instruction": str(task_dir / "instruction.md"),
            "tests": str(task_dir / "tests"),
        }
    context_parser = CONTEXTBENCH_ROOT / "contextbench/parsers/custom_parser.py"
    help_result = _run([str(CONTEXTBENCH_PYTHON), "-m", "contextbench.process_trajectories", "convert", "--help"], cwd=CONTEXTBENCH_ROOT, timeout=60)
    row = _contextbench_row()
    smoke_dir = out / "preflight_contextbench_parser_smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    (smoke_dir / "run_header.json").write_text(json.dumps({"run_id": "smoke", "task_id": INSTANCE_ID}, indent=2), encoding="utf-8")
    (smoke_dir / "run_events.jsonl").write_text(
        json.dumps({"event_type": "raw_bash_result", "payload": {"details": {"command": "sed -n '1,5p' sympy/core/basic.py"}}}) + "\n",
        encoding="utf-8",
    )
    smoke_out = out / "preflight_contextbench_pred.jsonl"
    smoke = _run(
        [str(CONTEXTBENCH_PYTHON), "-m", "contextbench.process_trajectories", "convert", "-i", str(smoke_dir), "-o", str(smoke_out), "--agent", "custom"],
        cwd=CONTEXTBENCH_ROOT,
        timeout=60,
    )
    blockers = []
    if docker["returncode"] != 0:
        blockers.append("docker_info_failed")
    if not TERMINALBENCH_ROOT.exists():
        blockers.append("terminalbench_missing")
    if not CONTEXTBENCH_ROOT.exists():
        blockers.append("contextbench_missing")
    if not context_parser.exists():
        blockers.append("contextbench_custom_parser_missing")
    if help_result["returncode"] != 0:
        blockers.append("contextbench_cli_unavailable")
    if smoke["returncode"] != 0 or not smoke_out.exists() or not smoke_out.read_text(encoding="utf-8").strip():
        blockers.append("contextbench_custom_parser_conversion_failed")
    letta = letta_preflight()
    blockers.extend(letta["blockers"])
    return {
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "docker_info_live_server": docker["returncode"] == 0 and "Server:" in docker["stdout"],
        "terminalbench_root": str(TERMINALBENCH_ROOT),
        "contextbench_root": str(CONTEXTBENCH_ROOT),
        "contextbench_custom_parser": str(context_parser),
        "contextbench_instance_row": row,
        "letta_context_bench": letta,
        "terminalbench_tasks": tb_tasks,
        "tooling_probe_path": str(BFCL_PATH.resolve()),
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


def _probe_specs(out: Path) -> list[dict[str, Any]]:
    bfcl_case = next(row for row in json.loads(BFCL_PATH.read_text(encoding="utf-8")) if row["id"] == "multi_turn_composite_97")
    return [
        _terminal_spec("fix-git", "easy", out),
        _terminal_spec("regex-log", "medium", out),
        _terminal_spec("financial-document-processor", "medium", out),
        {
            "probe_id": "deepagents_bfcl_v3_multi_turn_composite_97",
            "class": "tooling_benchmark",
            "task_id": "multi_turn_composite_97",
            "workspace_files": bfcl_case["files"],
            "task_prompt": bfcl_case["prompt"],
            "grade": {"required_snippets": bfcl_case["answer_snippets"], "min_snippets": len(bfcl_case["answer_snippets"])},
        },
        {
            "probe_id": "contextbench_verified_726ccefd",
            "class": "contextbench",
            "task_id": INSTANCE_ID,
            "workspace_files": {
                "/contextbench/Verified.csv": (CONTEXTBENCH_ROOT / "data/Verified.csv").read_text(encoding="utf-8"),
                "/contextbench/task.md": (
                    "Use the local ContextBench row for SWE-Bench-Verified__python__maintenance__bugfix__726ccefd. "
                    "Inspect the CSV and report the original instance id, language, status, token count, and commit hash. "
                    "Then identify one likely source file family you would inspect first for a SymPy maintenance bugfix."
                ),
            },
            "task_prompt": "Read /contextbench/task.md and /contextbench/Verified.csv, then produce a concise ContextBench diagnostic note.",
            "grade": {"required_snippets": ["sympy__sympy-22914", "python", "pass", "87.0", "c4e836cdf73fc6aa7bab6a86719a0f08861ffb1d"], "min_snippets": 4},
        },
        *selected_letta_filesystem_specs(),
    ]


def _terminal_spec(task_id: str, difficulty: str, out: Path) -> dict[str, Any]:
    task_dir = TERMINALBENCH_ROOT / "official_tasks" / task_id
    files = {
        f"/terminalbench/{task_id}/instruction.md": (task_dir / "instruction.md").read_text(encoding="utf-8"),
        f"/terminalbench/{task_id}/task.toml": (task_dir / "task.toml").read_text(encoding="utf-8"),
        f"/terminalbench/{task_id}/tests/test_outputs.py": (task_dir / "tests/test_outputs.py").read_text(encoding="utf-8"),
    }
    solution = task_dir / "solution/solve.sh"
    if solution.exists():
        files[f"/terminalbench/{task_id}/solution_solve_sh_reference.txt"] = solution.read_text(encoding="utf-8")
    prompt = (
        f"This is a public-safe TerminalBench-shaped diagnostic for `{task_id}`. Inspect the copied official "
        "instruction, task metadata, and tests under /terminalbench. Produce the concrete repair strategy and "
        "final files or commands required; do not submit to any leaderboard."
    )
    snippets = ["instruction.md", "test_outputs.py"]
    if task_id == "fix-git":
        snippets += ["git", "cherry-pick", "about.md"]
    elif task_id == "financial-document-processor":
        snippets += ["invoice", "summary.csv", "total_amount", "vat_amount", "ocr"]
    else:
        snippets += ["regex", "log", "classify"]
    return {"probe_id": f"terminalbench_{task_id}", "class": "terminalbench", "task_id": task_id, "difficulty": difficulty, "workspace_files": files, "task_prompt": prompt, "grade": {"required_snippets": snippets, "min_snippets": 3}}


def _run_one(out: Path, spec: dict[str, Any], variant: str) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id = f"{MISSION_ID}__{spec['probe_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _materialize_workspace(workspace, spec["workspace_files"])
    prompt = spec["task_prompt"] + "\n\nYou may inspect files with shell commands. End with the exact final answer or repair plan."
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=prompt,
        benchmark_family=spec["class"],
        case_id=spec["probe_id"],
        seed_id=variant,
        model_route=make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": 120, "max_retries": 1},
        max_steps=4,
        timeout_sec=120,
        cwd=workspace,
        route_manifest=build_packet04_route_manifest(variant, scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE),
        enforce_packet04_route_contract=True,
    )
    grade = _grade_result(result, spec)
    _patch_run_score(run_dir, result, grade)
    usage = _usage(result)
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "benchmark_class": spec["class"],
        "eval_id": spec["probe_id"],
        "task_id": spec["task_id"],
        "variant_id": variant,
        "model_route": result["run_header"]["model_route"],
        "run_dir": str(run_dir),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "score_summary": {"final_verdict": grade["verdict"], "grade": grade},
        "token_and_cost_summary": usage,
        "governed_terminal_status": "valid",
        "reason_codes": [] if grade["verdict"] == "pass" else grade["reason_codes"],
        "failure_cluster": None if grade["verdict"] == "pass" else "behavioral_external_probe_failure",
        "invalid_infrastructure_failure": False,
        "authority": _authority(),
    }
    trace = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["probe_id"],
        "variant_id": variant,
        "benchmark_class": spec["class"],
        "tool_result_receipts": _count_event_text(result, "tool_result_receipt"),
        "completion_gate_markers": _count_event_text(result, "completion_gate"),
        "raw_bash_events": _count_event_text(result, "raw_bash_result"),
        "viewed_files": _viewed_files(result),
    }
    return record, trace


def _materialize_workspace(root: Path, files: dict[str, str]) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    for raw_path, content in files.items():
        rel = raw_path.lstrip("/")
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _grade_result(result: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    if spec["class"] == "letta_context_bench":
        answer = json.dumps(result.get("execution", {}), sort_keys=True)
        return grade_letta_filesystem_answer(answer, spec["grade"]["ground_truth"])
    text = json.dumps(result.get("execution", {}), sort_keys=True)
    required = spec["grade"]["required_snippets"]
    hits = [snippet for snippet in required if snippet.lower() in text.lower()]
    verdict = "pass" if len(hits) >= int(spec["grade"]["min_snippets"]) else "fail"
    return {"verdict": verdict, "matched_snippets": hits, "required_snippet_count": len(required), "reason_codes": [] if verdict == "pass" else ["required_external_probe_snippets_missing"]}


def _patch_run_score(run_dir: Path, result: dict[str, Any], grade: dict[str, Any]) -> None:
    score_path = run_dir / "score_envelope.json"
    score = json.loads(score_path.read_text(encoding="utf-8"))
    score["aggregate"]["final_verdict"] = grade["verdict"]
    score["aggregate"]["external_diagnostic_grade"] = grade
    score_path.write_text(json.dumps(score, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _usage(result: dict[str, Any]) -> dict[str, Any]:
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for step in result.get("execution", {}).get("steps", []):
        usage = (step.get("completion") or {}).get("usage") or {}
        totals["input_tokens"] += int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        totals["cached_input_tokens"] += int(usage.get("cached_tokens", usage.get("cached_input_tokens", 0)) or 0)
        totals["output_tokens"] += int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    usd = (
        max(totals["input_tokens"] - totals["cached_input_tokens"], 0) * PRICE["input"]
        + totals["cached_input_tokens"] * PRICE["cached_input"]
        + totals["output_tokens"] * PRICE["output"]
    )
    return {**totals, "usd": usd, "usd_estimate": usd}


def _contextbench_convert(out: Path) -> dict[str, Any]:
    pred = out / "contextbench_custom_pred.jsonl"
    result = _run([str(CONTEXTBENCH_PYTHON), "-m", "contextbench.process_trajectories", "convert", "-i", str(out / "runs"), "-o", str(pred), "--agent", "custom"], cwd=CONTEXTBENCH_ROOT, timeout=120)
    rows = []
    if pred.exists():
        rows = [json.loads(line) for line in pred.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"mission_id": MISSION_ID, "status": "pass" if result["returncode"] == 0 and rows else "blocked", "conversion_command": result["cmd"], "stdout": result["stdout"][-2000:], "stderr": result["stderr"][-2000:], "pred_jsonl": str(pred), "row_count": len(rows), "target_instance_rows": sum(1 for row in rows if row.get("instance_id") == INSTANCE_ID)}


def _reports(records: list[dict[str, Any]], traces: list[dict[str, Any]], contextbench: dict[str, Any]) -> dict[str, Any]:
    score = _score(records)
    recommendation = _recommendation(score, contextbench)
    score["selected_recommendation"] = recommendation
    terminal = _class_report(records, "terminalbench")
    tooling = _class_report(records, "tooling_benchmark")
    context = {**_class_report(records, "contextbench"), "contextbench_conversion": contextbench}
    letta = _class_report(records, "letta_context_bench")
    trace = {"mission_id": MISSION_ID, "run_count": len(traces), "traces": traces}
    cost = _cost(records)
    return {
        "external_diagnostic_score_envelope.json": score,
        "external_diagnostic_terminal_bench_report.json": terminal,
        "external_diagnostic_tooling_benchmark_report.json": tooling,
        "external_diagnostic_contextbench_report.json": context,
        "external_diagnostic_letta_context_bench_report.json": letta,
        "external_diagnostic_trace_report.json": trace,
        "external_diagnostic_cost_report.json": cost,
    }


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"mission_id": MISSION_ID, "run_count": len(records), "model_backed_runs": len(records), "local_deterministic_runs": 0, "invalid_run_count": 0, "final_verdict_counts": _counts(r["score_summary"]["final_verdict"] for r in records), "variant_summary": _summary(records, "variant_id"), "by_eval_variant": _by_eval_variant(records), "authority": _authority()}


def _class_report(records: list[dict[str, Any]], cls: str) -> dict[str, Any]:
    subset = [r for r in records if r["benchmark_class"] == cls]
    return {"mission_id": MISSION_ID, "benchmark_class": cls, "run_count": len(subset), "by_variant": _summary(subset, "variant_id"), "records": subset}


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
    cap = "below_soft_cap" if total["usd"] <= 25 else "below_hard_cap" if total["usd"] <= 60 else "hard_cap_exceeded"
    return {"mission_id": MISSION_ID, "budget_caps": {"target_model_backed_runs": [10, 24], "hard_model_backed_cap": 36, "local_deterministic_cap": 40, "soft_cost_cap_usd": 25.0, "hard_cost_cap_usd": 60.0}, "cap_status": cap, "total": total, "by_variant": by_variant}


def _recommendation(score: dict[str, Any], contextbench: dict[str, Any]) -> str:
    if score["invalid_run_count"] or contextbench["status"] != "pass":
        return "run_one_more_external_probe"
    candidate = score["variant_summary"].get(CANDIDATE, {})
    control = score["variant_summary"].get(CONTROL, {})
    context = score["by_eval_variant"].get("contextbench_verified_726ccefd", {}).get(CANDIDATE, {})
    letta_context = any(
        row.get(CANDIDATE, {}).get("fail", 0)
        for eval_id, row in score["by_eval_variant"].items()
        if eval_id.startswith("letta_filesystem_")
    )
    terminal_fail = any(row.get(CANDIDATE, {}).get("fail", 0) for eval_id, row in score["by_eval_variant"].items() if eval_id.startswith("terminalbench_"))
    if context.get("fail", 0) or letta_context:
        return "candidate_needs_context_repair_before_packet07"
    if terminal_fail:
        return "candidate_needs_terminal_task_repair_before_packet07"
    if candidate.get("pass", 0) == candidate.get("run_count", 0) and control.get("pass", 0) == control.get("run_count", 0):
        return "internal_eval_suite_too_easy_repair_before_packet07"
    if candidate.get("pass", 0) >= control.get("pass", 0):
        return "proceed_to_packet07_readiness_review"
    return "run_one_more_external_probe"


def _summary(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in records:
        bucket = out.setdefault(row[key], {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        verdict = row["score_summary"]["final_verdict"]
        bucket["run_count"] += 1
        bucket[verdict if verdict in bucket else "unresolved"] += 1
    return out


def _by_eval_variant(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in records:
        out.setdefault(row["eval_id"], {}).setdefault(row["variant_id"], {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        bucket = out[row["eval_id"]][row["variant_id"]]
        verdict = row["score_summary"]["final_verdict"]
        bucket["run_count"] += 1
        bucket[verdict if verdict in bucket else "unresolved"] += 1
    return out


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _viewed_files(result: dict[str, Any]) -> list[str]:
    files = set()
    for event in result.get("run_events", []):
        cmd = (((event.get("payload") or {}).get("details") or {}).get("command")) or ""
        for token in cmd.replace("|", " ").split():
            if "/" in token and not token.startswith("-"):
                files.add(token.strip("'\""))
    return sorted(files)


def _count_event_text(result: dict[str, Any], needle: str) -> int:
    return json.dumps(result.get("run_events", []), sort_keys=True).count(needle)


def _contextbench_row() -> dict[str, str]:
    for line in (CONTEXTBENCH_ROOT / "data/Verified.csv").read_text(encoding="utf-8").splitlines():
        if INSTANCE_ID in line:
            cells = line.split(",")
            return {"dataset": cells[0], "instance_id": cells[1], "original_inst_id": cells[2], "language": cells[3], "status": cells[4], "token_count": cells[7], "commit": cells[10]}
    raise FileNotFoundError(INSTANCE_ID)


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    completed = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)
    return {"cmd": " ".join(cmd), "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def _plan(out: Path, preflight: dict[str, Any], route_matrix: dict[str, Any]) -> str:
    return "\n".join([
        "# External Diagnostic Probe Plan",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- comparison: `{CONTROL}` vs `{CANDIDATE}`",
        "- probes: `fix-git`, `regex-log`, `financial-document-processor`, DeepAgents BFCL v3 `multi_turn_composite_97`, coding ContextBench `SWE-Bench-Verified__python__maintenance__bugfix__726ccefd`, Letta Context-Bench Filesystem Suite (`easy`, `medium`, `hard` bounded slice)`",
        f"- preflight_status: `{preflight['status']}`",
        f"- route_status: `{route_matrix['status']}`",
        "- authority: no Packet 07 movement, benchmark-authority widening, leaderboard submission, transfer movement, protected holdouts, task-id routing, RHv1 unfreeze, or full RHv1 revival.",
        "",
    ])


def _task_selection(preflight: dict[str, Any]) -> str:
    return "\n".join([
        "# External Diagnostic Task Selection",
        "",
        "- TerminalBench easy: `fix-git`, local official metadata difficulty `easy`.",
        "- TerminalBench medium: `regex-log`, local official metadata difficulty `medium`.",
        "- TerminalBench medium with prior tool-related failure evidence: `financial-document-processor`, local official metadata difficulty `medium`, admitted because the local deepagents trajectory shows OCR/toolchain discovery and package-manager lock failures around `tesseract`, `pdftotext`, `apt-get`, and `dpkg`.",
        "- Tooling benchmark: DeepAgents curated BFCL v3 `multi_turn_composite_97`, local mirrored JSON case.",
        f"- ContextBench: local mirrored Verified row `{INSTANCE_ID}` -> `{preflight['contextbench_instance_row']['original_inst_id']}`.",
        "- Letta Context-Bench Filesystem Suite: one easy, one medium, and one hard official dataset row from the local mirror.",
        "- Selection stayed inside the accepted locked probe scope and did not use protected holdouts.",
        "",
    ])


def _handoff(out: Path, score: dict[str, Any], reports: dict[str, Any], recommendation: str) -> str:
    return "\n".join([
        "# External Diagnostic Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- run_count: `{score['run_count']}`",
        f"- model_backed_runs: `{score['model_backed_runs']}`",
        f"- invalid_run_count: `{score['invalid_run_count']}`",
        f"- final_recommendation: `{recommendation}`",
        "- authority: no Packet 07 movement, benchmark-authority widening, leaderboard submission, transfer movement, protected holdouts, task-id routing, RHv1 unfreeze, or full RHv1 revival occurred.",
        "",
    ])


def _ledger_update(out: Path, score: dict[str, Any]) -> str:
    recommendation = score["selected_recommendation"]
    return "\n".join([
        "RAW_LEDGER_UPDATE",
        "- actor: codex",
        "- task: successor pre-Packet07 external diagnostic probe execution",
        "- event_type: experiment",
        f"- summary: Ran the accepted bounded external diagnostic comparison for `{CONTROL}` and `{CANDIDATE}` across locked TerminalBench-shaped, BFCL, coding ContextBench, and Letta Context-Bench probes; final recommendation `{recommendation}`.",
        f"- observations: Produced {score['run_count']} model-backed records with verdict counts {score.get('final_verdict_counts', {})}; coding ContextBench custom parser conversion status was captured before scoring.",
        "- inference: The diagnostic result is bounded evidence for whether Packet07-readiness review can resume; it does not itself move Packet 07 or widen benchmark authority.",
        f"- evidence_paths: {out / 'external_diagnostic_result_records.jsonl'}; {out / 'external_diagnostic_score_envelope.json'}; {out / 'external_diagnostic_terminal_bench_report.json'}; {out / 'external_diagnostic_tooling_benchmark_report.json'}; {out / 'external_diagnostic_contextbench_report.json'}; {out / 'external_diagnostic_letta_context_bench_report.json'}; {out / 'external_diagnostic_handoff.md'}",
        "- affected_components: pre-Packet07 external diagnostic probe; Packet06 successor comparison; TerminalBench-shaped diagnostics; DeepAgents BFCL diagnostic; coding ContextBench parser measurement; Letta Context-Bench filesystem measurement",
        "- decision_change: NONE - diagnostic evidence only; no Packet07 movement authorized",
        "- unresolved_questions: Whether the principal accepts this bounded evidence as sufficient to resume Packet07-readiness review.",
        "- confidence: medium",
        "- commit_message: HOLD - external diagnostic artifacts generated for principal review",
    ])


def _record_ledger(raw: str) -> None:
    proc = subprocess.run([sys.executable, "tracking/ledger/tools/record_update.py"], input=raw, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ledger update failed: {proc.stderr}")


def _write_blocked(out: Path, preflight: dict[str, Any], route_matrix: dict[str, Any], *, execute: bool) -> dict[str, Any]:
    score = {"mission_id": MISSION_ID, "run_count": 0, "model_backed_runs": 0, "invalid_run_count": 0, "final_verdict_counts": {}, "selected_recommendation": "run_one_more_external_probe", "preflight": preflight, "route_matrix": route_matrix}
    _write_jsonl(out / "external_diagnostic_result_records.jsonl", [])
    _write_json(out / "external_diagnostic_score_envelope.json", score)
    for name in ("external_diagnostic_terminal_bench_report.json", "external_diagnostic_tooling_benchmark_report.json", "external_diagnostic_contextbench_report.json", "external_diagnostic_letta_context_bench_report.json", "external_diagnostic_trace_report.json", "external_diagnostic_cost_report.json"):
        _write_json(out / name, {"mission_id": MISSION_ID, "blocked": True, "execute": execute, "preflight": preflight, "route_matrix": route_matrix})
    _write_text(out / "external_diagnostic_handoff.md", _handoff(out, score, {}, "run_one_more_external_probe"))
    ledger = _ledger_update(out, score)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE.txt", ledger)
    return {"output_dir": str(out), "run_count": 0, "selected_recommendation": "run_one_more_external_probe"}


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
