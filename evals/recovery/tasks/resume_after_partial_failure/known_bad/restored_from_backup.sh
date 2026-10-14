#!/usr/bin/env bash
# expect: missing_row
# Trusts the newest-looking copy in backup/, which is an older snapshot of 8 rows.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
cp backup/users_v2.jsonl.bak data/output/users_v2.jsonl
