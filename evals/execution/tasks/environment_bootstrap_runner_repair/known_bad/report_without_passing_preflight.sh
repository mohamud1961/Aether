#!/usr/bin/env bash
# expect: runner_run_failed
# Writes the canonical command into the runner, but a stray cd makes the run fail. The report still says preflight passed.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
printf '#!/usr/bin/env bash\nset -euo pipefail\ncd /nonexistent/runner-root\npython3 -m unittest tests.test_runner_contract\n' > scripts/run_tests.sh
