#!/usr/bin/env bash
# expect: insufficient_handoff_steps
# Writes the correct bundle and submission, but lists only two handoff steps and stops before the check.
set -euo pipefail
mkdir -p stage/final out
python3 - <<'PY'
import hashlib, json
from pathlib import Path
seed = json.loads(Path("stage/inbox/artifact_seed.json").read_text())
Path("stage/final/handoff_bundle.json").write_text(json.dumps({k: seed[k] for k in ("artifact_id", "payload", "source")}, indent=2, sort_keys=True) + "\n")
sub = {"artifact_id": seed["artifact_id"], "bundle_path": "stage/final/handoff_bundle.json",
       "bundle_sha256": hashlib.sha256(Path("stage/final/handoff_bundle.json").read_bytes()).hexdigest(),
       "handoff_steps": [f"read seed for {seed['artifact_id']}", f"write bundle for {seed['artifact_id']}"],
       "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json"}
Path("out/final_submission.json").write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n")
PY
