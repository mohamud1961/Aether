from __future__ import annotations

import json

from aether.atif_export import build_atif_trajectory
from aether.model_hooks import ModelHooks


def _pcr_act(command: str = "printf hello") -> str:
    return json.dumps({
        "kind": "act",
        "action": {
            "kind": "run_command",
            "arguments": {"command": command},
        },
    })


def test_model_hooks_capture_visible_provider_exchange_without_changing_call() -> None:
    output = _pcr_act()
    model = lambda messages, max_output_tokens=8000: output
    hooks = ModelHooks(model, model, run_id="run-1", task_id="task-1")
    result = hooks._call_text_model(
        model,
        [{"role": "user", "content": "do it"}],
        max_output_tokens=100,
        model_role="solver",
        stable_prefix_count=0,
    )
    assert result == output
    exchanges = hooks.drain_model_exchange_captures()
    assert len(exchanges) == 1
    row = exchanges[0]
    assert row["provider_call_succeeded"] is True
    assert row["output"] == output
    assert row["input_messages"] == [{"role": "user", "content": "do it"}]
    assert len(row["output_sha256"]) == 64


def test_atif_projection_pairs_solver_action_with_exact_aether_receipt_handle() -> None:
    output = _pcr_act()
    # PCR action id is content-derived; obtain it through the same production parser.
    from aether.model_parse import parse_solver_turn
    action = parse_solver_turn(output).actions[0]
    run_record = {
        "runtime_identity": {"run_id": "run-42", "raw_task_sha256": "abc"},
        "model_exchange_records": [{
            "model_role": "solver",
            "role_call_ordinal": 1,
            "provider_call_succeeded": True,
            "input_transcript_sha256": "insha",
            "output": output,
            "output_sha256": "outsha",
        }],
        "receipt_records": [{
            "receipt_id": f"step-1:{action.action_id}:cmd",
            "step": 1,
            "kind": "run_command",
            "success": True,
            "summary": "command exit=0",
            "state_change": False,
            "failure_class": "",
            "payload": {
                "command": "printf hello",
                "exit_code": 0,
                "stdout": "hello",
                "stderr": "",
                "stdout_full": "hello",
                "stderr_full": "",
                "stdout_handle": "1:abc:stdout",
                "stderr_handle": "1:abc:stderr",
                "stdout_bytes": 5,
                "stderr_bytes": 0,
            },
        }],
        "model_call_telemetry": [{
            "input_tokens": 100,
            "cached_input_tokens": 40,
            "output_tokens": 20,
            "cost_usd": 0.01,
        }],
    }
    trajectory = build_atif_trajectory(
        instruction="Say hello through the shell",
        run_record=run_record,
        model_name="gpt-5.6-luna",
    )
    assert trajectory["schema_version"] == "ATIF-v1.7"
    assert trajectory["steps"][0]["source"] == "user"
    agent = trajectory["steps"][1]
    assert agent["source"] == "agent"
    assert agent["tool_calls"][0]["function_name"] == "run_command"
    obs = agent["observation"]["results"][0]
    assert "hello" in obs["content"]
    assert obs["extra"]["stdout_handle"] == "1:abc:stdout"
    assert "stdout_full" not in json.dumps(trajectory)
    assert trajectory["final_metrics"] == {
        "total_prompt_tokens": 100,
        "total_completion_tokens": 20,
        "total_cached_tokens": 40,
        "total_cost_usd": 0.01,
        "total_steps": 2,
    }


def test_verifier_is_embedded_as_independent_subagent_not_solver_message() -> None:
    run_record = {
        "runtime_identity": {"run_id": "run-v"},
        "model_exchange_records": [{
            "model_role": "verifier",
            "role_call_ordinal": 1,
            "provider_call_succeeded": True,
            "input_transcript_sha256": "verifier-in",
            "input_messages": [
                {"role": "system", "content": "independent verifier"},
                {"role": "user", "content": "check exact evidence"},
            ],
            "output": '{"verdict":"completed"}',
            "output_sha256": "verifier-out",
        }],
        "receipt_records": [],
        "model_call_telemetry": [],
    }
    trajectory = build_atif_trajectory(instruction="task", run_record=run_record)
    assert len(trajectory["subagent_trajectories"]) == 1
    verifier = trajectory["subagent_trajectories"][0]
    assert verifier["agent"]["name"] == "aether-next-verifier"
    assert verifier["steps"][0]["message"] == "check exact evidence"
    parent_messages = [step["message"] for step in trajectory["steps"]]
    assert '{"verdict":"completed"}' not in parent_messages
    ref = trajectory["steps"][-1]["observation"]["results"][0]["subagent_trajectory_ref"][0]
    assert ref["trajectory_id"] == verifier["trajectory_id"]
