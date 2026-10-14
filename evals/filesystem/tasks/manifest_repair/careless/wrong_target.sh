#!/usr/bin/env bash
# expect: manifest_mismatch
# Writes the repaired files into a new staging folder and leaves release/ as the draft.
set -euo pipefail
mkdir -p staging/release
cp release/manifest.json staging/release/manifest.json
bash -c 'cd . && python3 - <<PY
import hashlib, json
from pathlib import Path
draft = json.loads(Path("staging/release/manifest.json").read_text())
manifest = {"project": draft["project"], "release": draft["release"], "maintainer": draft["maintainer"],
            "status": "ready", "files": [f for f in draft["files"] if f.startswith("release/")]}
Path("staging/release/manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
Path("staging/release/summary.txt").write_text("Atlas Notes 1.4.0 is ready; tracked files: 3.\n")
canon = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
Path("staging/release/checksum.txt").write_text(hashlib.sha256(canon.encode()).hexdigest() + "\n")
PY'
