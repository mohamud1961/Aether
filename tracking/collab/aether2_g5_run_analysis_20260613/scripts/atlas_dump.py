#!/usr/bin/env python3
"""Dump fuller evidence (verifier tails, details, first/last tool calls,
finalize reason) for failure-atlas anchor tasks from the 24 captured rows."""
import json
import re
from pathlib import Path

BUNDLE = Path("tracking/collab/vm_pulls/tracking/collab/"
              "aether2_g5_failure_analysis_clean_20260613T121431Z")

text = (BUNDLE / "rows" / "attempt1_rows_combined.jsonl").read_text()
parts = re.split(r"^### FILE: (.+)$", text, flags=re.MULTILINE)
blocks = {}
it = iter(parts[1:])
for marker, body in zip(it, it):
    m = re.search(r"/([^/]+)/row\.json", marker)
    try:
        blocks[m.group(1)] = json.loads(body.strip())
    except Exception:
        pass

ANCHORS = ["3d-model-format-legacy", "aimo-airline-departures", "amuse-install",
           "broken-networking", "broken-python", "add-benchmark-lm-eval-harness",
           "build-pov-ray", "build-linux-kernel-qemu", "blind-maze-explorer-5x5",
           "build-stp", "accelerate-maximal-square"]

for t in ANCHORS:
    o = blocks.get(t)
    if not o:
        print(f"\n##### {t}: NOT CAPTURED"); continue
    lr = o.get("loop_result") or {}
    print(f"\n##### {t} | status={o.get('row_status')} vexit={o.get('verifier_exit_code')} reason={o.get('reason')} finalize={lr.get('finalize_reason')} steps={lr.get('steps')} calls={lr.get('model_calls')} advisory_clean={lr.get('verifier_clean')}")
    if o.get("details"):
        print(f"  DETAILS: {json.dumps(o.get('details'))[:400]}")
    so = (o.get("verifier_stdout_tail") or "")[-600:]
    se = (o.get("verifier_stderr_tail") or "")[-300:]
    if so:
        print(f"  STDOUT_TAIL(last600): {so!r}")
    if se:
        print(f"  STDERR_TAIL(last300): {se!r}")
    tis = lr.get("tool_invocations") or []
    if tis:
        first = tis[0]
        last = tis[-1]
        def desc(ti):
            a = ti.get("arguments", {})
            env = ti.get("envelope", {})
            cmd = a.get("cmd") or a.get("path") or a.get("content","")[:60]
            return f"step{ti.get('step')} {ti.get('tool_name')} exit={env.get('exit_code')} cmd={str(cmd)[:90]!r}"
        print(f"  FIRST tool: {desc(first)}")
        print(f"  LAST  tool: {desc(last)}")
