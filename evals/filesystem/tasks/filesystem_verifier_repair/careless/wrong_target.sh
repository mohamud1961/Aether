#!/usr/bin/env bash
# expect: candidate_target_mismatch
# Applies the right change to the archived 2025 layout, which is not the file the boot wrapper loads.
set -euo pipefail
mkdir -p out
sed -i.bak 's/^retries: .*/retries: 5/' app/config/archive/service-2025.yaml && rm -f app/config/archive/service-2025.yaml.bak
python3 - <<'PY'
import json
sub = {"patched_target": "app/config/archive/service-2025.yaml",
       "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
       "decoy_untouched": True}
open("out/final_submission.json", "w").write(json.dumps(sub, indent=2) + "\n")
PY
python3 checks/visible_check.py --candidate out/final_submission.json | tee out/verifier_run.log
