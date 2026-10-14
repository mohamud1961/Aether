#!/usr/bin/env bash
# expect: final_value_mismatch
# Uses the lagging mirror copy of ev-1177 (2010) instead of the ledger row (2050) when summing.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

def value_of(path, evidence_id):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["evidence_id"] == evidence_id:
            return int(row["value"])
    raise SystemExit(f"{evidence_id} not found in {path}")

ledger = value_of("data/shards/shard-a.jsonl", "ev-1177")
mirror = value_of("data/mirror/shard-a.jsonl", "ev-1177")
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["final_value"] = data["final_value"] - ledger + mirror
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
