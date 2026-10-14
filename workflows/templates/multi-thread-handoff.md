# Multi-thread orchestration handoff

Use this when a worker hands results back to an orchestrator. Fill every field. Write `none` or `not applicable` where that is the truth. Do not leave a field blank.

```text
WORKER_HANDOFF
- final_status: complete | partial | blocked | invalid_due_to_environment
- objective_completed: <exact scope completed>
- scope_respected: yes | no (explain if no)
- files_changed:
  - <file>: <what changed and why>
- harvest_files_inspected:
  - <file>: <what was used>
- requirement_disposition:
  - <requirement>: complete | partial | blocked | not_applicable
- tests_run:
  - command: <exact command>
    result: <pass count, or failure message>
    evidence_path: <path>
- review_disposition: <review tool used, or "manual self-review" with checklist>
- accepted_findings:
  - <finding>: <how addressed>
- rejected_findings:
  - <finding>: <why rejected, with evidence>
- missing_items:
  - <item>: <why missing, what is needed>
- blockers:
  - <blocker>: <what it prevents>
- external_state:
  - <process, VM, container, or service still running>: <status>
- ledger_update: <entry written, path, or not material>
- next_action: <exact next step>
- delivery_receipt:
  - delivered_to: <orchestrator thread or role>
  - method: <thread message, tool, or channel>
  - result: <received | error | not yet confirmed>
```

## Quality checks before sending

- The summary matches the live tree.
- Claims are qualified where evidence is incomplete.
- Every number has an evidence path.
- The orchestrator can choose the next slice without reopening the task.
- The handoff was sent to the originating orchestrator. A file on disk, or a final message nobody received, does not count.
