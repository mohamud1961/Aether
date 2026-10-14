#!/usr/bin/env bash
# expect: input_hash_mismatch
# Correct counts from the current export, but input_sha256 is the hash of the legacy data/events.csv.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import hashlib, json
from pathlib import Path
path = Path("out/summary.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["input_sha256"] = hashlib.sha256(Path("data/events.csv").read_bytes()).hexdigest()
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
