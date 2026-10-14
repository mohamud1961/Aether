#!/usr/bin/env bash
# expect: final_value_mismatch
# Takes the declared total from data/index.json, lists the status-active rows, and never checks revisions.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path
data_dir = Path("data")
index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
rows = [
    json.loads(line)
    for shard in index["shards"]
    for line in (data_dir / shard).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
batch = [row for row in rows if row["batch"] == index["batch"]]
active = [row for row in batch if row["status"] == "active"]
rejected = [row for row in batch if row["status"] != "active"]
submission = {
    "final_value": index["declared_total"],
    "evidence_ids": [row["evidence_id"] for row in active],
    "rejected_stale_ids": [row["evidence_id"] for row in rejected],
    "justification_trace": {
        row["evidence_id"]: f"status {row['status']} in the export"
        for row in active + rejected
    },
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
}
Path("out/final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json
