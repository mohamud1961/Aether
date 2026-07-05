RAW_LEDGER_UPDATE
- actor: claude worker
- task: BFCL faithfulness audit — determine whether BFCL can genuinely run model-backed against official cases and grader
- event_type: audit
- summary: Audited the entire BFCL native adapter stack (bfcl_native.py, bfcl_assets.py, API classes, benchmark samples, external_benchmarks.py grader source, vendor/compat shims). Verdict: BFCL CANNOT run faithfully model-backed. The shims are cosmetic — they satisfy import checks and make native_grader_preflight() report native_runtime_available:True, but every data layer underneath is synthetic or stubbed.
- observations: |
    1. bfcl_v3_final.json contains 3 synthetic cases (not official BFCL data) with ground truth using only ping(tag=...) calls. 2 of 5 curated case IDs are missing (multi_turn_composite_199, multi_turn_miss_func_55). load_official_curated_cases() would raise ValueError.
    2. BFCL API classes (eval_suite/fixtures/bfcl/bfcl/bfcl_apis/*.py) are stubs: a _Base class with only ping() and _load_scenario(). No domain methods (create_ticket, send_message, place_order, etc.). Real BFCL API classes have dozens of methods each.
    3. external_benchmarks.py is a sentinel stub: BFCL_V3_CASES=[], run_bfcl_case() returns {"status":"stubbed"}.
    4. Vendor shims (deepagents, langchain_core, langgraph, langsmith) use CompatObject — a permissive no-op that swallows all attribute access.
    5. The prior n2 attempt (20260620T014137Z) ran 2 rows with model_calls>0 but against these synthetic ping() cases — not real BFCL. Both failed (candidate_missing), but even a pass would be meaningless.
    6. The adapter code itself (grade_bfcl_case_native, state-replay logic) is genuine and correctly implemented — it just operates on fake data.
- inference: The BFCL adapter is real plumbing operating on synthetic fixtures. Making it faithful requires: (a) real BFCL API source from gorilla repo, (b) real bfcl_v3_final.json with official cases, (c) real grader source. Without these, any model-backed run produces measurement theater.
- evidence_paths: eval_suite/adapters/bfcl_native.py; eval_suite/adapters/bfcl_assets.py; eval_suite/fixtures/bfcl/bfcl/bfcl_apis/ticket_api.py; eval_suite/fixtures/bfcl/bfcl/benchmark_samples/bfcl_v3_final.json; research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py; research/sources/bfcl_native_vendor/compat.py
- affected_components: BFCL native adapter, BFCL API fixtures, BFCL benchmark samples, vendor shims
- decision_change: native_grader_preflight() reporting native_runtime_available:True is misleading and should not be treated as evidence that BFCL runs faithfully. model_backed_run_count from prior n2 attempt is not meaningful.
- unresolved_questions: none — the missing pieces are clearly identified
- confidence: high
- model_backed_run_performed: false
- model_backed_run_count: 0
- reason_for_no_run: all data layers are synthetic/stubbed; running would produce fraudulent results
- pytest_result: 128 passed, 1 skipped
- commit_message: NONE - no code changes, audit only
