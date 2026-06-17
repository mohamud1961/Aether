#!/usr/bin/env python3
"""Parse the frozen combined row file into structured per-task records.

The combined file is NOT valid JSONL. It is a concatenation of pretty-printed
row.json files, each preceded by a header line:  ### FILE: <path>/row.json

This script splits on those markers, parses each JSON block, and emits a
flat summary. It is read-only against the frozen evidence bundle.
"""
import json
import re
import sys
from pathlib import Path

BUNDLE = Path(
    "tracking/collab/vm_pulls/tracking/collab/"
    "aether2_g5_failure_analysis_clean_20260613T121431Z"
)


def parse_combined(path: Path):
    text = path.read_text()
    if not text.strip():
        return []
    # Split keeping the FILE markers
    parts = re.split(r"^### FILE: (.+)$", text, flags=re.MULTILINE)
    # parts[0] is preamble (empty); then alternating marker, body, marker, body
    records = []
    it = iter(parts[1:])
    for marker, body in zip(it, it):
        marker = marker.strip()
        body = body.strip()
        try:
            obj = json.loads(body)
        except json.JSONDecodeError as e:
            records.append({"_file": marker, "_parse_error": str(e)})
            continue
        records.append({"_file": marker, "_obj": obj})
    return records


def path_fields(marker: str):
    # .../attempt_1/<TS>/<task_id>/row.json
    m = re.search(r"attempt_(\d+)/([0-9TZ]+)/([^/]+)/row\.json", marker)
    if m:
        return int(m.group(1)), m.group(2), m.group(3)
    return None, None, None


def main():
    a1 = parse_combined(BUNDLE / "rows" / "attempt1_rows_combined.jsonl")
    print(f"attempt1: parsed {len(a1)} row blocks")

    # collect union of top-level + loop_result keys
    top_keys = set()
    lr_keys = set()
    for r in a1:
        if "_obj" not in r:
            continue
        o = r["_obj"]
        top_keys.update(o.keys())
        if isinstance(o.get("loop_result"), dict):
            lr_keys.update(o["loop_result"].keys())
    print("\nTOP-LEVEL KEYS (union):", sorted(top_keys))
    print("\nLOOP_RESULT KEYS (union):", sorted(lr_keys))

    print("\n=== PER-ROW SUMMARY ===")
    hdr = ["task_id", "att", "ts", "diff", "category", "grader_reward",
           "finalize_reason", "model_calls", "steps", "recoveries",
           "tok_fresh", "tok_cached", "cost", "n_discrep", "n_tools",
           "job_surv", "sess_surv", "compactions"]
    print("\t".join(hdr))
    out_rows = []
    for r in a1:
        marker = r["_file"]
        att, ts, task = path_fields(marker)
        if "_parse_error" in r:
            print(f"{task}\t{att}\t{ts}\tPARSE_ERROR:{r['_parse_error']}")
            out_rows.append({"task_id": task, "attempt": att, "ts": ts,
                             "parse_error": r["_parse_error"]})
            continue
        o = r["_obj"]
        lr = o.get("loop_result", {}) if isinstance(o.get("loop_result"), dict) else {}
        disc = lr.get("discrepancy_reports") or []
        rec = {
            "task_id": task,
            "attempt": att,
            "ts": ts,
            "difficulty": o.get("difficulty"),
            "category": o.get("category"),
            "grader_reward": lr.get("grader_reward"),
            "finalize_reason": lr.get("finalize_reason"),
            "model_calls": lr.get("model_calls"),
            "steps": lr.get("steps"),
            "recoveries": lr.get("recoveries"),
            "tokens_fresh": lr.get("tokens_fresh"),
            "tokens_cached": lr.get("tokens_cached"),
            "cost": lr.get("cost"),
            "n_discrepancy_reports": len(disc),
            "n_tool_invocations": len(lr.get("tool_invocations") or []),
            "job_survival": lr.get("job_survival"),
            "session_survival": lr.get("session_survival"),
            "compaction_count": lr.get("compaction_count"),
            # capture any top-level grader/test/reward fields beyond loop_result
            "_top_extra": {k: o[k] for k in o.keys()
                           if k not in ("loop_result", "tool_invocations")
                           and not isinstance(o.get(k), (dict, list))},
        }
        out_rows.append(rec)
        print("\t".join(str(rec[c2]) for c2 in
                        ["task_id", "attempt", "ts", "difficulty", "category",
                         "grader_reward", "finalize_reason", "model_calls",
                         "steps", "recoveries", "tokens_fresh", "tokens_cached",
                         "cost", "n_discrepancy_reports", "n_tool_invocations",
                         "job_survival", "session_survival", "compaction_count"]))

    # write json for downstream
    outp = Path("tracking/collab/aether2_g5_run_analysis_20260613/scripts/parsed_rows_attempt1.json")
    outp.write_text(json.dumps(out_rows, indent=2))
    print(f"\nwrote {outp}")

    # grader_reward distribution
    from collections import Counter
    gr = Counter(str(r.get("grader_reward")) for r in out_rows if "parse_error" not in r)
    print("\nGRADER_REWARD distribution (attempt1, 24 captured):", dict(gr))
    fr = Counter(str(r.get("finalize_reason")) for r in out_rows if "parse_error" not in r)
    print("FINALIZE_REASON distribution:", dict(fr))


if __name__ == "__main__":
    main()
