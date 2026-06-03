from __future__ import annotations

import json
from pathlib import Path

import pytest


def _module():
    return pytest.importorskip("runner.packet07_golden_diagnostic")


def test_prepare_mode_writes_four_arm_plan_with_screening_default(tmp_path, monkeypatch):
    mod = _module()
    monkeypatch.setattr(mod, "_preflight", lambda specs: {"mission_id": mod.MISSION_ID, "checks": {}})

    result = mod.launch_packet07_golden_diagnostic(output_dir=tmp_path, execute=False)

    assert result["status"] == "prepared"
    run_spec = json.loads(Path(result["run_spec_path"]).read_text(encoding="utf-8"))
    arm_ids = [row["arm_id"] for row in run_spec["arms"]]
    assert arm_ids == [
        "current_conditions",
        "extended_budget_only",
        "extended_budget_orientation",
        "extended_budget_orientation_python3",
    ]
    assert run_spec["model_tier_selector"] == "screening_default"
    assert {int(row["max_steps"]) for row in run_spec["arms"]} == {4, 12}


def test_orientation_env_sets_cwd_data_root_safe_listing_and_python_contract(tmp_path):
    mod = _module()
    workspace = tmp_path / "workspace"
    data_root = workspace / "letta" / "filesystem"
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "people.txt").write_text("a\n", encoding="utf-8")
    (data_root / "pets.txt").write_text("b\n", encoding="utf-8")

    env = mod._orientation_env(
        workspace,
        {"inject_orientation": True, "python_contract": True},
    )

    assert env is not None
    assert env["cwd"] == str(workspace)
    assert env["data_root"] == str(data_root)
    assert env["safe_file_listing"] == ["people.txt", "pets.txt"]
    assert env["python_binary"] == "python3"
    assert env["environment_flags"]["orientation_injected"] is True
    assert env["environment_flags"]["python_contract_explicit"] is True


def test_run_one_records_required_diagnostic_fields(tmp_path, monkeypatch):
    mod = _module()
    captured: dict[str, object] = {}

    def fake_seed(workspace: Path, spec: dict[str, object]) -> None:
        data_root = workspace / "letta" / "filesystem"
        data_root.mkdir(parents=True, exist_ok=True)
        (data_root / "people.txt").write_text("pers-0099 George Peterson\n", encoding="utf-8")

    def fake_run_reference_baseline(**kwargs):  # type: ignore[no-untyped-def]
        captured["orientation_env_overrides"] = kwargs.get("orientation_env_overrides")
        return {
            "execution": {
                "last_completion": {"text": "George Peterson"},
                "step_count": 3,
            },
            "run_events": [
                {
                    "event_type": "raw_bash_result",
                    "payload": {"details": {"command": "python3 -V", "exit_code": 0}},
                }
            ],
        }

    monkeypatch.setattr(mod, "_seed_workspace", fake_seed)
    monkeypatch.setattr(mod, "run_reference_baseline", fake_run_reference_baseline)
    monkeypatch.setattr(mod, "_build_route_manifest", lambda variant, arm: {"variant_id": variant})
    monkeypatch.setattr(
        mod,
        "resolve_packet07_context_model_route",
        lambda model_tier_selector: {"request_settings": {"pricing_model_id": "gpt-5.4-mini"}},
    )
    monkeypatch.setattr(mod, "_grade_spec", lambda spec, result, workspace: {"verdict": "pass", "reason_codes": []})
    monkeypatch.setattr(mod, "_usage", lambda result: {"total_tokens": 9, "usd_estimate": 0.01})

    spec = {
        "eval_id": "letta_filesystem_001_easy",
        "task_id": "filesystem_code_001",
        "task_prompt": "prompt",
        "benchmark_class": "letta_context_bench",
        "max_steps": 12,
        "timeout_sec": 120,
        "arm": {
            "arm_id": "extended_budget_orientation_python3",
            "inject_orientation": True,
            "python_contract": True,
        },
        "environment_flags": {
            "orientation_injected": True,
            "python_contract_explicit": True,
            "max_steps": 12,
        },
    }

    record, trace = mod._run_one(tmp_path, spec, mod.BACKBONE_INCUMBENT, model_tier_selector="screening_default")

    for key in (
        "final_answer",
        "exact_grade",
        "step_count",
        "tool_commands",
        "exit_codes",
        "trace_path",
        "model_id",
        "variant_id",
        "max_steps",
        "environment_flags",
        "root_cause_classification",
    ):
        assert key in record
    assert trace["trace_path"] == record["trace_path"]
    assert record["model_id"] == "gpt-5.4-mini"
    assert record["tool_commands"] == ["python3 -V"]
    assert record["exit_codes"] == [0]

    orientation_env = captured["orientation_env_overrides"]
    assert isinstance(orientation_env, dict)
    assert orientation_env["python_binary"] == "python3"
    assert orientation_env["safe_file_listing"] == ["people.txt"]
    assert orientation_env["data_root"].endswith("/workspace/letta/filesystem")


def test_env_snapshot_orientation_renders_environment_fields():
    mod = pytest.importorskip("blocks.orientation.env_snapshot")
    oriented = mod.orient(
        "Solve the task.",
        env_info={
            "cwd": "/tmp/work",
            "data_root": "/tmp/work/letta/filesystem",
            "safe_file_listing": ["people.txt"],
            "python_binary": "python3",
            "environment_flags": {"orientation_injected": True},
        },
    )

    content = oriented["messages"][0]["content"]
    assert "Workspace cwd: /tmp/work" in content
    assert "Data root: /tmp/work/letta/filesystem" in content
    assert "Safe file listing:" in content
    assert "- people.txt" in content
    assert "Use `python3` for Python commands in this environment." in content
