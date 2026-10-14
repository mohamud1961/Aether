#!/usr/bin/env bash
# Reconciles the repository from its checkpoints and handoff manifest, writes the repaired config,
# the recovery bundle and the closure submission, then runs the visible verifier.
set -euo pipefail

python3 - <<'PY'
import json
import re
from pathlib import Path

root = Path(".")


def load(relative):
    return json.loads((root / relative).read_text(encoding="utf-8"))


checkpoint_a = load("data/checkpoints/checkpoint_a.json")
checkpoint_b = load("data/checkpoints/checkpoint_b.json")
checkpoint_c = load("data/checkpoints/checkpoint_c.json")
manifest = load("ops/release/handoff_manifest.json")
chat = (root / "reports/incident/ops_chat_excerpt.log").read_text(encoding="utf-8")

host = checkpoint_a["runtime_host_candidate"].strip() or checkpoint_b["runtime_host_candidate"].strip()
queue = checkpoint_b["queue_name"].strip()
suffix = checkpoint_a["token_suffix"].strip()
commit = checkpoint_a.get("commit_marker", "").strip() or checkpoint_c.get("commit_marker", "").strip()
ticket = manifest["ticket_prefix"] + checkpoint_c["closure_ticket_suffix"].strip()
mode = re.search(r"recovery mode must be `(\w+)`", chat).group(1)
bundle_path = manifest["bundle_output_path"]

env_path = root / "services/catalog/config/runtime.env"
updates = {
    "RUNTIME_HOST": host,
    "QUEUE_NAME": queue,
    "RECOVERY_TOKEN": f"token-recovery-{suffix}",
    "RECOVERY_MODE": mode,
}
lines = []
seen = set()
for raw in env_path.read_text(encoding="utf-8").splitlines():
    key = raw.split("=", 1)[0].strip()
    if key in updates:
        lines.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        lines.append(raw)
lines.extend(f"{key}={value}" for key, value in updates.items() if key not in seen)
env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

bundle = {
    "closure_ticket": ticket,
    "runtime_host": host,
    "queue_name": queue,
    "token_suffix": suffix,
    "commit_marker": commit,
}
target = root / bundle_path
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

submission = {
    "output_path": bundle_path,
    "closure_ticket": ticket,
    "runtime_host": host,
    "queue_name": queue,
    "verifier_command": "python3 scripts/verify_recovery.py --bundle artifacts/recovery/final/recovery_bundle.json --config services/catalog/config/runtime.env",
}
(root / "out").mkdir(exist_ok=True)
(root / "out/final_submission.json").write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

python3 scripts/verify_recovery.py --bundle artifacts/recovery/final/recovery_bundle.json --config services/catalog/config/runtime.env
