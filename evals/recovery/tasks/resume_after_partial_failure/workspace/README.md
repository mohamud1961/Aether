# users migration

Converts `data/input/users.jsonl` into `data/output/users_v2.jsonl` with `tools/migrate_users.py`.

The migration is safe to re-run from the start. If the output looks wrong, copy the newest
snapshot from `backup/` back into `data/output/` and run the tool again. The journal is for
information only.
