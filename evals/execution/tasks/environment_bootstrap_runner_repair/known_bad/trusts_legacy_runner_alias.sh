#!/usr/bin/env bash
# expect: runner_command_mismatch
# Leaves the stale runner alone and reports the legacy alias from the old notes as the runner command.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
from pathlib import Path
report = {
    "runner_command": "bash scripts/run_legacy_tests.sh",
    "package_manager": "pip",
    "preflight_success": True,
    "evidence": ["docs/stale_runner_guidance.md says to run the legacy script"],
}
Path("out/toolchain_repair_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
Path("out/patches_applied.txt").write_text("scripts/run_tests.sh\n", encoding="utf-8")
PY
printf '#!/usr/bin/env bash\nset -euo pipefail\nbash scripts/run_legacy_tests.sh\n' > scripts/run_tests.sh
