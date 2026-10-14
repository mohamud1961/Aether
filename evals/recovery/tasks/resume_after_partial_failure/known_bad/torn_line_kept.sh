#!/usr/bin/env bash
# expect: invalid_output_line
# Finishes the rows but leaves the partial line from the crash at the end of the file.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
printf '%s' '{"user_id": 31, "email": "dana' >> data/output/users_v2.jsonl
