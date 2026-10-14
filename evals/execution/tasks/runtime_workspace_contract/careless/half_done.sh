#!/usr/bin/env bash
# expect: runtime_classification_mismatch
# Resolves three of the four fields, then stops before the classification.
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
}
Path("out/final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
