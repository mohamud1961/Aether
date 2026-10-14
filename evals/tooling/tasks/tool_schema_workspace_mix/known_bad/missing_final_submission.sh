#!/usr/bin/env bash
# expect: missing_final_submission
# Writes the plan and the selector correctly, then removes the submission.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
rm -f out/final_submission.json
