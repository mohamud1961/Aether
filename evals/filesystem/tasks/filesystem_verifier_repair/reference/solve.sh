#!/usr/bin/env bash
# Produces the correct final state in the current directory (the workspace root).
# Follows app/build.json to the config the boot wrapper loads, reads the requested value
# from the ticket, sets that one key, writes the submission and runs the visible check.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
import re
from pathlib import Path

root = Path(".")
target = json.loads((root / "app/build.json").read_text(encoding="utf-8"))["config_file"]
ticket = (root / "notes/ticket.md").read_text(encoding="utf-8")
wanted = int(re.search(r"Set `retries` in the live config to (\d+)", ticket).group(1))
path = root / target
text = path.read_text(encoding="utf-8")
patched, count = re.subn(r"(?m)^retries:[ \t]*\d+[ \t]*$", f"retries: {wanted}", text)
if count != 1:
    raise SystemExit(f"expected one retries line in {target}, found {count}")
path.write_text(patched, encoding="utf-8")

submission = {
    "patched_target": target,
    "verifier_command": "python3 checks/visible_check.py --candidate out/final_submission.json",
    "decoy_untouched": True,
}
(root / "out" / "final_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
PY
python3 checks/visible_check.py --candidate out/final_submission.json | tee out/verifier_run.log
