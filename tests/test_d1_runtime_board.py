from __future__ import annotations

import json
from pathlib import Path

from evals.performance.d1_runtime_board import EXPECTED_CASE_IDS, load_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evals" / "performance" / "D1_RUNTIME_BOARD_V1.json"


def test_d1_manifest_is_exact_six_case_provider_free_board() -> None:
    doc = load_manifest(MANIFEST)
    assert tuple(row["id"] for row in doc["cases"]) == EXPECTED_CASE_IDS
    assert doc["provider_policy"] == {
        "fake_provider_fixtures_allowed": True,
        "mode": "provider_free",
        "real_provider_calls_allowed": False,
    }
    assert len(doc["cases"]) == 6


def test_d1_manifest_points_only_to_real_test_files_and_unique_nodes() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    nodes: list[str] = []
    for case in doc["cases"]:
        for node in case["pytest_nodes"]:
            rel = node.split("::", 1)[0]
            assert (ROOT / rel).is_file(), node
            nodes.append(node)
    assert len(nodes) == len(set(nodes))
