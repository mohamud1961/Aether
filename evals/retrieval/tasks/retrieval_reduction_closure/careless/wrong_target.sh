#!/usr/bin/env bash
# expect: missing_candidate
# Derives the correct closure but writes it to a path the grader does not read.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path
data_dir = Path("data")
index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
rows = []
for shard in index["shards"]:
    for line in (data_dir / shard).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
batch = [row for row in rows if row["batch"] == index["batch"]]
current = {}
for row in batch:
    best = current.get(row["line_key"])
    if best is None or row["revision"] > best["revision"]:
        current[row["line_key"]] = row
counted = [r for r in batch if current[r["line_key"]]["evidence_id"] == r["evidence_id"] and r["status"] == "active"]
counted_ids = {r["evidence_id"] for r in counted}
rejected = [r for r in batch if r["evidence_id"] not in counted_ids]
submission = {
    "final_value": sum(int(r["value"]) for r in counted),
    "evidence_ids": [r["evidence_id"] for r in counted],
    "rejected_stale_ids": [r["evidence_id"] for r in rejected],
    "justification_trace": {r["evidence_id"]: f"{r['line_key']} rev {r['revision']} {r['status']}" for r in counted + rejected},
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
}
Path("out/closure.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
