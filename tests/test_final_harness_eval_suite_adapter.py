from __future__ import annotations

from pathlib import Path

from runner.final_harness_eval_suite_adapter import load_final_suite_row_specs

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_final_suite_row_specs_resolves_all_rows():
    specs = load_final_suite_row_specs(REPO_ROOT)
    assert len(specs) == 28
    assert specs[0].row_id == "fhard_01_toolchain_runner_repair"
    assert specs[7].row_id == "fhard_08_original_noisy_open_workflow"
    assert specs[12].row_id == "fsent_05_long_handoff_composition_smoke"
    assert specs[-1].row_id == "ftb_challenge_install_windows_3_11"


def test_load_final_suite_row_specs_bridges_legacy_and_v1_shapes():
    specs = {row.row_id: row for row in load_final_suite_row_specs(REPO_ROOT)}

    legacy = specs["fhard_01_toolchain_runner_repair"]
    assert legacy.legacy_layout is True
    assert legacy.canonical_workspace_root == "/workspace/fhard_01"
    assert legacy.expected_candidate_output == "candidate"

    modern = specs["fsent_02_runtime_workspace_contract"]
    assert modern.legacy_layout is False
    assert modern.canonical_workspace_root == "/workspace/runtime"
    assert modern.runtime_python_command == "python3"
    assert modern.max_solver_seconds == 180


def test_load_final_suite_row_specs_includes_official_benchmark_and_tb_challenge_lanes():
    specs = load_final_suite_row_specs(REPO_ROOT)
    by_source = {}
    for spec in specs:
        by_source[spec.execution_source] = by_source.get(spec.execution_source, 0) + 1
    assert by_source == {
        "task_pack": 13,
        "benchmark_adapter": 13,
        "terminalbench_challenge": 2,
    }

    benchmark_counts: dict[str, int] = {}
    for spec in specs:
        if spec.execution_source != "benchmark_adapter":
            continue
        assert spec.benchmark_name is not None
        benchmark_counts[spec.benchmark_name] = benchmark_counts.get(spec.benchmark_name, 0) + 1
    assert benchmark_counts == {
        "BFCL": 3,
        "ACEBench": 3,
        "ContextBench": 3,
        "Letta": 3,
        "TerminalBench": 1,
    }
    assert all(count <= 3 for count in benchmark_counts.values())

    terminalbench_row = next(
        spec for spec in specs if spec.row_id == "terminalbench_public_financial-document-processor"
    )
    assert terminalbench_row.execution_source == "benchmark_adapter"
    assert terminalbench_row.benchmark_name == "TerminalBench"
    assert terminalbench_row.benchmark_case_id == "financial-document-processor"

    challenge_task_ids = {
        spec.challenge_task_id
        for spec in specs
        if spec.execution_source == "terminalbench_challenge"
    }
    assert challenge_task_ids == {"extract-moves-from-video", "install-windows-3.11"}
