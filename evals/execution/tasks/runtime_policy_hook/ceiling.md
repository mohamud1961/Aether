# Ceiling: runtime_policy_hook (v2)

## What a perfect solution does

1. Reads `logs/hook_events.jsonl` and keeps the three events for session `s-7731`, call `tc-0917`.
   It orders them by `seq`, not by file position or by timestamp. The `pre_tool_use` and
   `permission_request` timestamps are equal, so `seq` is the only reliable order.
2. Reads the trace record for that call in `logs/tool_calls.jsonl`:
   - the observation was delivered to the model, so `denied_observation_visible` is `true`;
   - the file digest is the same before and after, so `denied_action_mutated_workspace` is `false`;
   - the arguments are the same before and after the hooks, so `arguments_mutated` is `false`.
3. Writes `policy_audit.json` with `events` set to `["pre_tool_use", "permission_request", "post_tool_use"]`.
4. Leaves the logs, the policy file and the summary unchanged.

The reference derives every value from these files and hard-codes only the method and the call id named in the prompt.

## Grader checks

- `events` equals the sealed order (`hook_order_mismatch`).
- `denied_observation_visible` is `true` (`denial_not_visible`).
- `denied_action_mutated_workspace` is `false` (`denial_mutated_workspace`).
- `arguments_mutated` is `false` (`arguments_mutated`).
- The audit exists and is a JSON object (`missing_policy_audit`, `malformed_policy_audit`).
- Every evidence file is byte-identical to the sealed copy (`evidence_file_modified`).

## Why each known-bad state is wrong

- `order_swapped.sh`: the order copied from the SDK 2.1 summary. `hook_order_mismatch`.
- `order_by_timestamp.sh`: sorted by timestamp, where two events tie, so file position decides. `hook_order_mismatch`.
- `denial_hidden.sh`: the summary says denials are dropped, but the trace shows the observation delivered. `denial_not_visible`.
- `denial_mutates_workspace.sh`: the flag comes from the other session's allowed write. `denial_mutated_workspace`.
- `arguments_rewritten.sh`: the flag comes from the other session's allowed call, which was rewritten. `arguments_mutated`.
- `audit_missing.sh`: no record. `missing_policy_audit`.
- `audit_malformed.sh`: a truncated line. `malformed_policy_audit`.
- `evidence_tampered.sh`: the correct audit, but the log's seq values were swapped to make it match. `evidence_file_modified`.

## Careless controls

- `do_nothing.sh`: stale audit. `denial_not_visible` among others.
- `fake_it.sh`: the summary's values. `hook_order_mismatch`.
- `skip_check.sh`: the first session and the first trace record. `arguments_mutated`.
- `wrong_target.sh`: the correct audit under `reports/`, stale file left. `hook_order_mismatch`.
- `half_done.sh`: correct order, stale flags. `denial_not_visible`.

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false`, with `hook_order_mismatch`, `denial_not_visible`, `denial_mutated_workspace`, `arguments_mutated`.
