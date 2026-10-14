#!/usr/bin/env bash
# expect: missing_verifier_pass_event
# Writes the correct bundle, config and submission, but never leaves a verifier pass receipt.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
rm -f out/verifier_receipt.json
