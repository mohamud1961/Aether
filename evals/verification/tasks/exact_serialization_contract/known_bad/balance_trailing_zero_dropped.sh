#!/usr/bin/env bash
# expect: balance_precision_mismatch
# Reference state, but Bob's balance is written as 0.0 instead of 0.00.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
sed -i.bak 's/"balance": 0.00,/"balance": 0.0,/' out/canonical.json && rm -f out/canonical.json.bak
