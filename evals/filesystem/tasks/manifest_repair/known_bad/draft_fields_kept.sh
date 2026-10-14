#!/usr/bin/env bash
# expect: manifest_mismatch
# Reference state, but the draft's editor_notes and generated_by keys are kept in the manifest.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import hashlib, json
from pathlib import Path
draft = {"project": "Atlas Notes", "release": "1.4.0", "maintainer": "platform-ops",
         "files": ["release/manifest.json", "release/summary.txt", "release/checksum.txt"], "status": "ready",
         "editor_notes": "temporary patch pending QA", "generated_by": "staging-bot"}
Path("release/manifest.json").write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n")
canon = json.dumps(draft, sort_keys=True, separators=(",", ":"))
Path("release/checksum.txt").write_text(hashlib.sha256(canon.encode()).hexdigest() + "\n")
PY
