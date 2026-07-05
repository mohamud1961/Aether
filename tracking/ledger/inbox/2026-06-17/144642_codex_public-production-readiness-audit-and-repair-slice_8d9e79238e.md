# Raw Ledger Update

- recorded_at_utc: 2026-06-17T14:46:42.262216+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: public production-readiness audit and repair slice
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 8d9e79238e83939104ebacc8b650cd1ed8403d19ab9cc1655ab38a3ccef98aea
- commit_message: HOLD - substantial public audit repair slice completed but full public-surface restoration remains incomplete
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-17/144642_codex_public-production-readiness-audit-and-repair-slice_8d9e79238e.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: public production-readiness audit and repair slice
- event_type: implementation
- summary: Audited the public repo for audit readiness, verified the curated public path, and repaired a high-signal public split slice by restoring missing phase65 compatibility wrappers, benchmark-adapter smoke/native-attempt entrypoints, the active evidence kernel health gate, public-safe fallback data paths, and import-time resilience in legacy packet modules.
- observations: `make public-readiness` still passes. A full `python3 -m pytest -q` no longer fails with 43 collection errors; after the repair slice it fails with 15 collection errors concentrated in still-missing public tool/orchestrator surfaces (`tools.clean_tool_contract_diagnostic_family`, `tools.run_eval_substrate_smoke`, `tools.eval_suite_orchestrator`, `tools.run_first_eval_core*`, `tools.run_clean_tool_contract_*`, `tools.run_eval_suite_v1_certification_baseline`, `tools.run_first_result_attribution_mechanism_*`, `tools.run_model_backed_baseline_certified_core`, `tools.run_goal1b_tooling_family_sprint`, `tools.ingest_final_harness_recipe_candidates`, `tools.overnight_control_plane`) plus local-env `pypdf` absence for `tests/test_extract_papers_text.py`.
- inference: The public repo is materially closer to being self-contained, but it is not yet production-grade or audit-pass for a full technical review because important claimed/public test surfaces are still absent rather than merely failing behaviorally.
- evidence_paths: README.md; PUBLIC_REVIEWER_GUIDE.md; pyproject.toml; research/sources/codebases/ContextBench/data/Verified.csv; runner/phase65_measurement_contracts.py; runner/phase65_measurement_grading.py; eval_suite/adapters/contextbench.py; runner/legacy_packets/letta_context_bench.py; runner/legacy_packets/packet07_hard_row_robustness_probe.py; runner/legacy_packets/packet04_route_manifest.py; runner/legacy_packets/successor_phase65_measurement_repair.py; tools/run_benchmark_adapter_contextbench_smoke.py; tools/run_benchmark_adapter_letta_smoke.py; tools/run_benchmark_adapter_terminalbench_smoke.py; tools/run_benchmark_adapter_acebench_smoke.py; tools/run_benchmark_adapter_contextbench_native_attempt.py; tools/run_benchmark_adapter_letta_native_attempt.py; tools/run_benchmark_adapter_terminalbench_native_attempt.py; tools/run_active_evidence_kernel_health_gate.py
- affected_components: public benchmark adapter smoke surfaces; phase65 grading compatibility; legacy packet import resilience; public fallback fixtures; audit readiness
- decision_change: Reduced the immediate recommendation from broad docs-only cleanup to public-surface restoration, because the main audit blocker is incomplete split wiring rather than narrative alone.
- unresolved_questions: Which of the remaining missing tool/orchestrator surfaces are intended to be truly public and should be restored versus removed from the public tree? Should `pypdf` be installed in CI/dev bootstrap or made optional/lazy for non-document flows?
- confidence: high
- commit_message: HOLD - substantial public audit repair slice completed but full public-surface restoration remains incomplete
```
