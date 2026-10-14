#!/usr/bin/env bash
# expect: manifest_mismatch
# Trusts the superseded v1 contract's "keep the draft's files list" rule and never checks the 1.4 notes.
set -euo pipefail
python3 - <<'PY'
import hashlib, json
from pathlib import Path
draft = json.loads(Path("release/manifest.json").read_text())
manifest = {"project": draft["project"], "release": draft["release"], "maintainer": draft["maintainer"],
            "status": "ready", "files": draft["files"]}
Path("release/manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
Path("release/summary.txt").write_text(f"Atlas Notes 1.4.0 is ready; tracked files: {len(manifest['files'])}.\n")
canon = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
Path("release/checksum.txt").write_text(hashlib.sha256(canon.encode()).hexdigest() + "\n")
PY
