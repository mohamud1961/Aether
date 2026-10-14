# Dispatch runbook

- The call is recorded against the revision named in `contracts/tool_schema.json`.
- Draft revisions are not authoritative until someone promotes them to `active`.
- The receipt goes to `out/dispatch_receipt.json`. A call that did not pass is not closed as passed.
- Use the revision's `tool_name` and its required ticket and owner values.
