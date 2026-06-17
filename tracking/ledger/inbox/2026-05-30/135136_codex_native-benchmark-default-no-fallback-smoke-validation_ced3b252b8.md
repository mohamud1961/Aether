# Raw Ledger Update

- recorded_at_utc: 2026-05-30T13:51:36.029090+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: native benchmark default + no-fallback smoke validation
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: ced3b252b8158dadbde65644e18089839d7aceec744a296351200b0a055a8b69
- commit_message: HOLD - native-mode and VM smoke verified but working tree is globally dirty and needs isolated commit slicing
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-05-30/135136_codex_native-benchmark-default-no-fallback-smoke-validation_ced3b252b8.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: native benchmark default + no-fallback smoke validation
- event_type: implementation
- summary: Implemented native-mode runner paths for ContextBench and Letta, staged ACEBench upstream on VM, and validated VM no-model native smoke for benchmark and TerminalBench challenge lanes without invalid adapter-unsupported outcomes.
- observations: Benchmark native smoke run 20260530T134928Z on VM produced 12/12 non-invalid rows (all fail, zero invalid). TerminalBench challenge smoke run 20260530T135017Z produced 2/2 executed rows with terminalbench_verifier_failed (no invalid). Prior run 20260530T134621Z showed native_runtime_not_implemented removed for ContextBench and replaced by executed fail outcomes.
- inference: Native-default execution is now active and strict no-fallback for implemented families; current rows fail for task-performance reasons rather than adapter coverage/runtime-not-implemented invalids.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/tools/run_final_harness_eval_suite_baseline.py; /Users/mohamud/Downloads/harnesseng/runner/benchmark_adapter_contextbench.py; /Users/mohamud/Downloads/harnesseng/runner/benchmark_adapter_letta.py; /Users/mohamud/Downloads/harnesseng/runner/benchmark_adapter_acebench.py; /private/tmp/fhes_pull_native_smoke/20260530T134928Z_result_rows.jsonl; /private/tmp/fhes_pull_native_smoke/20260530T135017Z_result_rows.jsonl
- affected_components: final harness baseline runner; contextbench adapter; letta adapter; acebench adapter; VM benchmark assets
- decision_change: Keep native as default benchmark mode and continue using VM-only runs for authoritative smoke.
- unresolved_questions: Whether to add a dedicated native preflight-only CLI mode and whether to deallocate VM now or keep alive for immediate next run.
- confidence: high
- commit_message: HOLD - native-mode and VM smoke verified but working tree is globally dirty and needs isolated commit slicing
```
