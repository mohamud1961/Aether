# Research

Distilled research output for agentic harness design: deep synthesis, planning,
reviews, analyses, mechanism maps, failure taxonomies, and run-level evidence
interpretation.

The substantive research lives in four public subdirectories:

---

## `synthesis/`

Canonical promoted synthesis outputs:

- **`failure-taxonomy.md`** — Cumulative 4-wave failure taxonomy with 12+ identified failure families, wave-by-wave saturation status, and contradiction register.
- **`mechanism-map.md`** — Principal mechanism family map with 6 accepted families and their interaction structure.
- **`mechanism_map_accepted_claims.md`** — Accepted MECHANISM_CARDs from Wave 01 anchor, with evidence-backed structure.
- **`mechanism_map_contradiction_register.md`** — Open contradictions in the mechanism evidence base.
- **`bigai_harness_answered_questions.md`** — 18 question families answered
  over 312 parsed runs, with confidence labels.
- **`bigai_harness_reconstruction.md`** — Stable doctrine vs. variable
  behavior vs. boundary analysis.
- **`source_system_dossiers/`** — source-system dossiers with 9+ wave updates
  each.
- **`informal_cluster_dossiers/`** — Cross-corpus informal evidence synthesis by cluster.
- **`eval_dossiers/`** — Eval surface design evidence for the
  verification/completion family.

---

## `case_studies/`

Trajectory case studies and harness run analyses:

**Trajectory case studies** (10 task families, cross-system comparison):

| File | Task Family | Key Theme |
|---|---|---|
| `cancel_async_tasks.md` | Async cancellation | Loop engineering: cleanup-confirmed completion |
| `db_wal_recovery.md` | WAL recovery | Artifact-backed proof vs. verifier-mediated closure |
| `headless_terminal.md` | Interactive terminal | Teardown + completion protocol |
| `break_filter_js_from_html.md` | JS filter extraction | Artifact discipline + verifier hygiene |
| `git_multibranch.md` | Multi-branch git | Workspace/branch drift |
| `openssl_selfsigned_cert.md` | TLS cert generation | Wave 06 planning orchestration anchor |
| `cobol_modernization.md` | COBOL modernization | Long-horizon coordination |
| `custom_memory_heap_crash.md` | Memory allocator debugging | Runtime-memory boundary case |
| `retrieval_extraction_hard_row.md` | Retrieval extraction | Multimodal completion failure |
| `prove_plus_comm.md` | Formal proof | Formal verification family |

**Harness run analyses** (detecting unsupported task completion / false progress):

| File | Run | Key Finding |
|---|---|---|
| `aether2_g5_run_failure_taxonomy.md` | G5 2026-06-13 | F1 import-path collapse (94.8%), F2 false-positive task_done, F4 advisory verifier over-optimism |
| `aether2_g5_outcome_scoreboard.md` | G5 2026-06-13 | Forensic 4-way validity classification |
| `aether2_g5_task_findings.md` | G5 2026-06-13 | Per-task capability diagnosis |
| `aether2_g5_lane_recommendation.md` | G5 2026-06-13 | Import-path repair recommendation |
| `aether2_g5_prediction_audit.md` | G5 2026-06-13 | Pre/post prediction comparison |
| `aether2_run_analysis_20260614.md` | Full board 2026-06-14 | 22-task analysis; verifier/grader disagreement taxonomy |
| `aether2_run_analysis_20260615_l1_targeted.md` | L1 targeted 2026-06-15 | 3 structural harness defects: pseudo-requirement pollution, tool-contract schema drift, read-only verifier rejection |
| `aether2_fake_progress_analysis_20260614.md` | Fake progress 2026-06-14 | Loop incentive error: self-authored artifacts competing with real evidence |
| `aether2_fake_progress_fix_plan.md` | Fix plan | Engineering response to detected fake-progress |

---

## `phases/`

Research phase artifacts and build orchestration:

- **Synthesis phases**: `deep-synthesis-plan.md`, `deep-synthesis-wave-plan.md`, `evidence-inventory.md`, `coverage-access.md`, `deep-synthesis-setup.md`
- **Build orchestration**: `build_orchestration_decision_log.md`, `build_orchestration_handoffs/` (hour0 contracts, G1 checkpoint, pre-G3 handoff, orchestration ledger)
- **Build spec**: `aether2_build_spec.md`, `aether2_build_spec_predictions.md`
- **Variant cards**: `variant_cards_packet04.md` (4 real variant cards with
  deep-synthesis traceability), `variant_family_seeds/`
- **Phase 6.5 follow-up**: `phase65_environment_runtime_followup_handoff.md`, `phase65_environment_runtime_deep_trace_analysis.md`

---

## `methodology/`

Research methodology and tooling:

- **Source intake**: `source_intake_checklist.md`, `corpus_capture_audit.md`
- **Prompting**: `prompt_designer_meta_prompt.md`
- **Adversarial review**: `red_team_handoff.md`
- **References**: `references.md`
- **BigAI trace layer**: `bigai_trace_layer/` — `build.py`, `answer_questions.py`, `question_catalog.py` (engineering the 312-run trace analysis layer)
- **Deep Synthesis protocols**: `deep_synthesis_protocols/` — execution protocol, handoff schema, lane closure criteria, multi-agent workflow guide, phase/wave operating plan
- **Adjudication**: `adjudication/` — V1 audit checklist, wave audit checklist, failure taxonomy checklist, mechanism map checklist

---

## What is NOT here

- `sources/` — Private source captures, raw run archives, papers, and issues
- `intake/` — Intake records, normalization artifacts (private)
- `external/` — External repo mirrors (private)

Only distilled synthesis is public. All evidence citations in the public files
use `[private-source: <label>]` format to preserve traceability without
exposing private paths.
