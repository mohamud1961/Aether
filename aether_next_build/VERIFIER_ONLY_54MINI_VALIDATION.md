# Verifier-Only Evaluation Validation

Bundle: `verifier_only_eval_54mini_20260629_220014`

Overall: `PASS`

## Cases

| case | ok | parsed verdict | active findings | problems |
|---|---:|---|---|---|
| insufficient_evidence | True | uncertain_missing_evidence | [] | [] |
| missing_artifact | True | needs_repair | ['missing-out-txt-001'] | [] |
| repeated_no_progress | True | needs_repair | ['vf-loop'] | [] |
| schema_mismatch | True | needs_repair | ['missing-result-key-in-out-txt'] | [] |
| semantic_wrong | True | needs_repair | ['wrong_token_in_out_txt'] | [] |

This validator is offline-only. It does not call a model, solver, Docker, VM, benchmark, board, or official grader.
