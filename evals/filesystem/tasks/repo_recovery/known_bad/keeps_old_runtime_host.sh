#!/usr/bin/env bash
# expect: runtime_env_mismatch
# Reconciles everything, then puts the deprecated runtime host back into runtime.env.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
perl -pi -e 's/^RUNTIME_HOST=.*/RUNTIME_HOST=catalog-old.internal/' services/catalog/config/runtime.env
