#!/usr/bin/env bash
# expect: missing_candidate
# Writes the dispatch receipt with the right values, then stops before writing the summary.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path

rev = json.loads(Path("contracts/revisions/rev-07.json").read_text(encoding="utf-8"))
Path("out/dispatch_receipt.json").write_text(json.dumps({
    "status": rev["required_receipt_status"],
    "tool_name": rev["tool_name"],
    "ticket_id": rev["required_ticket_id"],
    "owner": rev["required_owner"],
}, indent=2) + "\n", encoding="utf-8")
PY
