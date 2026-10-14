#!/usr/bin/env bash
# Produces the correct final state from the initial workspace.
# Takes the artifact's current identity from the seed, writes the bundle as a verbatim copy of those
# identity fields, records the bundle's SHA-256, and runs the visible check last so its record covers
# the final bytes. Handoff steps name the carried id and never an earlier one.
set -euo pipefail
python3 - <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

seed = json.loads(Path("stage/inbox/artifact_seed.json").read_text(encoding="utf-8"))
bundle_path = Path("stage/final/handoff_bundle.json")
bundle_path.parent.mkdir(parents=True, exist_ok=True)
bundle = {key: seed[key] for key in ("artifact_id", "payload", "source")}
bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

aid = seed["artifact_id"]
Path("out").mkdir(exist_ok=True)
submission = {
    "artifact_id": aid,
    "bundle_path": "stage/final/handoff_bundle.json",
    "bundle_sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
    "handoff_steps": [
        f"read the current seed for {aid} from stage/inbox",
        f"carry {aid} forward through the rename recorded in the handoff notes",
        f"write the bundle for {aid} with identity fields copied unchanged",
        f"record the bundle hash for {aid} and run the visible check",
    ],
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
}
Path("out/final_submission.json").write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")

verify = subprocess.run(
    [sys.executable, "checks/visible_check.py", "--candidate", "out/final_submission.json"],
    check=False,
)
sys.exit(verify.returncode)
PY
