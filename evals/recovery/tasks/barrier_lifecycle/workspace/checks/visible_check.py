"""Visible smoke check: confirms the JobRunner API exists and one trivial job joins. Shape only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobctl.runner import JobRunner  # noqa: E402

runner = JobRunner()
job = runner.start("smoke", [sys.executable, "-c", "print('ok')"])
result = runner.join(job, timeout=10)
if sorted(result) == ["cancelled", "exit_code", "name", "output"] and result["name"] == "smoke":
    print("passed")
    raise SystemExit(0)
print("failed")
raise SystemExit(1)
