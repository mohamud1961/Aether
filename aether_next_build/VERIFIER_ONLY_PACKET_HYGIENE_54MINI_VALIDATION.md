# Verifier-Only Evaluation Validation

Bundle: `verifier_only_eval_20260704_packet_hygiene_54mini`

Overall: `FAIL`

## Cases

| case | ok | parsed verdict | active findings | problems |
|---|---:|---|---|---|
| insufficient_evidence | False | uncertain_missing_evidence | [] | ['judgement.evidence_bound is not true'] |
| missing_artifact | True | needs_repair | ['missing-out-txt'] | [] |
| repeated_no_progress | True | needs_repair | ['vf-loop'] | [] |
| schema_mismatch | True | needs_repair | ['missing-result-key'] | [] |
| semantic_wrong | True | needs_repair | ['out-txt-wrong-token'] | [] |
| solver_claim_conflicts_with_raw_state | True | uncertain_missing_evidence | [] | [] |

This validator is offline-only. It does not call a model, solver, Docker, VM, benchmark, board, or official grader.
