from __future__ import annotations

import json
from pathlib import Path

from runner.agent import _build_declared_tools_dispatch, run_reference_baseline
from runner.evidence_kernel import EvidenceKernel
from runner.model_client import make_no_model_route


class _ScriptedModel:
    def __init__(self, responses):
        self._responses = list(responses)

    def complete(self, _messages, **_kwargs):  # type: ignore[no-untyped-def]
        if self._responses:
            return self._responses.pop(0)
        return {"text": "", "tool_calls": []}


def test_evidence_kernel_records_typed_receipts_and_lineage(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "seed.txt").write_text("seed\n", encoding="utf-8")

    kernel = EvidenceKernel(run_id="run1", task_id="task1", workspace_root=workspace)
    kernel.bind_session({"sandbox_type": "none", "cwd": str(workspace)})

    (workspace / "out.txt").write_text("hello\n", encoding="utf-8")
    receipt = kernel.record_action(
        action_type="command",
        action_payload={"command": "printf hello > out.txt"},
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
        cwd=str(workspace),
    )

    assert receipt["action_type"] == "command"
    assert receipt["mutation_observed"] is True
    assert "out.txt" in kernel.lineage
    assert kernel.export_state()["receipt_count"] == 1


def test_evidence_kernel_updates_verifier_and_artifact_gates(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "run_header.json").write_text("{}", encoding="utf-8")

    kernel = EvidenceKernel(run_id="run2", task_id="task2", workspace_root=workspace)
    kernel.set_verifier_gate(passed=True, reason_codes=["verifier_passed"])
    kernel.set_artifact_gate(required_paths=["run_header.json", "missing.json"], workspace_root=workspace)

    state = kernel.export_state()
    assert state["verifier_gate"]["status"] == "pass"
    assert state["artifact_gate"]["status"] == "fail"
    assert state["artifact_gate"]["missing_paths"] == ["missing.json"]
    assert state["artifact_gate"]["hash_algorithm"] == "sha256"
    assert isinstance(state["artifact_gate"]["observed_hashes"]["run_header.json"], str)
    assert state["artifact_gate"]["observed_hashes"]["run_header.json"]

    pack = kernel.build_working_context_pack()
    assert "run_header.json" in pack["open_obligations"]["artifact_gate_hashes_recorded"]
    assert pack["artifact_contract"]["required_path_count"] == 2
    assert pack["artifact_contract"]["missing_path_count"] == 1
    assert pack["artifact_contract"]["hashed_path_count"] == 1


def test_evidence_kernel_inferrs_service_actions_and_updates_registry(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    kernel = EvidenceKernel(run_id="run3", task_id="task3", workspace_root=workspace)
    kernel.bind_session({"sandbox_type": "none", "cwd": str(workspace)})

    kernel.record_action(
        action_type=None,
        action_payload={"tool_name": "raw_bash", "command": "python3 launch_service.py --port 8080"},
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
        cwd=str(workspace),
    )
    kernel.record_action(
        action_type=None,
        action_payload={"tool_name": "raw_bash", "command": "curl -sf http://127.0.0.1:8080/health"},
        result_payload={"exit_code": 0, "stdout": "ok", "stderr": "", "timed_out": False},
        cwd=str(workspace),
    )
    state = kernel.export_state()
    assert state["receipts"][0]["action_type"] == "start_service"
    assert state["receipts"][1]["action_type"] == "probe_service"
    assert state["service_registry"]["managed_service"]["status"] == "ready"
    assert state["service_registry"]["managed_service"]["last_action_type"] == "probe_service"
    assert len(state["service_registry"]["managed_service"]["events"]) == 2
    assert state["process_registry"]["managed_service"]["status"] == "running"
    assert state["process_registry"]["managed_service"]["start_receipt_id"] == "r0001"
    assert state["process_registry"]["managed_service"]["last_probe_receipt_id"] == "r0002"


def test_evidence_kernel_tracks_declared_tools_and_native_mode():
    kernel = EvidenceKernel(run_id="run4", task_id="task4", workspace_root=Path("."))
    kernel.set_declared_tools([{"name": "raw_bash"}, {"name": "native_lookup"}])
    state = kernel.export_state()
    assert state["native_tool_mode_active"] is True
    assert "native_lookup" in state["declared_tool_names"]


def test_run_reference_baseline_emits_evidence_kernel_receipts(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runner.agent.resolve_model_client",
        lambda _route, **_kwargs: _ScriptedModel(
            [
                {
                    "text": "run command",
                    "tool_calls": [{"id": "c1", "name": "raw_bash", "arguments": {"command": "echo hello > out.txt"}}],
                },
                {"text": "done", "tool_calls": []},
            ]
        ),
    )

    run_dir = tmp_path / "run"
    result = run_reference_baseline(
        run_id="run-kernel",
        run_dir=run_dir,
        task_id="task-kernel",
        task_prompt="write a file",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        max_steps=3,
        timeout_sec=10,
    )

    events = [
        json.loads(line)
        for line in (run_dir / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_types = [event["event_type"] for event in events]
    assert "evidence_kernel_receipt" in event_types
    assert "evidence_kernel_state" in event_types
    assert "evidence_kernel_working_context_pack" in event_types
    assert "action_bus_recorded" in event_types
    assert "action_bus_summary" in event_types
    action_bus_summary = result["action_bus"]
    assert action_bus_summary["action_count"] >= 1
    action_types = {record.get("action_type") for record in action_bus_summary.get("records", [])}
    assert "verify" in action_types
    assert "finalize" in action_types
    assert result["evidence_kernel"]["receipt_count"] >= 1
    assert result["evidence_kernel"]["receipts"][0]["action_type"] == "command"
    assert result["evidence_kernel"]["receipts"][0]["action_id"]
    context_pack = result["evidence_kernel_working_context_pack"]
    assert context_pack["task_contract"]["task_id"] == "task-kernel"
    assert "recent_receipts" in context_pack
    assert "allowed_action_types" in context_pack
    assert "service_summary" in context_pack


def test_declared_tools_dispatch_supports_non_raw_tool_names():
    observed_names: list[str] = []

    class _Sandbox:
        def exec(self, _command):  # type: ignore[no-untyped-def]
            return {"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}

    def _fake_executor(call, _sandbox):  # type: ignore[no-untyped-def]
        observed_names.append(call.get("name"))
        return {"tool_name": call.get("name"), "command": "", "exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}

    probe = type("_Probe", (), {"call_count": 0, "total_sec": 0.0})()
    tools = _build_declared_tools_dispatch(
        tool_definitions=[{"name": "native_case_tool"}],
        sandbox=_Sandbox(),
        tool_executor=_fake_executor,
        probe=probe,
    )
    tools["native_case_tool"]({"arguments": {"command": "noop"}})
    assert observed_names == ["native_case_tool"]


def test_run_reference_baseline_emits_bounded_autopsy_after_repeated_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runner.agent.resolve_model_client",
        lambda _route, **_kwargs: _ScriptedModel(
            [
                {
                    "text": "retry one",
                    "tool_calls": [{"id": "c1", "name": "raw_bash", "arguments": {"command": "false"}}],
                },
                {
                    "text": "retry two",
                    "tool_calls": [{"id": "c2", "name": "raw_bash", "arguments": {"command": "false"}}],
                },
                {"text": "done", "tool_calls": []},
            ]
        ),
    )

    run_dir = tmp_path / "run-autopsy"
    result = run_reference_baseline(
        run_id="run-autopsy",
        run_dir=run_dir,
        task_id="task-autopsy",
        task_prompt="avoid repeated failure",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        max_steps=4,
        timeout_sec=10,
    )
    autopsy = result["execution"].get("autopsy", {})
    assert autopsy.get("triggered") is True
    assert autopsy.get("replan_required") is True
    kernel_autopsy = result["evidence_kernel"]["autopsy_state"]
    assert kernel_autopsy["triggered"] is True
    assert kernel_autopsy["replan_required"] is True
    assert kernel_autopsy["trigger_count"] == 1
    assert "bounded_autopsy_replan_required_after_repeated_failure" in kernel_autopsy["reason_codes"]
    assert result["evidence_kernel_working_context_pack"]["open_obligations"]["autopsy_replan_required"] is True
    assert "autopsy_replan_required" in result["evidence_kernel"]["evidence_capsule"]["stale_reasons"]


def test_runtime_probe_actions_are_recorded_in_action_bus_and_kernel(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runner.agent.resolve_model_client",
        lambda _route, **_kwargs: _ScriptedModel([{"text": "done", "tool_calls": []}]),
    )
    run_dir = tmp_path / "run-probe"
    result = run_reference_baseline(
        run_id="run-probe",
        run_dir=run_dir,
        task_id="task-probe",
        task_prompt="probe action capture",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        max_steps=2,
        timeout_sec=10,
        runtime_probe={
            "probe_id": "probe-1",
            "contamination_safe": True,
            "forced_tool_calls": [
                {
                    "phase": "tool",
                    "label": "probe_pwd",
                    "tool_call": {"name": "raw_bash", "arguments": {"command": "pwd"}},
                }
            ],
        },
    )
    assert result["action_bus"]["action_count"] >= 1
    receipts = result["evidence_kernel"]["receipts"]
    assert any(receipt.get("phase") == "tool" for receipt in receipts)
    assert any((receipt.get("command") or "").strip() == "pwd" for receipt in receipts)
    assert any(receipt.get("action_type") == "verify" for receipt in receipts)
    assert any(receipt.get("action_type") == "finalize" for receipt in receipts)


def test_runtime_probe_recover_phase_marks_cleanup_observed(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runner.agent.resolve_model_client",
        lambda _route, **_kwargs: _ScriptedModel([{"text": "done", "tool_calls": []}]),
    )
    run_dir = tmp_path / "run-probe-recover"
    result = run_reference_baseline(
        run_id="run-probe-recover",
        run_dir=run_dir,
        task_id="task-probe-recover",
        task_prompt="probe recover cleanup",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        max_steps=2,
        timeout_sec=10,
        runtime_probe={
            "probe_id": "probe-recover",
            "contamination_safe": True,
            "forced_tool_calls": [
                {
                    "phase": "recover",
                    "label": "probe_recover_cleanup",
                    "tool_call": {"name": "raw_bash", "arguments": {"command": "true"}},
                }
            ],
        },
    )
    assert result["execution"]["runtime_probe"]["cleanup_observed"] is True


def test_working_context_pack_reports_service_not_ready_obligation(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    kernel = EvidenceKernel(run_id="run5", task_id="task5", workspace_root=workspace)
    kernel.record_action(
        action_type=None,
        action_payload={"tool_name": "raw_bash", "command": "python3 launch_service.py --port 9000"},
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
        cwd=str(workspace),
    )
    kernel.record_action(
        action_type=None,
        action_payload={"tool_name": "raw_bash", "command": "curl -sf http://127.0.0.1:9000/health"},
        result_payload={"exit_code": 1, "stdout": "", "stderr": "fail", "timed_out": False},
        cwd=str(workspace),
    )
    pack = kernel.build_working_context_pack()
    assert "managed_service" in pack["open_obligations"]["service_not_ready"]
    assert "managed_service" in pack["open_obligations"]["process_not_running"]
    assert pack["process_summary"]["managed_service"]["status"] == "not_running"


def test_working_context_pack_includes_compressed_receipt_proof(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    kernel = EvidenceKernel(run_id="run6", task_id="task6", workspace_root=workspace)
    for index in range(3):
        (workspace / f"f{index}.txt").write_text(str(index), encoding="utf-8")
        kernel.record_action(
            action_type="command",
            action_payload={"tool_name": "raw_bash", "command": f"echo {index} > f{index}.txt"},
            result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
            cwd=str(workspace),
        )

    pack = kernel.build_working_context_pack(max_recent_receipts=1)
    compression = pack["compression"]
    assert compression["total_receipt_count"] == 3
    assert compression["recent_receipt_count"] == 1
    assert compression["omitted_receipt_count"] == 2
    assert isinstance(compression["omitted_receipt_digest"], str)
    assert compression["omitted_receipt_digest"]
    assert compression["omitted_receipt_id_range"] == ["r0001", "r0002"]
    assert pack["recent_receipts"][0]["receipt_id"] == "r0003"
    assert isinstance(pack["lineage_digest"]["lineage_fingerprint"], str)
    assert pack["lineage_digest"]["lineage_fingerprint"]


def test_effective_evidence_capsule_marks_stale_on_failed_gates(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    kernel = EvidenceKernel(run_id="run7", task_id="task7", workspace_root=workspace)
    kernel.set_verifier_gate(passed=False, reason_codes=["verification_failed"])
    kernel.set_artifact_gate(required_paths=["missing.txt"], workspace_root=workspace)
    state = kernel.export_state()
    assert state["evidence_capsule"]["freshness"] == "stale"
    assert "verifier_gate_failed" in state["evidence_capsule"]["stale_reasons"]
    assert "artifact_gate_failed" in state["evidence_capsule"]["stale_reasons"]


def test_evidence_kernel_validates_declared_tool_input_schema(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    kernel = EvidenceKernel(run_id="run8", task_id="task8", workspace_root=workspace)
    kernel.set_declared_tools(
        [
            {
                "name": "dispatch_ticket",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "owner": {"type": "string"},
                        "priority": {"type": "integer"},
                    },
                    "required": ["ticket_id", "owner"],
                },
            }
        ]
    )

    pass_receipt = kernel.record_action(
        action_type="native_tool_call",
        action_payload={
            "tool_name": "dispatch_ticket",
            "command": "",
            "arguments": {"ticket_id": "INC-42", "owner": "ops", "priority": 2},
        },
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
        cwd=str(workspace),
    )
    assert pass_receipt["tool_contract_status"]["status"] == "pass"

    fail_receipt = kernel.record_action(
        action_type="native_tool_call",
        action_payload={
            "tool_name": "dispatch_ticket",
            "command": "",
            "arguments": {"ticket_id": "INC-43", "priority": "urgent"},
        },
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
        cwd=str(workspace),
    )
    assert fail_receipt["tool_contract_status"]["status"] == "fail"
    assert fail_receipt["tool_contract_status"]["missing_required"] == ["owner"]
    assert fail_receipt["tool_contract_status"]["type_violations"][0]["key"] == "priority"

    pack = kernel.build_working_context_pack()
    assert "r0002" in pack["open_obligations"]["tool_contract_violations"]
    assert "r0002" in pack["native_tool_contract"]["violation_receipt_ids"]
    state = kernel.export_state()
    assert "tool_contract_violation" in state["evidence_capsule"]["stale_reasons"]


def test_apply_autopsy_updates_kernel_state_and_context_pack(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    kernel = EvidenceKernel(run_id="run9", task_id="task9", workspace_root=workspace)
    kernel.apply_autopsy(
        autopsy={
            "triggered": True,
            "replan_required": True,
            "reason_codes": ["bounded_autopsy_replan_required_after_repeated_failure"],
            "repeated_failure_signatures": ["raw_bash|false|tool_runtime_nonzero_exit|1|no_timeout"],
        },
        step_count=2,
    )
    state = kernel.export_state()
    assert state["autopsy_state"]["triggered"] is True
    assert state["autopsy_state"]["replan_required"] is True
    assert state["autopsy_state"]["trigger_count"] == 1
    assert state["autopsy_state"]["last_step_count"] == 2
    pack = kernel.build_working_context_pack()
    assert pack["open_obligations"]["autopsy_replan_required"] is True
    assert pack["autopsy_summary"]["triggered"] is True


def test_service_start_receipt_pid_is_reflected_in_process_registry(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    kernel = EvidenceKernel(run_id="run10", task_id="task10", workspace_root=workspace)
    kernel.record_action(
        action_type=None,
        action_payload={"tool_name": "raw_bash", "command": "python3 launch_service.py --port 7001"},
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False, "pid": 4321},
        cwd=str(workspace),
    )
    state = kernel.export_state()
    assert state["receipts"][0]["pid"] == 4321
    assert state["process_registry"]["managed_service"]["pid"] == 4321


def test_cwd_lineage_tracks_transitions_and_outside_workspace_signal(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subdir = workspace / "subdir"
    subdir.mkdir()
    kernel = EvidenceKernel(run_id="run11", task_id="task11", workspace_root=workspace)
    kernel.bind_session({"cwd": str(workspace), "sandbox_type": "none"})

    kernel.record_action(
        action_type="command",
        action_payload={"tool_name": "raw_bash", "command": "pwd"},
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
        cwd=str(workspace),
    )
    kernel.record_action(
        action_type="command",
        action_payload={"tool_name": "raw_bash", "command": "cd subdir && pwd"},
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
        cwd=str(subdir),
    )
    kernel.record_action(
        action_type="command",
        action_payload={"tool_name": "raw_bash", "command": "pwd"},
        result_payload={"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False},
        cwd="/tmp",
    )

    state = kernel.export_state()
    cwd_lineage = state["cwd_lineage"]
    assert cwd_lineage["initial_cwd"] == str(workspace)
    assert cwd_lineage["current_cwd"] == "/tmp"
    assert cwd_lineage["cwd_transition_count"] >= 2
    assert cwd_lineage["cwd_outside_workspace_count"] == 1
    assert state["receipts"][1]["cwd_changed_from_previous"] is True
    assert state["receipts"][2]["cwd_within_workspace_root"] is False
    assert "cwd_outside_workspace_root" in state["evidence_capsule"]["stale_reasons"]

    pack = kernel.build_working_context_pack()
    assert pack["open_obligations"]["cwd_outside_workspace_root_observed"] is True
    assert pack["cwd_contract"]["cwd_outside_workspace_count"] == 1
