#!/usr/bin/env bash
# expect: missing_final_submission
# Writes the closure report with the right decision and evidence, then stops before the submission.
set -euo pipefail
mkdir -p final
cat > final/closure_report.md <<'MD'
# Closure Report

## Decision
Closeout target: OPS-447 (owner: dax).

## Evidence IDs
- ev-02
- ev-03

## Rejected Distractors
- OPS-499: named only in an unstructured note; not a final-cycle ticket in the structured log.

## Verification
Ran `python3 checks/visible_check.py --report final/closure_report.md`: VISIBLE_PASS
MD
