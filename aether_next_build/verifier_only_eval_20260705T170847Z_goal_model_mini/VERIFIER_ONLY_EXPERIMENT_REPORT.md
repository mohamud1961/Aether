# Verifier-Only Experiment Report

Mode: `model`

| case | raw verdict | parsed verdict | parse ok | active findings | evidence-bound | actionable | notes | artifact paths |
|---|---|---|---|---|---|---|---|---|
| semantic_wrong | raw_text | needs_repair | True | ['out-txt-content-mismatch'] | True | True | deterministic judgement for semantic_wrong | ['out.txt'] |
| solver_claim_conflicts_with_raw_state | raw_text | needs_repair | True | ['wrong-error-count'] | True | True | deterministic judgement for solver_claim_conflicts_with_raw_state | ['summary.csv'] |
| missing_artifact | raw_text | needs_repair | True | ['missing-out-txt'] | True | True | deterministic judgement for missing_artifact | [] |
| schema_mismatch | raw_text | needs_repair | True | ['out-txt-missing-result-key'] | True | True | deterministic judgement for schema_mismatch | ['out.txt'] |
| repeated_no_progress | raw_text | needs_repair | True | ['vf-loop'] | True | True | deterministic judgement for repeated_no_progress | [] |
| insufficient_evidence | raw_text | needs_repair | True | ['f1'] | True | True | deterministic judgement for insufficient_evidence | ['out.txt'] |

No solver, Docker, VM, benchmark, or official grader run is performed by this script.
