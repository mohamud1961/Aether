#!/usr/bin/env python3
"""Readiness gate: checks that the output file parses as JSON and is an array (NOT correctness)."""
import json
import sys
from pathlib import Path

path = Path("out/canonical.json")
if not path.is_file():
    print("missing output")
    sys.exit(1)
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except ValueError:
    print(json.dumps({"passed": False, "reason": "not_json"}))
    sys.exit(1)
print(json.dumps({"passed": isinstance(data, list)}, sort_keys=True))
sys.exit(0 if isinstance(data, list) else 1)
