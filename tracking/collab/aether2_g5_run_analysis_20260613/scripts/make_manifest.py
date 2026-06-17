#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter

OUT = Path("tracking/collab/aether2_g5_run_analysis_20260613")
BUNDLE = ("tracking/collab/vm_pulls/tracking/collab/"
          "aether2_g5_failure_analysis_clean_20260613T121431Z")

rows = [json.loads(l) for l in (OUT / "normalized_attempt_rows.jsonl").read_text().splitlines()]
a1 = [r for r in rows if r["attempt"] == 1]
a2 = [r for r in rows if r["attempt"] == 2]


def vc(rs):
    return dict(Counter(r["validity_status"] for r in rs))


manifest = {
    "analysis_name": "aether2_g5_run_analysis_20260613",
    "analysis_date": "2026-06-13",
    "goal_objective": (
        "Analyze the frozen Aether-2 full-tournament evidence, establish trustworthy scored "
        "outcomes and failure classifications, identify the highest-value eval-governed G5 "
        "failure lane, and produce an evidence-backed recommendation without implementing a "
        "mechanism or starting another run."),
    "review_gate": "adversarial_only",
    "final_status": "READY_FOR_BOUNDED",
    "evidence_bundle": BUNDLE,
    "evidence_bundle_frozen_utc": "2026-06-13T12:14:31Z",
    "full_root_on_vm": "tracking/collab/aether2_full_tournament/full_twice_20260612T200830Z",
    "input_paths_analyzed": [
        f"{BUNDLE}/FREEZE_MARKER.txt",
        f"{BUNDLE}/file_manifest.txt",
        f"{BUNDLE}/error_grep.txt (index only)",
        f"{BUNDLE}/progress.tsv",
        f"{BUNDLE}/score_summary.txt (not trusted)",
        f"{BUNDLE}/resume_full_twice.sh",
        f"{BUNDLE}/rows/attempt1_rows_combined.jsonl",
        f"{BUNDLE}/rows/attempt2_rows_combined.jsonl (0 bytes)",
        f"{BUNDLE}/scoreboards/ (24 attempt_1)",
        f"{BUNDLE}/logs/ (482 per-task + master/autorestart/resume_nohup)",
        f"{BUNDLE}/source_snapshot/tools/run_aether2_g3_official.py",
        f"{BUNDLE}/source_snapshot/runner/aether2/",
        "AGENTS.md",
        "tracking/collab/aether2_build_spec/AETHER2_BUILD_SPEC.md (G5, §13, §15, §16)",
    ],
    "output_files": [
        "README.md", "evidence_inventory.md", "normalized_attempt_rows.jsonl",
        "outcome_scoreboard.md", "failure_taxonomy.md", "task_findings.md",
        "prediction_audit.md", "g5_lane_recommendation.md", "next_goal_prompt.md",
        "analysis_manifest.json",
        "scripts/parse_rows.py", "scripts/parse_rows_v2.py", "scripts/crossref.py",
        "scripts/build_normalized_rows.py", "scripts/atlas_dump.py", "scripts/make_manifest.py",
    ],
    "counts": {
        "distinct_task_ids": 241,
        "total_attempts": len(rows),
        "attempt1": {
            "n": len(a1),
            "validity": vc(a1),
            "authoritative_rows_captured": sum(1 for r in a1 if r["has_authoritative_row"]),
            "authoritative_passes": sum(1 for r in a1 if r["authoritative_pass"] is True),
            "pass_tasks": [r["task_id"] for r in a1 if r["authoritative_pass"] is True],
            "pass_rate_valid_scored": "5/19 = 26.32%",
            "pass_rate_captured": "5/24 = 20.83%",
            "pass_rate_all_attempt_naive": "5/241 = 2.07% (misleading)",
            "reach_grader_rate": "24/241 = 10%",
        },
        "attempt2": {
            "n": len(a2),
            "validity": vc(a2),
            "authoritative_rows_captured": 0,
            "authoritative_passes": 0,
            "status": "CONTAMINATED — not scoreable",
        },
        "invalid_launch_total_both_attempts": sum(
            1 for r in rows if r["validity_status"].startswith("INVALID_LAUNCH")),
    },
    "root_cause": {
        "family": "F1 environment/runtime — harness launch/import-path collapse",
        "signature": "ModuleNotFoundError: No module named 'runner' at run_aether2_g3_official.py:30",
        "trigger": "VM reboot ~12:05 UTC -> autorestart relaunched tournament without repo root on sys.path/PYTHONPATH",
        "affected_attempts": 457,
        "confidence": "HIGH",
    },
    "predictions": {
        "qemu-startup_pass_le12_calls": "INSUFFICIENT_EVIDENCE (import-crash tail; no row)",
        "extract-moves-from-video_flip": "INSUFFICIENT_EVIDENCE (import-crash tail; no row)",
        "install-windows-3.11_flip": "INSUFFICIENT_EVIDENCE (import-crash tail; no row)",
        "video-processing": "NOT DIAGNOSABLE here (import-crash tail; no row)",
        "cache_hit_ratio_ge80": "SUPPORTED — pooled 88.4%, 13/21 rows >=80% (easier subset only)",
        "fresh_tokens_le150k_per_hard_task": "SUPPORTED — hard tasks 61,499 and 17,806 (n=2)",
    },
    "selected_g5_lane": "L1 — eval-substrate launch integrity + valid n=2 re-baseline (environment/runtime repair)",
    "limitations": [
        "Authoritative grader rows cover only 24/241 Attempt-1 tasks and 0/241 Attempt-2 tasks.",
        "True 241-task capability pass rate is INSUFFICIENT_EVIDENCE (216/241 A1 + all A2 never ran).",
        "loop_result.grader_reward is null in every captured row; authoritative verdict derived from row_status/verifier_exit_code.",
        "G3-calibration rows for qemu-startup/extract-moves/install-windows referenced in manifest but NOT in bundle.",
        "Per-task model route, and per-row cost (cost=0.0 placeholder), are not populated.",
        "Capability families F2-F5 rest on 6-14 rows of a 95%-invalid run; not actionable without a valid baseline.",
        "Exact launch-env variable that broke `import runner` is inferred, not directly evidenced (no launch-env capture in bundle).",
        "Exit-127 (F5) ambiguity (agent vs grader-design fault) unresolved: run-tests.sh source not in bundle.",
    ],
    "implementation_or_new_runs_performed": "NONE (analysis only; bundle untouched)",
    "process_container_or_vm_left_running": "NONE by this analysis (read-only on local frozen copy)",
}

(OUT / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2))
print("wrote analysis_manifest.json")
print(json.dumps(manifest["counts"], indent=2))
