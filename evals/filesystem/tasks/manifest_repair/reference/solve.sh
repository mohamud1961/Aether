#!/usr/bin/env bash
# Derives the release contract from the draft in release/manifest.json and writes the three
# release files. Touches nothing outside release/.
set -euo pipefail
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

release = Path("release")
draft = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
manifest = {
    "files": [name for name in draft["files"] if name.startswith("release/")],
    "maintainer": draft["maintainer"],
    "project": draft["project"],
    "release": draft["release"],
    "status": "ready",
}
canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
(release / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(release / "summary.txt").write_text(
    f"{manifest['project']} {manifest['release']} is {manifest['status']}; "
    f"tracked files: {len(manifest['files'])}.\n",
    encoding="utf-8",
)
(release / "checksum.txt").write_text(hashlib.sha256(canonical.encode("utf-8")).hexdigest() + "\n", encoding="utf-8")
PY
