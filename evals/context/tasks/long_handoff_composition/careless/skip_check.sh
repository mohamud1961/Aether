#!/usr/bin/env bash
# expect: artifact_identity_lost
# Takes the identity from the first handoff note it reads (handoff-art-21), writes the bundle, and never runs the check.
set -euo pipefail
mkdir -p stage/final out
python3 - <<'PY'
import hashlib, json
from pathlib import Path
bundle = {"artifact_id": "handoff-art-21", "payload": "alpha-sequence", "source": "stage-inbox"}
Path("stage/final/handoff_bundle.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
sub = {"artifact_id": "handoff-art-21", "bundle_path": "stage/final/handoff_bundle.json",
       "bundle_sha256": hashlib.sha256(Path("stage/final/handoff_bundle.json").read_bytes()).hexdigest(),
       "handoff_steps": ["read intake", "write bundle", "record hash", "close chain"],
       "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json"}
Path("out/final_submission.json").write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n")
PY
