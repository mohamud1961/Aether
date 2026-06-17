# Raw Ledger Update

- recorded_at_utc: 2026-06-16T13:28:48.398286+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: promote actual public-safe eval and variant artifacts from collab/canonical sources into first-class public repo folders
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 3c46cfef99fb4b1098672c04130b0fa4fc81cf29a96db63cc4f7004925a89567
- commit_message: Promote real public eval packs, attempts, and variant code surfaces
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/132848_codex_promote-actual-public-safe-eval-and-variant-artifacts-from-collab-canonical-sources-into-first-class-public-repo-folders_3c46cfef99.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: promote actual public-safe eval and variant artifacts from collab/canonical sources into first-class public repo folders
- event_type: implementation
- summary: Promoted real code-bearing eval packs, graders, attempts, and mechanism modules into the public `eval_suite/`, `variants/`, and `research/synthesis/` surfaces to replace summary-only placeholders.
- observations: Copied executable benchmark-derived task packs with `grader/grade.py`, `timeout_policy.json`, visible verifiers, and visible solver workspaces into `eval_suite/benchmark_derived_families/task_packs/`; copied custom family packs into `eval_suite/custom/families/`; added harness-level custom registry `eval_suite/custom/harness/runtime_control_custom_harness_v1.json`; copied selected real attempt result-row JSON files into `eval_suite/attempts/final_harness_v1/`; copied real mechanism code into `variants/families/*/code/`, `variants/harness/code/`, and `variants/kernel/code/`; promoted deep synthesis artifacts into `research/synthesis/`; updated public indexes and scoreboards to point at executable leaves instead of prose-only surfaces.
- inference: The public repo map is materially stronger as a reviewer-facing proof surface because it now exposes actual engineering artifacts rather than mostly README wrappers.
- evidence_paths: README.md; eval_suite/README.md; eval_suite/custom/families/README.md; eval_suite/custom/harness/runtime_control_custom_harness_v1.json; eval_suite/benchmark_derived_families/task_packs/; eval_suite/harness_core/final_harness_v1/task_packs/; eval_suite/attempts/final_harness_v1/20260530T154156Z/ftb_challenge_extract_moves_from_video.json; eval_suite/scoreboards/public_benchmark_derived_families_v1.example.scoreboard.json; variants/families/tooling_tool_contract_tournament/code/contract_classifier.py; variants/families/attribution_guard_tournament/code/result_attribution_guard_common.py; variants/harness/code/packet04_route_manifest.py; variants/kernel/code/kernel_layer2_audit.py; research/synthesis/README.md; docs/publication/public_evidence_index.md
- affected_components: eval_suite; variants; research/synthesis; public evidence navigation
- decision_change: Replace summary-heavy public placeholders with code-bearing promoted artifacts wherever public-safe source material already exists.
- unresolved_questions: How much additional calibration-lane and whole-harness scoreboard material should be promoted as real attempts versus kept as aggregate public boards; whether more variant families should be promoted before publication freeze.
- confidence: high
- commit_message: Promote real public eval packs, attempts, and variant code surfaces
```
