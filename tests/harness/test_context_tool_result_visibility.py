"""Regression test for RC1: the per-step solver context packet rendered ONLY
run_command receipts (via the narrow `command_results` selector/section).
Results from service_probe, artifact_inspection (vision transcription),
read_file, process_launch, etc. never appeared in ANY rendered section, so
the solver acted blind to its own tool output and repeated the action.

Trace evidence: in a image-to-code run, a 90KB artifact_inspection vision
transcription was dropped from context (the step-1 packet was 561 chars
total). In a vm-boot-check run, 22 service_probe "live" results were
invisible, causing a 15-probe loop.

This test fails on pre-fix code because:
  - `ContextCompiler._available_sections` only ever built a `command_results`
    section filtered to `receipt.kind == "run_command"`; under the default
    (no-recipe) context policy nothing else ever surfaced a non-run_command
    tool receipt.
  - `context_views.receipt_inline_view` had no rendering branch for
    `artifact_inspection` or `service_probe`, so even a receipt lucky enough
    to land in some other section would not show its meaningful payload.
"""
from __future__ import annotations

import json

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.context_compiler import ContextCompiler
from aether.context_views import receipt_inline_view
from aether.ledger import ExecutionLedger, Receipt
from aether.runtime_ir import (
    CapabilityDescriptor,
    CompletionPolicy,
    ContextPolicy,
    ContextRecipe,
    ContextRecipeRecent,
    EnvMap,
    RuntimeConfigIR,
)


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Transcribe diagram.png and confirm the guest service is reachable.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor("filesystem", "Files", tool_names=("read_file", "write_file")),
            "shell": CapabilityDescriptor("shell", "Shell", tool_names=("run_command",)),
        },
    )


def _runtime() -> RuntimeConfigIR:
    return RuntimeConfigIR(
        architect_summary="tool result visibility regression",
        solver_identity_prompt="solver",
        selected_capabilities=("filesystem", "shell"),
        completion_policy=CompletionPolicy(require_all_obligations=False, require_recent_progress=False),
    )


def test_artifact_inspection_transcription_and_service_probe_summary_are_visible_to_solver() -> None:
    env = _env()
    compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(_runtime(), env)
    ledger = ExecutionLedger()
    ledger.ensure_objective(compiled.objective_graph)

    # A vision transcription is often the ENTIRE task input for an image
    # task. Pad it well past the 4000-char inline cap so truncation is also
    # exercised; the needle sits at the front so it survives the cap.
    transcription = "def add(a, b):\n    return a + b\n# " + ("x" * 5000)
    ledger.record(Receipt(
        receipt_id="insp-1",
        step=1,
        kind="artifact_inspection",
        success=True,
        summary=(
            f"vision transcription of diagram.png (12345 bytes, image/png): "
            f"{len(transcription)} chars extracted"
        ),
        payload={
            "path": "diagram.png",
            "mode": "vision",
            "extracted_text": transcription,
            "extraction_route": "vision_model",
            "extraction_authority": "model_transcription_not_ground_truth",
            "media_type": "image/png",
        },
    ))
    # state_change is left at its False default here, matching the real
    # PerceptionLane/vision_transcribe_receipt behavior for
    # artifact_inspection, and (for the probe below) deliberately NOT set to
    # True so this test isolates the tool_results mechanism under test rather
    # than riding into visibility via the unrelated recent_progress/
    # state_change channel that some receipts also happen to satisfy.
    ledger.record(Receipt(
        receipt_id="probe-1",
        step=2,
        kind="service_probe",
        success=True,
        summary="probe 127.0.0.1:6665: live",
        payload={
            "target": "127.0.0.1:6665",
            "service_name": "qemu-guest",
            "live": True,
            "detail": "tcp connect ok",
        },
    ))

    packet = ContextCompiler().compile(compiled, ledger, alerts=[])

    tool_results = {row["receipt_id"]: row for row in packet.get("tool_results", [])}
    assert "insp-1" in tool_results, "artifact_inspection receipt missing from context packet entirely"
    assert "def add(a, b):" in tool_results["insp-1"].get("extracted_text", ""), (
        "vision transcription excerpt missing from the artifact_inspection row"
    )
    assert "probe-1" in tool_results, "service_probe receipt missing from context packet entirely"
    assert tool_results["probe-1"].get("summary") == "probe 127.0.0.1:6665: live"
    assert tool_results["probe-1"].get("target") == "127.0.0.1:6665"
    assert tool_results["probe-1"].get("live") is True

    # Belt-and-braces per the reported defect: the evidence must be visible
    # somewhere in what actually gets serialized to the model, not just in an
    # internal structure this test happens to know the name of.
    serialized = json.dumps(packet, sort_keys=True, default=str)
    assert "def add(a, b):" in serialized
    assert "probe 127.0.0.1:6665: live" in serialized



def test_latest_solver_decision_and_exact_result_survive_queryable_history_recipe() -> None:
    env = _env()
    runtime = RuntimeConfigIR(
        architect_summary="causal transition visibility regression",
        solver_identity_prompt="solver",
        selected_capabilities=("filesystem", "shell"),
        context_policy=ContextPolicy(
            mode="default_bounded",
            recipe=ContextRecipe(
                always_include=("installed_capabilities", "artifacts_present"),
                include_recent=(ContextRecipeRecent("command_results", 4),),
                include_last_failure=1,
                make_queryable_not_inline=("command_results",),
            ),
        ),
        completion_policy=CompletionPolicy(
            require_all_obligations=False,
            require_recent_progress=False,
        ),
    )
    compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(runtime, env)
    ledger = ExecutionLedger()
    ledger.ensure_objective(compiled.objective_graph)
    ledger.record(Receipt(
        receipt_id="step-0:repair:solver_decision_state",
        step=0,
        kind="solver_decision_state",
        success=True,
        summary="repair the exact failed check",
        payload={
            "current_subgoal": "repair the exact failed check",
            "evidence_gap": "the failing line is unknown",
            "action_id": "repair",
            "action_kind": "run_command",
            "intent": "run the complete build",
            "expected_observation": "build and live proof succeed",
            "if_fail_next": "inspect the exact failure, repair the smallest issue, and rerun the failing piece",
            "mutation_generation": 0,
        },
    ))
    ledger.record(Receipt(
        receipt_id="step-0:repair:cmd",
        step=0,
        kind="run_command",
        success=False,
        summary="command exit=1: build",
        failure_class="test_failure",
        payload={
            "command": "python3 build.py",
            "exit_code": 1,
            "stdout": "dependency installed",
            "stderr": "AttributeError: package has no attribute __version__",
        },
    ))
    ledger.record(Receipt(
        receipt_id="step-0:repair:solver_progress_assessment",
        step=0,
        kind="solver_progress_assessment",
        success=True,
        summary="mechanical action-result summary: unsuccessful_result_no_state_change",
        failure_class="",
        payload={
            "classification": "unsuccessful_result_no_state_change",
            "action_id": "repair",
            "action_kind": "run_command",
            "result_receipt_ids": ["step-0:repair:cmd"],
            "result_count": 1,
            "successful_result_count": 0,
            "failed_result_count": 1,
            "state_change_count": 0,
            "mutation_generation": 0,
            "interpretation_authority": "solver",
        },
    ))

    packet = ContextCompiler().compile(compiled, ledger, alerts=[])

    assert "command_results" not in packet
    transition = packet["latest_solver_transition"]
    assert transition["decision"]["previous_model_contingency"].startswith("inspect the exact failure")
    assert transition["decision"]["previous_model_expectation"] == "build and live proof succeed"
    assert transition["result_receipt_ids"] == ["step-0:repair:cmd"]
    assert transition["results"][0]["receipt_id"] == "step-0:repair:cmd"
    assert "AttributeError" in transition["results"][0]["stderr"]
    assert transition["mechanical_outcome"]["classification"] == "unsuccessful_result_no_state_change"
    assert transition["mechanical_outcome"]["failed_result_count"] == 1
    assert transition["observation_boundary"]["interpretation_authority"] == "solver"
    assert transition["observation_boundary"]["previous_contingency_is_nonbinding"] is True
    serialized = json.dumps(packet, sort_keys=True, default=str)
    assert "repair the smallest issue" in serialized
    assert "AttributeError" in serialized



def test_terminal_read_observation_exposes_requested_bytes_and_structured_session_state() -> None:
    receipt = Receipt(
        receipt_id="step-2:read-terminal:terminal_read",
        step=2,
        kind="terminal_read",
        success=True,
        summary="read 41 terminal bytes from terminal:abc123",
        payload={
            "session_id": "terminal:abc123",
            "output": "TOKEN=1a4e3d\nREPLY_WITH_REVERSED_TOKEN\n",
            "bytes_read": 41,
            "cursor": 41,
            "total_bytes": 41,
            "more_available": False,
            "live": True,
            "exit_code": None,
            "process_generation": "abc123",
        },
    )

    row = receipt_inline_view(receipt)

    assert row["session_id"] == "terminal:abc123"
    assert row["bytes_read"] == 41
    assert row["cursor"] == 41
    assert row["total_bytes"] == 41
    assert row["live"] is True
    assert row["output"] == "TOKEN=1a4e3d\nREPLY_WITH_REVERSED_TOKEN\n"
    serialized = json.dumps(row, sort_keys=True)
    assert "TOKEN=1a4e3d" in serialized


def test_terminal_receipts_are_generic_tool_results_not_persistent_only() -> None:
    env = _env()
    compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(_runtime(), env)
    ledger = ExecutionLedger()
    ledger.ensure_objective(compiled.objective_graph)
    ledger.record(Receipt(
        receipt_id="terminal-start",
        step=1,
        kind="terminal_start",
        success=True,
        summary="started terminal session terminal:abc123",
        payload={
            "session_id": "terminal:abc123",
            "command": "python3 challenge.py",
            "live": True,
            "process_generation": "abc123",
        },
    ))
    ledger.record(Receipt(
        receipt_id="terminal-read",
        step=2,
        kind="terminal_read",
        success=True,
        summary="read 41 terminal bytes from terminal:abc123",
        payload={
            "session_id": "terminal:abc123",
            "output": "TOKEN=1a4e3d\nREPLY_WITH_REVERSED_TOKEN\n",
            "bytes_read": 41,
            "cursor": 41,
            "total_bytes": 41,
            "more_available": False,
            "live": True,
            "process_generation": "abc123",
        },
    ))

    packet = ContextCompiler().compile(compiled, ledger, alerts=[])
    by_id = {row["receipt_id"]: row for row in packet.get("tool_results", [])}
    assert by_id["terminal-start"]["session_id"] == "terminal:abc123"
    assert by_id["terminal-read"]["output"].startswith("TOKEN=1a4e3d")
