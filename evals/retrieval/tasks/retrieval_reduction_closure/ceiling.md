# Ceiling: retrieval reduction closure (v2)

## What a perfect solution does

1. Reads `data/index.json`: batch `B-2026-10`, shards `shards/shard-b.jsonl` then `shards/shard-a.jsonl`.
   It ignores the declared total (7401), `docs/closure_notes.txt`, `data/mirror/`, `data/archive/` and the log.
2. Keeps the current row per `line_key` within the batch (the highest revision). `L-04` is revision 2 (`ev-1177`),
   not `ev-2101`. `L-09` is revision 2 (`ev-2104`). `L-12` is `ev-1180`. For `L-15`, revision 2 (`ev-1185`) is
   stale, so nothing is counted.
3. Counts a current row only if its `status` is `active`. Sum = 1950 + 2050 + 600 = 4600.
4. Lists counted IDs in index shard order: `["ev-2104", "ev-1177", "ev-1180"]`.
5. Rejects every other batch row in the same order: `["ev-2101", "ev-2103", "ev-1183", "ev-1185"]`. `ev-2101`
   and `ev-1183` say `active` but are superseded.
6. Writes a justification of at least 10 characters for all seven IDs and the exact verifier command.
   Then it runs the visible check, which passes on shape alone.

The reference derives everything from the export. It does not hard-code the values.

## Why each known-bad state is wrong

- `stale_scalar_from_summary.sh`: final_value is the declared total 7401. `final_value_mismatch`.
- `active_status_only.sh`: trusts the row's own status and counts superseded `ev-2101` and `ev-1183`. The scalar and
  `evidence_ids` are both wrong (`final_value_mismatch`).
- `mirror_copy_value.sh`: uses the lagging mirror value 2010 for `ev-1177`. `final_value_mismatch`.
- `drop_active_evidence_id.sh`: omits `ev-1180`, an active row that supports the scalar (`evidence_ids_mismatch`).
- `omit_stale_rejections.sh`: no stale IDs are rejected (`stale_ids_mismatch`).
- `missing_stale_justification.sh`: the lists are right but `ev-1183` has no justification (`justification_missing`).
- `edited_input_row.sh`: the submission is correct, but a ledger row was edited to fit (`input_file_modified`).

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`, `reasons: []`.
- Untouched workspace (no `out/`): `passed: false`, reason `missing_candidate`.
