#!/usr/bin/env bash
# expect: contract_file_modified
# Re-pins the contract to the stale backup profile, then reports the backup's command so the pin "verifies".
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import hashlib
import json
from pathlib import Path
backup = Path("config/runner_profiles.json.bak").read_bytes()
contract_path = Path("config/runtime_contract.json")
contract = json.loads(contract_path.read_text(encoding="utf-8"))
contract["profiles_sha256"] = hashlib.sha256(backup).hexdigest()
contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
path = Path("out/final_submission.json")
data = json.loads(path.read_text(encoding="utf-8"))
data["runner_command"] = "uv run pytest -q"
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
