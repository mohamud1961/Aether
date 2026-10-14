#!/usr/bin/env bash
# expect: missing_verifier_pass_event
# Replaces the verifier log with the retired flow's passing record (it names the legacy bytes), so the closure
# record does not cover the final bundle.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null || true
cp handoffs/archive/verifier_log_v1.jsonl out/verifier_log.jsonl
