#!/usr/bin/env bash
# expect: final_value_mismatch
# Writes a plausible-looking submission with the right shape, without deriving anything from the export.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path
submission = {
    "final_value": 4321,
    "evidence_ids": ["ev-2104", "ev-1177"],
    "rejected_stale_ids": ["ev-2101"],
    "justification_trace": {
        "ev-2104": "latest revision of the line, active",
        "ev-1177": "latest revision of the line, active",
        "ev-2101": "older revision of the same line",
    },
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
}
Path("out/final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json
