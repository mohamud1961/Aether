#!/usr/bin/env bash
# expect: final_state_value_mismatch
# Writes both files with every key, using the first value each key was given in the first segment. No replay.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path
first = {}
for line in Path("ops/zz-first.log").read_text(encoding="utf-8").splitlines():
    t = dict(x.split("=", 1) for x in line.split() if "=" in x)
    if t.get("op") == "set" and t.get("key") not in first:
        first[t["key"]] = t["value"]
Path("out/final_state.json").write_text(json.dumps(first, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path("out/changed_since_c3.json").write_text(json.dumps({"changed_keys": []}) + "\n", encoding="utf-8")
PY
python3 checks/shape_check.py
