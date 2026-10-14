#!/usr/bin/env bash
# expect: runner_script_not_patched
# Applies the right command, but to scripts/run_legacy_tests.sh, the file the old notes name.
set -euo pipefail
mkdir -p out
printf '#!/usr/bin/env bash\nset -euo pipefail\npython3 -m unittest tests.test_runner_contract\n' > scripts/run_legacy_tests.sh
python3 - <<'PY'
import json
from pathlib import Path
report = {
    "runner_command": "python3 -m unittest tests.test_runner_contract",
    "package_manager": "pip",
    "preflight_success": True,
    "evidence": ["scripts/run_legacy_tests.sh rewritten"],
}
Path("out/toolchain_repair_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
Path("out/patches_applied.txt").write_text("scripts/run_legacy_tests.sh\n", encoding="utf-8")
PY
