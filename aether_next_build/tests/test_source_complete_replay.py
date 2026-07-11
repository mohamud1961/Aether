from __future__ import annotations

import json
from pathlib import Path

from replay_engine.source_complete import build_source_complete_manifest


ROOT = Path(__file__).resolve().parents[2]
PACK = Path("/private/tmp/aether_v61/AETHER_NEXT_SOURCE_COMPLETE_HANDOFF_V6_1_20260711")


def test_source_complete_builder_reproduces_supplied_v61_manifest() -> None:
    if not PACK.exists():
        raise AssertionError("V6.1 pack must be extracted for this provenance test")
    manifest = build_source_complete_manifest(
        (Path("/Users/mohamud/Downloads/Archive.zip"), Path("/Users/mohamud/Downloads/2Archive.zip")),
        PACK / "replay_engine/historical_replay_expectations.json",
    )
    supplied = json.loads((PACK / "replay_engine/generated/historical_replay_manifest.json").read_text())
    assert manifest["manifest_sha256"] == supplied["manifest_sha256"]
    assert manifest["mode_counts"] == {"architect_only": 8, "solver_checkpoint": 6, "verifier_packet": 9}


def test_source_complete_role_inputs_are_evaluator_separated() -> None:
    manifest = build_source_complete_manifest(
        (Path("/Users/mohamud/Downloads/Archive.zip"), Path("/Users/mohamud/Downloads/2Archive.zip")),
        PACK / "replay_engine/historical_replay_expectations.json",
    )
    for case in manifest["cases"]:
        encoded = json.dumps(case["role_input"], sort_keys=True)
        assert "historical_reward" not in encoded
        assert "historical_parsed_result" not in encoded
        assert '"future_steps"' not in encoded
