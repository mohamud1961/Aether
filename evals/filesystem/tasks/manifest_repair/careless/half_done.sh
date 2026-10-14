#!/usr/bin/env bash
# expect: missing_release_checksum
# Repairs the manifest and summary correctly, then stops before the checksum.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
draft = json.loads(Path("release/manifest.json").read_text())
manifest = {"project": draft["project"], "release": draft["release"], "maintainer": draft["maintainer"],
            "status": "ready", "files": [f for f in draft["files"] if f.startswith("release/")]}
Path("release/manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
Path("release/summary.txt").write_text(f"Atlas Notes 1.4.0 is ready; tracked files: {len(manifest['files'])}.\n")
Path("release/checksum.txt").unlink(missing_ok=True)
PY
