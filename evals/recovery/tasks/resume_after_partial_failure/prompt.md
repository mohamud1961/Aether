# Finish the users migration that crashed

The users migration (`tools/migrate_users.py`) died partway through its last run, in batch 3. We need the full `data/output/users_v2.jsonl` finished, with the progress journal brought up to date. The migration rules and the output and journal formats are in `docs/migration_format.md`.

Some things you find in the workspace may be out of date or misleading. The README, the status note and the backup folder all describe the state differently. Work out what the crashed run actually committed.

## Deliverable

- `data/output/users_v2.jsonl` holds exactly one correct line for every input row, in input order, with no duplicate, missing or partial lines.
- `state/migration_journal.jsonl` is consistent with the output, as the format doc describes.
- `data/input/users.jsonl` is the original export and must stay byte-for-byte unchanged. Do not restore anything from `backup/`.
- Do not edit the README, the format doc, the backup, the checks or the logs.
- Before you finish, run `python3 checks/visible_check.py` from the workspace root. It only looks at the last journal event, so it does not show that the output is right.
