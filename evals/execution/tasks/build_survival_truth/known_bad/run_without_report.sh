#!/usr/bin/env bash
# expect: missing_build_report
# Runs the simulator and stops without writing a report.
set -euo pipefail
python3 build/simulate_build.py >/dev/null 2>&1 || true
