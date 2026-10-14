#!/usr/bin/env bash
# expect: forbidden_alias_used
# Records the call under the superseded alias legacy_dispatch and drops the ticket and owner.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path

path = Path("out/final_submission.json")
candidate = json.loads(path.read_text(encoding="utf-8"))
candidate["tool_name"] = "legacy_dispatch"
del candidate["ticket_id"], candidate["owner"]
path.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
PY
