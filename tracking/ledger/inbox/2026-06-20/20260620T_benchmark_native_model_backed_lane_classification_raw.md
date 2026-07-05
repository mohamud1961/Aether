RAW_LEDGER_UPDATE
- actor: codex worker
- task: real model-backed benchmark lane classification for ACEBench, Letta, ContextBench, and BFCL
- event_type: source_analysis
- summary: Inspected adapter/runtime surfaces, native preflight reports, and saved local run artifacts to classify which lanes are real model-backed benchmark attempts versus equivalent or static diagnostics.
- observations: |
    - ACEBench native preflight reports missing upstream assets and pandas/openpyxl dependencies; the current smoke wrapper is equivalent-only and there is no dedicated benchmark-native model attempt wrapper in tools/.
    - ContextBench native preflight reports no blockers, but the current native code path is a static gold-ceiling evaluator run and the saved native-attempt wrapper remains a blocked-equivalent wrapper rather than a model-backed benchmark run.
    - Letta native preflight reports no blockers, but the current native code path is an official-judge routing/preflight surface and the saved native-attempt wrapper remains equivalent smoke plus blocker evidence rather than a benchmark-native model attempt.
    - BFCL native preflight reports missing official model runtime dependencies and missing official grader source; separately, the repo has a benchmark-derived local model board with scored Aether attempts, but that board is not an official/native BFCL promotion run.
- inference: None of the four benchmarks currently has a complete real benchmark-native model-backed lane in this checkout. ContextBench and Letta are closest to readiness but still lack an actual model-backed native runner path. ACEBench is upstream-blocked. BFCL remains blocked for official/native promotion even though a local model-backed homolog board exists.
- evidence_paths: |
    tracking/local_runs/benchmark_adapter_acebench/20260620T185646Z_post_all_targeted_repairs/native_blocker_report.json
    tracking/local_runs/benchmark_adapter_contextbench_native_attempt/20260619T191000Z/native_blocker_report.json
    tracking/local_runs/benchmark_adapter_letta_native_attempt/20260619T191000Z/native_blocker_report.json
    tracking/local_runs/benchmark_adapter_bfcl/20260619T191200Z/bfcl_readiness.json
    tracking/local_runs/bfcl_native_n2_attempt/20260620T014137Z/run_summary.json
    eval_suite/adapters/acebench.py
    eval_suite/adapters/contextbench.py
    eval_suite/adapters/contextbench_native.py
    eval_suite/adapters/letta.py
    eval_suite/adapters/letta_native.py
    eval_suite/adapters/bfcl_native.py
    tests/test_benchmark_adapter_readiness.py
    tests/test_benchmark_adapter_contracts.py
- affected_components: benchmark adapter readiness classification, native preflight reporting, local run evidence organization
- decision_change: No code changes were made in this slice. The next viable action is to add benchmark-native model-backed runners only where upstream assets and authoritative evaluators exist, starting with ContextBench or Letta in a follow-up goal if approved.
- unresolved_questions: Whether upstream-authoritative model-backed runner wrappers already exist outside this checkout for ContextBench or Letta; whether ACEBench upstream assets can be staged into /private/tmp/acebench_upstream; whether BFCL official vendor source and Python deps can be installed in a benchmark-native environment.
- confidence: high
- commit_message: NONE - no tracked file changes
