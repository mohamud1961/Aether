#!/usr/bin/env bash
# expect: runner_command_mismatch
# Takes the first plausible command from the old pytest runner, swaps in python3, reports preflight as passed, and never runs it.
set -euo pipefail
mkdir -p out
printf '#!/usr/bin/env bash\nset -euo pipefail\npython3 -m pytest tests/test_runner_contract.py -q\n' > scripts/run_tests.sh
python3 - <<'PY'
import json
from pathlib import Path
report = {
    "runner_command": "python3 -m pytest tests/test_runner_contract.py -q",
    "package_manager": "pip",
    "preflight_success": True,
    "evidence": ["scripts/run_tests.sh rewritten"],
}
Path("out/toolchain_repair_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
Path("out/patches_applied.txt").write_text("scripts/run_tests.sh\n", encoding="utf-8")
PY
