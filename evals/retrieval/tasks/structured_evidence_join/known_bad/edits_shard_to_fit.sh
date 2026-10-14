#!/usr/bin/env bash
# expect: other_file_modified
# Reference state, but the warehouse event shard is edited to match the export's 13:10 ship time for O-1002.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
sed -i.bak 's/"corrected_shipped_at": "2026-10-03T09:50:00Z"/"corrected_shipped_at": "2026-10-03T11:10:00Z"/' events/shard-a.jsonl && rm -f events/shard-a.jsonl.bak
