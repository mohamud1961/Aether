# Ceiling: resume_after_partial_failure

## What a perfect solution does

1. Reads `docs/migration_format.md`. Treats `state/STATUS.txt` ("COMPLETE") and the README's restore advice as wrong.
2. Reads the journal. Batches 1 and 2 are committed. Batch 3 has a started event and no commit. Batch 4 has no events.
3. Keeps the committed rows. Discards the uncommitted rows of batch 3 and the torn line, then writes batches 3 and 4 from the input with the documented transform. Or rewrites the whole output from the input with the same transform, which gives the same result.
4. Writes the journal so that every batch has exactly one committed event, with the right row count and last id, and every batch ends on a commit. Keeps the earlier committed events.
5. Leaves `data/input/users.jsonl` and everything in `backup/` untouched. Runs the visible check, which passes once the journal ends on a commit.

## Grader checks (end state)

- The output has one line per input row. Each line is a complete JSON object with exactly the four keys (`invalid_output_line`, `missing_output`).
- No duplicate ids (`duplicate_row`), no missing ids (`missing_row`), no ids that are not in the input (`unexpected_row`), no wrong values (`row_value_mismatch`), and input order preserved (`row_order_mismatch`).
- The journal has exactly one committed event for each of the 4 batches, with the right `rows` and `last_id`, and each batch ends on its commit (`journal_inconsistent`).
- The input hash is unchanged (`input_modified`). The protected files are unchanged (`protected_file_modified`).

## Why each known-bad is wrong

- `duplicate_row_after_rerun`: the stale uncommitted rows are kept and batch 3 is appended again, so user 17 appears twice (`duplicate_row`).
- `skipped_last_batch`: batch 4 is never written (`missing_row`).
- `restored_from_backup`: the older 8-row snapshot is taken as the output (`missing_row`).
- `torn_line_kept`: the crash's partial line is left at the end (`invalid_output_line`).
- `journal_double_commit`: the output is exact, but the journal has two commits for batch 2 (`journal_inconsistent`).
- `stale_transform_row`: one row keeps an old, un-lower-cased email (`row_value_mismatch`).
- `input_edited`: the original export is cleaned in place (`input_modified`).

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched crash state: fails with `invalid_output_line`, `journal_inconsistent` and `missing_row`.
