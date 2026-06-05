from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_first_result_attribution_mechanism_replay import run_replay_tournament


def test_replay_tournament_writes_rows_and_comparison(tmp_path):
    summary = run_replay_tournament(tmp_path)
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))
    comparison = json.loads((tmp_path / "comparison_summary.json").read_text(encoding="utf-8"))

    assert summary["row_count"] == 12
    assert scoreboard["row_count"] == 12
    assert set(comparison["by_variant"]) == {
        "control_no_mechanism",
        "no_call_attribution_guard",
        "ignored_result_ids_guard",
        "combined_guard",
    }
