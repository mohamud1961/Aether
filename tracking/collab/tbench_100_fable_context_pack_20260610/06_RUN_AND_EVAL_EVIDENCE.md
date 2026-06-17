# 06 — Run and Eval Evidence

This is the consolidated evidence ledger across official TB tasks, custom
eval suite runs, family-level/harness-level evals, smoke tests, and
benchmark-adapter results. **Failures are included deliberately** — this is
not a highlight reel.

---

## 1. 2026-05-17 — Combined Guard V1.5 Tournament (`076ba7694` / `0678492e2`)

- **Backend**: Azure VM `harnesseng-dev`, Ubuntu 24.04, Docker 29.1.3 —
  `docker_preflight.available: true`. **This is a confirmed-valid certified
  run.**
- **Task**: `clean_tool_contract_semantics` family — 2 target tasks
  (`ctc_semantics_002_no_call_wrong_call_traps`,
  `ctc_semantics_003_result_attribution`) + 1 sentinel
  (`ctc_semantics_001_multi_required_order`).
- **Variant/config**: 4 variants — `control_no_mechanism`,
  `ignored_result_ids_guard`, `no_call_attribution_guard`, `combined_guard`.
- **Result rows** (`comparison_summary.json`):
  | variant | target_pass | sentinel_pass | model_calls | tool_calls | total_sec |
  |---|---|---|---|---|---|
  | control_no_mechanism | 0/2 | 1/1 | — | — | — |
  | ignored_result_ids_guard | 0/2 | 1/1 | — | — | — |
  | no_call_attribution_guard | 1/2 | 1/1 | — | — | — |
  | combined_guard | **2/2** | **0/1** | 11 | 8 | ~20.8 |
- **Overall scoreboard** (`scoreboard.json`): `row_count: 12`,
  `totals: {pass: 6, fail: 6, invalid: 0}` = 6/12 (50%).
- **Status/result**: `combined_guard` hit both target tasks but **regressed
  the sentinel** — `prediction.json` predicted "no_material_regression," and
  that prediction **failed**.
- **What happened**: Mislabeled internally as a "perfect tournament run."
- **What we learned**: (a) Azure VM Docker backend works and is fast (~21s
  for 11 model calls / 8 tool calls); (b) the combined-guard mechanism is
  hardcoded to one tool name (`lookup_customer_order`) and not generalizable;
  (c) sentinel discipline matters — without it this would have been
  (wrongly) promoted.
- **Evidence strength**: HIGH (valid certified run) but **negative/mixed**
  result under the project's own promotion rules.
- **Paths**: `tracking/collab/first_result_attribution_mechanism_tournament/`
  (comparison_summary.json, prediction.json, scoreboard.json),
  `blocks/tools/result_attribution_guard_common.py`.

---

## 2. 2026-05-18 — Goal 1: Single-Family Winner Discovery (vm-pulled)

- **Backend**: mixed — some rows correctly excluded for being mislabeled
  `azure_vm_docker` when actually run on a failed local Mac Docker socket
  (see authority audit below).
- **Families/tasks**: `tool_result_attribution`, `long_horizon_artifact_handoff`,
  `dependency_config_environment`, `filesystem_open_workflow`,
  `terminalbench_verifier_repair` (+ parked `bfcl_tool_call_sentinel`,
  `structured_retrieval_reduction`).
- **Results**:
  | family | result |
  |---|---|
  | tool_result_attribution | all 4 variants: 0/2 target, 0/1 sentinel |
  | long_horizon_artifact_handoff | `spb_01` & `bounded_episode_01`: pass target+TB, **fail BFCL** |
  | dependency_config_environment | target uplift present, didn't carry to sentinels/global board |
  | filesystem_open_workflow | both routes: fail target rows entirely |
  | terminalbench_verifier_repair | both routes pass all rows — **eval non-discriminating** |
- **Status**: `winner_found = 0` — explicit honest closeout, no promotions.
- **Authority audit finding**: rows labeled `admission_level=certified`,
  `backend_ref=azure_vm_docker` for `filesystem_open_workflow`,
  `bfcl_tool_call_sentinel`, `terminalbench_verifier_repair`,
  `structured_retrieval_reduction` had **actually run on a failed local Mac
  Docker socket** — excluded from promotion math.
- **What we learned**: This is the gold-standard bookkeeping example in the
  repo — explicit `debug != certified`, `equivalent != native`, `lane winner
  != promoted` distinctions. BFCL acts as an effective cross-family
  regression sentinel (caught `long_horizon_artifact_handoff`'s regression).
- **Evidence strength**: HIGH (rigorous), result = **no winner found**.
- **Paths**: `vm-pulled:tracking/collab/autonomous_loop/single_family_winner_discovery_gate/{closeout.md,claim_authority_audit.md,tool_result_attribution/fresh_certified_tournament_run_2026-05-18_vm/,long_horizon_artifact_handoff/bounded_tournament_2026_05_18_vm/,dependency_config_environment/rerun_2026-05-18_env_forwarded/,filesystem_open_workflow/rerun_2026-05-18_env_forwarded/}`,
  `tracking/collab/autonomous_loop/goal_1_recovery_and_next_unlocks/terminalbench_verifier_repair_gap_repair/certified_reruns/`.

---

## 3. 2026-05-30 — Family-Level Diagnostic Run (`eval_suite_v1_*`)

- **Backend**: appears Docker-valid (this is the run the project treats as
  its current best diagnostic baseline).
- **Families and scores**:
  | family | score | notes |
  |---|---|---|
  | filesystem/cwd | **0/6** | wrong cwd/root, wrong target-file pattern matching — every row failed |
  | service readiness | **0/3** | wrong process identity + missing readiness proof — every row failed |
  | context/reduction | 2/7 | evidence carry-forward, relevant retrieval, wrong field, stale state after mutation |
  | environment/toolchain | 4/7 | stale docs source, wrong canonical-runner discovery, wrong python invocation |
  | tooling baseline | 4/7 → **7/7 with combined tooling guard** | see caveat: combined guard = item 1 above, sentinel-regressed |
  | long-horizon artifact handoff | **6/6** | already solved |
- **Lean/zero-abstraction probe**: improved one path-state row but
  **regressed by hiding evidence and using brittle anchors** — net
  negative.
- **What we learned**: This is the clearest, most actionable scoreboard in
  the repo. Filesystem and service-readiness are the worst, most
  unambiguous gaps. Long-horizon and (cautiously, modulo sentinel) tooling
  are largely solved.
- **Evidence strength**: HIGH — this is the evidence base `winning_harness_v1`
  (item 4) was synthesized from.
- **Paths**: `tracking/collab/eval_suite_v1_baseline/certified_runs/.../result_rows.jsonl`
  (environment/filesystem/context families),
  `tracking/collab/eval_suite_v1_repair_runs/20260526T165436Z_service_process_readiness_rerun/result_rows.jsonl`,
  `tracking/collab/eval_suite_v1_baseline/certified_runs/20260523T145906Z_tooling_family_gpt54mini_vm_copy/result_rows.jsonl`,
  `tracking/collab/eval_suite_v1_tournament_runs/tooling_tool_contract_certified_tournament/variant_combined_guard/scoreboard.json`.

---

## 4. 2026-05-30 — `winning_harness_v1` Scoring Attempt (HOLD)

- **Backend**: local Mac — **Docker daemon unavailable**.
- **Run surfaces attempted**:
  | surface | rows | result |
  |---|---|---|
  | family-level | 35/35 | INVALID |
  | final-suite private | 13/13 | INVALID |
  | benchmark | 12/12 | INVALID |
  | TB challenge | 2/2 | INVALID |
- **Status**: `commit_message: "HOLD - rerun winning_harness_v1 eval surfaces
  on certified Docker backend before promotion"`.
- **What we learned**: 100% INVALID across 62 attempted rows — purely an
  environment/runtime issue, NOT a capability signal. The implementation
  itself (route manifest builds, targeted unit/adapter tests) was fine.
- **Evidence strength**: ZERO capability evidence; HIGH evidence that the
  local Mac environment cannot produce certified eval results.
- **Paths**: `tracking/collab/final_harness_eval_suite/runs/20260530T15280{7,23,41}Z/run_summary.json`,
  `tracking/collab/final_harness_eval_suite/reviews/winning_harness_v1_goal_closeout_2026-05-30.md`,
  `tracking/collab/eval_suite_v1_baseline/certified_runs/result_rows.jsonl` + `scoreboard.json`.

---

## 5. 2026-06-04 — Local Iteration Loop (evidence-stripped)

- **Backend**: local (likely Mac, same Docker problem suspected).
- **Tasks**: `final_harness_eval_suite` task packs —
  `fhard_01_toolchain_runner_repair`, `fhard_02_service_orchestration_flagship`,
  `fhard_03_filesystem_decoy_patch`, `fhard_04_hidden_verifier_repair`,
  `fhard_05_structured_retrieval_reduction`,
  `fhard_06_original_repo_recovery_flagship`,
  `fhard_07_original_tool_schema_workspace_mix`,
  `fhard_08_original_noisy_open_workflow`,
  `fsent_01_tool_call_bfcl_composite`, `fsent_03_filesystem_verifier_repair`,
  `fsent_05_long_handoff_composition_smoke` (and likely `fsent_02`/`fsent_04`,
  not directly observed).
- **Run dirs found**: `baseline_runs/20260604T111218Z/`,
  `baseline_runs/20260604T112901Z/`, `full_board_rerun/20260604T151902Z/`,
  `next_bounded_vm_slice/20260604T145313Z/`.
- **Status**: **Only `__pycache__/*.pyc` files survive** for
  `grading_pack/{grader/grade.py, reviewer_pack/hidden_verifier.py}` per
  row. No `result_rows.jsonl`, `scoreboard.json`, or `answer.json` present
  anywhere in this tree.
- **What we learned**: A real run happened (4 separate timestamped run
  dirs, full row structure for 11+ tasks) but **all scored output is
  missing from the repo** — either gitignored, deleted, or never committed.
  This is the single largest "evidence we know existed but cannot read"
  gap (see `gap_report.md`).
- **Evidence strength**: UNKNOWN — directory structure proves the run
  happened; no scores recoverable from this checkout.

---

## 6. 2026-06-05/06 — Model-Led Substrate v1 (no eval run)

- **Backend**: n/a — no eval run; pure code + unit tests + adversarial
  review.
- **Unit test results**: `tests/test_kernel_layer2_audit.py` 7/7 pass;
  `tests/test_model_led_substrates.py` — focused pytest passed after the
  06-06 recovery-path fix.
- **Adversarial review**: 4 findings, all 4 fixed same day
  (`tracking/collab/model_led_substrate_v1/reviews/adversarial_review_01.md`,
  `accepted_findings_resolution.md`).
- **What we learned**: Code-level correctness improved significantly, but
  **this is unit-test/code-review evidence only** — see `08` for why this
  cannot be marked "solved" at the live or certified level.
- **Evidence strength**: Code-correctness evidence only. Zero eval evidence.
- **Paths**: `tracking/collab/model_led_substrate_v1/workers/*.md`,
  `tracking/collab/model_led_substrate_v1/reviews/*.md`,
  `tests/test_kernel_layer2_audit.py`, `tests/test_model_led_substrates.py`.

---

## 7. BigAI Trace-Layer Corpus (external reference, not Aether's own run)

- **Source**: `research/analysis/bigai_trace_layer/` — 314 runs, 86 TB2.0
  tasks, planner/executor/verifier architecture, Gemini 3.1-pro-preview.
- **Result**: ~82% pass (256 pass / 53 fail / 5 unknown).
- **What we learned**: This is **not Aether's score** — it's a different
  team's harness on the same benchmark — but it is the highest pass-rate
  data point in the repo and the best calibration target. The
  planner/executor/verifier split and the failure modes in the 53 failing
  runs are directly relevant to `07`/`10`.
- **Evidence strength**: HIGH as external calibration; not directly
  comparable without normalizing for model/harness differences.

---

## 8. Test suite growth (194 → 220+)

- The repo's pytest suite has grown from roughly 194 to 220+ passing tests
  over the period covered by this packet (exact commit-by-commit counts not
  individually verified — see `gap_report.md`). Growth is attributable to:
  kernel module unit tests (Phase 1/6), benchmark-adapter contract tests,
  eval-substrate contract tests, and the Phase 6 model-led-substrate tests.
- **What this does and does NOT mean**: It means the codebase has more
  internally-consistent, type/contract-checked modules. It does **NOT**
  mean any of these modules have been exercised in a live agent run or a
  certified benchmark run — see `08` for the unit/smoke/live/certified
  distinction, which this packet treats as load-bearing.

---

## 9. 2026-06-11 — MLPCP v3 Official Run (Paused)

- **Backend**: Azure VM Docker (`harnesseng-dev`).
- **Variant/config**: `mlpcp_v3` with background tools and `receipt-memory-cockpit` patches.
- **Pulled Run Artifacts & Folders**:
  - `official_harbor_hard4_20260610T215341Z`: Scored run on 4 hard tasks (Mean: 1.000 for `qemu-startup` trial, 0.000 for `extract-moves-from-video`, `install-windows-3.11`, and `video-processing`).
  - `official_harbor_receipt_memory_qemu_20260611T105226Z` & `official_harbor_receipt_memory_hard3_20260611T110509Z`: Run records validating qemu and hard3 tasks under the cockpit memory layout.
  - `official_harbor_bgtools_hard2_20260611T112824Z` (plus audits `_audit` and `_audit_2`): Reruns of `extract-moves-from-video` and `install-windows-3.11` showing the model ignored background tools (`background_job`, `monitor_job`, `service_probe_loop`) and kept looping.
  - `official_harbor_live_app_qemu_20260611T013015Z` (plus audit): Evaluates the live app container integration.
  - `official_harbor_meta_patch_rerun3_20260611T011342Z` & `official_harbor_patch_rerun3_20260611T005731Z` (including deep audits, command audits, and trace summaries): Re-evaluation runs for patch applications.
  - `harbor_bridge_patch_targets_20260611T012730Z` & `harbor_memory_cockpit_patch_targets_20260611T013921Z`: Target files and directories used during local patching.
- **Results**:
  - `qemu-startup` / live app qemu: **PASS** (1.000 reward).
  - `hard2`/`hard3`/`hard4` tasks: **0.000** (due to background tools loop or VM disconnects).
- **Status/result**: Paused. Progress-escalation patch unapplied due to missing anchors.
- **What we learned**: Introduce explicit steering when deploying background service tools to prevent model looping.
- **Evidence strength**: HIGH (direct official run artifacts and audits on VM Docker).
- **Paths**: `tracking/variants/mlpcp_v3/MLPCP_V3_PAUSE_STATE_20260611.md`, `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/`.

---

## Summary table — all runs

| Date | Run | Backend | Result | Evidence type |
|---|---|---|---|---|
| 2026-05-17 | Combined Guard V1.5 tournament | Azure VM Docker (valid) | 6/12 overall; combined_guard 2/2 target but 0/1 sentinel regression | certified, mixed/negative |
| 2026-05-18 | Goal 1 winner discovery (7 families) | mixed, audited | `winner_found = 0`; 1 family non-discriminating; 1 BFCL regression | certified (audited), no winner |
| 2026-05-30 | Family-level diagnostic | Docker-valid | filesystem 0/6, service 0/3, context 2/7, env 4/7, tooling 4/7→7/7*, long-horizon 6/6 | certified, primary diagnostic |
| 2026-05-30 | `winning_harness_v1` (4 surfaces, 62 rows) | local Mac, no Docker | 100% INVALID | invalid, no capability signal |
| 2026-06-04 | Local iteration loop (11+ fhard/fsent tasks) | local, unknown | scores not recoverable (only .pyc remain) | unknown/missing |
| 2026-06-05/06 | Model-led substrate v1 | n/a | unit tests pass, adversarial review clean | code-correctness only |
| 2026-06-11 | MLPCP v3 official run | Azure VM Docker | `qemu-startup` passed, `hard2` tasks stayed 0.0 (session paused) | certified (partial), paused |
| (external) | BigAI trace-layer corpus | other team's harness | ~82% (256/314) | external calibration |

\* with sentinel-regressed combined guard — treat as unresolved, not 7/7.

**Bottom line for Fable**: The only number close to a "current capability score" is the 2026-05-30 family-level diagnostic (strong on long-horizon handoff/tooling, weak-to-zero on filesystem/service readiness/context). While the newly pulled 2026-06-11 MLPCP v3 run shows a pass on `qemu-startup` after a receipt patch, its `hard2` tasks failed (staying at 0.0) and the session was paused during progress-escalation patch design. No architecture built since May 30 (winning_harness_v1, model-led substrate v1, MLPCP v3) has been fully scored against the baseline.
