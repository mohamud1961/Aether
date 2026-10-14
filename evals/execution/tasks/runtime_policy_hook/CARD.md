# Task card: runtime_policy_hook (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design.

## Design (v2)

- The prompt names the session and call only. It does not state the order, the visibility, the workspace effect or
  the argument effect. Those are derived from `logs/hook_events.jsonl`, `logs/tool_calls.jsonl` and `config/hook_policy.json`.
- Traps: file order is not seq order, and the target's pre and permission events share a timestamp. A summary written
  for SDK 2.1 gives the wrong order and says denials are hidden. Another session's allowed call has a rewritten path
  and changed files, so a naive reader flags a mutation.
- The grader seals the derived values and hashes every evidence file. Editing a log to match the audit fails.

## Controls

- Known-bad: 8 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| hook_order_mismatch | known_bad order_swapped, order_by_timestamp; careless fake_it, wrong_target |
| denial_not_visible | known_bad denial_hidden; careless do_nothing, half_done |
| denial_mutated_workspace | known_bad denial_mutates_workspace |
| arguments_mutated | known_bad arguments_rewritten; careless skip_check |
| missing_policy_audit | known_bad audit_missing |
| malformed_policy_audit | known_bad audit_malformed |
| evidence_file_modified | known_bad evidence_tampered |
