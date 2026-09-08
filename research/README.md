# Historical Aether research archive

This directory preserves **distilled research from the earlier nine-month development path**. It is not the current production architecture.

The current system is documented in [`../docs/`](../docs/), implemented in [`../aether/`](../aether/), and evidenced in [`../evidence/`](../evidence/).

Why keep this archive visible? Because Aether did not appear as a finished thesis. The current model-led runtime emerged from repeated investigation of planning, execution, context, tooling, verification, recovery and failure attribution.

## High-signal historical material

### `synthesis/`

Deep synthesis that helped shape the project:

- `mechanism_map_accepted_claims.md` — accepted mechanism claims from the research corpus;
- `failure-taxonomy.md` — accumulated failure families;
- `bigai_harness_reconstruction.md` — reconstruction of harness behaviour and boundaries;
- `bigai_harness_answered_questions.md` — research questions answered against the analysed corpus;
- `informal_cluster_dossiers/` — synthesis across planning, execution, tools, context, verification and recovery;
- `eval_dossiers/` — evidence used to reason about evaluation and completion mechanisms.

### `case_studies/`

Historical task and run analyses. Several are especially useful for understanding why the architecture changed:

- `aether2_fake_progress_analysis_20260614.md` — how activity-shaped progress could be mistaken for task progress;
- `aether2_run_analysis_20260615_l1_targeted.md` — targeted diagnosis of structural harness defects;
- `break_filter_js_from_html.md` — an older task-level analysis in the family later used for a held-out boundary case;
- `cancel_async_tasks.md`, `db_wal_recovery.md`, `headless_terminal.md` — examples of completion and execution failure analysis.

### `methodology/`

Historical research protocols, source intake, red-team checklists and adjudication machinery used during the exploration phase.

### `phases/`

Planning and build artifacts from earlier Aether-2 and synthesis phases. These are retained as development history, not as instructions for the current runtime.

## Important interpretation rule

A file in this directory may discuss architectures, mechanisms or terminology that Aether later removed.

Do **not** infer current production behaviour from this archive.

For current claims, use this authority order:

1. `aether/` — current implementation;
2. `tests/` + `tools/check_production_surface.py` — current deterministic checks;
3. `evidence/` — promoted public evidence;
4. `docs/` — current architecture and research programme;
5. `research/` — historical research context only.

That distinction is part of the project's story: mechanisms were researched, tested, revised and often removed rather than accumulated indefinitely.
