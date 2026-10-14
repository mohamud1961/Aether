# Task card: tool schema workspace mix (v2)

Admission: **capability**. Controls test the v2 design. They do not establish parity with the original trace contract.

## Design (v2)

- Append-only snapshot: the latest event per ticket decides state, not file order (`seq`).
- Indirection: the production prefix comes from `config/environments.json` through the contract's scope pointer.
- Decoys: `config/environments.legacy.json` (`ws-prd`), `data/archive/` (September snapshot), `tmp/tool_cache` (stale staging hint).
- Stale notes: `ops/runbooks/operator_notes.md` recommends the cache as a "fast path".
- Visible verifier checks shape and self-consistency only.
- Pristine inputs are sealed by hash.

## Controls

- Known-bad: 6 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| selected_workspace_mismatch | known_bad stale_selector, cache_ticket_selected; careless fake_it |
| source_event_mismatch | known_bad stale_last_row |
| action_commands_mismatch | known_bad dispatch_commands_reversed |
| missing_final_submission | known_bad missing_final_submission; careless do_nothing, half_done |
| other_file_modified | known_bad snapshot_rewritten |
| selected_ticket_mismatch | careless skip_check |
| dispatch_plan_path_mismatch | careless wrong_target |

Operation order (`required_order`) is not graded by this final-state grader.
