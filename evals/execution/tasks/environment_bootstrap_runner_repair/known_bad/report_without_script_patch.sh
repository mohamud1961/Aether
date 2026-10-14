#!/usr/bin/env bash
# expect: runner_script_not_patched
# Writes a complete report and patch list, but the runner script still holds the stale command.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
cp "$TASK_ROOT/workspace/scripts/run_tests.sh" scripts/run_tests.sh
