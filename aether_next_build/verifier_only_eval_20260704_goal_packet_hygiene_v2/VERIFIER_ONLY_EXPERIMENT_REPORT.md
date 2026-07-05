# Verifier-Only Experiment Report

Mode: `fake`

| case | raw verdict | parsed verdict | parse ok | active findings | evidence-bound | actionable | notes | artifact paths |
|---|---|---|---|---|---|---|---|---|
| semantic_wrong | needs_repair | needs_repair | True | ['vf-semantic-wrong'] | True | True | deterministic judgement for semantic_wrong | ['out.txt'] |
| solver_claim_conflicts_with_raw_state | uncertain_missing_evidence | uncertain_missing_evidence | True | [] | True | True | deterministic judgement for solver_claim_conflicts_with_raw_state | ['summary.csv'] |
| missing_artifact | needs_repair | needs_repair | True | ['vf-missing-artifact'] | True | True | deterministic judgement for missing_artifact | [] |
| schema_mismatch | needs_repair | needs_repair | True | ['vf-schema'] | True | True | deterministic judgement for schema_mismatch | ['out.txt'] |
| repeated_no_progress | needs_repair | needs_repair | True | ['vf-loop-still-active'] | True | True | deterministic judgement for repeated_no_progress | [] |
| insufficient_evidence | uncertain_missing_evidence | uncertain_missing_evidence | True | [] | True | True | deterministic judgement for insufficient_evidence | ['out.txt'] |

No solver, Docker, VM, benchmark, or official grader run is performed by this script.
