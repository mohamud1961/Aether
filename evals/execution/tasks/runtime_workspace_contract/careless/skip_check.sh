#!/usr/bin/env bash
# expect: runner_command_mismatch
# Takes the ci-python entry from the backup profile file it found first, and never checks the pin or the live file.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path
profile = json.loads(Path("config/runner_profiles.json.bak").read_text(encoding="utf-8"))["profiles"]["ci-python"]
submission = {
    "python_command": "python3",
    "workspace_root": "/workspace/runtime",
    "runner_command": profile["command"],
    "runtime_classification": "capability_success",
}
Path("out/final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
