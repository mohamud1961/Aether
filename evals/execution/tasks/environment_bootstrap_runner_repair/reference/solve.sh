#!/usr/bin/env bash
# Derives the runner command and package manager from config/toolchain_contract.json, rewrites
# scripts/run_tests.sh to that command, runs it with the python3 on PATH, and records the result.
set -euo pipefail
mkdir -p out
python3 - <<'PY'
import json
import subprocess
import sys
from pathlib import Path

root = Path(".")
contract = json.loads((root / "config" / "toolchain_contract.json").read_text(encoding="utf-8"))
command = " ".join(f"{contract['test_runner']} {contract['test_target']}".split())

(root / "scripts" / "run_tests.sh").write_text(
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    "\n"
    "# Canonical runner, from config/toolchain_contract.json.\n"
    f"{command}\n",
    encoding="utf-8",
)

run = subprocess.run(["bash", "scripts/run_tests.sh"], capture_output=True, text=True)
tail = (run.stdout + run.stderr).strip().splitlines()[-3:]
report = {
    "runner_command": command,
    "package_manager": contract["package_manager"],
    "preflight_success": run.returncode == 0,
    "evidence": [
        "config/toolchain_contract.json: test_runner and test_target give the runner command",
        f"interpreter: {sys.version.split()[0]} from python3 on PATH (contract min_python {contract['min_python']})",
        f"bash scripts/run_tests.sh exit status {run.returncode}; last output line: {tail[-1] if tail else ''}",
        "scripts/run_tests.sh rewritten to the contract command",
    ],
}
(root / "out" / "toolchain_repair_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(root / "out" / "patches_applied.txt").write_text("scripts/run_tests.sh\n", encoding="utf-8")
PY

python3 checks/visible_check.py --candidate out/toolchain_repair_report.json
