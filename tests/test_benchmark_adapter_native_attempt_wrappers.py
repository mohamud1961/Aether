from __future__ import annotations

import json

from tools.run_benchmark_adapter_contextbench_native_attempt import run_contextbench_native_attempt
from tools.run_benchmark_adapter_letta_native_attempt import run_letta_native_attempt
from tools.run_benchmark_adapter_terminalbench_native_attempt import run_terminalbench_native_attempt


def test_contextbench_native_attempt_wrapper_emits_equivalent_with_blocker(tmp_path):
    summary = run_contextbench_native_attempt(tmp_path / "contextbench")
    scoreboard = json.loads((tmp_path / "contextbench" / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["authority_mode"] == "equivalent"
    assert summary["native_attempt_status"] == "blocked"
    assert summary["native_blocker_report_path"]
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}


def test_letta_native_attempt_wrapper_emits_equivalent_with_blocker(tmp_path):
    summary = run_letta_native_attempt(tmp_path / "letta")
    scoreboard = json.loads((tmp_path / "letta" / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["authority_mode"] == "equivalent"
    assert summary["native_attempt_status"] == "blocked"
    assert summary["native_blocker_report_path"]
    assert summary["official_native_status"]["authority_label"] == "official_native"
    assert summary["azure_equivalent_status"]["authority_label"] == "azure_equivalent"
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}


def test_terminalbench_native_attempt_wrapper_emits_equivalent_with_blocker(tmp_path):
    summary = run_terminalbench_native_attempt(tmp_path / "terminalbench")
    scoreboard = json.loads((tmp_path / "terminalbench" / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["authority_mode"] == "equivalent"
    assert summary["native_attempt_status"] == "blocked"
    assert summary["native_blocker_report_path"]
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}
