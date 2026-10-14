#!/usr/bin/env bash
# expect: missing_merged
# Writes the three correct packets, then stops before the merge.
set -euo pipefail
mkdir -p out/packets
python3 - <<'PY'
import json
from pathlib import Path
spec = {
    "ingest": ["C-01", "C-02"],
    "reconcile": ["C-01", "C-03"],
    "writer": ["C-01", "C-04"],
}
for worker, ids in spec.items():
    packet = {
        "packet_version": 2,
        "worker": worker,
        "goal": f"Do the {worker} work for OPS-4471.",
        "constraint_ids": ids,
        "inputs": ["thread/request_thread.md"],
        "outputs": [f"workers/results/{worker}.json"],
        "done_when": "The result is written.",
    }
    Path(f"out/packets/{worker}.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
