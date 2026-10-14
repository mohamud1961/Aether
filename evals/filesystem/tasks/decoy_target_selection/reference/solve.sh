#!/usr/bin/env bash
# Produces the correct final state in the current directory (the workspace root).
# Resolves the live service and environment through deploy_manifest.json and its profile file,
# raises the timeout in that environment's overlay (the layer that wins over base.yaml),
# writes out/final_submission.json, and runs the visible check.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
import re
from pathlib import Path

root = Path(".")
manifest = json.loads((root / "deploy_manifest.json").read_text(encoding="utf-8"))
profile = json.loads((root / manifest["profile_file"]).read_text(encoding="utf-8"))
service = profile["active_service"]
environment = profile["environment"]
target = f"services/{service}/overrides/{environment}.yaml"
path = root / target
text = path.read_text(encoding="utf-8")
patched, count = re.subn(r"(?m)^timeout:[ \t]*\d+[ \t]*$", "timeout: 300", text)
if count != 1:
    raise SystemExit(f"expected one timeout line in {target}, found {count}")
path.write_text(patched, encoding="utf-8")
effective = int(re.search(r"(?m)^timeout:[ \t]*(\d+)", patched).group(1))

submission = {
    "patched_target": target,
    "effective_timeout_s": effective,
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
    "decoy_untouched": True,
}
(root / "out" / "final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json
