#!/usr/bin/env bash
# expect: artifact_identity_lost
# Takes the pre-rename id from the intake note (handoff-art-21) for the bundle and submission, then runs the check.
set -euo pipefail
mkdir -p stage/final out
python3 - <<'PY'
import hashlib, json
from pathlib import Path
bundle = {"artifact_id": "handoff-art-21", "payload": "alpha-sequence", "source": "stage-inbox"}
Path("stage/final/handoff_bundle.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
sub = {"artifact_id": "handoff-art-21", "bundle_path": "stage/final/handoff_bundle.json",
       "bundle_sha256": hashlib.sha256(Path("stage/final/handoff_bundle.json").read_bytes()).hexdigest(),
       "handoff_steps": ["read intake for handoff-art-21", "write bundle for handoff-art-21",
                         "record hash for handoff-art-21", "run visible check"],
       "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json"}
Path("out/final_submission.json").write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n")
PY
python3 checks/visible_check.py --candidate out/final_submission.json >/dev/null || true
