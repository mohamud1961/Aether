#!/usr/bin/env bash
# expect: missing_toolchain_repair_report
# Repairs the runner script correctly, then stops before writing the report or the patch list.
set -euo pipefail
printf '#!/usr/bin/env bash\nset -euo pipefail\npython3 -m unittest tests.test_runner_contract\n' > scripts/run_tests.sh
