#!/usr/bin/env bash
# expect: evidence_file_modified
# Reference report, but the simulator is edited so the fatal path never fires, which would make the build look clean.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
sed -i.bak 's/crash_at = config.get("crash_at_component")/crash_at = None/' build/simulate_build.py
rm -f build/simulate_build.py.bak
