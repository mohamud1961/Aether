from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


def _load_context_module():
    module_name = "_worker_h1_context"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    module_path = Path(__file__).resolve().parents[1] / "runner" / "aether2" / "context.py"
    spec = spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ContextManager = _load_context_module().ContextManager


def test_prefix_bytes_stay_identical_across_appends() -> None:
    context = ContextManager()
    prefix = context.build_prefix(
        system_prompt="system",
        task_instruction="do the thing",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[{"function": {"name": "run_command"}}],
    )

    context.append_turn({"role": "assistant", "content": "plan"})
    context.append_turn({"role": "tool", "content": "ok", "name": "run_command"})
    context.assert_prefix_unchanged()

    assert prefix.frozen_bytes == context.prefix.frozen_bytes


def test_tail_only_rerenders_on_change() -> None:
    context = ContextManager()
    context.build_prefix(
        system_prompt="system",
        task_instruction="task",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[],
    )

    first = context.render_tail({"plan": "inspect", "streak": 0})
    second = context.render_tail({"plan": "inspect", "streak": 0})
    third = context.render_tail({"plan": "edit", "streak": 1})

    assert first == second
    assert third != second


def test_tail_render_is_stable_for_semantically_equal_payloads() -> None:
    context = ContextManager()
    context.build_prefix(
        system_prompt="system",
        task_instruction="task",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[],
    )

    first = context.render_tail({"plan": "inspect", "streak": 0, "fuel": {"elapsed": 1, "remaining": 2}})
    second = context.render_tail({"fuel": {"remaining": 2, "elapsed": 1}, "streak": 0, "plan": "inspect"})

    assert first == second


def test_prefix_token_estimate_stays_under_8k_for_synthetic_start_state() -> None:
    context = ContextManager()
    prefix = context.build_prefix(
        system_prompt="system " * 400,
        task_instruction="task " * 1200,
        orientation={"cwd": "/tmp/work", "listing": ["a", "b", "c"]},
        tool_schemas=[{"function": {"name": f"tool_{idx}"}} for idx in range(10)],
    )

    assert prefix.token_estimate <= 8000


def test_message_history_preserves_assistant_tool_calls() -> None:
    context = ContextManager()
    context.build_prefix(
        system_prompt="system",
        task_instruction="task",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[],
    )

    context.append_turn(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call-1", "name": "run_command", "arguments": "{\"cmd\":\"pwd\"}"}],
        }
    )

    history = context.message_history()
    assert history[-1]["tool_calls"][0]["name"] == "run_command"
    assert history[-1]["tool_calls"][0]["arguments"] == "{\"cmd\":\"pwd\"}"


def test_completion_contract_block_can_be_rendered_without_mutating_prefix() -> None:
    context = ContextManager()
    prefix = context.build_prefix(
        system_prompt="system",
        task_instruction="task contract",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[],
    )

    tail = context.render_tail(
        {"plan": "inspect", "derived_state": {"no_delta_streak": 0}},
        completion_contract={
            "unresolved_requirements": ["verify output file"],
            "next_required_evidence": ["run semantic check"],
        },
    )

    assert prefix.frozen_bytes == context.prefix.frozen_bytes
    assert "\"completion_contract\"" in tail
    assert context.current_completion_contract() == {
        "next_required_evidence": ["run semantic check"],
        "unresolved_requirements": ["verify output file"],
    }
    context.assert_prefix_unchanged()


def test_completion_contract_tail_render_is_stable_for_semantically_equal_payloads() -> None:
    context = ContextManager()
    context.build_prefix(
        system_prompt="system",
        task_instruction="task",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[],
    )

    first = context.render_tail(
        {"plan": "inspect", "fuel_gauge": {"elapsed_sec": 1.0}},
        completion_contract={"next_required_evidence": ["check hash"], "unresolved_requirements": ["artifact"]},
    )
    second = context.render_tail(
        {"fuel_gauge": {"elapsed_sec": 1.0}, "plan": "inspect"},
        completion_contract={"unresolved_requirements": ["artifact"], "next_required_evidence": ["check hash"]},
    )

    assert first == second
    assert context.current_tail_payload()["completion_contract"]["unresolved_requirements"] == ["artifact"]


def test_immutable_top_contract_exposes_verbatim_task_instruction() -> None:
    context = ContextManager()
    context.build_prefix(
        system_prompt="system",
        task_instruction="complete every stated requirement",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[],
    )

    assert context.immutable_top_contract() == {
        "task_instruction": "complete every stated requirement"
    }
