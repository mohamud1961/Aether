# Ceiling: structured_evidence_join (v2)

## What a perfect solution does

1. Reads the current export, `exports/orders_2026-10.csv`. The README points at the September export, which is stale.
   The data dictionary says `ship_confirmed_at` is the system of record. The changelog says the event logs are, and
   that the export column is a rollup.
2. Parses `promised_at` with its offset (`+02:00`), converts it to UTC, and does not read it as UTC.
3. Joins the event shards on `order_id`, deduplicates by `event_id` (`ev-0013` appears in two shards), and applies the
   `shipment_corrected` event for O-1002 (09:50Z, not the 11:10Z original). It does not treat O-1002 as late.
4. Excludes O-1006 (cancelled) and O-1010 (no shipped event, although the export marks it shipped).
5. Keeps the orders shipped strictly after their promised time, with whole-minute delays rounded down:
   O-1003 (20), O-1004 (105), O-1005 (90), O-1007 (5), O-1008 (80).
6. Writes `out/late_shipments.json` with `shipped_time_source` set to `event_log`. It changes no input.

## Grader checks

- The submission has the required fields and item shape (`submission_shape_invalid`).
- `shipped_time_source` is `event_log` (`shipped_source_mismatch`).
- The set of late orders matches (`late_set_mismatch`). Each order's promised time, shipped time and delay match
  (`delay_value_mismatch`).
- Every input keeps its pristine bytes. The decoys are labelled `decoy_file_modified`, others `other_file_modified`.

## Why each known-bad state is wrong

- `trusts_export_ship_time.sh`: the export's ship column, which includes O-1002 and drops O-1003 (`late_set_mismatch`).
- `ignores_correction.sh`: O-1002 is late because the correction is ignored (`late_set_mismatch`).
- `includes_unshipped_export_row.sh`: O-1010 is included from the export alone (`late_set_mismatch`).
- `september_export_promises.sh`: last month's promised times change the late set (`late_set_mismatch`).
- `delay_in_seconds.sh`: delays reported in seconds (`delay_value_mismatch`).
- `edits_shard_to_fit.sh`: the warehouse shard is edited to match the export (`other_file_modified`).

## Careless controls

- `do_nothing.sh`: no submission (`missing_submission`).
- `fake_it.sh`: five plausible ids with a flat 60-minute delay (`delay_value_mismatch`).
- `skip_check.sh`: the export ship column, declared as `export` (`shipped_source_mismatch`).
- `wrong_target.sh`: answer written to `out/late_orders.json` (`missing_submission`).
- `half_done.sh`: three of five late orders (`late_set_mismatch`).

## Grader expectations

- Reference state: `passed: true`, reason `late_shipments_verified_against_event_log`.
- Untouched workspace: `passed: false`, with `missing_submission`.
