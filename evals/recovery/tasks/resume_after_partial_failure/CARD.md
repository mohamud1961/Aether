# Task card: resume_after_partial_failure

Admission: capability (default). The grader inspects the end state only; it does not run the candidate's code, so the task is safe for model agents.

New task in the recovery family. It exercises resume-after-crash: a journal that is partly right, a torn output line, uncommitted rows from the failed batch, a stale "complete" status note and an older backup.

## Design

- The journal is the record of what committed. The output is rebuilt for every batch that is not committed, so uncommitted rows cannot leak in.
- The status note and the README's restore advice are stale distractors. The backup is an older snapshot with 8 rows.
- The visible check only tests that the last journal event is a commit. A journal-only fake passes it.

## Controls

- Known-bad: 7 scripts (`known_bad/`), each a single-rule mutation of the reference.
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Reason coverage

| Reason | Controls |
|---|---|
| duplicate_row | known_bad duplicate_row_after_rerun |
| missing_row | known_bad skipped_last_batch, restored_from_backup; careless skip_check |
| invalid_output_line | known_bad torn_line_kept; careless do_nothing |
| journal_inconsistent | known_bad journal_double_commit; careless half_done |
| row_value_mismatch | known_bad stale_transform_row; careless fake_it |
| input_modified | known_bad input_edited |
| protected_file_modified | careless wrong_target |
