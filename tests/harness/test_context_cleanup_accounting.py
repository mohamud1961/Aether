from __future__ import annotations

from aether.context_cleanup import apply_context_cleanup, measure_messages


def test_context_accounting_attributes_exact_sections_without_mutation() -> None:
    messages = [
        {"role": "system", "content": "[raw_user_task]\nDo the task."},
        {"role": "system", "content": "[tool_semantics]\nUse tools."},
        {"role": "system", "content": "[context_packet]\n{\"generation\":3}"},
    ]
    output, accounting = apply_context_cleanup(messages, mode="off")
    assert output == messages
    assert accounting["removed"] == []
    assert accounting["before"] == accounting["after"]
    assert [row["section"] for row in accounting["before"]["sections"]] == [
        "raw_user_task", "tool_semantics", "context_packet"
    ]
    assert accounting["before"]["bytes"] == measure_messages(messages)["bytes"]


def test_conservative_cleanup_removes_only_later_exact_duplicate_message() -> None:
    messages = [
        {"role": "system", "content": "[tool_semantics]\nUse tools."},
        {"role": "system", "content": "[tool_semantics]\nUse tools."},
        {"role": "system", "content": "[current_state]\nA contradiction remains."},
    ]
    output, accounting = apply_context_cleanup(messages, mode="conservative_v1")
    assert output == [messages[0], messages[2]]
    assert accounting["saved_bytes"] > 0
    assert accounting["removed"][0]["section"] == "tool_semantics"
    assert accounting["semantic_summarization_used"] is False
    assert accounting["native_history_changed"] is False


def test_conservative_cleanup_never_removes_raw_task_or_context_packet_duplicates() -> None:
    raw = {"role": "system", "content": "[raw_user_task]\nTask"}
    context = {"role": "system", "content": "[context_packet]\n{}"}
    output, accounting = apply_context_cleanup(
        [raw, raw, context, context], mode="conservative_v1"
    )
    assert output == [raw, raw, context, context]
    assert accounting["removed"] == []
    assert accounting["raw_task_authority_protected"] is True


def test_harbor_cleanup_selector_defaults_off_and_fails_closed(monkeypatch) -> None:
    from aether import harbor_runtime as hr
    monkeypatch.delenv(hr.CONTEXT_CLEANUP_ENV, raising=False)
    assert hr.selected_context_cleanup_mode(hr.build_selected_frontier_models) == "off"
    monkeypatch.setenv(hr.CONTEXT_CLEANUP_ENV, "conservative_v1")
    assert hr.selected_context_cleanup_mode(hr.build_selected_frontier_models) == "conservative_v1"
    monkeypatch.setenv(hr.CONTEXT_CLEANUP_ENV, "semantic-magic")
    import pytest
    with pytest.raises(RuntimeError, match=hr.CONTEXT_CLEANUP_ENV):
        hr.selected_context_cleanup_mode(hr.build_selected_frontier_models)


def test_runtime_identity_binds_explicit_cleanup_arm(monkeypatch) -> None:
    from aether import harbor_runtime as hr
    class Env:
        task_metadata = {}
        def digest(self): return "env-digest"
    class Context:
        metadata = {}
        context_id = "ctx"
    monkeypatch.setenv(hr.CONTEXT_CLEANUP_ENV, "conservative_v1")
    identity = hr._runtime_identity(Context(), Env(), model_factory=hr.build_selected_frontier_models)
    assert identity["research_context_cleanup"] == "conservative_v1"
    assert identity["research_context_cleanup_authority"] == hr.CONTEXT_CLEANUP_ENV
