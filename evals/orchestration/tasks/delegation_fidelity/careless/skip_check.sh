#!/usr/bin/env bash
# expect: retracted_constraint_present
# Builds packets from the first message of the thread (the asks Priya made before she retracted them) and never reads later replies.
set -euo pipefail
mkdir -p out/packets
python3 - <<'PY'
import json
from pathlib import Path
first = {"ingest": ["X-01", "C-01"], "reconcile": ["X-02", "C-01"], "writer": ["R-01", "C-01"]}
for worker, ids in first.items():
    packet = {
        "packet_version": 2,
        "worker": worker,
        "goal": f"Do the {worker} work for OPS-4471.",
        "constraint_ids": sorted(ids),
        "inputs": ["thread/request_thread.md"],
        "outputs": [f"workers/results/{worker}.json"],
        "done_when": "The result is written.",
    }
    Path(f"out/packets/{worker}.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
