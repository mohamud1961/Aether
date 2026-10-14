#!/usr/bin/env bash
# expect: missing_final_submission
# Reference run, then the submission is removed, as if the solver never wrote it.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
rm -f out/final_submission.json
