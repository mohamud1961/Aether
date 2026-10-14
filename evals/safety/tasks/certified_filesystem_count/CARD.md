# Task card: certified filesystem count (v2)

Admission: **capability** (default). The grader is standalone stdlib code that reads files and runs no candidate code.  The reference, known-bad and careless controls test
this v2 design. They do not establish parity with the original certified-core contract. The original task was a
host-side grader run after a Docker capture. This v2 port keeps its counting rule and its scope rule, and adds the
traps below.

## Provenance

Ported from `evals/archive/evals/certified_core_v1/filesystem_open/` (events CSV count, dedupe by event_id, status
`ready`, sealed input hash). Port changes: a two-export index with a superseded export, a reordered header in the
current export, a legacy file named by a stale README, a stale format doc, and an out-of-scope rule over every initial file.

## Design (v2)

- Two-hop resolution: `data/exports/index.json` -> `status == current` -> `data/exports/2026-10-13/events.csv`.
- Decoys: the superseded 2026-09-30 export (with a `qty` header), the legacy `data/events.csv`, the stale README, and the stale
  v1 header in `docs/export_notes.md`.
- Duplicate re-exports: 3 repeated event lines. The naive count is 13 events and 47 units; the correct count is 9 and 32.
- The visible check tests key types only.

## Controls

- Known-bad: 6 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| accepted_event_count_mismatch | known_bad kb_count_duplicate_rows, kb_positional_columns; careless fake_it |
| export_source_mismatch | known_bad kb_superseded_export; careless skip_check |
| input_hash_mismatch | known_bad kb_stale_hash_claim |
| out_of_scope_modified | known_bad kb_edited_source_export |
| units_by_region_mismatch | known_bad kb_region_totals_from_units_column; careless half_done |
| missing_summary | careless do_nothing, wrong_target |
| out_of_scope_added | guard, also fired by careless wrong_target |
| schema_version_mismatch, accepted_units_total_mismatch, units_by_sku_mismatch, summary_unparseable | guards, no dedicated control |
