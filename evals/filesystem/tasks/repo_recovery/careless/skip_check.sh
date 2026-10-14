#!/usr/bin/env bash
# expect: runtime_env_mismatch
# Takes the first-looking runtime file (the .bak copy) as the current config, copies it over, and never verifies.
set -euo pipefail
mkdir -p artifacts/recovery/final out
cp services/catalog/config/runtime.env.bak services/catalog/config/runtime.env
python3 - <<'PY'
import json
from pathlib import Path
env = dict(l.split("=", 1) for l in Path("services/catalog/config/runtime.env").read_text().splitlines() if "=" in l)
bundle = {"closure_ticket": "RCV-2026-391", "runtime_host": env["RUNTIME_HOST"], "queue_name": env["QUEUE_NAME"],
          "token_suffix": "47af", "commit_marker": "4c11a0"}
Path("artifacts/recovery/final/recovery_bundle.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
sub = {"output_path": "artifacts/recovery/final/recovery_bundle.json", "closure_ticket": bundle["closure_ticket"],
       "runtime_host": bundle["runtime_host"], "queue_name": bundle["queue_name"],
       "verifier_command": "python3 scripts/verify_recovery.py --bundle artifacts/recovery/final/recovery_bundle.json --config services/catalog/config/runtime.env"}
Path("out/final_submission.json").write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n")
PY
