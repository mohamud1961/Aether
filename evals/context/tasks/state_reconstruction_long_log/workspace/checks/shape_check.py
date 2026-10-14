"""Shape check for out/. Confirms the two files parse and have the right top-level types. It does not check values."""
import json
from pathlib import Path

problems = []
try:
    state = json.loads(Path("out/final_state.json").read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not all(isinstance(v, str) for v in state.values()):
        problems.append("final_state_shape")
except (OSError, ValueError):
    problems.append("final_state_unreadable")
try:
    changed = json.loads(Path("out/changed_since_c3.json").read_text(encoding="utf-8"))
    if not isinstance(changed, dict) or not isinstance(changed.get("changed_keys"), list):
        problems.append("changed_since_c3_shape")
except (OSError, ValueError):
    problems.append("changed_since_c3_unreadable")
print(json.dumps({"passed": not problems, "problems": problems}, sort_keys=True))
