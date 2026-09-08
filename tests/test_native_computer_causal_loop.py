from __future__ import annotations
import base64
import hashlib
import json
from types import SimpleNamespace

import pytest

from aether.execution import ComputerActionResult, MemoryExecutor
from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger
from aether.providers.azure_model import AzureModelCallable, AzureModelError
from aether.runtime_ir import ActionRequest, EnvMap


def _computer_response(n: int, action: object):
    call = SimpleNamespace(
        id=f"cu-{n}", call_id=f"ccall-{n}", type="computer_call", status="completed",
        action=action, actions=None, pending_safety_checks=[],
    )
    return SimpleNamespace(id=f"resp-{n}", status="completed", output=[call], usage=None, reasoning=None, error=None, incomplete_details=None)


def _computer_batch_response(n: int, actions: list[object]):
    call = SimpleNamespace(
        id=f"cu-{n}", call_id=f"ccall-{n}", type="computer_call", status="completed",
        action=None, actions=actions, pending_safety_checks=[],
    )
    return SimpleNamespace(id=f"resp-{n}", status="completed", output=[call], usage=None, reasoning=None, error=None, incomplete_details=None)


def _function_response(n: int):
    call = SimpleNamespace(
        id=f"fc-{n}", call_id=f"fcall-{n}", type="function_call", status="completed",
        name="read_file", arguments=json.dumps({"arguments":{"path":"/app/a"}}),
    )
    return SimpleNamespace(id=f"resp-{n}", status="completed", output=[call], usage=None, reasoning=None, error=None, incomplete_details=None)


class _Responses:
    def __init__(self, rows):
        self.rows=list(rows); self.requests=[]
    def create(self, **kwargs):
        self.requests.append(dict(kwargs)); return self.rows.pop(0)
    def retrieve(self, _id): raise AssertionError("completed fake must not poll")
    def cancel(self, _id): raise AssertionError("completed fake must not cancel")
class _Client:
    def __init__(self, rows): self.responses=_Responses(rows)


def _model(rows):
    client=_Client(rows)
    model=AzureModelCallable(
        client=client, deployment="unit-test-luna", effort="low", role="solver",
        responses_background=False, poll_interval_s=1, poll_timeout_s=30,
        max_retries=0, prompt_cache_mode="off",
    )
    return model,client


def test_computer_tool_is_advertised_only_for_admitted_runtime_scope() -> None:
    model, client = _model([_function_response(1)])
    model.call_with_telemetry_scope([{"role":"user","content":"x"}], run_id="r", task_id="t")
    assert all(tool.get("type") != "computer" for tool in client.responses.requests[0]["tools"])

    model2, client2 = _model([_computer_response(1, SimpleNamespace(type="screenshot"))])
    model2.set_computer_use_available(True, run_id="r", task_id="t")
    model2.call_with_telemetry_scope([{"role":"user","content":"x"}], run_id="r", task_id="t")
    assert sum(tool.get("type") == "computer" for tool in client2.responses.requests[0]["tools"]) == 1


def test_computer_call_requires_fresh_screenshot_before_next_luna_decision() -> None:
    model, client = _model([
        _computer_response(1, SimpleNamespace(type="click", button="left", x=5, y=7, keys=None)),
        _function_response(2),
    ])
    model.set_computer_use_available(True, run_id="r", task_id="t")
    model.call_with_telemetry_scope([{"role":"user","content":"first"}], run_id="r", task_id="t")
    model.commit_pending_response(run_id="r", task_id="t")
    with pytest.raises(AzureModelError, match="computer_observation_required"):
        model.call_with_telemetry_scope([{"role":"user","content":"second"}], run_id="r", task_id="t")
    assert len(client.responses.requests) == 1


def test_fresh_screenshot_is_returned_as_computer_call_output_bound_to_call_id() -> None:
    raw=b"\x89PNG\r\n\x1a\npost-action-pixels"
    digest=hashlib.sha256(raw).hexdigest()
    model, client = _model([
        _computer_response(1, SimpleNamespace(type="click", button="left", x=5, y=7, keys=None)),
        _function_response(2),
    ])
    model.set_computer_use_available(True, run_id="r", task_id="t")
    model.call_with_telemetry_scope([{"role":"user","content":"first"}], run_id="r", task_id="t")
    model.commit_pending_response(run_id="r", task_id="t")
    assert model.stage_computer_observation(
        screenshot_bytes=raw, media_type="image/png", screenshot_sha256=digest,
        source_receipt_id="step-1:computer", action={"type":"click","x":5,"y":7,"button":"left"},
        run_id="r", task_id="t",
    )
    model.call_with_telemetry_scope([{"role":"user","content":"second-boundary"}], run_id="r", task_id="t")
    request=client.responses.requests[1]
    assert request["previous_response_id"] == "resp-1"
    output=request["input"][0]
    assert output["type"] == "computer_call_output"
    assert output["call_id"] == "ccall-1"
    shot=output["output"]
    assert shot["type"] == "computer_screenshot"
    assert shot["detail"] == "original"
    prefix="data:image/png;base64,"
    assert shot["image_url"].startswith(prefix)
    assert base64.b64decode(shot["image_url"][len(prefix):]) == raw
    assert request["input"][1] == {"role":"user","content":"second-boundary"}


def test_kernel_computer_action_stages_exact_post_action_pixels() -> None:
    raw=b"png-pixels-after-click"
    executor=MemoryExecutor(workspace_root="/app")
    executor.register_computer(lambda _ex, action: ComputerActionResult(
        action=action, success=True, screenshot_bytes=raw, media_type="image/png",
        width=800, height=600, detail="fake desktop",
    ))
    staged=[]
    hooks=SimpleNamespace(stage_primary_computer_observation=lambda **kwargs: staged.append(kwargs) or True)
    kernel=SimpleNamespace(active_hooks=hooks)
    action=ActionRequest(
        action_id="c1", kind="computer_action", capability_id="computer_control",
        arguments={"actions":[{"type":"click","button":"left","x":10,"y":11}]},
        intent="", expected_observation="", if_fail_next="",
    )
    [receipt]=dispatch_action(
        kernel, action, 1, SimpleNamespace(), executor,
        EnvMap(task_prompt="", workspace_root="/app"), ExecutionLedger(),
    )
    assert receipt.success is True
    assert receipt.state_change is True
    assert receipt.payload["screenshot_sha256"] == hashlib.sha256(raw).hexdigest()
    assert staged and staged[0]["screenshot_bytes"] == raw
    assert staged[0]["action"]["actions"][0]["type"] == "click"


def test_kernel_refuses_computer_action_without_truthful_backend() -> None:
    executor=MemoryExecutor(workspace_root="/app")
    action=ActionRequest(
        action_id="c1", kind="computer_action", capability_id="computer_control",
        arguments={"actions":[{"type":"screenshot"}]}, intent="", expected_observation="", if_fail_next="",
    )
    [receipt]=dispatch_action(SimpleNamespace(active_hooks=SimpleNamespace()), action, 1, SimpleNamespace(), executor, EnvMap(task_prompt="",workspace_root="/app"), ExecutionLedger())
    assert receipt.success is False
    assert receipt.failure_class == "missing_capability"


def test_xdotool_backend_commands_preserve_action_parameters() -> None:
    from aether.harbor_executor import _xdotool_action_command
    click=_xdotool_action_command({"type":"click","button":"right","x":12,"y":34})
    arrow=_xdotool_action_command({"type":"keypress","keys":["ARROWLEFT"]})
    assert "left" in arrow.lower() and "arrowleft" not in arrow.lower()
    assert "mousemove --sync 12 34" in click and "click --repeat 1" in click and click.rstrip().endswith("3")
    typed=_xdotool_action_command({"type":"type","text":"hello world"})
    assert "xdotool type" in typed and "hello world" in typed
    scroll=_xdotool_action_command({"type":"scroll","x":1,"y":2,"scroll_x":-250,"scroll_y":350})
    assert "--repeat 4" in scroll and " 5" in scroll and "--repeat 3" in scroll and " 6" in scroll
    drag=_xdotool_action_command({"type":"drag","path":[{"x":1,"y":2},{"x":20,"y":30}]})
    assert "mousedown 1" in drag and "mousemove --sync 20 30" in drag and "mouseup 1" in drag


def test_pyautogui_backend_script_always_ends_in_fresh_screenshot() -> None:
    from aether.harbor_executor import _pyautogui_action_script
    script=_pyautogui_action_script({"actions":[{"type":"keypress","keys":["CTRL","A"]}]}, "/tmp/shot.png")
    assert "p.hotkey(*keys)" in script
    assert "p.screenshot().save('/tmp/shot.png')" in script


def test_full_kernel_modelhooks_loop_binds_post_action_screenshot_before_second_solver_turn() -> None:
    from aether.kernel import AetherNextKernel
    from aether.model_hooks import ModelHooks
    from aether.runtime_ir import CapabilityDescriptor

    raw=b"\x89PNG\r\n\x1a\nfull-loop-post-click"
    model, client = _model([
        _computer_batch_response(1, [
            SimpleNamespace(type="click", button="left", x=40, y=50, keys=None),
            SimpleNamespace(type="type", text="hello"),
        ]),
        _function_response(2),
    ])
    hooks=ModelHooks(model, lambda *_args, **_kwargs: "{}", run_id="full-r", task_id="full-t")
    executor=MemoryExecutor(workspace_root="/app", files={"a":"ok"})
    executor.register_computer(lambda _ex, action: ComputerActionResult(
        action=action, success=True, screenshot_bytes=raw, media_type="image/png", width=100, height=80,
    ))
    env=EnvMap(
        task_prompt="Use the visible computer then inspect the file.", workspace_root="/app",
        capabilities={
            "computer_control": CapabilityDescriptor("computer_control","gui",tool_names=("computer_action",)),
            "filesystem": CapabilityDescriptor("filesystem","files",tool_names=("read_file","write_file")),
        },
    )
    AetherNextKernel(max_steps=2).run(env, executor, hooks)
    assert executor.computer_history == [{"actions": [
        {"type": "click", "button": "left", "x": 40, "y": 50},
        {"type": "type", "text": "hello"},
    ]}]
    assert len(client.responses.requests) == 2
    first_tools=client.responses.requests[0]["tools"]
    assert any(tool.get("type") == "computer" for tool in first_tools)
    second=client.responses.requests[1]
    assert second["previous_response_id"] == "resp-1"
    computer_output=second["input"][0]
    assert computer_output["type"] == "computer_call_output"
    assert computer_output["call_id"] == "ccall-1"
    encoded=computer_output["output"]["image_url"].split(",",1)[1]
    assert base64.b64decode(encoded) == raw


def test_kernel_refreshes_computer_capability_when_backend_appears_mid_run() -> None:
    from aether.kernel import AetherNextKernel
    from aether.model_hooks import ModelHooks
    from aether.runtime_ir import CapabilityDescriptor

    raw=b"\x89PNG\r\n\x1a\nmid-run-desktop"
    # Turn 1 cannot use computer and creates the marker that makes the fake
    # backend available. Turn 2 must then see native Computer Use without a
    # recompile. Turn 3 must receive the fresh screenshot from turn 2.
    first_call = SimpleNamespace(
        id="fc-1", call_id="fcall-1", type="function_call", status="completed",
        name="write_file", arguments=json.dumps({"arguments":{"path":"/app/desktop.ready","content":"1"}}),
    )
    first_response = SimpleNamespace(
        id="resp-1", status="completed", output=[first_call], usage=None,
        reasoning=None, error=None, incomplete_details=None,
    )
    model, client = _model([
        first_response,
        _computer_response(2, SimpleNamespace(type="screenshot")),
        _function_response(3),
    ])
    hooks=ModelHooks(model, lambda *_args, **_kwargs: "{}", run_id="dyn-r", task_id="dyn-t")
    executor=MemoryExecutor(workspace_root="/app", files={"a":"ok"})

    # Availability is live executor truth, not the initial EnvMap. The first
    # write makes it become true; the computer executor then returns exact
    # post-action pixels.
    executor.computer_available = lambda: "desktop.ready" in executor.files  # type: ignore[attr-defined]
    executor.register_computer(lambda _ex, action: ComputerActionResult(
        action=action, success=True, screenshot_bytes=raw, media_type="image/png",
        width=320, height=200,
    ))
    env=EnvMap(
        task_prompt="Create the desktop marker, then use the computer.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor("filesystem","files",tool_names=("read_file","write_file")),
        },
    )
    result=AetherNextKernel(max_steps=3).run(env, executor, hooks)
    assert result.step >= 2
    requests=client.responses.requests
    assert len(requests) == 3
    assert all(tool.get("type") != "computer" for tool in requests[0]["tools"])
    assert sum(tool.get("type") == "computer" for tool in requests[1]["tools"]) == 1
    third=requests[2]
    assert third["previous_response_id"] == "resp-2"
    output=third["input"][0]
    assert output["type"] == "computer_call_output"
    assert output["call_id"] == "ccall-2"
    encoded=output["output"]["image_url"].split(",",1)[1]
    assert base64.b64decode(encoded) == raw
    refreshes=[r for r in result.receipts if r.kind == "runtime_capability_refresh"]
    assert any(r.payload.get("runtime_capability_ids") == ["computer_control"] for r in refreshes)


def test_kernel_removes_computer_tool_when_live_backend_disappears() -> None:
    from aether.kernel import AetherNextKernel
    from aether.model_hooks import ModelHooks
    from aether.runtime_ir import CapabilityDescriptor

    first_call = SimpleNamespace(
        id="fc-1", call_id="fcall-1", type="function_call", status="completed",
        name="write_file", arguments=json.dumps({"arguments":{"path":"/app/desktop.off","content":"1"}}),
    )
    first_response = SimpleNamespace(
        id="resp-1", status="completed", output=[first_call], usage=None,
        reasoning=None, error=None, incomplete_details=None,
    )
    model, client = _model([first_response, _function_response(2)])
    hooks=ModelHooks(model, lambda *_args, **_kwargs: "{}", run_id="gone-r", task_id="gone-t")
    executor=MemoryExecutor(workspace_root="/app", files={"a":"ok"})
    executor.computer_available = lambda: "desktop.off" not in executor.files  # type: ignore[attr-defined]
    env=EnvMap(
        task_prompt="Disable the desktop then inspect a file.", workspace_root="/app",
        capabilities={
            "computer_control": CapabilityDescriptor("computer_control","gui",tool_names=("computer_action",)),
            "filesystem": CapabilityDescriptor("filesystem","files",tool_names=("read_file","write_file")),
        },
    )
    AetherNextKernel(max_steps=2).run(env, executor, hooks)
    assert any(tool.get("type") == "computer" for tool in client.responses.requests[0]["tools"])
    assert all(tool.get("type") != "computer" for tool in client.responses.requests[1]["tools"])


def test_live_computer_capability_is_same_authority_for_context_and_kernel_admission() -> None:
    from aether.pcr_capabilities import pcr_capability_contract, pcr_capability_violation
    from aether.pcr_context import build_pcr_context
    from aether.pcr_runtime import build_pcr_runtime
    from aether.runtime_ir import CapabilityDescriptor

    # Compile without computer_control, then make it live dynamically.
    env=EnvMap(
        task_prompt="dynamic capability truth", workspace_root="/app",
        capabilities={"filesystem":CapabilityDescriptor("filesystem","files",tool_names=("read_file","write_file"))},
    )
    compiled=build_pcr_runtime(env).compiled
    assert compiled is not None
    ledger=ExecutionLedger(); ledger.set_runtime_capabilities({"computer_control"})
    packet=build_pcr_context(compiled,ledger,[])
    assert "computer_action" in packet["available_capabilities"]["action_kinds"]
    contract=pcr_capability_contract(compiled,runtime_capability_ids=ledger.runtime_capabilities)
    assert contract["computer_action"] == ("computer_control",)
    action=ActionRequest(
        action_id="dyn",kind="computer_action",capability_id="computer_control",
        arguments={"actions":[{"type":"screenshot"}]},intent="",expected_observation="",if_fail_next="",
    )
    assert pcr_capability_violation(action,compiled,runtime_capability_ids=ledger.runtime_capabilities) == ""

    # If the live probe later loses the backend, stale compiled state may not
    # preserve authority.
    env2=EnvMap(
        task_prompt="dynamic capability loss",workspace_root="/app",
        capabilities={"computer_control":CapabilityDescriptor("computer_control","gui",tool_names=("computer_action",))},
    )
    compiled2=build_pcr_runtime(env2).compiled
    assert compiled2 is not None
    denied=pcr_capability_violation(action,compiled2,runtime_capability_ids=set())
    assert "no available runtime capability" in denied
