#!/usr/bin/env bash
# expect: missing_verifier_pass_event
# Repairs the config and writes the bundle with the right values, then stops before the submission and the verifier.
set -euo pipefail
mkdir -p artifacts/recovery/final
perl -pi -e 's/^RUNTIME_HOST=.*/RUNTIME_HOST=catalog-core.internal/; s/^QUEUE_NAME=.*/QUEUE_NAME=catalog_reconcile_q/; s/^RECOVERY_TOKEN=.*/RECOVERY_TOKEN=token-recovery-47af/; s/^RECOVERY_MODE=.*/RECOVERY_MODE=hardened/' services/catalog/config/runtime.env
python3 - <<'PY'
import json
bundle = {"closure_ticket": "RCV-2026-391", "runtime_host": "catalog-core.internal", "queue_name": "catalog_reconcile_q",
          "token_suffix": "47af", "commit_marker": "4c11a0"}
open("artifacts/recovery/final/recovery_bundle.json", "w").write(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
PY
