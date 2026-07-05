# Verifier-Only Evaluation Validation

Bundle: `verifier_only_eval_20260704_packet_hygiene_54mini_v2`

Overall: `PASS`

## Cases

| case | ok | parsed verdict | active findings | problems |
|---|---:|---|---|---|
| insufficient_evidence | True | uncertain_missing_evidence | [] | [] |
| missing_artifact | True | needs_repair | ['missing-out-txt'] | [] |
| repeated_no_progress | True | needs_repair | ['vf-loop'] | [] |
| schema_mismatch | True | needs_repair | ['finding-outtxt-missing-result'] | [] |
| semantic_wrong | True | needs_repair | ['out-txt-wrong-token'] | [] |
| solver_claim_conflicts_with_raw_state | True | uncertain_missing_evidence | [] | [] |

This validator is offline-only. It does not call a model, solver, Docker, VM, benchmark, board, or official grader.
