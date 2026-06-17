# Research & Docs Move Map

Date: 2026-06-16
Author: discovery agent (read-only pass)
Status: DRAFT — human-gate required before any files move

---

## 1. Executive Summary

### Where the real research and synthesis actually lives

The substantive research and deep-synthesis output is concentrated in:

- **`research/synthesis/`** — the only subdirectory of `research/` with real content. Contains the canonical cumulative-synthesis carry-forward files (`failure-taxonomy.md`, `mechanism-map.md`), a full suite of source-system dossiers (BigAI_behavioral, KIRA, deepagents, a-evolve, claw-code), 10 trajectory case studies with multi-wave evidence updates, and 5 phases/planning documents.
- **`research/analysis/bigai_trace_layer/`** — real engineered analysis: Python builder (`build.py`, `answer_questions.py`, `question_catalog.py`) plus a complete output layer (`answered_questions.md`, `final_harness_reconstruction.md`, `motif_index.json`, `corpus_summary.json`, `exemplar_runs.json`, `coverage_report.json`, `question_answers.json`, individual run trace JSONs). This is the most quantitatively rich artifact in the repo: 312 parsed runs, 18+ question families, full confidence-labeled answers.
- **`tracking/collab/stage_02_synthesis/`** — the working execution records of the multi-wave Deep Synthesis: 6+ mechanism_map waves, 4+ failure_taxonomy waves, adjudication checklists, dossiers that mirror `research/synthesis/` (these are the working copies; `research/synthesis/` appears to hold promoted canonical copies), informal cluster dossiers, eval/eval dossiers, literature dossiers, and operating-protocol documents.
- **`tracking/collab/aether2_run_analysis_20260614/`**, **`aether2_run_analysis_20260615/`**, **`aether2_g5_run_analysis_20260613/`** — real harness run analyses with per-task root-cause tables, failure taxonomy, scoreboard reconstructions, and disagreement analysis.
- **`tracking/collab/aether2_build_orchestration/`** and **`aether2_build_spec/`** — real planning + decision artifacts (decision_log, hour0 contracts, orchestration ledger, g1/g3 handoffs, build spec with predictions).
- **`tracking/collab/stage_03_execution_planning/`** — variant cards (`packet_04`, `packet_06`) with deep-synthesis-to-variant traceability and phase 6.5 environment-runtime follow-up trace analyses.

### What is REAL vs PLACEHOLDER

**Real (substantive, non-stub):**
- `research/synthesis/failure-taxonomy.md` — 128-line cumulative synthesis with wave-by-wave saturation status, contradiction register, coverage frontier (4 waves accepted)
- `research/synthesis/mechanism-map.md` — wave anchor synthesis with accepted mechanism families and interaction map
- `research/synthesis/source_system_dossiers/BigAI_behavioral.md` — 256-line dossier with 9 wave update passes
- `research/synthesis/source_system_dossiers/KIRA.md` — 254-line dossier with source-backed architecture and 9 wave updates
- `research/synthesis/source_system_dossiers/deepagents.md` — full source-backed dossier
- `research/synthesis/trajectory_case_studies/*.md` — 10 real case studies (db_wal_recovery, cancel_async_tasks, headless_terminal, break_filter_js_from_html, cobol_modernization, custom_memory_heap_crash, retrieval_extraction_hard_row, git_multibranch, openssl_selfsigned_cert, prove_plus_comm), each multi-wave updated
- `research/analysis/bigai_trace_layer/output/answered_questions.md` — 352 lines, 16 question families fully answered with confidence labels and evidence citations
- `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md` — stable doctrine vs. variable behavior vs. boundary analysis
- `tracking/collab/aether2_g5_run_analysis_20260613/failure_taxonomy.md` — 7-family taxonomy with evidence-chained causal analysis
- `tracking/collab/aether2_g5_run_analysis_20260613/outcome_scoreboard.md` — forensic 4-way validity classification, reproducible from artifacts
- `tracking/collab/aether2_run_analysis_20260614/full_run_analysis_20260614T213000Z.md` — 22-row GPT-5.4-mini run analysis with per-task root causes and verifier/grader disagreement table
- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z_full_analysis.md` — 14-row targeted board analysis identifying 3 harness defect classes (verifier prompt pollution, tool-contract schema drift, read-only constraint violation)
- `docs/case-studies/aether-migration-direct-port.md` — real case study with validation summary table
- `docs/case-studies/public-manifest-repair-smoke.md` — real case study for eval-pack creation shape
- `docs/architecture/public-architecture.md` — real architecture map with mermaid diagram

**STUBS (thin placeholders, 1-5 lines):**
- `research/README.md` — 5-line placeholder workflow description
- `research/analysis/failure_modes.md` — 2-line TODO stub
- `research/analysis/lego_dimensions.md` — placeholder table with "TBD from research" in every cell
- `research/analysis/patterns.md` — not verified to exist; likely stub
- `docs/research/README.md` — placeholder (not yet read)
- `docs/schemas/README.md` — placeholder (not yet read)

### What must stay PRIVATE

The following families are confirmed private and must not be published:
- `research/sources/` — raw trajectories, codebases, papers text, informal sources, issues, postmortems, evals, docs, postmortems
- `research/intake/` — inbox, normalized records, rejected exclusions, corpus manifests
- `research/external/` — repo mirrors
- `research/sources/codebases/quarantine/` — quarantined codebases (explicitly listed in `.gitignore` via `research/sources/codebases/quarantine/`)
- `tracking/collab/aether2_g2_homologs/runs/` — raw run workspaces with full `.aether2/raw_logs/` trees
- `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/` — result_rows.jsonl files contain hardcoded `/home/azureuser/` VM paths and container IDs

---

## 2. Move Map Table

| Artifact | Current Path | Proposed Destination | Public/Private | Needs Sanitization | Replaces Placeholder | Notes |
|---|---|---|---|---|---|---|
| BigAI trace layer builder scripts | `research/analysis/bigai_trace_layer/{build.py,answer_questions.py,question_catalog.py}` | `research/methodology/bigai_trace_layer/` | PUBLIC | No | No | Real tooling; no private paths in scripts themselves |
| BigAI answered questions synthesis | `research/analysis/bigai_trace_layer/output/answered_questions.md` | `research/synthesis/bigai_harness_answered_questions.md` | PUBLIC | YES — check for `research/sources/trajectories/` citation paths; these are private source refs that should be converted to general citation format | No | 352-line deep synthesis output; citations reference private trajectory paths — rephrase citations generically |
| BigAI harness reconstruction | `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md` | `research/synthesis/bigai_harness_reconstruction.md` | PUBLIC | No | No | Clean — no private paths |
| BigAI trace layer output (JSON artifacts) | `research/analysis/bigai_trace_layer/output/{corpus_summary.json,motif_index.json,exemplar_runs.json,coverage_report.json,question_answers.json,question_coverage.json,run_index.jsonl,task_index.json,events.jsonl}` | `research/synthesis/bigai_trace_layer_outputs/` | PUBLIC | YES — run-level JSONs cite private trajectory tar.gz paths in source_file fields | No | Bulk derived artifacts; the JSON outputs cite raw source bundle paths; must strip or anonymize source_file references to private trajectory archives |
| Individual BigAI per-run trace JSONs | `research/analysis/bigai_trace_layer/output/runs/*/` | `research/synthesis/bigai_trace_layer_outputs/runs/` | PUBLIC | YES — same citation concern as above | No | ~312 run JSONs; same source_file sanitization needed |
| Failure taxonomy cumulative synthesis | `research/synthesis/failure-taxonomy.md` | `research/synthesis/failure-taxonomy.md` (already correct) | PUBLIC | No | No | Already in research/synthesis; no move needed, just confirm destination |
| Mechanism map principal synthesis | `research/synthesis/mechanism-map.md` | `research/synthesis/mechanism-map.md` (already correct) | PUBLIC | No | No | Already correct |
| Synthesis phases: deep-synthesis-plan | `research/synthesis/phases/deep-synthesis-plan.md` | `research/phases/deep-synthesis-plan.md` | PUBLIC | No | No | Real planning document; corpus scope policy and operating model |
| Synthesis phases: evidence-inventory | `research/synthesis/phases/evidence-inventory.md` | `research/phases/evidence-inventory.md` | PUBLIC | No | No | Stage 2A closeout and opening rationale |
| Synthesis phases: deep-synthesis-wave-plan | `research/synthesis/phases/deep-synthesis-wave-plan.md` | `research/phases/deep-synthesis-wave-plan.md` | PUBLIC | No | No | Compressed 14-wave model rationale |
| Synthesis phases: coverage-access | `research/synthesis/phases/coverage-access.md` | `research/phases/coverage-access.md` | PUBLIC | No | No | Real coverage access brief |
| Synthesis phases: deep-synthesis-setup | `research/synthesis/phases/deep-synthesis-setup.md` | `research/phases/deep-synthesis-setup.md` | PUBLIC | No | No | Setup brief |
| Source system dossier: BigAI_behavioral | `research/synthesis/source_system_dossiers/BigAI_behavioral.md` | `research/synthesis/source_system_dossiers/BigAI_behavioral.md` (already correct) | PUBLIC | YES — contains citation paths under `research/sources/trajectories/` which are private | No | 256 lines, 9 wave updates; trajectory paths must be anonymized or described generically |
| Source system dossier: KIRA | `research/synthesis/source_system_dossiers/KIRA.md` | `research/synthesis/source_system_dossiers/KIRA.md` (already correct) | PUBLIC | YES — private codebase paths and trajectory paths | No | 254 lines, 9 wave updates; `research/sources/codebases/KIRA/` and trajectory paths must be anonymized |
| Source system dossier: deepagents | `research/synthesis/source_system_dossiers/deepagents.md` | `research/synthesis/source_system_dossiers/deepagents.md` | PUBLIC | YES — private codebase/trajectory paths | No | Same as KIRA |
| Source system dossier: a-evolve | `research/synthesis/source_system_dossiers/a-evolve.md` | `research/synthesis/source_system_dossiers/a-evolve.md` | PUBLIC | YES — likely same private path pattern | No | Not fully read; assume same citation pattern |
| Source system dossier: claw-code | `research/synthesis/source_system_dossiers/claw-code.md` | `research/synthesis/source_system_dossiers/claw-code.md` | PUBLIC | YES — likely same private path pattern | No | Not fully read |
| Trajectory case study: db_wal_recovery | `research/synthesis/trajectory_case_studies/db_wal_recovery.md` | `research/case_studies/db_wal_recovery.md` | PUBLIC | YES — private trajectory paths in run_paths and evidence_paths | No | Strong 3-system comparison; trajectory citation paths must be anonymized |
| Trajectory case study: cancel_async_tasks | `research/synthesis/trajectory_case_studies/cancel_async_tasks.md` | `research/case_studies/cancel_async_tasks.md` | PUBLIC | YES — same trajectory path issue | No | Strongest cross-family cleanup-completion evidence |
| Trajectory case study: headless_terminal | `research/synthesis/trajectory_case_studies/headless_terminal.md` | `research/case_studies/headless_terminal.md` | PUBLIC | YES | No | Real execution-control case; teardown + completion protocol |
| Trajectory case study: break_filter_js_from_html | `research/synthesis/trajectory_case_studies/break_filter_js_from_html.md` | `research/case_studies/break_filter_js_from_html.md` | PUBLIC | YES | No | Artifact-discipline + verifier hygiene |
| Trajectory case study: cobol_modernization | `research/synthesis/trajectory_case_studies/cobol_modernization.md` | `research/case_studies/cobol_modernization.md` | PUBLIC | YES | No | Not fully read; assume same pattern |
| Trajectory case study: custom_memory_heap_crash | `research/synthesis/trajectory_case_studies/custom_memory_heap_crash.md` | `research/case_studies/custom_memory_heap_crash.md` | PUBLIC | YES | No | Not fully read; runtime-memory boundary case |
| Trajectory case study: retrieval_extraction_hard_row | `research/synthesis/trajectory_case_studies/retrieval_extraction_hard_row.md` | `research/case_studies/retrieval_extraction_hard_row.md` | PUBLIC | YES | No | Multimodal completion failure family |
| Trajectory case study: git_multibranch | `research/synthesis/trajectory_case_studies/git_multibranch.md` | `research/case_studies/git_multibranch.md` | PUBLIC | YES | No | Workspace/branch drift |
| Trajectory case study: openssl_selfsigned_cert | `research/synthesis/trajectory_case_studies/openssl_selfsigned_cert.md` | `research/case_studies/openssl_selfsigned_cert.md` | PUBLIC | YES | No | Wave 06 planning orchestration anchor |
| Trajectory case study: prove_plus_comm | `research/synthesis/trajectory_case_studies/prove_plus_comm.md` | `research/case_studies/prove_plus_comm.md` | PUBLIC | YES | No | Formal proof/verification family |
| G5 run analysis: failure taxonomy | `tracking/collab/aether2_g5_run_analysis_20260613/failure_taxonomy.md` | `research/case_studies/aether2_g5_run_failure_taxonomy.md` | PUBLIC | No | No | Clean analysis; no private local paths in content |
| G5 run analysis: outcome scoreboard | `tracking/collab/aether2_g5_run_analysis_20260613/outcome_scoreboard.md` | `research/case_studies/aether2_g5_outcome_scoreboard.md` | PUBLIC | No | No | Forensic validity classification |
| G5 run analysis: task findings | `tracking/collab/aether2_g5_run_analysis_20260613/task_findings.md` | `research/case_studies/aether2_g5_task_findings.md` | PUBLIC | No | No | Per-task capability diagnosis |
| G5 run analysis: g5 lane recommendation | `tracking/collab/aether2_g5_run_analysis_20260613/g5_lane_recommendation.md` | `research/case_studies/aether2_g5_lane_recommendation.md` | PUBLIC | No | No | Import-path repair recommendation |
| G5 run analysis: prediction audit | `tracking/collab/aether2_g5_run_analysis_20260613/prediction_audit.md` | `research/case_studies/aether2_g5_prediction_audit.md` | PUBLIC | No | No | Pre/post prediction comparison |
| Aether2 full run analysis 20260614 | `tracking/collab/aether2_run_analysis_20260614/full_run_analysis_20260614T213000Z.md` | `research/case_studies/aether2_run_analysis_20260614.md` | PUBLIC | No | No | 22-task analysis; no private paths in the md content itself |
| Aether2 L1 targeted board analysis 20260615 | `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z_full_analysis.md` | `research/case_studies/aether2_run_analysis_20260615_l1_targeted.md` | PUBLIC | YES — line 3 contains `/Users/mohamud/...` local path; line 5 contains `/home/azureuser/` VM path | No | Strip lines 3-5 metadata header or replace with generic run identifier |
| Stage 02 synthesis: deep synthesis protocol docs | `tracking/collab/stage_02_synthesis/{DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md, DEEP_SYNTHESIS_HANDOFF_SCHEMA.md, DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md, DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md, DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md}` | `research/methodology/deep_synthesis_protocols/` | PUBLIC | No | No | Real methodology; no private paths in these protocol docs |
| Stage 02 adjudication checklists | `tracking/collab/stage_02_synthesis/adjudication/{DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md, DEEP_SYNTHESIS_WAVE_AUDIT_CHECKLIST.md, FAILURE_TAXONOMY_AUDIT_CHECKLIST.md, MECHANISM_MAP_AUDIT_CHECKLIST.md}` | `research/methodology/adjudication/` | PUBLIC | No | No | Real governance criteria |
| Stage 02 mechanism map accepted claims | `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/accepted_claims.md` | `research/synthesis/mechanism_map_accepted_claims.md` | PUBLIC | YES — evidence_paths use absolute `/Users/mohamud/...` paths | No | 274 lines; all MECHANISM_CARDs have absolute private evidence_paths that must be converted to repo-relative |
| Stage 02 mechanism map contradiction register | `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/contradiction_register.md` | `research/synthesis/mechanism_map_contradiction_register.md` | PUBLIC | No (likely) | No | 52 lines; spot-check needed |
| Stage 02 variant family seeds | `tracking/collab/stage_02_synthesis/variant_family_seeds/` | `research/phases/variant_family_seeds/` | PUBLIC | No (likely) | No | Stage planning artifact for variant design |
| Stage 03 packet 04 variant cards | `tracking/collab/stage_03_execution_planning/packets/packet_04_first_atomic_variants/outputs/variant_cards.md` | `research/phases/variant_cards_packet04.md` | PUBLIC | No | No | Real execution-planning output with deep-synthesis traceability |
| Stage 03 phase 6.5 handoff | `tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/runs/2026-05-07_successor_phase65_environment_runtime_followup/phase65_environment_runtime_followup_handoff.md` | `research/phases/phase65_environment_runtime_followup_handoff.md` | PUBLIC | YES — line 4 contains absolute output_root `/Users/mohamud/...` | No | Replace output_root value with repo-relative equivalent |
| Stage 03 phase 6.5 deep trace analysis | `tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/runs/2026-05-07_successor_phase65_environment_runtime_followup/phase65_environment_runtime_followup_deep_trace_analysis.md` | `research/phases/phase65_environment_runtime_deep_trace_analysis.md` | PUBLIC | No (likely) | No | Not fully read; spot-check for private paths |
| Source intake checklist | `research/source_intake_checklist.md` | `research/methodology/source_intake_checklist.md` | PUBLIC | No | No | Methodology doc |
| Prompt designer meta-prompt | `research/prompt_designer_meta_prompt.md` | `research/methodology/prompt_designer_meta_prompt.md` | PUBLIC | No | No | Source-finder methodology |
| Red team handoff | `research/red_team_handoff.md` | `research/methodology/red_team_handoff.md` | PUBLIC | No | No | Adversarial review methodology |
| References | `research/references.md` | `research/methodology/references.md` | PUBLIC | No | No | Literature references |
| Corpus local capture audit | `research/analysis/2026-03-31__accepted_corpus_local_capture_audit.md` | `research/methodology/corpus_capture_audit.md` | PUBLIC | YES — may reference local paths; spot-check needed | No | |
| Source system dossiers README | `research/synthesis/source_system_dossiers/README.md` | `research/synthesis/source_system_dossiers/README.md` | PUBLIC | No | No | Already in place |
| Trajectory case studies README | `research/synthesis/trajectory_case_studies/README.md` | `research/case_studies/README.md` | PUBLIC | No | No | |
| Synthesis README | `research/synthesis/README.md` | `research/synthesis/README.md` | PUBLIC | No | No | |
| Aether2 fake progress analysis | `tracking/collab/aether2_fake_progress_analysis_20260614/older_vm_and_trace_rerun_fake_progress_analysis_20260614.md` | `research/case_studies/aether2_fake_progress_analysis_20260614.md` | PUBLIC | YES — title says "older VM" suggesting VM-path references | No | Detect and document fake-progress pattern; spot-check |
| Aether2 fake progress implementation plan | `tracking/collab/aether2_fake_progress_implementation_plan_20260614/{IMPLEMENTATION_FIX_PLAN.md,TARGETED_BOARD.md}` | `research/case_studies/aether2_fake_progress_fix_plan.md` | PUBLIC | No (likely) | No | Engineering response to detected fake-progress |
| Build orchestration decision log | `tracking/collab/aether2_build_orchestration/decision_log.md` | `research/phases/build_orchestration_decision_log.md` | PUBLIC | No (likely) | No | Real planning evidence; decision log |
| Build orchestration handoffs | `tracking/collab/aether2_build_orchestration/{g1_checkpoint_handoff.md,pre_g1_completion_handoff.md,pre_g3_readiness_handoff.md,hour0_contracts.md,orchestration_ledger.md}` | `research/phases/build_orchestration_handoffs/` | PUBLIC | No (likely) | No | Stage-gated engineering evidence |
| Aether2 build spec | `tracking/collab/aether2_build_spec/AETHER2_BUILD_SPEC.md` | `research/phases/aether2_build_spec.md` | PUBLIC | No | No | Original harness design contract |
| Aether2 build spec predictions | `tracking/collab/aether2_build_spec/predictions.md` | `research/phases/aether2_build_spec_predictions.md` | PUBLIC | No | No | Pre-build predictions for post-audit |
| Docs: public architecture | `docs/architecture/public-architecture.md` | `docs/architecture/public-architecture.md` | PUBLIC | No | No | Already in place, real |
| Docs: case study aether migration | `docs/case-studies/aether-migration-direct-port.md` | `docs/case-studies/aether-migration-direct-port.md` | PUBLIC | No | No | Already in place, real |
| Docs: case study manifest repair smoke | `docs/case-studies/public-manifest-repair-smoke.md` | `docs/case-studies/public-manifest-repair-smoke.md` | PUBLIC | No | No | Already in place, real |
| Docs: attribution guard tournament | `docs/case-studies/attribution-guard-tournament.md` | `docs/case-studies/attribution-guard-tournament.md` | PUBLIC | No (spot-check) | No | In place |
| Docs: provenance policy | `docs/provenance/{agent_runtime_adaptation_policy.md,third_party_notices.md}` | `docs/provenance/` (already correct) | PUBLIC | No | No | In place, real |
| Docs: publication gap list | `docs/publication/publication_gap_list.md` | `docs/publication/publication_gap_list.md` | PUBLIC | No | No | In place, real |
| Docs: public evidence index | `docs/publication/public_evidence_index.md` | `docs/publication/public_evidence_index.md` | PUBLIC | No | No | In place, real |
| Informal cluster dossiers | `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/*.md` | `research/synthesis/informal_cluster_dossiers/` | PUBLIC | YES — spot-check for private source paths | No | 7 dossiers covering execution/terminal, verification/completion, context/state/memory, planning/orchestration, tools/environment; real synthesis |
| Eval/eval dossiers | `tracking/collab/stage_02_synthesis/eval_dossiers/*.md` | `research/synthesis/eval_dossiers/` | PUBLIC | YES — spot-check | No | 2 dossiers on verification/completion/recovery eval surfaces |

---

## 3. Stages and Phases Narrative

The research progressed through four identifiable phases, reconstructed from artifacts:

### Phase 0 — Source Intake and Corpus Assembly
*Artifacts:* `research/source_intake_checklist.md`, `research/analysis/2026-03-31__accepted_corpus_local_capture_audit.md`, `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json` (PRIVATE), `research/tools/capture_backfill.py`, `harvest_user_sources.py`, `extract_papers_text.py`

The intake phase built a structured corpus from multiple source classes: BigAI trajectory bundles, KIRA trajectory bundles, terminus-kira trajectory bundles, deepagents trajectory bundles, vix trajectories, mirrored codebases (KIRA, deepagents, a-evolve, claw-code), papers with extracted text, docs captures, informal sources (issues, postmortems). A dedicated `source_finder_prompt_pack/` provided structured prompting for source discovery. The corpus manifest is the integrity anchor for all later synthesis.

### Phase 1 — BigAI Post-Hoc Trace Layer and Exploratory Analysis
*Artifacts:* `research/analysis/bigai_trace_layer/` (full directory), `research/analysis/bigai_trace_layer/README.md`, `research/synthesis/mechanism-map.md` Wave 01 exploratory anchor, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_01_*/`

The BigAI trace layer was engineered to normalize 312+ raw trajectory bundles into a queryable, confidence-labeled event layer. Key outputs: `events.jsonl` (flattened event rows), `motif_index.json`, `corpus_summary.json`, `answered_questions.md` (18 question families answered with evidence), `final_harness_reconstruction.md` (stable vs. variable doctrine). This layer surfaced the planner-executor-verifier observable contract, 0.908 verifier-present success rate, recovery loop prevalence, and the boundary between observable doctrine and hidden mechanism. The mechanism_map Wave 01 exploratory anchor extracted the first mechanism families from this evidence.

### Phase 2 — Deep Synthesis (Mechanism Map + Failure Taxonomy Waves)
*Artifacts:* `tracking/collab/stage_02_synthesis/` (entire directory), `research/synthesis/failure-taxonomy.md`, `research/synthesis/mechanism-map.md`, `research/synthesis/source_system_dossiers/*.md`, `research/synthesis/trajectory_case_studies/*.md`, `research/synthesis/phases/*.md`

A 14-wave multi-agent Deep Synthesis under a formal protocol:

- **mechanism_map Wave 01** (exploratory anchor): surfaced 6 mechanism families — tool_gateway, execution_control, verification_or_completion, state_and_recovery, workspace_or_artifact_hygiene, workflow_role_separation. Accepted with carry-forward warnings.
- **mechanism_map Wave 02** (execution_control_and_terminal_grounding): vertical domain wave, accepted.
- **mechanism_map Wave 03** (verification_completion_and_recovery): verifier-mediated closure vs. inline postcondition proof vs. grader mismatch. Key interaction: execution control × verification × state recovery.
- **mechanism_map Waves 04-06** (context_state_memory_workspace; tools_environment_coordination; planning_orchestration_and_interactions): progressive deepening.
- **failure_taxonomy Waves 01-04**: four failure domain waves, each with multi-lane analysis (trajectory/failure analyst, codebase/source-reconstruction analyst, literature analyst, informal/issues/postmortems analyst). Accepted with carry-forward warnings. Key families identified: terminal-grounding/repo-state drift, cancellation/process-lifecycle breakdown, false success from weak acceptance, verifier completion vs. final acceptance divergence, recovery/resume state fragility, context compaction/state-operator failure, workspace/branch/path drift, session persistence failure, tool gateway mismatch, cwd/workdir contract failure, permission-policy/runtime mismatch, timeout-heavy long-horizon coordination degradation.

Parallel support tracks ran continuously: coverage_access, source_system_dossiers, trajectory_case_studies, literature_dossiers, informal_cluster_dossiers, eval_dossiers, coverage_register.

Operating protocol documents (`DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`, `DEEP_SYNTHESIS_HANDOFF_SCHEMA.md`, `DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`, etc.) governed the multi-agent execution discipline throughout.

### Phase 3 — Execution Planning and Harness Build
*Artifacts:* `tracking/collab/stage_03_execution_planning/`, `tracking/collab/aether2_build_orchestration/`, `tracking/collab/aether2_build_spec/`, `tracking/collab/aether2_g2_homologs/`, `tracking/collab/aether2_g5_implementation_orchestration_20260613/`

Synthesis findings were converted into variant cards (packet 04 atomic variants, packet 06 paired combo variants), then into a real harness build (`harness.aether2`). The build was orchestrated with explicit gates: hour0 contracts, G1 checkpoint, pre-G3 readiness handoff. The G2 homolog suite validated 5 concrete task contracts (file artifact, service_survives_exit, interactive_session, package_install, long_running_job) with real run evidence. The G5 implementation orchestration closed the main capability lanes.

### Phase 4 — Eval and Run Analysis
*Artifacts:* `tracking/collab/aether2_g5_run_analysis_20260613/`, `tracking/collab/aether2_run_analysis_20260614/`, `tracking/collab/aether2_run_analysis_20260615/`, `tracking/collab/aether2_fake_progress_analysis_20260614/`, `tracking/collab/aether2_fake_progress_implementation_plan_20260614/`

Three major run analyses closed the feedback loop from harness build back to failure taxonomy:
- **G5 run analysis (2026-06-13)**: identified the F1 import-path collapse catastrophic environment failure (94.8% of attempts), F2 false-positive task_done, F4 advisory verifier over-optimism (14/21 false-clean), establishing the harness-vs-capability attribution discipline.
- **Full run analysis (2026-06-14)**: 22-task GPT-5.4-mini analysis, identified verifier/grader disagreement taxonomy (8 verifier-false-positive rows), root-cause table per task, harness false-positive completion gate as dominant failure class.
- **L1 targeted board analysis (2026-06-15)**: 14-task analysis identified 3 structural harness defects — verifier prompt pseudo-requirement pollution, tool-contract schema drift (12 task_done schema mismatches), read-only verifier inspection incorrectly rejecting harmless read commands. 6/6 grader passes were false-blocked. This analysis also contains the private `/Users/mohamud/` and `/home/azureuser/` paths needing sanitization.

---

## 4. Case Study Candidates

The following are the strongest materials for distilling into public case studies, tuned to the four target topics:

### A. Loop Engineering
**Primary:** `research/synthesis/trajectory_case_studies/cancel_async_tasks.md`
Evidence: 3-system comparison showing how the agent repair-and-retest loop (KIRA's iterative redesign, BigAI's verifier-gated loop, DeepAgents' compact inline proof) maps to cleanup-confirmed completion as a required loop contract. Multi-wave updated.

**Secondary:** `research/synthesis/trajectory_case_studies/headless_terminal.md`
Evidence: All 3 families converge on same failure shape — apparent completion before robust interactive verification is unstable. Shows how loop depth and loop-exit criteria determine whether teardown failures surface.

**Supporting:** `research/analysis/bigai_trace_layer/output/answered_questions.md` sections on Recovery and Adaptation (REC-01 through REC-06), Planning Dynamics (PLAN-03 through PLAN-07), Stopping and Termination (STOP-01 through STOP-06).

### B. Building an Agent Harness by Orchestration
**Primary:** `tracking/collab/aether2_build_orchestration/{decision_log.md,hour0_contracts.md,orchestration_ledger.md,g1_checkpoint_handoff.md,pre_g3_readiness_handoff.md}`
Evidence: Real orchestration records showing the stage-gate build pattern, explicit decision log, hour-zero contract setup, and the G1-to-G3 handoff. This is the most direct evidence of building a harness by multi-agent orchestration.

**Secondary:** `tracking/collab/aether2_build_spec/AETHER2_BUILD_SPEC.md` + `predictions.md`
Evidence: Upfront spec and predictions against which actual build outcomes can be compared.

**Supporting:** `tracking/collab/stage_02_synthesis/variant_family_seeds/`, `tracking/collab/stage_03_execution_planning/packets/packet_04_first_atomic_variants/outputs/variant_cards.md`
Evidence: Synthesis-to-variant traceability chain, showing how mechanism_map and failure_taxonomy claims translate to concrete harness variant design.

**Also:** `docs/case-studies/aether-migration-direct-port.md` — already a real public case study for the namespace migration and direct-port loop.

### C. Detecting Unsupported Task Completion (False Positive / Fake Progress)
**Primary:** `tracking/collab/aether2_run_analysis_20260614/full_run_analysis_20260614T213000Z.md`
Evidence: 22-row analysis with explicit verifier/grader disagreement taxonomy — 8 rows where verifier_clean=True but grader failed. Per-task root causes identify the false-positive completion gate as the dominant harness failure class. Strongest concrete evidence for unsupported task completion detection.

**Secondary:** `tracking/collab/aether2_g5_run_analysis_20260613/failure_taxonomy.md` (F2 and F4 families) + `outcome_scoreboard.md`
Evidence: F4 advisory verifier over-optimism (26% precision, very low recall), F2 false-positive task_done taxonomy. Rigorous 4-way validity classification.

**Secondary:** `tracking/collab/aether2_fake_progress_analysis_20260614/older_vm_and_trace_rerun_fake_progress_analysis_20260614.md`
Evidence: Specific analysis of the fake-progress detection problem.

**Secondary:** `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z_full_analysis.md` (after sanitization)
Evidence: Three structural harness defects including pseudo-requirement pollution causing false-blocked outcomes; verifier_clean=false on all 6 grader passes; this is the flip side — detecting false negatives / false blocking.

**Supporting:** `research/synthesis/failure-taxonomy.md` Wave 02 (verifier or completion success signal diverges from final acceptance), `research/synthesis/trajectory_case_studies/cancel_async_tasks.md` Wave 02 update (self-check pass / external verifier fail as first-class pattern).

### D. Variant Iteration
**Primary:** `tracking/collab/stage_03_execution_planning/packets/packet_04_first_atomic_variants/outputs/variant_cards.md`
Evidence: 4 real variant cards (v04_vc_01 through v04_vc_04) with deep-synthesis claim anchors, required atomic evals, anticipated interaction evals, promotion thresholds, retirement conditions, and telemetry requirements.

**Secondary:** `tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/runs/2026-05-07_successor_phase65_environment_runtime_followup/phase65_environment_runtime_followup_handoff.md` + `deep_trace_analysis.md`
Evidence: Phase 6.5 20-run environment/runtime follow-up with 4 local probe passes, selected recommendation, and doctrine/route/preflight status.

**Supporting:** `research/synthesis/mechanism-map.md` (mechanism families → variant design rationale), `research/synthesis/failure-taxonomy.md` (failure saturation levels → which variants are promotion-ready), `variants/families/attribution_guard_tournament/decision_table.json`, `variants/scoreboards/attribution_guard_tournament_v1.json` (actual variant scoreboard evidence).

---

## 5. Private Inventory (Must Stay Out)

| Path | Why Private | Notes |
|---|---|---|
| `research/sources/trajectories/` | Raw captured trajectory bundles (.tar.gz, -traj.txt) from BigAI, terminus-kira, deepagents, vix corpora | Private source material — only distilled synthesis is public |
| `research/sources/codebases/` | Mirrored source repos (KIRA, deepagents, a-evolve, claw-code, quarantine) | Private mirrors; quarantine explicitly in .gitignore |
| `research/sources/papers/` | Captured paper text and metadata | Private intake material |
| `research/sources/docs/` | Captured docs artifacts | Private |
| `research/sources/informal/` | Captured informal sources | Private |
| `research/sources/issues/` | Captured GitHub issues | Private |
| `research/sources/postmortems/` | Captured postmortems | Private |
| `research/sources/evals/` | Eval captures | Private |
| `research/intake/` | inbox, normalized records, rejected exclusions, manifests | Private intake pipeline artifacts |
| `research/external/` | External repo mirrors | Private |
| `tracking/collab/aether2_g2_homologs/runs/` | Raw run workspaces with `.aether2/raw_logs/` trees | Raw run artifacts; private |
| `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/` (subdirectories) | result_rows.jsonl files contain `/home/azureuser/` VM paths, container IDs, full artifact trees | Sanitize the full_analysis.md but keep subdirs private |
| `tracking/collab/aether2_g2_homologs/g2_01_file_artifact/` etc. (homolog raw receipts) | Raw model exchange JSON, raw receipt content files | Private run-level artifacts |
| `research/sources/trajectories/vix/` | VIX trajectory analysis results and manifests | Private source; analysis_results.md may contain synthesis but provenance unclear |
| Raw ledger updates (`RAW_LEDGER_UPDATE` files) | Internal tracking ledger records | Private state |

---

## 6. Open Questions

1. **Sanitization scope of dossiers:** The source_system_dossiers in `research/synthesis/` contain many `evidence_paths:` sections listing `research/sources/trajectories/` and `research/sources/codebases/` private paths. The question is whether to (a) strip these evidence_paths entirely, (b) replace them with placeholder labels like `[private-trajectory: BigAI/db-wal-recovery]`, or (c) convert them to generic citation prose. Option (b) preserves traceability without exposing private paths.

2. **Mechanism map accepted_claims.md absolute paths:** `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/accepted_claims.md` contains `evidence_paths:` entries with absolute `/Users/mohamud/Downloads/harnesseng/...` paths. This file needs systematic path-stripping or conversion to repo-relative format before any public copy.

3. **Stage 02 dossier duplication:** The `tracking/collab/stage_02_synthesis/source_system_dossiers/` tree appears to mirror `research/synthesis/source_system_dossiers/` — both contain BigAI_behavioral.md, KIRA.md, etc. It is unclear whether these are identical copies or have diverged. The canonical location should be confirmed before the move (the `research/synthesis/` copies were read and appear to be the canonical promoted versions).

4. **VIX trajectory analysis:** `research/sources/trajectories/vix/analysis_results.md` and `INDEX.md` may contain synthesis-level findings that could be distilled publicly, but the entire `vix/` subtree is under `sources/` which is private by policy. Confirm whether the analysis outputs have been promoted to `research/synthesis/` or remain private only.

5. **`tracking/collab/stage_02_synthesis/mechanism_map/waves/*/` full wave output files:** These contain multi-lane analyst outputs, contradiction reviews, and principal synthesis per wave. They were not fully read in this discovery pass. They likely contain private path references in evidence sections. A systematic grep for `/Users/mohamud/` and `/home/azureuser/` across the full stage_02_synthesis/mechanism_map/waves/ tree is needed before any public promotion.

6. **aether2_g5_implementation_orchestration_20260613:** Not explored in this pass. Likely contains implementation decisions and run evidence for the G5 capability lanes. Needs a discovery read.

7. **stage_03_execution_planning packet 05 and others:** Only packet_04 and packet_06 were inspected. Other packets in stage_03 may contain additional variant iteration and eval evidence.

8. **`tracking/collab/aether2_fake_progress_analysis_20260614/older_vm_and_trace_rerun_fake_progress_analysis_20260614.md`:** The word "older VM" in the filename suggests VM-path references. Spot-check needed before public promotion.

9. **`docs/research/README.md` and `docs/schemas/README.md`:** Not read in this pass. Confirm whether these are real or stub.

10. **Publication master plan alignment:** `tracking/collab/public_repo_readiness/publication_master_plan.md` was not read. It may contain a pre-existing promotion policy that should govern or constrain this move map.

---

## 10-Line Summary

1. The substantive research lives in three places: `research/synthesis/` (canonical promoted synthesis), `research/analysis/bigai_trace_layer/` (engineered trace layer over 312 BigAI runs), and `tracking/collab/stage_02_synthesis/` (working multi-wave Deep Synthesis execution records).
2. `research/analysis/failure_modes.md` and `research/analysis/lego_dimensions.md` are stubs with TODO placeholders — the real equivalents are `research/synthesis/failure-taxonomy.md` and the mechanism map.
3. The BigAI trace layer is the most quantitatively dense artifact: 18 question families answered with confidence labels, 312 parsed runs, motif index, corpus summary, and exemplar runs — all distilled from private trajectory bundles.
4. The source_system_dossiers (BigAI_behavioral, KIRA, deepagents, a-evolve, claw-code) are real, multi-wave updated, but every one contains private evidence_path citations that must be sanitized before public promotion.
5. The 10 trajectory case studies are real and strong, but all contain `run_paths:` and `evidence_paths:` fields with private trajectory archive paths that need sanitization.
6. Three run analyses (G5/2026-06-13, full/2026-06-14, L1-targeted/2026-06-15) form a concrete case-study chain for unsupported-completion detection; the 2026-06-15 analysis has hardcoded `/Users/mohamud/` and `/home/azureuser/` paths requiring sanitization.
7. The stages narrative is fully reconstructible from artifacts: Phase 0 (intake), Phase 1 (BigAI trace layer), Phase 2 (Deep Synthesis waves 01-06+ across mechanism_map and failure_taxonomy), Phase 3 (execution planning + harness build), Phase 4 (run analysis + feedback).
8. All of `research/sources/`, `research/intake/`, and `research/external/` are confirmed private; raw run workspaces and result_rows.jsonl files with VM paths are also private.
9. The mechanism map accepted_claims.md in stage_02_synthesis/mechanism_map/synthesis/ has absolute `/Users/mohamud/Downloads/harnesseng/` paths in every evidence_paths field — this is the most systematic sanitization job in the proposed move set.
10. No files were created or modified during this discovery pass except this deliverable; all findings above are read-only observations requiring human gate approval before any moves proceed.
