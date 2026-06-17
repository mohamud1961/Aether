#!/usr/bin/env python3
"""Render deterministic final-board scoreboard outputs from synthetic row statuses."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ALLOWED_ROW_STATUS = {"pass", "fail", "invalid"}
ALLOWED_STABILITY_GATE = {"pass", "fail", "not_run"}
ALLOWED_COST_STEP_GATE = {"pass", "warn", "fail"}
PLACEHOLDER_RECIPE_IDS = {"recipe_control", "recipe_candidate_a", "recipe_candidate_b"}
RANKING_TIEBREAK_ORDER = [
    "higher_hard_task_pass_count",
    "stronger_critical_cluster_coverage",
    "better_stability_consistency",
    "lower_contamination_invalidity_risk",
    "lower_cost_step_profile",
    "lower_composition_risk_complexity",
]


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:  # pragma: no cover
        cmd = [
            "ruby",
            "-ryaml",
            "-rjson",
            "-e",
            "puts JSON.dump(YAML.load_file(ARGV[0]))",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)
    else:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a YAML mapping")
    return payload


def _registry_view(registry: dict[str, Any]) -> dict[str, Any]:
    hard_rows = [str(item["row_id"]) for item in registry.get("hard_rows", []) if isinstance(item, dict)]
    sentinel_rows = [
        str(item["row_id"])
        for item in registry.get("sentinel_or_composition_rows", [])
        if isinstance(item, dict)
    ]
    flagships = [str(item) for item in registry.get("flagship_row_ids", [])]
    critical_cluster_map = registry.get("critical_cluster_map", {})
    required_clusters = [str(item) for item in registry.get("required_critical_clusters", [])]
    if not hard_rows or not sentinel_rows:
        raise ValueError("final suite registry must define hard and sentinel/composition rows")
    return {
        "board_id": str(registry.get("board_id", "final_harness_eval_suite_v1")),
        "board_version": int(registry.get("board_version", 1)),
        "hard_rows": hard_rows,
        "sentinel_rows": sentinel_rows,
        "flagships": flagships,
        "required_clusters": required_clusters,
        "critical_cluster_map": critical_cluster_map,
        "required_rows": hard_rows + sentinel_rows,
    }


def _normalize_row_statuses(recipe: dict[str, Any], required_row_ids: list[str]) -> dict[str, str]:
    row_statuses = recipe.get("row_statuses")
    if isinstance(row_statuses, dict):
        normalized = {str(key): str(value) for key, value in row_statuses.items()}
    else:
        normalized = {}
        rows = recipe.get("rows", [])
        if isinstance(rows, list):
            for item in rows:
                if isinstance(item, dict):
                    normalized[str(item.get("row_id", ""))] = str(item.get("status", ""))
    missing = [row_id for row_id in required_row_ids if row_id not in normalized]
    for row_id in missing:
        normalized[row_id] = "invalid"
    for row_id, status in list(normalized.items()):
        if status not in ALLOWED_ROW_STATUS:
            normalized[row_id] = "invalid"
    return normalized


def _cluster_coverage(row_statuses: dict[str, str], cluster_map: dict[str, Any]) -> tuple[dict[str, bool], int]:
    coverage: dict[str, bool] = {}
    for cluster, mapping in cluster_map.items():
        row_ids: list[str] = []
        if isinstance(mapping, dict):
            for key in ("hard_rows", "sentinel_or_composition_rows", "row_ids"):
                value = mapping.get(key)
                if isinstance(value, list):
                    row_ids.extend(str(item) for item in value)
        coverage[str(cluster)] = any(row_statuses.get(row_id) == "pass" for row_id in row_ids)
    return coverage, sum(1 for covered in coverage.values() if covered)


def _evaluate_recipe(recipe: dict[str, Any], view: dict[str, Any], allow_pre_stability: bool) -> dict[str, Any]:
    recipe_id = str(recipe.get("recipe_id", "")).strip() or "unknown_recipe"
    row_statuses = _normalize_row_statuses(recipe, view["required_rows"])
    sentinel_statuses = [row_statuses[row_id] for row_id in view["sentinel_rows"]]
    flagship_statuses = [row_statuses[row_id] for row_id in view["flagships"]]
    hard_statuses = [row_statuses[row_id] for row_id in view["hard_rows"]]

    sentinel_gate = "invalid" if "invalid" in sentinel_statuses else ("pass" if all(v == "pass" for v in sentinel_statuses) else "fail")
    flagship_gate = "invalid" if "invalid" in flagship_statuses else ("pass" if all(v == "pass" for v in flagship_statuses) else "fail")
    hard_task_pass_count = sum(1 for value in hard_statuses if value == "pass")
    hard_task_gate = "pass" if hard_task_pass_count >= 6 else "fail"

    coverage, coverage_count = _cluster_coverage(row_statuses, view["critical_cluster_map"])
    required_clusters = view["required_clusters"]
    critical_cluster_gate = "pass" if all(coverage.get(cluster, False) for cluster in required_clusters) else "fail"

    contamination = recipe.get("contamination", {})
    contaminated_row_ids = set(contamination.get("contaminated_row_ids", [])) if isinstance(contamination, dict) else set()
    suspect_excluded_row_ids = (
        set(contamination.get("unresolved_suspect_excluded_row_ids", [])) if isinstance(contamination, dict) else set()
    )
    contamination_hit = {
        row_id for row_id in view["required_rows"] if row_id in contaminated_row_ids or row_id in suspect_excluded_row_ids
    }
    contamination_gate = "fail" if contamination_hit else "pass"

    invalidity = recipe.get("invalidity", {})
    unresolved_invalid = set(invalidity.get("unresolved_invalid_row_ids", [])) if isinstance(invalidity, dict) else set()
    required_invalid_rows = {row_id for row_id in view["required_rows"] if row_statuses.get(row_id) == "invalid"}
    invalidity_hit = required_invalid_rows | {row_id for row_id in unresolved_invalid if row_id in view["required_rows"]}
    invalidity_gate = "fail" if invalidity_hit else "pass"

    stability = recipe.get("stability", {})
    stability_gate = "not_run"
    stability_consistency = 0.0
    if isinstance(stability, dict):
        candidate = str(stability.get("status", "not_run"))
        if candidate in ALLOWED_STABILITY_GATE:
            stability_gate = candidate
        score = stability.get("consistency_score")
        if isinstance(score, (int, float)):
            stability_consistency = float(score)
    if stability_gate == "pass" and stability_consistency <= 0:
        stability_consistency = 1.0
    if stability_gate != "pass":
        stability_consistency = 0.0

    cost_step_gate = str(recipe.get("cost_step_gate", "pass"))
    if cost_step_gate not in ALLOWED_COST_STEP_GATE:
        cost_step_gate = "warn"
    composition_risk_complexity = recipe.get("composition_risk_complexity", 0)
    if not isinstance(composition_risk_complexity, int):
        composition_risk_complexity = 0

    gate_trace = [
        {"gate": "sentinel_gate", "status": sentinel_gate},
        {"gate": "flagship_gate", "status": flagship_gate},
        {"gate": "hard_task_gate", "status": hard_task_gate},
        {"gate": "critical_cluster_gate", "status": critical_cluster_gate},
        {"gate": "contamination_gate", "status": contamination_gate},
        {"gate": "invalidity_gate", "status": invalidity_gate},
        {"gate": "stability_gate", "status": stability_gate},
    ]
    gate_pass_before_stability = all(
        gate["status"] == "pass" for gate in gate_trace if gate["gate"] != "stability_gate"
    )

    if sentinel_gate == "invalid" or flagship_gate == "invalid" or invalidity_hit:
        verdict = "invalid"
    elif gate_pass_before_stability and (stability_gate == "pass" or (allow_pre_stability and stability_gate == "not_run")):
        verdict = "finalist_eligible"
    else:
        verdict = "not_eligible"

    contamination_risk = len(contamination_hit)
    invalidity_risk = len(invalidity_hit)
    cost_score = {"pass": 0, "warn": 1, "fail": 2}[cost_step_gate]
    ranking_key = (
        -hard_task_pass_count,
        -coverage_count,
        -stability_consistency,
        contamination_risk + invalidity_risk,
        cost_score,
        composition_risk_complexity,
        recipe_id,
    )

    return {
        "recipe_id": recipe_id,
        "sentinel_gate": sentinel_gate,
        "flagship_gate": flagship_gate,
        "hard_task_pass_count": hard_task_pass_count,
        "hard_task_gate": hard_task_gate,
        "critical_cluster_gate": critical_cluster_gate,
        "contamination_gate": contamination_gate,
        "invalidity_gate": invalidity_gate,
        "stability_gate": stability_gate,
        "cost_step_gate": cost_step_gate,
        "admission_verdict": verdict,
        "finalist_rank": None,
        "known_weaknesses": list(recipe.get("known_weaknesses", [])),
        "evidence_refs": list(recipe.get("evidence_refs", [])),
        "cluster_coverage": coverage,
        "cluster_coverage_count": coverage_count,
        "contamination_risk_count": contamination_risk,
        "invalidity_risk_count": invalidity_risk,
        "stability_consistency": stability_consistency,
        "composition_risk_complexity": composition_risk_complexity,
        "ranking_key": ranking_key,
        "gate_trace": gate_trace,
    }


def render_scoreboard(payload: dict[str, Any], view: dict[str, Any], *, allow_pre_stability: bool) -> dict[str, Any]:
    recipes = payload.get("recipes", [])
    if not isinstance(recipes, list):
        raise ValueError("input payload must contain recipes: []")
    evaluated = [_evaluate_recipe(item, view, allow_pre_stability) for item in recipes if isinstance(item, dict)]

    eligible = sorted(
        (item for item in evaluated if item["admission_verdict"] == "finalist_eligible"),
        key=lambda item: item["ranking_key"],
    )
    for idx, item in enumerate(eligible, start=1):
        item["finalist_rank"] = idx
    for item in evaluated:
        item.pop("ranking_key", None)

    scoreboard = {
        "schema_version": "final_harness_scoreboard_stub.v1",
        "run_id": str(payload.get("run_id", "synthetic_scoreboard_run")),
        "board_id": view["board_id"],
        "board_version": view["board_version"],
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "allow_pre_stability_eligibility": allow_pre_stability,
        "ranking_tiebreak_order": RANKING_TIEBREAK_ORDER,
        "recipes": sorted(evaluated, key=lambda item: item["recipe_id"]),
        "finalists": [{"recipe_id": item["recipe_id"], "finalist_rank": item["finalist_rank"]} for item in eligible],
    }
    cost_summary = payload.get("cost_summary")
    if isinstance(cost_summary, dict):
        scoreboard["cost_summary"] = cost_summary
    return scoreboard


def _scoreboard_markdown(scoreboard: dict[str, Any]) -> str:
    lines = [
        "# Final Harness Scoreboard",
        "",
        f"- run_id: `{scoreboard['run_id']}`",
        f"- board: `{scoreboard['board_id']}` v{scoreboard['board_version']}",
        f"- generated_at_utc: `{scoreboard['generated_at_utc']}`",
        "",
        "| recipe_id | verdict | sentinel | flagship | hard(pass/8) | cluster | contam | invalidity | stability | rank |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in scoreboard["recipes"]:
        lines.append(
            "| {recipe_id} | {admission_verdict} | {sentinel_gate} | {flagship_gate} | {hard_task_pass_count}/8 ({hard_task_gate}) | "
            "{critical_cluster_gate} | {contamination_gate} | {invalidity_gate} | {stability_gate} | {finalist_rank} |".format(
                recipe_id=item["recipe_id"],
                admission_verdict=item["admission_verdict"],
                sentinel_gate=item["sentinel_gate"],
                flagship_gate=item["flagship_gate"],
                hard_task_pass_count=item["hard_task_pass_count"],
                hard_task_gate=item["hard_task_gate"],
                critical_cluster_gate=item["critical_cluster_gate"],
                contamination_gate=item["contamination_gate"],
                invalidity_gate=item["invalidity_gate"],
                stability_gate=item["stability_gate"],
                finalist_rank=item["finalist_rank"] if item["finalist_rank"] is not None else "-",
            )
        )
    lines.extend(["", "Ranking tie-break order:", ""])
    for rule in scoreboard["ranking_tiebreak_order"]:
        lines.append(f"- {rule}")
    cost_summary = scoreboard.get("cost_summary")
    if isinstance(cost_summary, dict):
        lines.extend(["", "Cost summary:", "", "```json", json.dumps(cost_summary, indent=2, sort_keys=True), "```"])
    return "\n".join(lines) + "\n"


def write_scoreboard_outputs(scoreboard: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scoreboard_json = output_dir / "scoreboard.json"
    scoreboard_md = output_dir / "scoreboard.md"
    scoreboard_json.write_text(json.dumps(scoreboard, indent=2) + "\n", encoding="utf-8")
    scoreboard_md.write_text(_scoreboard_markdown(scoreboard), encoding="utf-8")
    return scoreboard_json, scoreboard_md


def write_finalist_selection(scoreboard: dict[str, Any], output_path: Path, *, allow_placeholder: bool) -> Path:
    finalists = list(scoreboard.get("finalists", []))
    placeholder_only = finalists and all(item["recipe_id"] in PLACEHOLDER_RECIPE_IDS for item in finalists)
    if placeholder_only and not allow_placeholder:
        finalists = []
    lines = [
        "# Finalist Selection",
        "",
        "Board-local deterministic output from scoreboard stub.",
        "",
        f"- run_id: `{scoreboard['run_id']}`",
        f"- board: `{scoreboard['board_id']}` v{scoreboard['board_version']}",
        "",
        "## Selected Finalists",
        "",
    ]
    if finalists:
        for item in finalists[:2]:
            lines.append(f"- `{item['recipe_id']}` (rank {item['finalist_rank']})")
    else:
        lines.append("- none selected")
    if placeholder_only and not allow_placeholder:
        lines.extend(
            [
                "",
                "## Deferred / Blocked",
                "",
                "- Placeholder recipe ids were detected; rerun with non-placeholder candidates before finalist claims.",
            ]
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Synthetic scoreboard input JSON")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for scoreboard files")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("tracking/collab/final_harness_eval_suite/final_suite_registry.yaml"),
        help="Final suite registry path",
    )
    parser.add_argument(
        "--allow-pre-stability-eligibility",
        action="store_true",
        help="Permit finalist_eligible verdicts when stability gate is not_run (screening-only mode).",
    )
    parser.add_argument(
        "--update-finalist-selection",
        type=Path,
        help="Optional path to write finalist_selection.md. Omit to keep placeholders unchanged.",
    )
    parser.add_argument(
        "--allow-placeholder-finalists",
        action="store_true",
        help="Allow placeholder recipe ids in finalist_selection output when update is requested.",
    )
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("--input JSON must contain an object")
    view = _registry_view(_load_yaml(args.registry))
    scoreboard = render_scoreboard(
        payload,
        view,
        allow_pre_stability=args.allow_pre_stability_eligibility,
    )
    scoreboard_json, scoreboard_md = write_scoreboard_outputs(scoreboard, args.output_dir)
    print(str(scoreboard_json))
    print(str(scoreboard_md))
    if args.update_finalist_selection:
        path = write_finalist_selection(
            scoreboard,
            args.update_finalist_selection,
            allow_placeholder=args.allow_placeholder_finalists,
        )
        print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
