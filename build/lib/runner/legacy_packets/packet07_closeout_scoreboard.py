"""Normalize Packet 07 closeout evidence into minimal append-only scoreboard rows."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from runner.schemas import utc_now

PACKET_ID = "packet_07"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_closeout_scoreboard"
)
DEFAULT_GOLDEN = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_golden_diagnostic_execute/packet07_golden_diagnostic_result_records.jsonl"
)
DEFAULT_FAIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_golden_diagnostic_fair_rerun/result_records.jsonl"
)
DEFAULT_HARD_MINI = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_hard_letta_extension/packet07_hard_letta_extension_result_records.jsonl"
)
DEFAULT_HARD_CODEX = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_hard_letta_extension_codex/packet07_hard_letta_extension_codex_result_records.jsonl"
)
REQUIRED_FIELDS = [
    "timestamp",
    "packet_id",
    "run_id",
    "eval_id",
    "benchmark_family",
    "variant_id",
    "model_id",
    "max_steps",
    "environment_flags",
    "score",
    "verdict",
    "final_answer",
    "ground_truth",
    "failure_class",
    "step_count",
    "tool_call_count",
    "trace_path",
    "grader_path_or_id",
    "notes",
]
ARM_GROUPS = {
    "golden": {"current_conditions": "current_conditions"},
    "fair": {"main_12": "fair_runtime_main", "rerun_7": "fair_runtime_confirm"},
    "hard_mini": {"main_25": "hard_extension_main", "rerun_15": "hard_extension_confirm"},
    "hard_codex": {"main_25": "hard_extension_main", "rerun_15": "hard_extension_confirm"},
}
DATE_PATTERN = re.compile(r"(20\d{2}-\d{2}-\d{2})")


def launch_packet07_closeout_scoreboard(
    *,
    output_dir: str | Path,
    golden_records: str | Path = DEFAULT_GOLDEN,
    fair_records: str | Path = DEFAULT_FAIR,
    hard_mini_records: str | Path = DEFAULT_HARD_MINI,
    hard_codex_records: str | Path = DEFAULT_HARD_CODEX,
    bfcl_records: tuple[str | Path, ...] = (),
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    source_specs = [
        ("golden", Path(golden_records)),
        ("fair", Path(fair_records)),
        ("hard_mini", Path(hard_mini_records)),
        ("hard_codex", Path(hard_codex_records)),
    ]
    normalized: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []
    for source_name, source_path in source_specs:
        raw_rows = _read_jsonl(source_path)
        kept = 0
        for row in raw_rows:
            group = ARM_GROUPS[source_name].get(str(row.get("arm_id", "")))
            if group is None:
                continue
            normalized.append(_normalize_row(row, source_path, group=group, source_name=source_name))
            kept += 1
        source_manifest.append({"source": source_name, "path": str(source_path.resolve()), "raw_rows": len(raw_rows), "kept_rows": kept})
    for bfcl_path_text in bfcl_records:
        bfcl_path = Path(bfcl_path_text)
        raw_rows = _read_jsonl(bfcl_path)
        for row in raw_rows:
            normalized.append(_normalize_row(row, bfcl_path, group="bfcl_sentinel_legacy", source_name="bfcl"))
        source_manifest.append({"source": "bfcl", "path": str(bfcl_path.resolve()), "raw_rows": len(raw_rows), "kept_rows": len(raw_rows)})
    rows_path = out / "packet07_minimal_scoreboard_rows.jsonl"
    summary_path = out / "packet07_score_summary_table.json"
    route_path = out / "packet07_route_keep_kill_defer_table.json"
    manifest_path = out / "packet07_scoreboard_manifest.json"
    _write_jsonl(rows_path, normalized)
    _write_json(summary_path, _score_summary(normalized))
    _write_json(route_path, _route_table(normalized))
    _write_json(
        manifest_path,
        {
            "packet_id": PACKET_ID,
            "generated_at_utc": utc_now(),
            "row_count": len(normalized),
            "source_manifest": source_manifest,
            "required_fields": REQUIRED_FIELDS,
            "outputs": {
                "packet07_minimal_scoreboard_rows_jsonl": str(rows_path),
                "packet07_score_summary_table_json": str(summary_path),
                "packet07_route_keep_kill_defer_table_json": str(route_path),
                "packet07_scoreboard_manifest_json": str(manifest_path),
            },
        },
    )
    return {"output_dir": str(out), "row_count": len(normalized), "manifest_path": str(manifest_path)}


def _normalize_row(row: dict[str, Any], source_path: Path, *, group: str, source_name: str) -> dict[str, Any]:
    verdict = _verdict(row)
    arm_id = str(row.get("arm_id", ""))
    tool_commands = row.get("tool_commands")
    tool_call_count = row.get("tool_call_count") if isinstance(row.get("tool_call_count"), int) else len(tool_commands) if isinstance(tool_commands, list) else None
    out = {
        "timestamp": str(row.get("timestamp") or _timestamp_from_path(source_path)),
        "packet_id": PACKET_ID,
        "run_id": str(row.get("run_id", "")),
        "eval_id": str(row.get("eval_id", "")),
        "benchmark_family": _benchmark_family(row),
        "variant_id": str(row.get("variant_id", "")),
        "model_id": str(row.get("model_id") or row.get("model_route", {}).get("model_name") or ""),
        "max_steps": int(row.get("max_steps", 0) or 0),
        "environment_flags": row.get("environment_flags") if isinstance(row.get("environment_flags"), dict) else {},
        "score": 1.0 if verdict == "pass" else 0.0,
        "verdict": verdict,
        "final_answer": str(row.get("final_answer") or ""),
        "ground_truth": row.get("exact_grade", {}).get("ground_truth"),
        "failure_class": str(row.get("failure_class") or row.get("root_cause_classification") or row.get("failure_cluster") or ""),
        "step_count": int(row.get("step_count", 0) or 0),
        "tool_call_count": tool_call_count,
        "trace_path": str(row.get("trace_path") or ""),
        "grader_path_or_id": str(row.get("grader_path_or_id") or row.get("grader_id") or row.get("task_id") or row.get("eval_id") or ""),
        "notes": f"row_group={group};source={source_name};arm_id={arm_id}",
        "row_group": group,
    }
    for field in REQUIRED_FIELDS:
        out.setdefault(field, None)
    return out


def _verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("scoreboard_verdict")
        or row.get("score_summary", {}).get("final_verdict")
        or row.get("exact_grade", {}).get("verdict")
        or "unknown"
    )


def _benchmark_family(row: dict[str, Any]) -> str:
    if row.get("benchmark_family"):
        return str(row["benchmark_family"])
    eval_id = str(row.get("eval_id", ""))
    return "bfcl" if eval_id.startswith("bfcl_") else "letta_context_bench" if eval_id.startswith("letta_") else "unknown"


def _timestamp_from_path(path: Path) -> str:
    match = DATE_PATTERN.search(str(path))
    return f"{match.group(1)}T00:00:00Z" if match else utc_now()


def _score_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[str, dict[str, int]] = {}
    by_variant: dict[str, dict[str, Any]] = {}
    for row in rows:
        group = str(row.get("row_group", "unknown"))
        verdict = str(row.get("verdict", "unknown"))
        variant = str(row.get("variant_id", ""))
        by_group.setdefault(group, {"run_count": 0, "pass": 0, "fail": 0, "invalid": 0})["run_count"] += 1
        if verdict in {"pass", "fail", "invalid"}:
            by_group[group][verdict] += 1
        bucket = by_variant.setdefault(variant, {"run_count": 0, "pass": 0, "score_sum": 0.0})
        bucket["run_count"] += 1
        bucket["pass"] += 1 if verdict == "pass" else 0
        bucket["score_sum"] += float(row.get("score", 0.0) or 0.0)
    for bucket in by_variant.values():
        runs = int(bucket["run_count"] or 0)
        bucket["pass_rate"] = (bucket["pass"] / runs) if runs else 0.0
        bucket["mean_score"] = (bucket["score_sum"] / runs) if runs else 0.0
    return {"packet_id": PACKET_ID, "row_count": len(rows), "by_group": by_group, "by_variant": by_variant}


def _route_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_variant.setdefault(str(row.get("variant_id", "")), []).append(row)
    decisions: list[dict[str, Any]] = []
    for variant, scoped in sorted(by_variant.items()):
        groups = {str(row.get("row_group", "")) for row in scoped}
        has_confirm_fail = any(row.get("row_group") in {"fair_runtime_confirm", "hard_extension_confirm", "bfcl_sentinel_legacy"} and row.get("verdict") != "pass" for row in scoped)
        all_pass = all(row.get("verdict") == "pass" for row in scoped)
        decision = "kill" if has_confirm_fail else "keep" if all_pass and {"current_conditions", "fair_runtime_main", "hard_extension_main"} <= groups else "defer"
        decisions.append({"variant_id": variant, "decision": decision, "row_count": len(scoped), "groups_covered": sorted(groups)})
    return {"packet_id": PACKET_ID, "rows": decisions}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--golden-records", default=str(DEFAULT_GOLDEN))
    parser.add_argument("--fair-records", default=str(DEFAULT_FAIR))
    parser.add_argument("--hard-mini-records", default=str(DEFAULT_HARD_MINI))
    parser.add_argument("--hard-codex-records", default=str(DEFAULT_HARD_CODEX))
    parser.add_argument("--bfcl-records", action="append", default=[])
    args = parser.parse_args()
    launch_packet07_closeout_scoreboard(
        output_dir=args.output_dir,
        golden_records=args.golden_records,
        fair_records=args.fair_records,
        hard_mini_records=args.hard_mini_records,
        hard_codex_records=args.hard_codex_records,
        bfcl_records=tuple(args.bfcl_records),
    )


if __name__ == "__main__":
    main()
