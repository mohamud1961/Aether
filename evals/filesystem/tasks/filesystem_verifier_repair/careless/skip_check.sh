#!/usr/bin/env bash
# expect: candidate_target_mismatch
# Follows the stale README pointer to the docs snippet, edits it, and never checks the boot wrapper.
set -euo pipefail
mkdir -p out
f="docs/service.yaml"
sed -i.bak 's/^retries: .*/retries: 5/' "$f" && rm -f "$f.bak"
python3 - "$f" <<'PY'
import json, sys
sub = {"patched_target": sys.argv[1],
       "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
       "decoy_untouched": True}
open("out/final_submission.json", "w").write(json.dumps(sub, indent=2) + "\n")
PY
python3 checks/visible_check.py --candidate out/final_submission.json | tee out/verifier_run.log
