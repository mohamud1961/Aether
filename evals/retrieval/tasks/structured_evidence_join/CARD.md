# Task card: structured_evidence_join (v2, new)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with the original trace contract.

## Design (v2)

- Two sources of truth that disagree: a CSV export with a `ship_confirmed_at` column, and JSONL event shards that the
  changelog names as the system of record.
- Conflicting timestamps: promised times carry `+02:00` offsets, and a `shipment_corrected` event overrides O-1002's shipped time.
- Duplicate events across shards (`ev-0013`), a cancelled order, an order with no shipped event, and inventory noise.
- Out-of-date data dictionary (says the export is the system of record and promised times are UTC).
- Stale README pointing at last month's export, plus that export with different promised times.
- Original content. Nothing is taken from Terminal-Bench.

## Controls

- Known-bad: 6 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| late_set_mismatch | known_bad trusts_export_ship_time, ignores_correction, includes_unshipped_export_row, september_export_promises; careless half_done |
| delay_value_mismatch | known_bad delay_in_seconds; careless fake_it |
| other_file_modified | known_bad edits_shard_to_fit |
| shipped_source_mismatch | careless skip_check |
| missing_submission | careless do_nothing, wrong_target |

Trace-dependent process checks are not established by this final-state grader.
