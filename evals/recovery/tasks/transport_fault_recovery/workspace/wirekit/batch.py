"""Batch runner for the wire client. Retry loop carried over from the v1 client."""
import json
import re

from wirekit.errors import ConnectionDropped

MAX_ATTEMPTS = 3


def run_batch(requests, transport):
    results, failed, attempts = {}, [], []
    for request in requests:
        op_id = request["op_id"]
        for number in range(1, MAX_ATTEMPTS + 1):
            try:
                response = transport(op_id, request["method"], request["payload"])
            except ConnectionDropped:
                attempts.append({"op_id": op_id, "attempt": number, "classification": "dropped"})
                continue
            if response["status"] == 429:
                failed.append(op_id)
                break
            if response["status"] != 200:
                attempts.append({"op_id": op_id, "attempt": number, "classification": "fatal"})
                continue
            match = re.search(r'"value": ?(.+?)\}?$', response["body"])
            if match is None:
                attempts.append({"op_id": op_id, "attempt": number, "classification": "truncated"})
                continue
            attempts.append({"op_id": op_id, "attempt": number, "classification": "ok"})
            results[op_id] = json.loads(match.group(1))
            break
    return {"results": results, "failed": failed, "attempts": attempts}
