#!/usr/bin/env bash
# expect: id_not_integer
# Reference values, but ids are written as strings.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh" >/dev/null
sed -i.bak -E 's/"id": ([0-9]+),/"id": "\1",/' out/canonical.json && rm -f out/canonical.json.bak
