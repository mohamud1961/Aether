from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _guard_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "check_production_surface.py"
    spec = importlib.util.spec_from_file_location("aether_production_surface_guard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_neutrality_guard_covers_a5_b5_and_frozen_board_sources() -> None:
    guard = _guard_module()
    task_ids, sources = guard.benchmark_neutrality_task_ids()
    ids = set(task_ids)
    # Regression for the exact audit gap: all five B5 rows must be derived from
    # evidence, not manually repeated in the checker implementation.
    assert {
        "wal-recovery-ordering",
        "dna-assembly",
        "cad-model",
        "make-mips-interpreter",
        "llm-inference-batching-scheduler",
    } <= ids
    assert len(ids) >= 100
    assert len(sources) == 4
    assert all(row.get("sha256") for row in sources)


def test_new_frozen_release_task_is_automatically_covered(tmp_path, monkeypatch) -> None:
    guard = _guard_module()
    board = json.loads(guard.NEUTRALITY_BOARD.read_text(encoding="utf-8"))
    synthetic = "synthetic-neutrality-regression-task"
    board["frontier_selection_authority"]["release_task_ids"].append(synthetic)
    board["frontier_selection_authority"]["release_inventory_authority"]["task_count"] += 1
    temp_board = tmp_path / "board.json"
    temp_board.write_text(json.dumps(board), encoding="utf-8")
    monkeypatch.setattr(guard, "NEUTRALITY_BOARD", temp_board)

    task_ids, _sources = guard.benchmark_neutrality_task_ids()
    assert synthetic in task_ids
