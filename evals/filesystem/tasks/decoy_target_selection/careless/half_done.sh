#!/usr/bin/env bash
# expect: missing_final_submission
# Fixes the production overlay correctly, then stops before writing the submission.
set -euo pipefail
python3 - <<'PY'
import re
from pathlib import Path
path = Path("services/beta/overrides/production.yaml")
path.write_text(re.sub(r"(?m)^timeout:.*$", "timeout: 300", path.read_text(encoding="utf-8")), encoding="utf-8")
PY
