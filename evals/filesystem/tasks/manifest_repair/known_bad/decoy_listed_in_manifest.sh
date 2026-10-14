#!/usr/bin/env bash
# expect: manifest_mismatch
# Keeps the stale notes/obsolete.md entry in the tracked set, so the count and checksum follow it.
set -euo pipefail
python3 - <<'PY'
import hashlib, json
from pathlib import Path
manifest = {"project": "Atlas Notes", "release": "1.4.0", "maintainer": "platform-ops", "status": "ready",
            "files": ["release/manifest.json", "release/summary.txt", "release/checksum.txt", "notes/obsolete.md"]}
Path("release/manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
canon = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
Path("release/summary.txt").write_text("Atlas Notes 1.4.0 is ready; tracked files: 4.\n")
Path("release/checksum.txt").write_text(hashlib.sha256(canon.encode()).hexdigest() + "\n")
PY
