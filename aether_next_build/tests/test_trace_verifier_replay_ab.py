from __future__ import annotations

import json

from run_trace_verifier_replay_ab import run


def test_trace_verifier_replay_ab_fake_writes_variant_artifacts(tmp_path) -> None:
    summary = run(mode="fake", out_dir=tmp_path)

    assert summary["counts"]["cases"] == 3
    assert summary["counts"]["ok"] == 3
    assert summary["counts"]["architect_prompt_improved"] == 3
    for row in summary["rows"]:
        task = row["task"]
        for variant in ("generic", "architect_prompt"):
            variant_dir = tmp_path / task / variant
            assert (variant_dir / "verifier_packet.json").exists()
            assert (variant_dir / "raw_output.json").exists()
            assert (variant_dir / "parsed_result.json").exists()
            assert (variant_dir / "active_findings_after.json").exists()
            assert (variant_dir / "judgement.json").exists()
        architect_packet = json.loads((tmp_path / task / "architect_prompt" / "verifier_packet.json").read_text())
        assert architect_packet["architect_verifier_prompt"]["rendered"]

