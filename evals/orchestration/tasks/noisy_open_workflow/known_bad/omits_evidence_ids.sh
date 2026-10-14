#!/usr/bin/env bash
# expect: missing_required_evidence
# Decision is right, but the evidence section omits ev-02 and ev-03.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
from pathlib import Path

def replace_once(path, old, new):
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one occurrence of {old!r} in {path}")
    target.write_text(text.replace(old, new), encoding="utf-8")

replace_once("final/closure_report.md", "- ev-02\n- ev-03\n", "- ev-01\n")
PY
