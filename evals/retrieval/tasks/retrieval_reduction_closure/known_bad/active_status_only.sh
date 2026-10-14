#!/usr/bin/env bash
# expect: final_value_mismatch
# Trusts each row's own status field and counts every batch row marked active, including superseded revisions.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
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
active = [row for row in rows if row["batch"] == index["batch"] and row["status"] == "active"]
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["final_value"] = sum(int(row["value"]) for row in active)
data["evidence_ids"] = [row["evidence_id"] for row in active]
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
