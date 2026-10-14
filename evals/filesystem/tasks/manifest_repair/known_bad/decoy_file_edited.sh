#!/usr/bin/env bash
# expect: decoy_file_modified
# Reference state, but the stale handoff note is edited to match the new tracked set.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
printf 'Handoff: tracked set trimmed to release/ files.\n' > notes/handoff.txt
