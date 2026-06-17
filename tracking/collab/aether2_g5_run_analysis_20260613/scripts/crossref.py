#!/usr/bin/env python3
"""Cross-reference progress.tsv against the 24 captured authoritative rows."""
import json
import re
from pathlib import Path
from collections import Counter

BUNDLE = Path("tracking/collab/vm_pulls/tracking/collab/"
              "aether2_g5_failure_analysis_clean_20260613T121431Z")

# Load progress.tsv  (attempt, task_id, rc, elapsed, date)
prog = {1: {}, 2: {}}
for line in (BUNDLE / "progress.tsv").read_text().splitlines():
    if not line.strip():
        continue
    f = line.split("\t")
    att = int(f[0]); task = f[1]; rc = int(f[2]); el = int(f[3])
    prog[att][task] = {"rc": rc, "elapsed": el, "date": f[4]}

print("attempt-1 tasks in progress:", len(prog[1]))
print("attempt-2 tasks in progress:", len(prog[2]))
print("attempt-1 task set == attempt-2 task set:", set(prog[1]) == set(prog[2]))

# RC distributions
print("\nattempt-1 RC:", dict(Counter(v["rc"] for v in prog[1].values())))
print("attempt-2 RC:", dict(Counter(v["rc"] for v in prog[2].values())))

# rc=0 attempt-1 tasks (claimed passes)
a1_rc0 = sorted(t for t, v in prog[1].items() if v["rc"] == 0)
print("\nattempt-1 rc=0 tasks (n=%d):" % len(a1_rc0), a1_rc0)
a1_rc143 = sorted(t for t, v in prog[1].items() if v["rc"] == 143)
print("attempt-1 rc=143 (timeout) tasks:", a1_rc143,
      [prog[1][t]["elapsed"] for t in a1_rc143])

# Load captured authoritative rows
rows = json.loads(Path("tracking/collab/aether2_g5_run_analysis_20260613/"
                       "scripts/authoritative_attempt1.json").read_text())
captured = {r["task_id"]: r for r in rows}
print("\ncaptured authoritative rows:", len(captured))
pass_tasks = sorted(t for t, r in captured.items() if r["row_status"] == "pass")
print("row_status=pass tasks:", pass_tasks)

# Cross-check: do rc=0 tasks == row_status=pass tasks?
print("\nrc=0 set == row_status=pass set:", set(a1_rc0) == set(pass_tasks))

# For each captured row, show progress rc vs row_status (validate mapping)
print("\n--- captured rows: rc vs row_status vs verifier_exit_code ---")
print("task\tprog_rc\trow_status\tvexit\treason")
for t in sorted(captured):
    r = captured[t]
    pr = prog[1].get(t, {}).get("rc", "NA")
    print(f"{t}\t{pr}\t{r['row_status']}\t{r['verifier_exit_code']}\t{r['reason']}")

# Are any rc=0 tasks NOT in captured? (would mean a pass we can't see)
rc0_not_captured = [t for t in a1_rc0 if t not in captured]
print("\nrc=0 tasks NOT among captured rows:", rc0_not_captured)

# Tail analysis: tasks after 'build-stp' (last captured) — uncaptured population
last_captured_ts = max(r["ts"] for r in rows)
print("\nlast captured run timestamp:", last_captured_ts)
# elapsed stats for attempt-1
a1_el = [v["elapsed"] for v in prog[1].values()]
a2_el = [v["elapsed"] for v in prog[2].values()]
import statistics as st
print("\nattempt-1 elapsed: min=%d max=%d mean=%.1f median=%d" %
      (min(a1_el), max(a1_el), st.mean(a1_el), st.median(a1_el)))
print("attempt-2 elapsed: min=%d max=%d mean=%.1f median=%d" %
      (min(a2_el), max(a2_el), st.mean(a2_el), st.median(a2_el)))
print("attempt-2 elapsed distribution:", dict(Counter(a2_el)))
# attempt-1 elapsed buckets
buckets = Counter()
for e in a1_el:
    if e <= 2: buckets["0-2s"] += 1
    elif e <= 10: buckets["3-10s"] += 1
    elif e <= 60: buckets["11-60s"] += 1
    elif e <= 300: buckets["61-300s"] += 1
    elif e <= 1800: buckets["301-1800s"] += 1
    else: buckets[">1800s"] += 1
print("attempt-1 elapsed buckets:", dict(buckets))
# How many attempt-1 tasks <=2s (likely instant crash like attempt 2)?
a1_instant = sorted(t for t, v in prog[1].items() if v["elapsed"] <= 2)
print("\nattempt-1 instant(<=2s) tasks (n=%d):" % len(a1_instant), a1_instant[:40])
