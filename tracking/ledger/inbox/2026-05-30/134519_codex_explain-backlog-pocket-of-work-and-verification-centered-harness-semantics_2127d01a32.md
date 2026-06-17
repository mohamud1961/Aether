# Raw Ledger Update

- recorded_at_utc: 2026-05-30T13:45:19.664372+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: explain backlog pocket-of-work and verification-centered harness semantics
- event_type: decision
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 2127d01a32cea85855daf1195e9f9713e8a791accc66c8394d28eb89169bdb7f
- commit_message: NONE - no tracked file changes
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-05-30/134519_codex_explain-backlog-pocket-of-work-and-verification-centered-harness-semantics_2127d01a32.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: explain backlog pocket-of-work and verification-centered harness semantics
- event_type: decision
- summary: Clarified that old pocket-of-work variants should not be adopted as-is, but the useful idea survives as a verified evidence/state capsule. Verification-centered harnessing should be layered: deterministic checks where task artifacts/tests/contracts exist, harness-generated generic sanity checks, model-generated verification plans for ambiguous tasks, and optional secondary-model review as advisory rather than authority.
- observations: Prior backlog analysis marked old work_pocket_answer_projection_01 as historically killed due unstable uplift and regressions. Latest failures include wrong artifact path/hash, missing solution file, wrong service port, and wrong command schema, all of which require evidence-bound state and verification receipts. TerminalBench-style tasks define final correctness through external tests/verifiers, but the agent harness only sees prompt, files, visible tests, and runtime evidence; it cannot deterministically know hidden grader truth except through task-provided or inferred checks.
- inference: The winning harness should use a verified work pocket/state capsule, not an unconstrained pocket-of-work answer projector. Internal verification should be deterministic-first, model-assisted-second, and externally-graded-last. A secondary model can be valuable for adversarial review or criteria extraction, but should not replace executable tests and receipts.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/tracking/collab/variant_hypothesis_backlog.md; /Users/mohamud/Downloads/harnesseng/tracking/collab/final_harness_eval_suite/runs/20260530T030414Z/result_rows/fsent_05_long_handoff_composition_smoke.json; /Users/mohamud/Downloads/harnesseng/tracking/collab/final_harness_eval_suite/runs/20260530T030414Z/result_rows/fhard_02_service_orchestration_flagship.json; /private/tmp/fhes_pull/full_runs_min/tracking/collab/final_harness_eval_suite/runs/20260530T000729Z
- affected_components: context/evidence memory; verification layer; proposed winning harness; backlog variant selection
- decision_change: Use verified evidence/state capsule as the successor to pocket-of-work; define verification as a layered evidence process, not only a deterministic oracle or only a model review.
- unresolved_questions: Need implementable interface for criteria extraction, evidence ledger, executable checks, and optional adversarial reviewer within the next harness prototype.
- confidence: high
- commit_message: NONE - no tracked file changes
```
