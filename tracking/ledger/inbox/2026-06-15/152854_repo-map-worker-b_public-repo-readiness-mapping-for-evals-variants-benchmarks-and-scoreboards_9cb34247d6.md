# Raw Ledger Update

- recorded_at_utc: 2026-06-15T15:28:54.492160+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: repo_map_worker_b
- task: public repo readiness mapping for evals, variants, benchmarks, and scoreboards
- event_type: source_analysis | decision
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 9cb34247d638ae222f51c9b1f083fe9c41b7291a9bd02a1c9e96bb299d9b9e08
- commit_message: HOLD - report only; no tracked code changes
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-15/152854_repo-map-worker-b_public-repo-readiness-mapping-for-evals-variants-benchmarks-and-scoreboards_9cb34247d6.md

```text
RAW_LEDGER_UPDATE
- actor: repo_map_worker_b
- task: public repo readiness mapping for evals, variants, benchmarks, and scoreboards
- event_type: source_analysis | decision
- summary: Mapped the public/private boundary for eval, variant, benchmark, task, and scoreboard surfaces across evals/, experiments/, tracking/variants/, tracking/collab/final_harness_eval_suite/, official_tasks/, tasks/, and tools/.
- observations: evals/ is only a lightweight scaffold today; experiments/ is a placeholder config area; tracking/variants/ is raw run evidence; final_harness_eval_suite mixes publicizable board manifests with private task packs and run folders; aether2_g2_homologs is the strongest public custom-homolog candidate; official_tasks/ contains 90 benchmark task dirs with no top-level license file in the scan; tracking/collab g5 analysis folders are private run-analysis bundles.
- inference: The public repo should be family-level and sanitized, not run-level; benchmark-derived hidden-contract task packs and raw host-receipt bundles should remain private; calibration-only boards can be public if explicitly non-certifying.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/evals/README.md; /Users/mohamud/Downloads/harnesseng/experiments/README.md; /Users/mohamud/Downloads/harnesseng/tasks/README.md; /Users/mohamud/Downloads/harnesseng/tracking/collab/final_harness_eval_suite/final_suite_registry.yaml; /Users/mohamud/Downloads/harnesseng/tracking/collab/final_harness_eval_suite/official_benchmark_family_board.yaml; /Users/mohamud/Downloads/harnesseng/tracking/collab/final_harness_eval_suite/terminalbench_challenge_lane.yaml; /Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/pre_g3_ready_handoff_20260612.md; /Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g5_run_analysis_20260613/analysis_manifest.json; /Users/mohamud/Downloads/harnesseng/tracking/collab/public_repo_readiness/repo_map_worker_b_evals_variants.md
- affected_components: evals; experiments; tracking/variants; tracking/collab/final_harness_eval_suite; tracking/collab/aether2_g2_homologs; tracking/collab/aether2_g5_*; official_tasks; tasks; tools
- decision_change: Recommend a sanitized public eval_suite/ plus family-level variants/ tree, while keeping official_tasks/ and all raw run bundles private by default.
- unresolved_questions: Whether aether2_g2_homologs should keep Aether-2 branding publicly; whether any adapter_fixtures can be redistributed without upstream license issues; whether any benchmark-derived custom rows beyond calibration lanes should be published at all.
- confidence: high
- commit_message: HOLD - report only; no tracked code changes
```
