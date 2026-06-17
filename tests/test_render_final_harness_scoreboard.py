from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.render_final_harness_scoreboard import _load_yaml, _registry_view, render_scoreboard


def _fixture_input() -> dict[str, object]:
    fixture_path = (
        REPO_ROOT
        / "tracking/collab/final_harness_eval_suite/fixtures/final_board_scoreboard_stub_input.synthetic.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _registry() -> dict[str, object]:
    registry_path = REPO_ROOT / "tracking/collab/final_harness_eval_suite/final_suite_registry.yaml"
    return _registry_view(_load_yaml(registry_path))


def test_render_final_harness_scoreboard_gate_verdicts_and_ordering():
    scoreboard = render_scoreboard(_fixture_input(), _registry(), allow_pre_stability=False)
    by_recipe = {entry["recipe_id"]: entry for entry in scoreboard["recipes"]}

    eligible = by_recipe["recipe_alpha_eligible"]
    assert eligible["admission_verdict"] == "finalist_eligible"
    assert eligible["sentinel_gate"] == "pass"
    assert eligible["flagship_gate"] == "pass"
    assert eligible["hard_task_pass_count"] == 7
    assert eligible["hard_task_gate"] == "pass"
    assert eligible["critical_cluster_gate"] == "pass"
    assert eligible["contamination_gate"] == "pass"
    assert eligible["invalidity_gate"] == "pass"
    assert eligible["stability_gate"] == "pass"
    assert eligible["finalist_rank"] == 1

    failed = by_recipe["recipe_beta_failed"]
    assert failed["admission_verdict"] == "not_eligible"
    assert failed["sentinel_gate"] == "fail"
    assert failed["flagship_gate"] == "fail"
    assert failed["hard_task_pass_count"] == 5
    assert failed["hard_task_gate"] == "fail"
    assert failed["finalist_rank"] is None

    invalid = by_recipe["recipe_gamma_invalid"]
    assert invalid["admission_verdict"] == "invalid"
    assert invalid["sentinel_gate"] == "invalid"
    assert invalid["flagship_gate"] == "invalid"
    assert invalid["invalidity_gate"] == "fail"

    assert scoreboard["finalists"] == [{"recipe_id": "recipe_alpha_eligible", "finalist_rank": 1}]
    assert [item["gate"] for item in eligible["gate_trace"]] == [
        "sentinel_gate",
        "flagship_gate",
        "hard_task_gate",
        "critical_cluster_gate",
        "contamination_gate",
        "invalidity_gate",
        "stability_gate",
    ]


def test_render_final_harness_scoreboard_cli_smoke(tmp_path):
    fixture_path = (
        REPO_ROOT
        / "tracking/collab/final_harness_eval_suite/fixtures/final_board_scoreboard_stub_input.synthetic.json"
    )
    registry_path = REPO_ROOT / "tracking/collab/final_harness_eval_suite/final_suite_registry.yaml"
    output_dir = tmp_path / "board_out"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/render_final_harness_scoreboard.py"),
            "--input",
            str(fixture_path),
            "--registry",
            str(registry_path),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "scoreboard.json").exists()
    assert (output_dir / "scoreboard.md").exists()
    assert not (output_dir / "finalist_selection.md").exists()
