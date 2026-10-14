#!/usr/bin/env bash
# Produces the correct final state in the current directory (the workspace root).
# Reads the live constraint tags from the thread, writes one packet per worker at the current
# packet version, then merges the worker results by the merge rules in specs/merge_rules.md.
set -euo pipefail
mkdir -p out/packets
python3 - <<'PY'
import json
import re
from pathlib import Path

root = Path(".")
schema = json.loads((root / "specs/packet_schema.json").read_text(encoding="utf-8"))
current = schema["packet_version_current"]
thread = (root / "thread/request_thread.md").read_text(encoding="utf-8")

applies: dict[str, list[str]] = {}
for cid, who in re.findall(r"\[(C-\d{2})\]\s*applies to:\s*([^\n]+)", thread):
    for worker in who.rstrip(". ").split(","):
        applies.setdefault(worker.strip(), []).append(cid)

plan = {
    "ingest": ("Pull the October source extracts in format v2 and report what was read.",
               ["thread/request_thread.md"], ["workers/results/ingest.json"]),
    "reconcile": ("Reconcile the extracts against the frozen ledger snapshot and report any differences.",
                  ["data/ledger_snapshot_2026-10-12.json"], ["workers/results/reconcile.json"]),
    "writer": ("Draft the vendor summary from the ingest and reconcile results, ASCII only.",
               ["workers/results/ingest.json"], ["workers/results/writer.json"]),
}
for worker in schema["workers"]:
    goal, inputs, outputs = plan[worker]
    packet = {
        "packet_version": current,
        "worker": worker,
        "goal": goal,
        "constraint_ids": sorted(applies.get(worker, [])),
        "inputs": inputs,
        "outputs": outputs,
        "done_when": f"{outputs[0]} is written with status ok.",
    }
    (root / "out/packets" / f"{worker}.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

accepted, rejected, findings, versions = [], [], [], {}
for worker in schema["workers"]:
    packet = json.loads((root / "out/packets" / f"{worker}.json").read_text(encoding="utf-8"))
    versions[worker] = packet["packet_version"]
    result = json.loads((root / "workers/results" / f"{worker}.json").read_text(encoding="utf-8"))
    if result["packet_version"] != packet["packet_version"]:
        rejected.append({
            "worker": worker,
            "reason": "stale_packet_version",
            "result_packet_version": result["packet_version"],
            "current_packet_version": packet["packet_version"],
        })
        continue
    accepted.append(worker)
    findings.extend(item["id"] for item in result["findings"])

merged = {
    "schema_version": "merged_run.v1",
    "accepted_workers": sorted(accepted),
    "rejected": sorted(rejected, key=lambda r: r["worker"]),
    "findings": sorted(findings),
    "packet_versions": dict(sorted(versions.items())),
}
(root / "out/merged.json").write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/merged.json
