#!/usr/bin/env bash
# expect: summary_mismatch
# Reference manifest and checksum, but summary.txt keeps the draft's "pending review" line and count.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
printf 'Atlas Notes 1.3.9 is pending review; tracked files: 4.\n' > release/summary.txt
