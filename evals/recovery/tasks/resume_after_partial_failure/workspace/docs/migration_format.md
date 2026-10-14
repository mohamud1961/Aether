# users_v2 migration format

This is the source of truth for the output and the journal.

## Input

`data/input/users.jsonl` is the original export: one JSON object per line with `id`, `email`,
`name` and `created`. It is never modified.

## Output

`data/output/users_v2.jsonl` holds one line per input row, in input order. Each line is a JSON
object with exactly these keys:

- `user_id`: the input `id`.
- `email`: the input `email`, trimmed and lower-cased.
- `display_name`: the input `name` with runs of whitespace collapsed to one space and the ends
  trimmed.
- `created_on`: the first 10 characters of the input `created` (the date).

The file has no duplicate rows, no missing rows, no blank lines and no partial lines. Every line
ends with a newline.

## Batches and journal

Rows go in batches of 8 input rows, numbered from 1. Batch n holds input rows (n-1)*8+1 to n*8.
The last batch may be shorter.

`state/migration_journal.jsonl` holds one JSON object per line:

- `{"batch": n, "event": "started", "first_id": ..., "last_id": ...}`
- `{"batch": n, "event": "committed", "rows": ..., "last_id": ...}`

A batch is committed when its rows are in the output and its committed event is written. In the
final journal, every batch has exactly one committed event, with `rows` equal to the batch size
and `last_id` equal to the batch's last `id`. Every batch's last event is its committed event.
Started events may repeat. No event may refer to a batch that does not exist.

## Backups

Files in `backup/` are snapshots taken during earlier runs. They are not a source of truth.
