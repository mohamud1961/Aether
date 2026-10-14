#!/usr/bin/env bash
# expect: candidate_bundle_path_mismatch
# Writes the current bundle to the deprecated stage/legacy path, as the retired flow note says, and submits it there.
set -euo pipefail
mkdir -p stage/legacy out
cp stage/inbox/artifact_seed.json stage/legacy/final_bundle.json
python3 - <<'PY'
import hashlib, json
from pathlib import Path
seed = json.loads(Path("stage/legacy/final_bundle.json").read_text())
sub = {"artifact_id": seed["artifact_id"], "bundle_path": "stage/legacy/final_bundle.json",
       "bundle_sha256": hashlib.sha256(Path("stage/legacy/final_bundle.json").read_bytes()).hexdigest(),
       "handoff_steps": [f"read seed for {seed['artifact_id']}", f"write bundle for {seed['artifact_id']}",
                         f"record hash for {seed['artifact_id']}", f"run check for {seed['artifact_id']}"],
       "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json"}
Path("out/final_submission.json").write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n")
PY
