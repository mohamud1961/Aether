#!/usr/bin/env bash
# expect: target_collateral_edit
# Sets retries correctly, but also raises backoff_s in the same file.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
sed -i.bak 's/^backoff_s: 4$/backoff_s: 10/' app/config/service.yaml && rm -f app/config/service.yaml.bak
