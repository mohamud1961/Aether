"""Visible check: the output file is non-empty and the journal's last event is a commit. Shape only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
output = ROOT / "data" / "output" / "users_v2.jsonl"
journal = ROOT / "state" / "migration_journal.jsonl"
events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
last = events[-1] if events else {}
if output.exists() and output.stat().st_size > 0 and last.get("event") == "committed":
    print("passed")
    raise SystemExit(0)
print("failed")
raise SystemExit(1)
