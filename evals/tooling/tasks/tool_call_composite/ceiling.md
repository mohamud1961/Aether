# Ceiling: tool_call_composite (v2)

## What a perfect solution does

1. Reads `contracts/tool_schema.json`, which is a pointer. It names `rev-07` as the active revision.
2. Reads `contracts/revisions/rev-07.json` for the values in force: tool `dispatch_ticket`, ticket
   `ticket-4472`, owner `owner-lyra`, receipt status `passed`.
3. Ignores `rev-08-draft.json` (status `draft`), `rev-06.json` (superseded), the stale notes in
   `docs/legacy_tooling_notes.md`, and the old history rows in `dispatch_log/history.ndjson`.
4. Writes `out/dispatch_receipt.json` with those values and `out/final_submission.json` with
   `tool_name`, `ticket_id`, `owner`, `receipt_path` (`out/dispatch_receipt.json`) and the exact
   `verifier_command`.
5. Runs the visible check and sees `passed`. That check only confirms keys, so the solver must check the
   values itself.
6. Leaves every pristine file byte-identical.

## Why each known-bad state is wrong

- `legacy_no_argument_call.sh`: the summary uses the superseded alias `legacy_dispatch` and drops the
  ticket and owner. Grader: `forbidden_alias_used`.
- `draft_revision_values.sh`: the draft revision's ticket and owner are used consistently in both files.
  The files agree with each other, but not with the revision in force. Grader: `ticket_id_mismatch`.
- `missing_receipt.sh`: the summary is correct, but no receipt exists. Grader: `receipt_missing`.
- `receipt_status_failed.sh`: the receipt records `failed` for a call that is being closed as passed.
  Grader: `receipt_status_mismatch`.
- `verifier_evidence_omitted.sh`: the verifier command is missing from the summary. Grader:
  `verifier_command_mismatch`.
- `contract_edited_to_match.sh`: the active revision file is rewritten so the wrong ticket is confirmed.
  Grader: `other_file_modified` (the revision is pristine), plus `ticket_id_mismatch`.
- `near_miss_ticket_id.sh`: digits transposed in both files, so the files agree but the value is wrong.
  Grader: `ticket_id_mismatch`.

## Careless controls

- `do_nothing.sh`: `missing_candidate`.
- `fake_it.sh`: values copied from an old history row, no contract read. `ticket_id_mismatch`.
- `skip_check.sh`: takes the highest-numbered revision (the draft) without checking status. `ticket_id_mismatch`.
- `wrong_target.sh`: correct values, receipt moved to a scratch folder. `receipt_path_mismatch`.
- `half_done.sh`: writes the receipt, stops before the summary. `missing_candidate`.

## Grader expectations

- Reference: `passed: true`, `score: 1.0`.
- Untouched workspace: `missing_candidate`.
- Every known-bad fails with its `# expect:` code in `reasons`.

## Limits

The grader checks final files only. It cannot see whether the dispatch tool was invoked or whether the
visible check ran; a solver that writes both files by hand passes, as the original port did.
