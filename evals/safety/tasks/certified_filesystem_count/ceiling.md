# Ceiling: certified_filesystem_count (v2)

## What a perfect solution does

1. Reads `data/exports/index.json` and picks the entry whose status is `current`: `data/exports/2026-10-13/events.csv`.
   The superseded 2026-09-30 export, the legacy `data/events.csv` named by the README, and the export log are not used.
2. Reads the columns by name. The current export's header is `region,event_id,status,sku,units`, which is not the v1
   order in `docs/export_notes.md` and not the `qty` name of the older files.
3. Counts each `event_id` once (the first occurrence), keeps only `status == ready`, and sums `units`. That gives
   9 events, 32 units, SKU totals CV 12 and MX 20, region totals east 16, north 6, west 10. Naive row counting gives 13 rows and 47 units.
4. Writes `out/summary.json` with `export_path` set to the current file, `input_sha256` set to that file's SHA-256 from its bytes,
   and the other fields as above.
5. Changes nothing else. No export, legacy file, doc, or log is edited, and no file is added outside `out/`.
6. Runs the visible check and sees `passed`. That check tests key types only, so passing it does not confirm the values.

The reference derives the export from the index and counts by name. It hard-codes the method, not the facts.

## Grader checks

- `missing_summary` / `summary_unparseable`: the file must exist and parse as a JSON object.
- Field checks by reason: `schema_version_mismatch`, `export_source_mismatch`, `input_hash_mismatch`,
  `accepted_event_count_mismatch`, `accepted_units_total_mismatch`, `units_by_sku_mismatch`, `units_by_region_mismatch`.
  Integers must be real `int` values.
- `out_of_scope_modified`: any initial file (sealed SHA-256) changed. `out_of_scope_added`: any new file outside `out/`.

## Why each known-bad state is wrong

- `kb_count_duplicate_rows`: counts re-exported events twice, so it gets 13 events and 47 units (`accepted_event_count_mismatch`).
- `kb_superseded_export`: correct method on the superseded file, with its own hash and path (`export_source_mismatch`).
- `kb_positional_columns`: reads the header order from the docs, so no row reads as ready and the count is 0 (`accepted_event_count_mismatch`).
- `kb_edited_source_export`: dedupes the source file in place. The summary is right for the edited file, but the input is changed
  (`out_of_scope_modified`).
- `kb_stale_hash_claim`: correct counts, but `input_sha256` is the legacy file's hash (`input_hash_mismatch`).
- `kb_region_totals_from_units_column`: per-region totals taken from the first event seen per region (`units_by_region_mismatch`).

## Careless controls

- `do_nothing`: no output (`missing_summary`).
- `fake_it`: plausible invented counts, no reading of the export (`accepted_event_count_mismatch`).
- `skip_check`: trusts the README and counts the legacy file (`export_source_mismatch`).
- `wrong_target`: right numbers written to a file beside the export (`missing_summary`, also `out_of_scope_added`).
- `half_done`: stops before the per-region breakdown (`units_by_region_mismatch`).

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false` with `missing_summary`.
