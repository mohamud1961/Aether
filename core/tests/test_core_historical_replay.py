"""High-level safety regression for deterministic Core-loop action/result playback."""

import importlib.util
from pathlib import Path


def _replay_module():
    source = Path(__file__).resolve().parents[1] / "qa" / "replay_corpus.py"
    spec = importlib.util.spec_from_file_location("aether_core_replay_corpus", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_core_loop_replays_only_exact_action_without_starting_host_process(monkeypatch):
    replay = _replay_module()

    def forbidden_process(*_args, **_kwargs):
        raise AssertionError("scripted replay attempted to start a host process")

    monkeypatch.setattr(replay.asyncio, "create_subprocess_shell", forbidden_process)
    monkeypatch.setattr(replay.asyncio, "create_subprocess_exec", forbidden_process)
    result = replay._t2_scripted_action_playback(
        "synthetic harmless action",
        "captured observation fixture\\n",
        "SYNTHETIC/RECREATED",
    )

    assert result["status"] == "PASS", result
    assert result["evidence"]["playback_hits"] == 1
    assert result["evidence"]["blocked_actions"] == 1
    checks = {item["check"]: item["ok"] for item in result["checks"]}
    assert checks["captured_observation_delivered_exactly"]
    assert checks["transformed_action_blocked"]
    assert checks["no_environment_process_execution"]


def test_missing_required_evidence_cannot_produce_a_green_replay_gate():
    import copy
    import json
    replay = _replay_module()
    artifact = Path(__file__).resolve().parents[2] / "research/core_consolidation_20261025/c1/replay_results_safe_boundary.json"
    baseline = json.loads(artifact.read_text())
    assert replay._verdict(baseline)["ok"]
    for section, missing in (
        ("t2", {"counts": {"pass": 0, "fail": 0, "unavailable": 1}, "controls": []}),
        ("negative_controls", {"counts": {"expected_fail": 0, "detected": 0}, "controls": []}),
        ("t1", {"counts": {"pass": 0, "fail": 0, "rows_checked": 0, "rows_expected": 955, "unavailable": 955}}),
    ):
        changed = copy.deepcopy(baseline)
        changed[section] = missing
        assert not replay._verdict(changed)["ok"], section
