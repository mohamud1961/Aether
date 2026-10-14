"""Visible smoke check: confirms run_batch exists and returns the three result keys. Shape only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wirekit.batch import run_batch  # noqa: E402

result = run_batch([], None)
if sorted(result) == ["attempts", "failed", "results"]:
    print("passed")
    raise SystemExit(0)
print("failed")
raise SystemExit(1)
