"""Read single-step Harbor trial results without creating fictional task/cost evidence.

Imported rows use the shared trial schema, with raw source hashes and availability
flags in a sidecar. Multi-step protocols require explicit reduction and are refused.
"""

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from .trials import TrialRow, TrialTrace, trace_path_for


def ingest(paths, out, run_id, arm):
    out = Path(out)
    if out.exists() or trace_path_for(out).exists():
        raise FileExistsError("choose new output paths")
    rows = []
    traces = []
    seen = set()
    for path in paths:
        path = Path(path)
        r = json.loads(path.read_text())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if r.get("step_results"):
            raise ValueError("multi-step reward aggregation is unsupported")
        if not r.get("task_name") or not r.get("trial_name"):
            raise ValueError("not a Harbor trial result")
        identity = r["trial_name"]
        if identity in seen:
            raise ValueError("duplicate Harbor trial identity")
        seen.add(identity)
        task_id = "external-" + hashlib.sha256(r["task_name"].encode()).hexdigest()[:16]
        attempt = 1 + sum(row.task_id == task_id for row in rows)
        reward = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        error = r.get("exception_info")
        valid = error is None and type(reward) in (int, float) and math.isfinite(reward)
        started = r.get("started_at")
        finished = r.get("finished_at")
        wall = (
            (
                datetime.fromisoformat(finished) - datetime.fromisoformat(started)
            ).total_seconds()
            if started and finished
            else 0.0
        )
        ctx = r.get("agent_result") or {}
        info = r.get("agent_info") or {}
        rows.append(
            TrialRow(
                run_id,
                arm,
                task_id,
                attempt,
                started or "unknown",
                wall,
                valid and reward == 1,
                float(reward) if valid else 0.0,
                (),
                valid,
                None if valid else "external_protocol_or_exception",
                ctx.get("n_input_tokens") or 0,
                ctx.get("n_output_tokens") or 0,
                ctx.get("cost_usd") or 0.0,
                0,
                0,
                info.get("version", "unknown"),
                "unavailable",
                r.get("task_checksum", "unavailable"),
                None,
            )
        )
        traces.append(
            TrialTrace(
                run_id,
                arm,
                task_id,
                attempt,
                None,
                (),
                (
                    {
                        "external_source_sha256": digest,
                        "trial_identity_sha256": hashlib.sha256(
                            identity.encode()
                        ).hexdigest(),
                        "usage_known": ctx.get("n_input_tokens") is not None,
                        "cost_known": ctx.get("cost_usd") is not None,
                        "wall_known": bool(started and finished),
                        "grader_hash_known": False,
                        "protocol": "Harbor single-step reward",
                    },
                ),
            )
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    # Prepare the entire import before writing; never partially hide a malformed input.
    out.write_text("".join(r.to_json() + "\n" for r in rows))
    trace_path_for(out).write_text("".join(t.to_json() + "\n" for t in traces))
    return rows
