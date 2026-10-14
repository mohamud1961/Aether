#!/usr/bin/env bash
# Finishes the migration in the current directory (the workspace root) from the journal.
# Batches already committed in the journal are kept as they are; the uncommitted batch's
# started event and any rows it left behind are discarded; the remaining batches are written
# from the input with the documented transform. The input and backups are not touched.
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path

size = 8
rows = [json.loads(l) for l in Path("data/input/users.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
batches = [rows[i:i + size] for i in range(0, len(rows), size)]


def transform(r):
    return {"user_id": r["id"], "email": r["email"].strip().lower(),
            "display_name": " ".join(r["name"].split()), "created_on": r["created"][:10]}


journal_path = Path("state/migration_journal.jsonl")
events = [json.loads(l) for l in journal_path.read_text(encoding="utf-8").splitlines() if l.strip()]
committed = {e["batch"] for e in events if e["event"] == "committed"}
kept = [e for e in events if e["batch"] in committed]
out_lines = []
for number, batch in enumerate(batches, start=1):
    if number not in committed:
        kept.append({"batch": number, "event": "started", "first_id": batch[0]["id"], "last_id": batch[-1]["id"]})
    out_lines.extend(json.dumps(transform(r), sort_keys=True, ensure_ascii=False) for r in batch)
    if number not in committed:
        kept.append({"batch": number, "event": "committed", "rows": len(batch), "last_id": batch[-1]["id"]})
Path("data/output/users_v2.jsonl").write_text("\n".join(out_lines) + "\n", encoding="utf-8")
journal_path.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in kept), encoding="utf-8")
PY
python3 checks/visible_check.py
