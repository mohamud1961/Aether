#!/usr/bin/env python3
"""Extract AUTHORITATIVE top-level grader fields + advisory fields per row.

Authoritative external grader = top-level: row_status, verifier_exit_code,
timed_out, reason, wall_time_sec, verifier_stdout_tail/stderr_tail.
Advisory verifier = loop_result.verifier_clean / discrepancy_reports.
loop_result.grader_reward is null in every captured row (verified).
"""
import json
import re
from pathlib import Path
from collections import Counter

BUNDLE = Path(
    "tracking/collab/vm_pulls/tracking/collab/"
    "aether2_g5_failure_analysis_clean_20260613T121431Z"
)


def parse_combined(path: Path):
    text = path.read_text()
    if not text.strip():
        return []
    parts = re.split(r"^### FILE: (.+)$", text, flags=re.MULTILINE)
    records = []
    it = iter(parts[1:])
    for marker, body in zip(it, it):
        try:
            obj = json.loads(body.strip())
        except json.JSONDecodeError as e:
            records.append({"_file": marker.strip(), "_parse_error": str(e)})
            continue
        records.append({"_file": marker.strip(), "_obj": obj})
    return records


def path_fields(marker: str):
    m = re.search(r"attempt_(\d+)/([0-9TZ]+)/([^/]+)/row\.json", marker)
    if m:
        return int(m.group(1)), m.group(2), m.group(3)
    return None, None, None


def short(s, n=120):
    if s is None:
        return None
    s = str(s).replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + "..."


a1 = parse_combined(BUNDLE / "rows" / "attempt1_rows_combined.jsonl")
print(f"parsed {len(a1)} attempt-1 row blocks\n")

rows = []
for r in a1:
    att, ts, task = path_fields(r["_file"])
    o = r.get("_obj", {})
    lr = o.get("loop_result") if isinstance(o.get("loop_result"), dict) else None
    rec = {
        "task_id": task, "attempt": att, "ts": ts,
        "row_status": o.get("row_status"),
        "verifier_exit_code": o.get("verifier_exit_code"),
        "timed_out": o.get("timed_out"),
        "reason": o.get("reason"),
        "wall_time_sec": o.get("wall_time_sec"),
        "difficulty": o.get("difficulty"),
        "category": o.get("category"),
        "has_loop_result": lr is not None,
        "grader_reward": (lr or {}).get("grader_reward"),
        "verifier_clean": (lr or {}).get("verifier_clean"),
        "finalize_reason": (lr or {}).get("finalize_reason"),
        "model_calls": (lr or {}).get("model_calls"),
        "steps": (lr or {}).get("steps"),
        "tokens_fresh": (lr or {}).get("tokens_fresh"),
        "tokens_cached": (lr or {}).get("tokens_cached"),
        "verifier_stdout_tail": short(o.get("verifier_stdout_tail")),
        "verifier_stderr_tail": short(o.get("verifier_stderr_tail")),
        "details": short(o.get("details"), 200),
    }
    rows.append(rec)

# Print authoritative table
cols = ["task_id", "row_status", "verifier_exit_code", "timed_out", "reason",
        "verifier_clean", "finalize_reason", "wall_time_sec"]
print("\t".join(cols))
for r in rows:
    print("\t".join(short(str(r.get(c)), 40) for c in cols))

print("\n=== DISTRIBUTIONS (24 captured attempt-1 rows) ===")
print("row_status:", dict(Counter(str(r["row_status"]) for r in rows)))
print("verifier_exit_code:", dict(Counter(str(r["verifier_exit_code"]) for r in rows)))
print("timed_out:", dict(Counter(str(r["timed_out"]) for r in rows)))
print("reason:", dict(Counter(str(r["reason"]) for r in rows)))
print("verifier_clean (advisory):", dict(Counter(str(r["verifier_clean"]) for r in rows)))
print("has_loop_result:", dict(Counter(str(r["has_loop_result"]) for r in rows)))

print("\n=== verifier stdout/stderr tails for non-setup rows ===")
for r in rows:
    print(f"\n--- {r['task_id']} | row_status={r['row_status']} | vexit={r['verifier_exit_code']} | timed_out={r['timed_out']} | reason={r['reason']}")
    print(f"    verifier_clean(advisory)={r['verifier_clean']} finalize={r['finalize_reason']} wall={r['wall_time_sec']}")
    if r["verifier_stdout_tail"]:
        print(f"    STDOUT_TAIL: {r['verifier_stdout_tail']}")
    if r["verifier_stderr_tail"]:
        print(f"    STDERR_TAIL: {r['verifier_stderr_tail']}")
    if r["details"]:
        print(f"    DETAILS: {r['details']}")

Path("tracking/collab/aether2_g5_run_analysis_20260613/scripts/authoritative_attempt1.json").write_text(json.dumps(rows, indent=2))
print("\nwrote authoritative_attempt1.json")
