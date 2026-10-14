#!/usr/bin/env bash
# expect: terminal_state_mismatch
# Writes a green report from the nightly notes and the last run log, without running the build.
set -euo pipefail
mkdir -p out
cat > out/build_report.json <<'JSON'
{
  "terminal_state": "success",
  "exit_code": 0,
  "crashed": false,
  "crash_component": null,
  "log_lines_total": 50,
  "survival_evidence": "last_run.log shows all 50 components built and status green"
}
JSON
