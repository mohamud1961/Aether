# Ceiling: delegation_fidelity (v2)

## What a perfect solution does

1. Reads `thread/request_thread.md` in full, including the replies. The latest decisions win: format v2 (not v1), the frozen
   snapshot (not the live database), and packet version 2 for all workers.
2. Notices the retraction: the PII redaction ask `[R-01]` is dropped (Priya, msg 3).
3. Finds the constraint buried in Marco's reply to Sam (msg 5): `[C-01]`, no worker opens or edits `vendor/`. It applies to all three workers.
4. Writes `out/packets/ingest.json`, `reconcile.json` and `writer.json` with exactly the keys in `specs/packet_schema.json`.
   `constraint_ids` are: ingest `C-01, C-02`; reconcile `C-01, C-03`; writer `C-01, C-04`. `packet_version` is 2.
   The stale README template (with `deadline` and `constraints` fields) is not used.
5. Merges by `specs/merge_rules.md`. `reconcile` returns `packet_version` 1, which does not match the current 2, so it is rejected
   with reason `stale_packet_version`, and `REC-001` stays out. The merge is written to `out/merged.json`:
   accepted `ingest` and `writer`, findings `ING-001, ING-002, WRT-001`, packet versions 2 for all workers.
6. Changes nothing outside `out/`. The vendor sync files and the thread stay byte-identical.
7. Runs the visible check and sees `passed`. That check tests key types only.

The reference reads the `[C-xx] applies to:` tags from the thread and the current version from the schema file. It hard-codes the method
and the goal wording, not the constraint assignments.

## Grader checks

- `missing_packets`, `unexpected_packet`, `duplicate_packet`: exactly one packet per worker, in `out/packets/`.
- `packet_schema_mismatch`: exact key set and types.
- `packet_version_mismatch`: must equal the current version (2).
- `retracted_constraint_present`: any `R-` or `X-` id in `constraint_ids`.
- `live_constraint_missing`: a live `C-` id the worker needs is absent.
- `constraint_misassigned`: a live `C-` id is assigned to a worker it does not apply to.
- `missing_merged`, `merged_unparseable`, `merge_mismatch`: exact merge content.
- `stale_result_accepted`: `reconcile` in `accepted_workers`, or `REC-001` among the findings.
- `vendor_modified`, `input_modified`: any initial file changed (out/ excluded).

## Why each known-bad state is wrong

- `kb_keeps_retracted_redaction`: the writer packet still carries the retracted `R-01` (`retracted_constraint_present`).
- `kb_drops_vendor_rule`: the ingest packet omits the buried `C-01` (`live_constraint_missing`).
- `kb_accepts_stale`: the merge accepts the version-1 reconcile result and its finding (`stale_result_accepted`).
- `kb_extra_packet_key`: the `deadline` field from the stale template (`packet_schema_mismatch`).
- `kb_live_db_reconcile`: reconcile gets the rejected live-database ask `X-02` instead of `C-03` (`retracted_constraint_present`).
- `kb_vendor_edit`: appends a checksum line to `vendor/checksums.txt` (`vendor_modified`).

## Careless controls

- `do_nothing`: no packets (`missing_packets`).
- `fake_it`: every constraint on every worker, and a merge that accepts the stale result (`constraint_misassigned`).
- `skip_check`: builds packets from the first message, including the retracted and superseded asks (`retracted_constraint_present`).
- `wrong_target`: packets written to `out/packet/` (`missing_packets`).
- `half_done`: correct packets, no merge (`missing_merged`).

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false` with `missing_packets` and `missing_merged`.
