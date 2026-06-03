from __future__ import annotations

from blocks.orientation.packet07_hard_row_doctrine import orient


def test_direct_answer_scalar_prompt_includes_hard_row_doctrine():
    result = orient(
        "Using the workspace files, compute the final count and respond with only the final numeric value.",
        env_info={"cwd": "/tmp/work", "task_id": "demo_direct_answer"},
    )
    system_text = result["messages"][0]["content"]
    assert "Packet 07 hard-row doctrine" in system_text
    assert "Reduction discipline:" in system_text
    assert "Focused recount:" in system_text


def test_non_direct_answer_tool_calling_prompt_excludes_hard_row_doctrine():
    result = orient(
        "Use tools to inspect the API schema and produce a brief plan, then call the right tool with arguments.",
        env_info={"cwd": "/tmp/work", "task_id": "demo_tool_calling"},
    )
    system_text = result["messages"][0]["content"]
    assert "Packet 07 hard-row doctrine" not in system_text
    assert "Reduction discipline:" not in system_text
    assert "General orientation:" in system_text
