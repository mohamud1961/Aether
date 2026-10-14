#!/usr/bin/env bash
# expect: candidate_target_mismatch
# Takes the README's "Active service: alpha" at face value, raises alpha's production overlay, and never checks the manifest.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
import re
from pathlib import Path
path = Path("services/alpha/overrides/production.yaml")
path.write_text(re.sub(r"(?m)^timeout:.*$", "timeout: 300", path.read_text(encoding="utf-8")), encoding="utf-8")
submission = {
    "patched_target": "services/alpha/overrides/production.yaml",
    "effective_timeout_s": 300,
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
    "decoy_untouched": True,
}
Path("out/final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json
