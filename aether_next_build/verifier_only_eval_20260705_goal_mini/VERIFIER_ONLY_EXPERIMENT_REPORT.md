# Verifier-Only Experiment Report

Mode: `model`

| case | raw verdict | parsed verdict | parse ok | active findings | evidence-bound | actionable | notes | artifact paths |
|---|---|---|---|---|---|---|---|---|
| semantic_wrong | raw_text | uncertain_missing_evidence | True | [] | True | True | deterministic judgement for semantic_wrong | ['out.txt'] |
| solver_claim_conflicts_with_raw_state | raw_text | uncertain_missing_evidence | True | [] | True | True | deterministic judgement for solver_claim_conflicts_with_raw_state | ['summary.csv'] |
| missing_artifact | raw_text | parse_error | False | [] | False | False | parse failed | [] |
| schema_mismatch | raw_text | uncertain_missing_evidence | True | [] | True | True | deterministic judgement for schema_mismatch | ['out.txt'] |
| repeated_no_progress | raw_text | parse_error | False | ['vf-loop'] | False | False | parse failed | [] |
| insufficient_evidence | raw_text | parse_error | False | [] | False | False | parse failed | ['out.txt'] |

No solver, Docker, VM, benchmark, or official grader run is performed by this script.
