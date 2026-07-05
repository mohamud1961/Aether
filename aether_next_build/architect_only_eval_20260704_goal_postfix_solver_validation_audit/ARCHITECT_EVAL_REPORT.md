# Architect-Only Eval Report

Scope: old ContractArchitect vs Runtime Workbench Architect on official task prompts/workspace maps.
Official test/grader excerpts are saved as review context only; they are not sent to the architect model.

| task | old score | overall | solver | verifier | config | key missing |
|---|---:|---:|---:|---:|---:|---|
| log-summary-date-ranges | 0/8 | 10.0/10 | 10/10 | 10/10 | 10/10 | none |

## Notes

### log-summary-date-ranges

- Old missing: parseable TaskContract
- Overall: 10.0/10
- Solver prompt: 10/10 missing=none
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 551
- Verifier prompt words: 405
- Solver role: Log aggregation and CSV emission agent for date-bucketed severity counting.
- Verifier role: Read-only current-state auditor for the log summary CSV.
- Workflow: First inspect /app/logs and sample the log format; if the directory is missing, empty, or ambiguous, inspect /app/log_generator_deterministic.py only as a format clue before writing the parser. / Compute counts by parsing each filename date and each line's exact severity token, using 2025-08-12 as the fixed reference date and inclusive boundaries for today, last 7 days, last 30 days, month-to-date, and total. / Write /app/summary.csv with the exact header and exact row order requested, then use run_command or the best available interpreter to recompute counts from the source logs and compare every period/severity bucket against the CSV. / If automatic memory surfaces a repeat read, check, or write, reuse the prior evidence, narrow the scope to the changed file or suspected bucket, or justify the repeat only if the source logs or parser logic changed. / If a failed check or verifier finding names a missing or wrong row, repair that artifact, rerun the relevant validation, and resubmit only after fresh evidence shows the gap is closed.
- Self-verification: Confirm /app/summary.csv exists, has exactly the header plus 15 data rows, and every required period/severity pair appears exactly once in the specified order. / Recompute the five date windows from the log filenames and verify the CSV counts are nonnegative integers that exactly match the recomputed matrix for ERROR, WARNING, and INFO. / Check that the date windows are inclusive, that month-to-date starts on 2025-08-01, and that total covers all log files regardless of date. / If a failed check exposes a mismatch, inspect the named period/severity bucket or date filter, change the parser or aggregation logic, rerun the same validation, and only then resubmit. / Do not rely on file existence or syntax checks alone as proof of correct counts.
- Evidence requirements: Produce /app/summary.csv with the exact header and the 15 required data rows in the specified order. / Demonstrate that counts were derived from all relevant /app/logs files using filename dates and exact severity tokens, with inclusive date windows anchored to 2025-08-12. / Produce a fresh local recomputation or validation pass that matches the CSV exactly before submission.
- False-positive risks: Hardcoding totals or counting only visible filenames instead of parsing every log line. / Missing inclusive boundaries, especially 2025-08-12 itself, 2025-08-01 for month-to-date, and the full last-7-day and last-30-day windows. / Case-insensitive or substring matching that treats non-exact severity text as ERROR, WARNING, or INFO. / A CSV that passes shape checks but has the wrong row order or stale counts after the logs changed.
- Minimum completion evidence: /app/summary.csv exists and is readable. / The file contains the exact header and 15 required rows in order. / A fresh recomputation over /app/logs matches every period/severity count in the CSV.
