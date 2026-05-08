# Research Documentation

Public research artifacts promoted from the multi-wave Deep Synthesis and run-analysis phases.

## Synthesis

Core multi-wave synthesis outputs in `research/synthesis/`:

- **`failure-taxonomy.md`** — Cumulative 4-wave failure taxonomy: 12+ identified failure families with saturation status, contradiction register, and coverage frontier. Families include terminal-grounding drift, false completion signals, verifier/grader mismatch, recovery-state fragility, context compaction failures, workspace drift, and tool-contract mismatch.
- **`mechanism-map.md`** — Wave-anchor synthesis of 6 mechanism families (tool_gateway, execution_control, verification_or_completion, state_and_recovery, workspace_or_artifact_hygiene, workflow_role_separation) with interaction map.
- **`mechanism_map_accepted_claims.md`** — Accepted MECHANISM_CARDs from Wave 01 exploratory anchor: PTY terminal control, layered completion gating, cleanup-restore hygiene, planner/executor/verifier role split, backend policy mismatch risk. Evidence-backed with private-source citations.
- **`mechanism_map_contradiction_register.md`** — Open contradictions and tension points across the mechanism map evidence base.
- **`bigai_harness_answered_questions.md`** — 352-line synthesis answering 18 question families over 312 parsed BigAI runs: recovery loops, stopping criteria, planning dynamics, role separation, verifier behavior, workspace hygiene.
- **`bigai_harness_reconstruction.md`** — Stable doctrine vs. variable behavior vs. boundary analysis for the BigAI behavioral corpus.
- **`source_system_dossiers/`** — Per-system behavioral dossiers for BigAI, KIRA, deepagents, a-evolve, and claw-code. Each dossier covers architecture, execution, workflow doctrine, context model, verification, recovery, and wave-by-wave updates.
- **`informal_cluster_dossiers/`** — Cross-corpus informal evidence synthesis grouped by failure cluster: execution control, verification/completion/recovery, context/state/memory, planning/orchestration, tools/environment.
- **`eval_benchmark_dossiers/`** — Evidence dossiers on eval surface design for verification, completion, and recovery families.

## Case Studies

Trajectory case studies and harness run analyses in `research/case_studies/`:

- **10 trajectory case studies** — Multi-wave cross-system analyses of concrete task families (db_wal_recovery, cancel_async_tasks, headless_terminal, break_filter_js_from_html, cobol_modernization, custom_memory_heap_crash, extract_moves_from_video, git_multibranch, openssl_selfsigned_cert, prove_plus_comm). Each compares BigAI, KIRA, and deepagents behavior with failure-mode implications.
- **Harness run analyses** — Three concrete run analysis case studies closing the feedback loop from harness build back to failure taxonomy (G5/2026-06-13, full-board/2026-06-14, L1-targeted/2026-06-15).

## Phases and Methodology

Research phases narrative in `research/phases/`. Methodology documentation in `research/methodology/`.

See [synthesis README](../../research/synthesis/README.md) for the full synthesis index.
