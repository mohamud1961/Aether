from pathlib import Path

import runner.terminalbench_failure_probe as probe


def test_run_variant_uses_real_task_docker_sandbox(monkeypatch, tmp_path):
    called = {}

    def fake_run_reference_baseline(**kwargs):  # type: ignore[no-untyped-def]
        called.update(kwargs)
        return {
            "run_header": {"model_route": {"provider_route": "openai_api"}},
            "execution": {"steps": [], "status": "completed"},
            "run_events": [],
        }

    monkeypatch.setattr(probe, "run_reference_baseline", fake_run_reference_baseline)
    monkeypatch.setattr(
        probe,
        "_run_official_verifier",
        lambda workspace, run_dir: {
            "status": "fail",
            "reward": "0",
            "invalid_infrastructure_failure": False,
        },
    )
    monkeypatch.setattr(probe, "_patch_score", lambda *args, **kwargs: None)
    monkeypatch.setattr(probe, "_trace_row", lambda *args, **kwargs: {"trace": "ok"})
    monkeypatch.setattr(
        probe,
        "_usage",
        lambda result: {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "usd": 0.0,
            "usd_estimate": 0.0,
        },
    )

    record, trace = probe._run_variant(tmp_path, probe.CONTROL, 1)

    workspace = Path(called["cwd"])
    assert called["sandbox_type"] == "docker"
    assert called["sandbox_image"] == probe.DOCKER_IMAGE
    assert called["timeout_sec"] == probe.AGENT_TIMEOUT_SEC
    assert called["max_steps"] == probe.TASK_STEP_BUDGET
    assert called["orientation_env_overrides"] == {"step_budget_hint": probe.TASK_STEP_BUDGET}
    assert "Official task instruction:" in called["task_prompt"]
    assert "task_evidence_summary.md" not in called["task_prompt"]
    assert (workspace / "instruction.md").exists()
    assert not (workspace / "task_evidence_summary.md").exists()
    assert record["failure_mode"]["primary"] == "false completion / unsupported completion claim"
    assert trace == {"trace": "ok"}
