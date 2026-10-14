#!/usr/bin/env bash
# expect: candidate_target_mismatch
# Patches the docs snippet instead of the loaded config and names the snippet as the target.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path
p = Path("docs/service.yaml")
p.write_text(p.read_text(encoding="utf-8").replace("retries: 3", "retries: 5"), encoding="utf-8")
sub = {"patched_target": "docs/service.yaml",
       "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
       "decoy_untouched": False}
Path("out/final_submission.json").write_text(json.dumps(sub, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json | tee out/verifier_run.log
