#!/usr/bin/env bash
# expect: journal_inconsistent
# Output is exact, but the journal gets a second committed event for batch 2.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
printf '%s\n' '{"batch": 2, "event": "committed", "rows": 8, "last_id": 16}' >> state/migration_journal.jsonl
