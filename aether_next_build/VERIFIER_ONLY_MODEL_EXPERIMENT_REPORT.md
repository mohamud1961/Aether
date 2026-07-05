# VERIFIER_ONLY_MODEL_EXPERIMENT_REPORT

- generated_at: 2026-06-29T22:11:04
- scope: verifier-only fixed packets; no solver loop and no task attempts
- cases: semantic_wrong, missing_artifact, schema_mismatch, repeated_no_progress, insufficient_evidence

## Summary

| model | parse_ok | validation | verdicts | evidence_bound | actionable | active findings |
|---|---:|---|---|---:|---:|---|
| 5.4-mini | 5/5 | PASS | semantic_wrong=needs_repair, missing_artifact=needs_repair, schema_mismatch=needs_repair, repeated_no_progress=needs_repair, insufficient_evidence=uncertain_missing_evidence | 5/5 | 5/5 | semantic_wrong:wrong_token_in_out_txt, missing_artifact:missing-out-txt-001, schema_mismatch:missing-result-key-in-out-txt, repeated_no_progress:vf-loop, insufficient_evidence:none |
| 5.3-codex | 5/5 | PASS | semantic_wrong=needs_repair, missing_artifact=needs_repair, schema_mismatch=needs_repair, repeated_no_progress=needs_repair, insufficient_evidence=uncertain_missing_evidence | 5/5 | 5/5 | semantic_wrong:out-token-mismatch, missing_artifact:missing-out-txt-artifact, schema_mismatch:missing-result-key-outtxt, repeated_no_progress:vf-loop, insufficient_evidence:missing-content-and-verification-evidence |

## Assessment

- 5.4-mini satisfies the Phase 3 gate: all packets parsed, all expected verdicts matched, every row is evidence-bound and actionable, and validation is PASS.
- 5.3-codex comparison also validates on the same packets. It records an active finding for `insufficient_evidence` while retaining the required `uncertain_missing_evidence` verdict; that is a permissible but stricter feedback style to monitor.
- No solver, task, board, Docker, VM, or official grader was run in this phase.

## Evidence Paths

- `verifier_only_eval_54mini_20260629_220014/summary.json`
- `verifier_only_eval_54mini_20260629_220014/*/{raw_output.json,parsed_result.json,active_findings_after.json,judgement.json,verifier_packet.json}`
- `VERIFIER_ONLY_54MINI_VALIDATION.md`
- `verifier_only_eval_53codex_20260629_220134/summary.json`
- `verifier_only_eval_53codex_20260629_220134/*/{raw_output.json,parsed_result.json,active_findings_after.json,judgement.json,verifier_packet.json}`
- `VERIFIER_ONLY_53CODEX_VALIDATION.md`