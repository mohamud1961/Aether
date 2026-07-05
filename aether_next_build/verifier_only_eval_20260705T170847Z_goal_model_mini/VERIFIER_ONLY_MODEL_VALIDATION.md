# Verifier-Only Evaluation Validation

Bundle: `/Users/mohamud/Downloads/harnesseng/aether_next_build/verifier_only_eval_20260705T170847Z_goal_model_mini`

Overall: `FAIL`

## Cases

| case | ok | parsed verdict | active findings | problems |
|---|---:|---|---|---|
| insufficient_evidence | False | needs_repair | ['f1'] | ["expected uncertain_missing_evidence, got 'needs_repair'"] |
| missing_artifact | True | needs_repair | ['missing-out-txt'] | [] |
| repeated_no_progress | True | needs_repair | ['vf-loop'] | [] |
| schema_mismatch | True | needs_repair | ['out-txt-missing-result-key'] | [] |
| semantic_wrong | True | needs_repair | ['out-txt-content-mismatch'] | [] |
| solver_claim_conflicts_with_raw_state | False | needs_repair | ['wrong-error-count'] | ["expected uncertain_missing_evidence, got 'needs_repair'"] |

This validator is offline-only. It does not call a model, solver, Docker, VM, benchmark, board, or official grader.
