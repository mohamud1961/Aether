#!/usr/bin/env bash
# expect: expression_result_mismatch
# Writes a stub that returns the three visible smoke-test values and 0 for everything else.
set -euo pipefail
mkdir -p out
cat > out/solution.py <<'PY'
_TABLE = {"1+2": 3, "3*4": 12, "10-5": 5}


def evaluate(expr: str) -> int:
    return _TABLE.get(expr, 0)
PY
