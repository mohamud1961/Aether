from __future__ import annotations

from types import SimpleNamespace

from aether.verify_inspection_requests import _verifier_identity_prompt_for


def _compiled(*, with_method_constraints: bool) -> SimpleNamespace:
    methods = (SimpleNamespace(constraint_id="method:required"),) if with_method_constraints else ()
    return SimpleNamespace(
        verifier_identity_prompt="Task-specific verifier prompt.",
        task_contract=SimpleNamespace(method_constraints=methods),
    )


def test_verifier_prompt_omits_action_history_without_method_constraints() -> None:
    rendered = _verifier_identity_prompt_for(_compiled(with_method_constraints=False))
    tool_list = rendered.split("Available inspection kinds include ", 1)[1].split(". ", 1)[0]
    assert "inspect_action_receipts" not in tool_list
    assert "overlay_run_command" in tool_list


def test_verifier_prompt_retains_action_history_for_real_method_constraints() -> None:
    rendered = _verifier_identity_prompt_for(_compiled(with_method_constraints=True))
    tool_list = rendered.split("Available inspection kinds include ", 1)[1].split(". ", 1)[0]
    assert "inspect_action_receipts" in tool_list
    assert "exact method clause_ids" in rendered
