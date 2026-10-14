# Task card: exact_serialization_contract (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with the original trace contract.

## Design (v2)

- Export pointer: `data/EXPORTS.json` names the current export. A README and a `records.csv` snapshot point at the old one.
- A v1 spec that is superseded (sorting by name, null tags, one item per line).
- Messy export: unsorted rows, quoted and escaped names, unpadded balances, an extra row.
- Output bytes must match the spec, including the inline array format the spec now states.
- Inputs are sealed by pristine hash.

## Controls

- Known-bad: 5 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| balance_precision_mismatch | known_bad balance_trailing_zero_dropped; careless half_done |
| key_order_mismatch | known_bad keys_out_of_order |
| formatting_mismatch | known_bad no_trailing_newline |
| id_not_integer | known_bad numbers_as_strings |
| record_value_mismatch | careless fake_it |
| record_count_mismatch | known_bad stale_snapshot_values; careless skip_check |
| output_missing | careless do_nothing, wrong_target |

Trace-dependent process checks are not established by this final-state grader.
