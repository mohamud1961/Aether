# Ceiling: exact_serialization_contract (v2)

## What a perfect solution does

1. Reads `data/EXPORTS.json`, which names `data/exports/2026-10-14.csv` as the current export. The `data/README.md`
   and `data/records.csv` point at the 2026-09 snapshot, and `spec/format_spec.v1.md` is superseded.
2. Follows `spec/format_spec.md` (v2): key order, integer ids, balances with two decimals, booleans, inline tag arrays,
   empty tags as `[]`, sorted by id, two-space indentation, trailing newline.
3. Handles the messy export: an unsorted row order, a quoted name with a comma and doubled quotes, balances written
   as `1234.5`, `0` and `7`, and an extra row (id 6) that the snapshot does not have.
4. Writes `out/canonical.json` and leaves `data/`, `spec/` and `checks/` byte-identical.
5. Runs the visible check. It only checks shape, so it does not confirm the values.

## Grader checks

- Output exists and parses (`output_missing`, `output_not_json`).
- Structure: key set, key order, integer ids, string names, two-decimal balances, boolean `active`, string-array
  `tags`, sorted root (`key_order_mismatch`, `id_not_integer`, `balance_precision_mismatch`, and others).
- Values equal the current export (`record_count_mismatch`, `record_value_mismatch`).
- Bytes equal the spec format (`formatting_mismatch`).
- Input files keep their pristine bytes. Stale files are labelled `decoy_file_modified`, others `input_file_modified`.

## Why each known-bad state is wrong

- `balance_trailing_zero_dropped.sh`: writes `0.0` for Bob's `0.00` (`balance_precision_mismatch`).
- `keys_out_of_order.sh`: `active` before `balance` (`key_order_mismatch`).
- `no_trailing_newline.sh`: right values, no trailing newline (`formatting_mismatch`).
- `numbers_as_strings.sh`: ids as strings (`id_not_integer`).
- `stale_snapshot_values.sh`: renders the stale five-row snapshot (`record_count_mismatch`).

## Careless controls

- `do_nothing.sh`: no output (`output_missing`).
- `fake_it.sh`: right shape and count, invented values with no export read (`record_value_mismatch`).
- `skip_check.sh`: renders the stale five-row snapshot (`record_count_mismatch`).
- `wrong_target.sh`: right records, written to `out/records.json` (`output_missing`).
- `half_done.sh`: copies CSV balances as-is (`balance_precision_mismatch`).

## Grader expectations

- Reference state: `passed: true`, reason `canonical_output_ok`.
- Untouched workspace: `passed: false`, with `output_missing`.
