#!/usr/bin/env bash
# expect: bundle_sha_mismatch
# Reference state, then the bundle gets a trailing newline and the submission keeps the old hash.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null || true
printf '\n' >> stage/final/handoff_bundle.json
