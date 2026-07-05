# Verifier-Only Evaluation Validation

Bundle: `verifier_only_eval_fake_memory_verifier_repair_check`

Overall: `PASS`

## Cases

| case | ok | parsed verdict | active findings | problems |
|---|---:|---|---|---|
| insufficient_evidence | True | uncertain_missing_evidence | [] | [] |
| missing_artifact | True | needs_repair | ['vf-missing-artifact'] | [] |
| repeated_no_progress | True | needs_repair | ['vf-loop-still-active'] | [] |
| schema_mismatch | True | needs_repair | ['vf-schema'] | [] |
| semantic_wrong | True | needs_repair | ['vf-semantic-wrong'] | [] |

This validator is offline-only. It does not call a model, solver, Docker, VM, benchmark, board, or official grader.
