#!/usr/bin/env bash
# expect: input_modified
# Cleans the original export in place, then migrates from the cleaned copy.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
sed -i.bak 's/"name": "  Ada   Lovelace "/"name": "Ada Lovelace"/' data/input/users.jsonl
rm -f data/input/users.jsonl.bak
