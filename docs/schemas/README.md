# Schemas

Public schema references for the harness and eval suite artifact contracts.

## Key Schemas

- **Task result schema** — `eval_suite/schemas/` contains the canonical schemas for task result rows, scoreboard entries, and eval artifact contracts.
- **Variant card schema** — Variant cards follow the structure defined in `research/phases/variant_cards_packet04.md`: mechanism anchor, required atomic evals, anticipated transfer evals, promotion thresholds, retirement conditions, telemetry.
- **Harness artifact schema** — The `aether2_result.json` shape captures verifier evidence, task_done call, step count, model exchange metadata, and completion reason. See `eval_suite/schemas/` for the formal definition.
- **MECHANISM_CARD schema** — Defined in the Deep Synthesis protocol (`research/methodology/deep_synthesis_protocols/DEEP_SYNTHESIS_HANDOFF_SCHEMA.md`): mechanism_id, name, short_definition, mechanism_family, harness_area, operational_shape, evidence_paths, confidence, failure_role, interaction_notes.
- **TRAJECTORY_CASE_STUDY schema** — Defined by the case study format in `research/case_studies/`: case_id, wave, task_family, systems_compared, run_paths, outcome_profile, per_run_notes, cross_run_comparison, failure_point_comparison, mechanism_implications.

## Source Schemas

The source intake and normalization schemas are documented in `research/methodology/source_intake_checklist.md`. The intake record format uses the `src_<type>_<hash>` identifier convention throughout the corpus.
