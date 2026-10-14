#!/usr/bin/env bash
# expect: candidate_not_json
# Reference submission, but the write was cut off partway through, leaving invalid JSON.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
head -c 60 out/final_submission.json > out/final_submission.tmp && mv out/final_submission.tmp out/final_submission.json
