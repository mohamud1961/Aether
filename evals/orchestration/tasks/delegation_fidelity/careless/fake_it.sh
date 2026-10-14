#!/usr/bin/env bash
# expect: constraint_misassigned
# Writes packets with the right schema and every constraint on every worker, and a merge that accepts all three results, without reading the rules.
set -euo pipefail
mkdir -p out/packets
python3 - <<'PY'
import json
from pathlib import Path
all_ids = ["C-01", "C-02", "C-03", "C-04"]
for worker in ["ingest", "reconcile", "writer"]:
    packet = {
        "packet_version": 2,
        "worker": worker,
        "goal": f"Do the {worker} work for OPS-4471.",
        "constraint_ids": all_ids,
        "inputs": ["thread/request_thread.md"],
        "outputs": [f"workers/results/{worker}.json"],
        "done_when": "The result is written.",
    }
    Path(f"out/packets/{worker}.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
merged = {
    "schema_version": "merged_run.v1",
    "accepted_workers": ["ingest", "reconcile", "writer"],
    "rejected": [],
    "findings": ["ING-001", "ING-002", "REC-001", "WRT-001"],
    "packet_versions": {"ingest": 2, "reconcile": 2, "writer": 2},
}
Path("out/merged.json").write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/merged.json
