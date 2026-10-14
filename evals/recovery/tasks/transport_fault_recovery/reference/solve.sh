#!/usr/bin/env bash
# Produces the correct batch runner in the current directory (the workspace root).
# Classifies each reply from its status and body, retries only where the contract allows,
# and keeps one attempt record per transport call.
set -euo pipefail
cat > wirekit/batch.py <<'PYEOF'
"""Batch runner for the wire client. Retry policy: docs/transport_contract.md."""
import json

from wirekit.errors import ConnectionDropped

MAX_ATTEMPTS = 4
IDEMPOTENT_METHODS = frozenset({"GET", "PUT", "DELETE"})


def _classify(response):
    status = response["status"]
    if status == 429:
        return "rate_limited", None
    if not 200 <= status < 300:
        return "fatal", None
    try:
        doc = json.loads(response["body"])
    except ValueError:
        return "truncated", None
    if isinstance(doc, dict) and "value" in doc:
        return "ok", doc["value"]
    return "truncated", None


def run_batch(requests, transport):
    results, failed, attempts = {}, [], []
    for request in requests:
        op_id = request["op_id"]
        method = request["method"].upper()
        for number in range(1, MAX_ATTEMPTS + 1):
            try:
                label, value = _classify(transport(op_id, method, request["payload"]))
            except ConnectionDropped:
                label, value = "dropped", None
            attempts.append({"op_id": op_id, "attempt": number, "classification": label})
            if label == "ok":
                results[op_id] = value
                break
            if label == "fatal":
                failed.append(op_id)
                break
            if label in ("dropped", "truncated") and method not in IDEMPOTENT_METHODS:
                failed.append(op_id)
                break
        else:
            failed.append(op_id)
    return {"results": results, "failed": failed, "attempts": attempts}
PYEOF
python3 checks/visible_check.py
