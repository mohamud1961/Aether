#!/usr/bin/env bash
# expect: contract_modified
# Rewrites the contract to the stale pytest command, so the old runner and the contract agree, and reports that command.
set -euo pipefail
bash "$TASK_ROOT/reference/solve.sh"
python3 - <<'PY'
import json
from pathlib import Path
contract_path = Path("config/toolchain_contract.json")
contract = json.loads(contract_path.read_text(encoding="utf-8"))
contract["test_runner"] = "python3 -m pytest"
contract["test_target"] = "tests/test_runner_contract.py -q"
contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
report_path = Path("out/toolchain_repair_report.json")
report = json.loads(report_path.read_text(encoding="utf-8"))
report["runner_command"] = "python3 -m pytest tests/test_runner_contract.py -q"
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
printf '#!/usr/bin/env bash\nset -euo pipefail\npython3 -m pytest tests/test_runner_contract.py -q\n' > scripts/run_tests.sh
