# Verifier-Only Evaluation Validation

Bundle: `verifier_only_eval_53codex_20260629_220134`

Overall: `PASS`

## Cases

| case | ok | parsed verdict | active findings | problems |
|---|---:|---|---|---|
| insufficient_evidence | True | uncertain_missing_evidence | ['missing-content-and-verification-evidence'] | [] |
| missing_artifact | True | needs_repair | ['missing-out-txt-artifact'] | [] |
| repeated_no_progress | True | needs_repair | ['vf-loop'] | [] |
| schema_mismatch | True | needs_repair | ['missing-result-key-outtxt'] | [] |
| semantic_wrong | True | needs_repair | ['out-token-mismatch'] | [] |

This validator is offline-only. It does not call a model, solver, Docker, VM, benchmark, board, or official grader.
