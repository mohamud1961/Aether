"""Migrate data/input/users.jsonl to data/output/users_v2.jsonl in batches, journaling each batch.

Layout and journal rules: docs/migration_format.md.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "input" / "users.jsonl"
OUTPUT = ROOT / "data" / "output" / "users_v2.jsonl"
JOURNAL = ROOT / "state" / "migration_journal.jsonl"
BATCH_SIZE = 8


def transform(record):
    return {
        "user_id": record["id"],
        "email": record["email"].strip().lower(),
        "display_name": " ".join(record["name"].split()),
        "created_on": record["created"][:10],
    }


def load_rows():
    with INPUT.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main():
    rows = load_rows()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("", encoding="utf-8")
    with JOURNAL.open("a", encoding="utf-8") as journal, OUTPUT.open("a", encoding="utf-8") as out:
        for number, start in enumerate(range(0, len(rows), BATCH_SIZE), start=1):
            batch = rows[start:start + BATCH_SIZE]
            journal.write(json.dumps({"batch": number, "event": "started",
                                      "first_id": batch[0]["id"], "last_id": batch[-1]["id"]}) + "\n")
            journal.flush()
            for record in batch:
                out.write(json.dumps(transform(record), sort_keys=True, ensure_ascii=False) + "\n")
            out.flush()
            journal.write(json.dumps({"batch": number, "event": "committed",
                                      "rows": len(batch), "last_id": batch[-1]["id"]}) + "\n")
            journal.flush()


if __name__ == "__main__":
    main()
