#!/usr/bin/env bash
# expect: missing_verifier_log
# Correct edit and a correct submission, but the visible check output is never saved.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
rm -f out/verifier_run.log
