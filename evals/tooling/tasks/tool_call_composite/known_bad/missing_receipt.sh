#!/usr/bin/env bash
# expect: receipt_missing
# Writes the candidate summary but never writes the dispatch receipt.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
rm -f out/dispatch_receipt.json
