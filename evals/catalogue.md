# Eval catalogue

Every evaluation built in the programme, November 2025 to October 2026, one line each. Detail lives on the
target pages and [method pages](methods/). Grades: **A** kept as a validated instrument; **B** design kept and
improved into the current tasks; **C** historical record (its lesson is on a target or method page); **D** retired
(duplicate, broken or lineage hold). Terminal-Bench runs are summarised without task names; held-out evaluations appear
as aggregates only.
151 evaluations: 1 A, 56 B, 82 C, 12 D.


| ID | Evaluation | When | Grade | Result |
|---|---|---|---|---|
| PG-01 | Middleware OSS bug-fix task set (21 IDs: fastapi F1-F3, poetry P1-P5, django D1–D5, sqlalchemy S1–S5, celery C1-C3) | Nov 2025–Feb 2026 | C | No scores recorded. Ends Jan 13 with the line's stop. |
| PG-02 | compliance validator and synthetic thin-slice report (Eval Index v0.1) | Nov 2025–Feb 2026 | B | Validator built; report is synthetic. No model. |
| PG-03 | TerminalBench harness experiments and determinism audit | Nov 2025–Feb 2026 | C | Not aggregated. find returned 571 summary.json; M06 says 508 (recount needed). |
| PG-04 | Eval-layer property checks (Feb 20 sessions) | Nov 2025–Feb 2026 | C | Defects logged, no score. |
| A00 | Phase 0-1 packet lineage | Mar–Jul 2026 | C | Long-horizon artifact handoff 6/6 [C]. |
| A01 | Result-attribution guard tournament (Gen 2 harness, Phase 3; GLOSS: not listed) | Mar–Jul 2026 | B | control 0/2 target, 1/1 sentinel; ignored-IDs 0/2, KILL; no-call 1/2, keep; combined 2/2 target but 0/1 sentinel, keep for follow-up, not pr |
| A02 | Tooling tool-contract tournament | Mar–Jul 2026 | D | 6/12 pass; all fails tool_contract. Not decided. |
| A03 | Phase 4 single-family winner discovery | Mar–Jul 2026 | C | winner_found = 0. |
| A04 | Phase 5 family-level diagnostic | Mar–Jul 2026 | C | filesystem/cwd 0/6; service 0/3; context 2/7; environment 4/7; tooling 4/7 (7/7 with guard, sentinel regressed); long-horizon 6/6. |
| A05 | winning_harness_v1 and final-harness board (whole-harness) | Mar–Jul 2026 | D | HOLD; never rescored. |
| A06 | Zero-abstraction lean run | Mar–Jul 2026 | C | REJECTED for evidence hiding. |
| A08 | receipt-memory cockpit receipt-memory cockpit | Mar–Jul 2026 | C | One pass after patch; both hard rows 0.0. |
| A09 | Gen 2 full tournament (Gen 2 board) | Mar–Jul 2026 | C | Valid-scored 5/19 (26.3%). Naive 5/241 (2.07%) misleading. Full-population INSUFFICIENT_EVIDENCE. |
| A10 | local homolog series (Gen 2 gate) | Mar–Jul 2026 | B | 5/5 once; 4 pass + 1 invalid on 06-17. |
| A11 | Fake-progress targeted board, - (Gen 2) | Mar–Jul 2026 | B | Not executed. |
| A12 | L1 targeted 14-row board (Gen 2) | Mar–Jul 2026 | C | 6 pass, 4 fail of 10 scoreable; 0 false cleans; verifier_clean False on all 6 passes. |
| A13 | Adaptive Harness Profiles (Adaptive Harness Profiles) A/B | Mar–Jul 2026 | C | Stage 2d 4/4 both arms. Reproducibility baseline 1/4 vs Adaptive Harness Profiles 3/4. Extension 0 wins, 0 regressions. |
| A14 | Gen 2 overnight board2 (Gen 2) | Mar–Jul 2026 | D | None. |
| A15 | Pro receipt board, GPT-5.3-codex toolshape rerun (Gen 3) | Mar–Jul 2026 | C | 0/5 valid; mean 0.0 on all five. |
| A16 | Gen 3 unattended GPT-5.4-Pro clean-room build (Gen 3) | Mar–Jul 2026 | D | Launched; result absent. |
| A17 | VM stage-1, py311 set (Gen 3) | Mar–Jul 2026 | C | 0/3 (one runner error, one incomplete, one completed at step 0). |
| A18 | Runtime enforcement stage-1 (Gen 3) | Mar–Jul 2026 | C | 0/1 (model_limit). |
| A19 | Canonical fresh stage-1 (Gen 3) | Mar–Jul 2026 | C | 1/3 (one completed at step 5). |
| A20 | Single-goal run (Gen 3) | Mar–Jul 2026 | D | None. |
| A21 | Verifier sentinel, 5 Terminal-Bench tasks, GPT-5.4-Pro (Gen 3) | Mar–Jul 2026 | C | 1/5. |
| A22 | Verifier sentinel, 200 steps, 2 Terminal-Bench tasks (Gen 3) | Mar–Jul 2026 | C | 1/2. |
| A23 | Known-bad verifier falsifier (Gen 3) | Mar–Jul 2026 | B | Run 1 3/5 hits; run 2 2/5 hits. |
| A24 | 15-task parallel batch "D16" (Gen 3) | Mar–Jul 2026 | D | Rerun incomplete (4/15 at snapshot, 9 running). |
| AE-01 | Verifier-only eval series (fake and model modes; 27 run folders) | Jun–Jul 2026 | B | gpt-5.4-mini 5/5 expected verdicts, PASS. gpt-5.3-codex 5/5, PASS. |
| AE-02 | Architect-only eval on official-task prompts (21 run folders) | Jun–Jul 2026 | B | Architect outputs scored 9-10/10 across rounds (see AE-04). |
| AE-03 | Architect isolated eval (5 Terminal-Bench tasks; primary gpt-5.4-mini, comparison gpt-5.3-codex) | Jun–Jul 2026 | B | gpt-5.4-mini 5/5 parseable, scores 9, 10, 9, 9, 9 (/10). gpt-5.3-codex 3/3 parseable. |
| AE-04 | Architect-as-skill 15-task audit | Jun–Jul 2026 | B | Final selected outputs 10/10 on verifier-prompt quality and config-contract quality. Remaining sub-10 solver scores. |
| AE-05 | Sentinel-regression gate | Jun–Jul 2026 | C | Software gate PASS; real run blocked. |
| AE-06 | Narrow real-task runs and one-real-run audit | Jun–Jul 2026 | C | 0/2 (harness_context_failure; grader_timeout_after_30s). Verifier-only rerun: 6/6 parse-ok. |
| AE-07 | Docker isolation smoke (3 cases, 3 stamps) | Jun–Jul 2026 | B | file golden 1.0; file known-bad 0.0; service golden 1.0. |
| AE-08 | Official task capability audit (classification, not a run) | Jun–Jul 2026 | C | Classification only. |
| AE-09 | Canonical alignment boards (3 pairs, 2026-07-03 and 07-04) | Jun–Jul 2026 | C | results not summarised |
| B01 | Architect v2 phase series, phases 9-29 | Aug–Sep 2026 | C | task_first_low 1/6; current_medium 3/6 (29,520 reasoning tokens); atomic_proof_low 3/6; 25B 9/18 strict. "No tested variant qualified both m |
| B02 | Architect mini board and runtime realization (held-out mini board, 36 rows) | Aug–Sep 2026 | B | 30 contract-valid rows; 4 full 10/10 passes; realization gate 1,354 tests passed. |
| B03 | Architect interface round 1 (A, C, E) and constraint boundary | Aug–Sep 2026 | B | A 12/12 and C 12/12 primary-semantic rows, zero critical. E: six false classifications. |
| B04 | Architect candidate, identity, downstream and context packages | Aug–Sep 2026 | C | None. |
| B05 | PTY substrate screen | Aug–Sep 2026 | C | No PTY default. |
| B06 | Solver efficiency objective audit and paired replication | Aug–Sep 2026 | B | Directional effect replicated; promotion gate missed. |
| B07 | Native function-call transport | Aug–Sep 2026 | C | Native transport qualifies for research. |
| B08 | Solver context replication | Aug–Sep 2026 | C | 0 transport events; 6 model_protocol_invalid. |
| B09 | Explicit Solver continuity ablation | Aug–Sep 2026 | C | Closed; no promotion authority. |
| B10 | Black-box semantic PTY screen | Aug–Sep 2026 | C | results not summarised |
| B11 | Gen 4 decision-contract A/B | Aug–Sep 2026 | C | Equal reward and official pass. |
| B12 | Gen 4 stable-context dedup live A/B | Aug–Sep 2026 | C | Both arms 3/3. Solver calls 16 to 25 (+56%); prefix bytes -29%; config bytes -74%. |
| B13 | Gen 4 architect causality, provider cardinality, Gen 4 crossover | Aug–Sep 2026 | C | B2 disposition recorded; other results results not summarised. |
| B14 | Gen 4 context-engineering variant board | Aug–Sep 2026 | C | Deleting dynamic context alone did not fix growth. |
| B15 | Gen 4 false-clean sentinel and completion-truth packs | Aug–Sep 2026 | B | Sentinel designed; other results results not summarised. |
| B16 | Lifecycle factuality board | Aug–Sep 2026 | A | 0 false cleans over 17 known-bad rows; all rows valid; passed: true. |
| B17 | frozen candidate board and forensics (Gen 4) | Aug–Sep 2026 | C | ~2.64M tokens, about 10x the clean baseline. Total reward results not summarised. |
| B18 | / causal self-verify (doctrine on vs off) | Aug–Sep 2026 | B | exact-contract 0/0; interaction-edge off 0 (provider failure) vs on 1.0; fresh-evidence 1.0 vs 1.0. |
| B19 | micro-A/B, Task-13 effort board, fresh 25-task board, Gate 1 Linux qualification | Aug–Sep 2026 | C | Gate 1 ACCEPTED with documented host-fixture normalization. Local suite 3,484 passed, 17 skipped. |
| B20 | S-series Gen 4 baselines | Aug–Sep 2026 | C | Mixed; per-arm numbers results not summarised. Selected treatments carried to S6.9. |
| B21 | verifier-effort replay | Aug–Sep 2026 | B | low 2 correct, 1 false-clean, 39,879 uncached input; high 2/1/40,588; medium 1 correct, 2 false-cleans, 40,570. |
| B22 | integrated candidate board | Aug–Sep 2026 | C | Candidate retained; no model-facing or runtime change. |
| B23 | canonical controller board | Aug–Sep 2026 | C | Full results results not summarised. |
| B24 | Phase C context-interface experiment and performance boards | Aug–Sep 2026 | C | INCONCLUSIVE_PROVIDER_FAILURE; SEALED_INCONCLUSIVE_KEEP_FULL. |
| B25 | execution board | Aug–Sep 2026 | C | 3 pass of 8 valid. Final readiness verdict. |
| B26 | terminal live board and compact-scoped successor | Aug–Sep 2026 | C | INCONCLUSIVE_HARNESS_FAILURE (V5); INCONCLUSIVE_MEASUREMENT_RUNTIME (V6). |
| B27 | pilot: mechanical vs semantic completion review | Aug–Sep 2026 | B | 4 ties; 1 mechanical-only win; 0 semantic wins. |
| B28 | walltime pilot (deadline cliff) | Aug–Sep 2026 | C | Visibility alone did not rescue the cliff task. |
| B29 | hypothesis-trap and model-namespace pilot | Aug–Sep 2026 | C | Closed; no promotion. · C |
| B30 | and boundary-verification pilots | Aug–Sep 2026 | B | Stage 2 admission not met. |
| B31 | Trio walltime and status calibration (non-causal) | Aug–Sep 2026 | C | 1 of 3 official (one timeout, one completed at 0, one pass). |
| B32 | Solver commitment hard-case ablation | Aug–Sep 2026 | B | Acceptable next actions control 2/9, treatment 3/9. Input tokens 22,551 vs 46,050. |
| B33 | Completion self-check causal ablation | Aug–Sep 2026 | C | DO_NOT_IMPLEMENT_SELF_CHECK_V1. · C |
| B34 | Held-out evaluation, September set | Aug–Sep 2026 | C | Official 0/3. Checks: 14 of 50; 1 of 2; 1 of 3. |
| B35 | Clean-rerun preregistration for one Terminal-Bench task | Aug–Sep 2026 | D | None. |
| B36 | claim-free review research programme: gates and frozen-head holdout (claim-free review) | Aug–Sep 2026 | B | Base 10/10; reversed 10/10; pooled 20/20 per INV. Several arms closed. No causal uplift claimed. |
| B37 | Completion-record ablation (v1 vs OFF) | Aug–Sep 2026 | C | KILL v1 as mandatory scaffold. OFF kept for pre-held-out candidate. |
| B38 | post-held-out Solver-quality pressure board | Aug–Sep 2026 | C | None. |
| C01 | Simplified-runtime screen, repair 09 (open-model programme) | Sep–Oct 2026 | B | 50 valid rows = 25 pairs: both pass 11, both fail 10, treatment-only 3, control-only 1. Wall time 72.5% throughput and pacer wait. |
| C02 | Preregistrations - and J-series (open-model programme) | Sep–Oct 2026 | C | M2 trace review: NO_PRESSURE. |
| C03 | frozen open-model baseline (custom F-series tasks, not Terminal-Bench) | Sep–Oct 2026 | B | 61 pass of 65 scored; 4 zeros; 7 infra-invalid. |
| C04 | Context-mode trace-first screens, (CF vs MC0 vs PT-NONE) | Sep–Oct 2026 | B | CF-F10 19 calls vs MC0-F10 45 (2.4x); CF-F05 13 vs MC0-F05 143 (about 11x). M10 says "2.4 to 13x"; unreconciled. |
| C05 | pre-held-out token and latency audit | Sep–Oct 2026 | C | By turn 16, 98.8% of the request is non-observed content. About 2.1 calls per minute. |
| C06 | Wave 0, Wave 1 and Wave 1b | Sep–Oct 2026 | C | A4 12.33/20; A5 11.00/19; A0 9.00/19; A1 10.00/20; A3 9.33/19. A4 and A5 3 wins each vs A0. |
| C07 | Wave 2 canonical dev board (H0, KH, MH; R0–R3 side arms) | Sep–Oct 2026 | C | H0 .83; KH .93; MH .90. R1 8/8 KILL; R3 4/8 KILL. Latest-exchange family cost 5-15x H0 calls. |
| C08 | a later revision PF lanes and hard rows | Sep–Oct 2026 | C | hard Terminal-Bench rows 0 (x2), session row 0, custom memory task 1.0 (23 calls); 1 valid solve of 3 hard valid attempts. |
| C09 | Gen 4 verifier and claim-free review matched boards (verifier and review arms) | Sep–Oct 2026 | C | 0 of 26 hard rows rewarded (memory). |
| C10 | M-TREE compactor full-coverage replay | Sep–Oct 2026 | B | Fidelity PASS on the replay. |
| C11 | Candidate screens - (claim ledger claim ledger, deadline visibility, lean packet, resilience; TB2.1 pool_v0, 13 tasks) | Sep–Oct 2026 | C | S1 claim ledger v1 12/13 vs control 10/13 . S2 23/26 vs 22/26. S3 claim ledger v4+deadline 25/26 vs control 21/26 |
| C12 | Candidate screens - (claim-ledger v5 vs v6; hold threshold; v7) | Sep–Oct 2026 | C | S5 v6 24/26 vs v5 23/26; S6 v6 25/29 vs v7 24/29. |
| C13 | Candidate screens - (sampling: temperature 0.0 vs 1.0) | Sep–Oct 2026 | C | v6a 13/14; v8 12/14 (2/2 on the hard rows); v9 11/14 (23.2M tokens); v10 11/14 (8.8M tokens). |
| C14 | Candidate screen (three variants) | Sep–Oct 2026 | C | A 10/14; B 12/14; C 13/14. |
| C15 | Verifier bench and checkpoint bench (five gates, two benches) | Sep–Oct 2026 | B | v1 at 0.7 caught 22/29, 6/348 false holds. v1 at 0.8 19/29, 2/348. v6 artifacts 25/28 with 68/208 false holds (33%). Blind verifier 19/29, 3 |
| C16 | Held-out evaluation, October set | Sep–Oct 2026 | C | Aether 5/9 (56%); stock 4/6 (67%). Held-out A 3/3 vs 2/2; B 2/3 vs 2/2; C 0/3 vs 0/2. |
| C17 | Plan sections 17-21 audits | Sep–Oct 2026 | C | Notes raise time awareness in reasoning (54% vs about 30%), but content not engaged. Debug phase needs 9-27 steps after a 20-25 step build. |
| C18 | Aether C1 (lean core loop baseline) | Sep–Oct 2026 | C | 0/2 on the interpreter task; one row 2/3 tests. |
| C19 | Aether C2 (pre-registered screen, predictions P1-P8) | Sep–Oct 2026 | C | P7: 0 of 3 interpreter rows solved across v2, v2.1, v2.2 (one reached 2/3 tests and timed out at 1,785 s). P8 (the further Terminal-Bench ro |
| C20 | Aether development sweep overnight development sweep | Sep–Oct 2026 | C | Best attempt 18/29; first valid attempt 17/29 (INV reads the line from the C2 document; M13 treats 18/29 as unverified in repo). |
| F01 | held-out evaluation successor private development board (held-out successor) | Sep–Oct 2026 | B | Base selection: incumbent 1.0 on V2 and S1-type rows; Thin 0.0 on V2; both 0.0 on R1 and V1 (6 matched pairs). |
| F02 | F10 successor pack v1 (fault-injected transport recovery) | Sep–Oct 2026 | B | None. |
| F03 | Private pack (verifier heads) | Sep–Oct 2026 | C | results not summarised |
| F04 | claim-free review C1 retrieval asset pack | Sep–Oct 2026 | C | Contract checks only. · C |
| F05 | claim-free review head contract and saved-state pack | Sep–Oct 2026 | C | Baseline, ceiling, known-bad JSON present. · C |
| F06 | claim-free review inspection contract | Sep–Oct 2026 | C | Approvals present. · C |
| F07 | claim-free review contract-fidelity development pack | Sep–Oct 2026 | C | None. · C |
| F08 | source-linked contract and evidence homolog | Sep–Oct 2026 | C | None. · C |
| F09 | claim-free review Verifier - scaffold and feedback contract | Sep–Oct 2026 | C | None. · C |
| F10 | and event-contract diagnostic | Sep–Oct 2026 | B | Seven fixture observations. · B |
| F11 | barrier lifecycle diagnostic and async mechanical | Sep–Oct 2026 | B | Known-bad result-swap JSON present. · B |
| F12 | R backend capability and restart diagnostic | Sep–Oct 2026 | C | Fixture diagnostic. · C |
| F13 | completion mechanics diagnostic | Sep–Oct 2026 | B | Diagnostic; no model. · B |
| F14 | strategy assets and productive-checks | Sep–Oct 2026 | C | None. · C |
| F15 | Aether trace v1 (dual-partition analysis) | Sep–Oct 2026 | C | None. · C |
| F16 | Same-model homolog battery v1 | Sep–Oct 2026 | B | None. · B |
| F17 | Pilot packs | Sep–Oct 2026 | C | See B27-B30. · C |
| F18 | P1 completion-disposition pack | Sep–Oct 2026 | D | Designed; not carried to a board. · D |
| F19 | Provider-free integration pack | Sep–Oct 2026 | C | None extracted. · C |
| F20 | Certified core filesystem slice | Sep–Oct 2026 | B | Executable controls; no model rows. · B |
| F21 | messy inventory recovery diagnostic | Sep–Oct 2026 | C | Smoke only. · C |
| F22 | pre-held-out pressure calibration, successor, long-task and capability packs | Sep–Oct 2026 | C | Calibration certified (LP5). · C |
| F23 | post-held-out Solver-quality pack | Sep–Oct 2026 | C | None. · C |
| F24 | Build milestone efficiency pack | Sep–Oct 2026 | B | None. · B |
| F25 | Performance boards: calibration and development sweep-D5 | Sep–Oct 2026 | C | Board definitions. · C |
| F26 | Architect, divergence, solver and verifier scaffolds | Sep–Oct 2026 | C | None. · C |
| G02 | runtime_policy_hook_smoke (environment and custom copies) | 2026 | B | None (smoke). · B |
| G03 | skill_loader_contract_smoke (tooling and custom copies) | 2026 | B | None (smoke). · B |
| G04 | subagent_handoff_contract_smoke (orchestration and custom copies) | 2026 | B | None (smoke). · B |
| G05 | environment_bootstrap_runner_repair | 2026 | B | None. · B |
| G06 | sentinel task 02: runtime_workspace_contract | 2026 | B | None with model. · B |
| G07 | filesystem_decoy_target_selection | 2026 | B | None in tree. · B |
| G08 | sentinel task 03: filesystem_verifier_repair | 2026 | B | None in tree. · B |
| G09 | original_repo_recovery_flagship | 2026 | B | None in tree. · B |
| G10 | public_manifest_repair_smoke | 2026 | B | None (smoke). · B |
| G11 | sentinel task 05: long_handoff_composition_smoke | 2026 | B | None. · B |
| G12 | noisy_open_workflow | 2026 | B | None in tree. · B |
| G13 | subagent_handoff_contract_smoke (families copy) | 2026 | D | — · D |
| G14 | sentinel task 08: process_build_survival_truth | 2026 | B | None in tree. · B |
| G15 | sentinel task 04: retrieval_reduction_closure | 2026 | B | None in tree. · B |
| G16 | structured_retrieval_reduction | 2026 | D | None. · D (as ported; re-author) |
| G17 | sentinel task 07: semantic_equivalence_contract | 2026 | B | None. · B (blocked) |
| G18 | sentinel task 06: exact_serialization_contract | 2026 | B | None in tree. · B |
| G19 | service_lifecycle_readiness_flagship | 2026 | B | None in tree. · B (blocked) |
| G20 | sentinel task 01: tool_call_composite | 2026 | B | None with model. · B |
| G21 | tool_schema_workspace_mix | 2026 | B | Pass not in tree. · B |
| G22 | hidden_verifier_repair | 2026 | D | None. · D (quarantine) |
| G23 | judge_correlated_checkers_v1 | 2026 | B | J0 gate in B36. · B |
| G24 | judge_method_result_proof_v1 | 2026 | B | J0 gate passed (B36). · B |
| G25 | mcp_registry_contract_smoke | 2026 | B | None. · B |
| G26 | runtime_policy_hook_smoke (environment copy) | 2026 | D | — · D |
| G27 | homolog_contract_smoke | 2026 | B | None. · B |
| G28 | harness_registry_smoke (whole-harness) | 2026 | C | None. · C |
| G29 | final_harness_v1 registry and boards | 2026 | B | promotion_decision: no_promotion_yet. · B |
| G30 | Public boards and example scoreboards | 2026 | C | None. · C |
| H01 | Calibration lanes: tool_call, filesystem, terminal (retrieval lane excluded as third-party) | 2026 | C | None. · C |
