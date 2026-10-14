# Task card: tool call composite (v2)

Admission: **capability**. Controls test the v2 design. They do not establish parity with the original trace contract.

## Design (v2)

- Two-hop contract resolution: `contracts/tool_schema.json` (pointer) -> `contracts/revisions/rev-07.json`.
- Decoys: a draft revision with different ticket and owner, a superseded revision with the legacy alias.
- Stale doc: `docs/legacy_tooling_notes.md` describes the forbidden no-argument call.
- Noise: `dispatch_log/history.ndjson` with earlier passed and failed calls.
- Visible check is shape-only, so it gives false confidence on values.
- Pristine files are sealed by hash; out-of-scope edits are caught.

## Controls

- Known-bad: 7 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| forbidden_alias_used | known_bad legacy_no_argument_call |
| ticket_id_mismatch | known_bad draft_revision_values, near_miss_ticket_id; careless fake_it, skip_check |
| receipt_missing | known_bad missing_receipt |
| receipt_status_mismatch | known_bad receipt_status_failed |
| verifier_command_mismatch | known_bad verifier_evidence_omitted |
| other_file_modified | known_bad contract_edited_to_match |
| receipt_path_mismatch | careless wrong_target |
| missing_candidate | careless do_nothing, half_done |

Trace-dependent process checks (tool invocation order, verifier event) are not established by this final-state grader.
