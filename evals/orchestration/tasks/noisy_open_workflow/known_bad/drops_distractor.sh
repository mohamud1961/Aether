#!/usr/bin/env bash
# expect: distractor_not_rejected
# Correct decision and evidence, but the rejected-distractor section does not mention the sticky-note ticket.
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

replace_once(
    "final/closure_report.md",
    "- OPS-499: named only in an unstructured note; not a final-cycle ticket in the structured log.",
    "- None.",
)
PY
