from __future__ import annotations
from types import SimpleNamespace
import json
import pytest

from aether.model_parse import parse_solver_turn
from aether.providers.azure_model import AzureProviderOutputError, canonicalize_pcr_native_tool_output


def _response(call):
    return SimpleNamespace(id="resp-c", status="completed", output=[call])


def _computer(action=None, *, actions=None, checks=()):
    return SimpleNamespace(
        id="cu-1", call_id="call-c", type="computer_call", status="completed",
        action=action, actions=actions, pending_safety_checks=checks,
    )


def test_native_computer_click_becomes_one_canonical_kernel_action() -> None:
    call = _computer(SimpleNamespace(type="click", button="left", x=120, y=80, keys=None))
    canonical, receipt = canonicalize_pcr_native_tool_output(_response(call))
    turn = parse_solver_turn(canonical)
    [action] = turn.actions
    assert action.kind == "computer_action"
    assert action.capability_id == "computer_control"
    assert action.arguments == {"actions": [{"type": "click", "button": "left", "x": 120, "y": 80}]}
    assert receipt["native_tool_type"] == "computer_call"
    assert receipt["native_tool_call_id"] == "call-c"


def test_native_computer_screenshot_is_a_real_action() -> None:
    canonical, _ = canonicalize_pcr_native_tool_output(
        _response(_computer(SimpleNamespace(type="screenshot")))
    )
    [action] = parse_solver_turn(canonical).actions
    assert action.arguments == {"actions": [{"type": "screenshot"}]}


def test_native_computer_multi_action_batch_is_preserved_in_order() -> None:
    canonical, receipt = canonicalize_pcr_native_tool_output(_response(_computer(
        None,
        actions=[SimpleNamespace(type="click", button="left", x=1, y=2, keys=None), SimpleNamespace(type="type", text="x")],
    )))
    [action] = parse_solver_turn(canonical).actions
    assert action.arguments == {"actions": [
        {"type": "click", "button": "left", "x": 1, "y": 2},
        {"type": "type", "text": "x"},
    ]}
    assert receipt["provider_computer_action_count"] == 2
    assert receipt["provider_computer_action_types"] == ["click", "type"]


def test_native_computer_safety_check_is_never_silently_acknowledged() -> None:
    check = SimpleNamespace(id="s1", code="confirm_external_action", message="confirm")
    with pytest.raises(AzureProviderOutputError) as exc:
        canonicalize_pcr_native_tool_output(_response(_computer(SimpleNamespace(type="wait"), checks=[check])))
    assert exc.value.code == "provider_pcr_v0_computer_safety_check_pending"


def test_function_and_computer_call_mixture_is_rejected() -> None:
    function = SimpleNamespace(id="fc", call_id="fcall", type="function_call", name="read_file", arguments=json.dumps({"arguments":{"path":"/app/a"}}))
    computer = _computer(SimpleNamespace(type="wait"))
    response = SimpleNamespace(id="resp", status="completed", output=[function, computer])
    with pytest.raises(AzureProviderOutputError) as exc:
        canonicalize_pcr_native_tool_output(response)
    assert exc.value.code == "provider_pcr_v0_native_tool_mixed_output"
