#!/usr/bin/env bash
# Resolves the effective contract the way the contract says: base file, then runtime contract,
# then the profile named by runner_profile, verified against profiles_sha256. Writes the
# submission from those effective values and runs the visible check.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path(".")
base = json.loads((root / "config" / "base_contract.json").read_text(encoding="utf-8"))
contract = json.loads((root / "config" / "runtime_contract.json").read_text(encoding="utf-8"))
profiles_path = root / contract["profiles_file"]
profiles_bytes = profiles_path.read_bytes()
verified = hashlib.sha256(profiles_bytes).hexdigest() == contract["profiles_sha256"]
profile = json.loads(profiles_bytes.decode("utf-8"))["profiles"][contract["runner_profile"]]

classification = "capability_success" if verified else "invalid_environment"
submission = {
    "python_command": base["python_command"],
    "workspace_root": contract["workspace_root"],
    "runner_command": profile["command"],
    "runtime_classification": classification,
}
Path("out/final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json
