#!/usr/bin/env bash
# expect: expression_result_mismatch
# Writes a module with the right signature whose body is a placeholder, and never runs the smoke check.
set -euo pipefail
mkdir -p out
cat > out/solution.py <<'PY'
def evaluate(expr: str) -> int:
    return len(expr)
PY
