#!/usr/bin/env bash
# expect: missing_final_submission
# Resolves the contract from the live config files, but writes the result to a scratch name rather than out/final_submission.json.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path

root = Path(".")
base = json.loads((root / "config" / "base_contract.json").read_text(encoding="utf-8"))
contract = json.loads((root / "config" / "runtime_contract.json").read_text(encoding="utf-8"))
profile = json.loads((root / "config" / "runner_profiles.json").read_text(encoding="utf-8"))["profiles"][contract["runner_profile"]]
submission = {
    "python_command": base["python_command"],
    "workspace_root": contract["workspace_root"],
    "runner_command": profile["command"],
    "runtime_classification": "capability_success",
}
Path("out/runtime_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
