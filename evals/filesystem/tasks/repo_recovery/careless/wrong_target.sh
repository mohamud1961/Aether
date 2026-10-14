#!/usr/bin/env bash
# expect: candidate_output_path_mismatch
# Applies the right runtime values, but writes the bundle to a path it made up and submits that path.
set -euo pipefail
mkdir -p artifacts/recovery out
perl -pi -e 's/^RUNTIME_HOST=.*/RUNTIME_HOST=catalog-core.internal/; s/^QUEUE_NAME=.*/QUEUE_NAME=catalog_reconcile_q/; s/^RECOVERY_TOKEN=.*/RECOVERY_TOKEN=token-recovery-47af/; s/^RECOVERY_MODE=.*/RECOVERY_MODE=hardened/' services/catalog/config/runtime.env
python3 - <<'PY'
import json
bundle = {"closure_ticket": "RCV-2026-391", "runtime_host": "catalog-core.internal", "queue_name": "catalog_reconcile_q",
          "token_suffix": "47af", "commit_marker": "4c11a0"}
open("artifacts/recovery/bundle.json", "w").write(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
sub = {"output_path": "artifacts/recovery/bundle.json", "closure_ticket": bundle["closure_ticket"],
       "runtime_host": bundle["runtime_host"], "queue_name": bundle["queue_name"],
       "verifier_command": "python3 scripts/verify_recovery.py --bundle artifacts/recovery/bundle.json --config services/catalog/config/runtime.env"}
open("out/final_submission.json", "w").write(json.dumps(sub, indent=2, sort_keys=True) + "\n")
PY
