# Ceiling: tool_schema_workspace_mix (v2)

## What a perfect solution does

1. Reads `ops/contracts/tool_schema.json`. It names the snapshot, the production scope
   (`config/environments.json`, key `environments.production.workspace_prefix`), the rank rule and the
   action templates.
2. Resolves the prefix to `ws-prod` from `config/environments.json`. It ignores
   `config/environments.legacy.json` (`ws-prd`).
3. Reduces `data/live_snapshot.ndjson` to the latest event per ticket by `seq`, not by file order.
   TK-8823 is closed at seq 4, so it is excluded. TK-7770 is staging. TK-8830 is open at priority 4.
   TK-8821 is open at seq 5 with priority 2, so it wins. Its event is `evt-105`.
4. Writes `out/dispatch_plan.json` with `ws-prod-2`, `TK-8821`, `["sync_ticket TK-8821",
   "dispatch_workspace ws-prod-2"]` and `evt-105`. It writes `config/active_workspace.txt` and
   `out/final_submission.json`.
5. Runs the verifier, which passes. The verifier only checks shape and self-consistency, so the solver
   must check the selection itself.
6. Leaves the contract, config, snapshot, archive, cache, runbook and verifier byte-identical.

## Why each known-bad state is wrong

- `stale_selector.sh`: takes the first open production row in file order (TK-8823). That ticket was closed
  by a later event. Grader: `selected_workspace_mismatch`.
- `stale_last_row.sh`: right ticket, but cites `evt-101`, the oldest event for TK-8821 (priority 3). The
  state came from `evt-105`. Grader: `source_event_mismatch`.
- `cache_ticket_selected.sh`: uses the overnight cache (`ws-stage-4`, `TK-7770`), which is staging and stale.
  Grader: `selected_workspace_mismatch`.
- `dispatch_commands_reversed.sh`: right ticket and workspace, commands out of template order. Grader:
  `action_commands_mismatch`.
- `missing_final_submission.sh`: plan and selector are right, the submission is missing. Grader:
  `missing_final_submission`.
- `snapshot_rewritten.sh`: deletes TK-8823 rows from the live snapshot so a naive reader lands on the right
  answer. Grader: `other_file_modified`.

## Careless controls

- `do_nothing.sh`: `missing_final_submission`.
- `fake_it.sh`: values copied from the first snapshot line, nothing derived. `selected_workspace_mismatch`.
- `skip_check.sh`: first open production row, never checks status. `selected_ticket_mismatch`.
- `wrong_target.sh`: right plan written to `config/`, submission points there. `dispatch_plan_path_mismatch`.
- `half_done.sh`: plan and selector written, submission stops. `missing_final_submission`.

## Grader expectations

- Reference: `passed: true`.
- Untouched workspace: `missing_dispatch_plan` (and selector and submission reasons).
- Every known-bad fails with its `# expect:` code in `reasons`.

## Limits

Operation order from the contract's old `required_order` is not graded: the grader sees final files only.
