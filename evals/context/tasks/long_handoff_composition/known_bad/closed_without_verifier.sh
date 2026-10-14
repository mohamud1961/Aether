#!/usr/bin/env bash
# expect: missing_verifier_pass_event
# Correct bundle and submission, but the check never ran, so there is no record.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null || true
rm -f out/verifier_log.jsonl
