#!/usr/bin/env bash
# Derives the closure from the export named in data/index.json, writes out/final_submission.json,
# and runs the visible check.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path

data = Path("data")
index = json.loads((data / "index.json").read_text(encoding="utf-8"))
rows = []
for shard in index["shards"]:
    for line in (data / shard).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
batch = [row for row in rows if row["batch"] == index["batch"]]
current = {}
for row in batch:
    best = current.get(row["line_key"])
    if best is None or row["revision"] > best["revision"]:
        current[row["line_key"]] = row
counted = [
    row for row in batch
    if current[row["line_key"]]["evidence_id"] == row["evidence_id"] and row["status"] == "active"
]
counted_ids = {row["evidence_id"] for row in counted}
rejected = [row for row in batch if row["evidence_id"] not in counted_ids]
trace = {}
for row in counted:
    trace[row["evidence_id"]] = f"current revision {row['revision']} of {row['line_key']}, status active"
for row in rejected:
    trace[row["evidence_id"]] = f"rejected: {row['line_key']} rev {row['revision']} status {row['status']}"
submission = {
    "final_value": sum(int(row["value"]) for row in counted),
    "evidence_ids": [row["evidence_id"] for row in counted],
    "rejected_stale_ids": [row["evidence_id"] for row in rejected],
    "justification_trace": trace,
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
}
Path("out/final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json
