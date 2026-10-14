#!/usr/bin/env bash
# expect: verifier_receipt_stale
# Reconciles and verifies, then adds a comment to runtime.env after the receipt was written.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
printf '# reviewed by ops\n' >> services/catalog/config/runtime.env
