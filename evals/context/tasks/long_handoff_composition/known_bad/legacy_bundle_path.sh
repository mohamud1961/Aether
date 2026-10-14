#!/usr/bin/env bash
# expect: candidate_bundle_path_mismatch
# Writes the correct bundle to the deprecated stage/legacy path and submits that path.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null || true
mkdir -p stage/legacy
cp stage/final/handoff_bundle.json stage/legacy/final_bundle.json
python3 - <<'PY'
import hashlib, json
from pathlib import Path
p = Path("out/final_submission.json")
sub = json.loads(p.read_text())
sub["bundle_path"] = "stage/legacy/final_bundle.json"
sub["bundle_sha256"] = hashlib.sha256(Path("stage/legacy/final_bundle.json").read_bytes()).hexdigest()
p.write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n")
PY
