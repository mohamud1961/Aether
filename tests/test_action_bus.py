from __future__ import annotations

from runner.action_bus import ActionBus, extract_command, infer_action_type


def test_extract_command_parses_dict_and_json_string_arguments():
    assert extract_command({"command": "echo hi"}) == "echo hi"
    assert extract_command('{"command":"pwd"}') == "pwd"
    assert extract_command("ls -la") == "ls -la"


def test_infer_action_type_maps_native_and_service_probe_cases():
    assert infer_action_type(tool_name="native_schema_tool", command="") == "native_tool_call"
    assert infer_action_type(tool_name="raw_bash", command="python3 launch_service.py --port 8080") == "start_service"
    assert infer_action_type(tool_name="raw_bash", command="curl -sf http://127.0.0.1:8080/health") == "probe_service"


def test_action_bus_records_incrementing_action_ids():
    bus = ActionBus(run_id="run-action-bus")
    first = bus.record_from_tool_call(
        tool_call={"name": "raw_bash", "arguments": {"command": "echo one"}},
        step=0,
        tool_index=0,
    )
    second = bus.record_from_tool_call(
        tool_call={"name": "native_lookup", "arguments": {"query": "x"}},
        step=1,
        tool_index=0,
    )
    assert first.action_id.endswith("a0001")
    assert second.action_id.endswith("a0002")
    assert second.action_type == "native_tool_call"
    summary = bus.export_summary()
    assert summary["action_count"] == 2


def test_action_bus_records_system_actions():
    bus = ActionBus(run_id="run-system")
    record = bus.record_system_action(action_type="verify", phase="verify", command="verification_gate")
    assert record.tool_name == "system"
    assert record.action_type == "verify"
    assert record.phase == "verify"
