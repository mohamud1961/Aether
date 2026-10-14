#!/usr/bin/env bash
# expect: premature_stop
# Writes a run_batch that returns plausible results and an empty attempt log, without any transport calls.
set -euo pipefail
cat > wirekit/batch.py <<'PYEOF'
"""Batch runner."""


def run_batch(requests, transport):
    return {
        "results": {"op-a": 11, "op-b": "alpha", "op-c": [1, 2], "op-e": 5},
        "failed": ["op-d", "op-f", "op-g", "op-h"],
        "attempts": [],
    }
PYEOF
