#!/usr/bin/env bash
# expect: premature_stop
# Implements the v1 policy from the README (429 is terminal) and never checks it against the contract.
set -euo pipefail
cat > wirekit/batch.py <<'PYEOF'
"""Batch runner (v1 policy from the README)."""
import json

from wirekit.errors import ConnectionDropped


def run_batch(requests, transport):
    results, failed, attempts = {}, [], []
    for request in requests:
        op_id = request["op_id"]
        for number in range(1, 4):
            try:
                response = transport(op_id, request["method"], request["payload"])
            except ConnectionDropped:
                attempts.append({"op_id": op_id, "attempt": number, "classification": "dropped"})
                continue
            if response["status"] == 429:
                failed.append(op_id)
                break
            try:
                value = json.loads(response["body"])["value"]
            except (ValueError, KeyError, TypeError):
                attempts.append({"op_id": op_id, "attempt": number, "classification": "truncated"})
                continue
            attempts.append({"op_id": op_id, "attempt": number, "classification": "ok"})
            results[op_id] = value
            break
        else:
            failed.append(op_id)
    return {"results": results, "failed": failed, "attempts": attempts}
PYEOF
