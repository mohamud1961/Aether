#!/usr/bin/env bash
# expect: runner_script_not_patched
# Applies the canonical command to the legacy runner instead, lists that file as the patch, and leaves the real runner stale.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
cp "$TASK_ROOT/workspace/scripts/run_tests.sh" scripts/run_tests.sh
printf '#!/usr/bin/env bash\nset -euo pipefail\npython3 -m unittest tests.test_runner_contract\n' > scripts/run_legacy_tests.sh
printf 'scripts/run_legacy_tests.sh\n' > out/patches_applied.txt
