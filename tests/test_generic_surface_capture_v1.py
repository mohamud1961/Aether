from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger
from aether.pcr_provider_protocol import PCR_ACTION_ARGUMENT_VARIANTS
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import ActionRequest, EnvMap, FIXED_KERNEL_TOOL_SURFACE
from aether.surface_capture import execute_surface_capture


class _FailureParser:
    @staticmethod
    def classify(text: str, *, exit_code: int) -> str:
        del text
        return "command_failure" if exit_code else ""


class _Integrity:
    @staticmethod
    def validate_modified_paths(_objective, _paths) -> str:
        return ""


def _kernel():
    return SimpleNamespace(failure_parser=_FailureParser(), integrity_guards=_Integrity())


def _compiled():
    return SimpleNamespace(objective_graph=SimpleNamespace())


def _env(tmp_path: Path) -> EnvMap:
    return EnvMap(task_prompt="capture the visible surface", workspace_root=str(tmp_path))


def _action(command: str, *, output: str = "screen.png", surface: str = "display:0") -> ActionRequest:
    return ActionRequest(
        action_id="capture",
        kind="run_command",
        capability_id="shell",
        arguments={
            "command": command,
            "capture_surface": surface,
            "output_path": output,
        },
        intent="capture the current live visual surface",
        expected_observation="one exact content-addressed image capture",
        if_fail_next="inspect the capture command failure",
    )


def test_surface_capture_reuses_run_command_without_growing_fixed_tool_surface() -> None:
    assert "capture_screenshot" not in FIXED_KERNEL_TOOL_SURFACE
    assert "capture_surface" not in FIXED_KERNEL_TOOL_SURFACE
    variants = PCR_ACTION_ARGUMENT_VARIANTS["run_command"]
    argument_sets = [list(row["properties"]) for row in variants]
    assert ["command", "capture_surface", "output_path"] in argument_sets
    assert ["command", "capture_surface", "output_path", "timeout_s"] in argument_sets


def test_surface_capture_binds_fresh_exact_pixels_to_named_surface(tmp_path: Path) -> None:
    pixels = b"\x89PNG\r\n\x1a\nsynthetic-screen-pixels"
    (tmp_path / "capture-source.png").write_bytes(pixels)
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_surface_capture(
        _kernel(),
        _action("cp capture-source.png {output}"),
        4,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is True
    assert receipt.kind == "run_command"
    assert receipt.payload["capture_surface"] == "display:0"
    assert receipt.payload["artifact_identity"]["path"] == "screen.png"
    assert receipt.payload["artifact_identity"]["sha256"] == hashlib.sha256(pixels).hexdigest()
    assert receipt.payload["artifact_handle"] == f"artifact:sha256:{hashlib.sha256(pixels).hexdigest()}"
    derivation = receipt.payload["screen_capture_derivation"]
    assert derivation["source"]["path"] == "surface:display:0"
    assert derivation["source"]["media_type"] == "application/x-aether-live-surface"
    assert derivation["derivative"]["sha256"] == hashlib.sha256(pixels).hexdigest()
    assert derivation["transform"] == "exact_screen_capture"
    assert derivation["transform_version"].startswith("task_local_command:")
    assert receipt.payload["capture_authority"].endswith("not_semantic_truth")
    assert (tmp_path / "screen.png").read_bytes() == pixels


def test_surface_capture_rejects_preexisting_target_before_execution(tmp_path: Path) -> None:
    target = tmp_path / "screen.png"
    target.write_bytes(b"stale")
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_surface_capture(
        _kernel(),
        _action("printf fresh > {output}"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is False
    assert receipt.failure_class == "stale_evidence"
    assert target.read_bytes() == b"stale"


def test_surface_capture_accepts_literal_declared_output_without_hidden_placeholder_rule(tmp_path: Path) -> None:
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_surface_capture(
        _kernel(),
        _action("printf fresh > screen.png"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is True
    assert receipt.payload["artifact_identity"]["sha256"] == hashlib.sha256(b"fresh").hexdigest()


def test_surface_capture_placeholder_quotes_declared_output_path(tmp_path: Path) -> None:
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_surface_capture(
        _kernel(),
        _action("printf pixels > {output}", output="screen with spaces.png"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is True
    assert (tmp_path / "screen with spaces.png").read_bytes() == b"pixels"


def test_surface_capture_success_without_output_fails_closed(tmp_path: Path) -> None:
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_surface_capture(
        _kernel(),
        _action("true # {output}"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is False
    assert receipt.failure_class == "missing_artifact"
    assert "missing.png" not in receipt.payload.get("artifact_paths", ())


def test_surface_capture_empty_output_is_not_valid_evidence(tmp_path: Path) -> None:
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_surface_capture(
        _kernel(),
        _action(": > {output}"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is False
    assert receipt.failure_class == "invalid_artifact"


def test_kernel_dispatch_routes_surface_capture_before_static_artifact_transform(tmp_path: Path) -> None:
    pixels = b"\x89PNG\r\n\x1a\ndispatch-screen"
    (tmp_path / "capture-source.png").write_bytes(pixels)
    executor = SubprocessExecutor(str(tmp_path))
    rows = dispatch_action(
        _kernel(),
        _action("cp capture-source.png {output}"),
        2,
        _compiled(),
        executor,
        _env(tmp_path),
        ExecutionLedger(),
    )
    assert len(rows) == 1
    receipt = rows[0]
    assert receipt.success is True
    assert receipt.receipt_id.endswith(":surface_capture")
    assert "screen_capture_derivation" in receipt.payload
    assert "source_artifact_identity" not in receipt.payload


def test_surface_capture_module_contains_no_backend_or_benchmark_strategy() -> None:
    import inspect
    import aether.surface_capture as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "qemu-system",
        "playwright",
        "freecad",
        "vncserver",
        "medical-claims-processing",
        "code-from-image",
    ):
        assert forbidden not in source



def test_environment_command_discovery_is_bounded_without_per_entry_resolution() -> None:
    """Broad PATH inventory deduplicates/caps without command-v work per entry."""
    from aether.environment_probe import _MAX_DISCOVERED_COMMANDS, _probe_commands
    from aether.execution import CommandResult

    class Executor:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30):
            del cwd, timeout_s
            self.commands.append(command)
            if command.startswith("for c in "):
                return CommandResult(command=command, exit_code=0, stdout="python3\t/usr/bin/python3\n")
            if "path_rest=\"${PATH}:\"" in command:
                return CommandResult(command=command, exit_code=0, stdout="freecadcmd\t/usr/local/bin/freecadcmd\n")
            raise AssertionError(f"unexpected command: {command}")

    executor = Executor()
    commands = _probe_commands(
        executor, workspace_root="/app", command_probe_names=("python3",),
    )
    assert commands["freecadcmd"] == {
        "available": True, "path": "/usr/local/bin/freecadcmd",
    }
    discovery = next(command for command in executor.commands if "path_rest=\"${PATH}:\"" in command)
    assert "command -v --" not in discovery
    assert "seen='|'" in discovery
    assert f'-ge {_MAX_DISCOVERED_COMMANDS}' in discovery
    assert "break 2" in discovery



def test_surface_capture_output_flows_into_same_primary_native_image_perception(tmp_path: Path) -> None:
    from aether.execution import PerceptionLane

    pixels = b"\x89PNG\r\n\x1a\nend-to-end-screen-pixels"
    (tmp_path / "capture-source.png").write_bytes(pixels)
    executor = SubprocessExecutor(str(tmp_path))
    staged: list[dict[str, object]] = []
    kernel = SimpleNamespace(
        failure_parser=_FailureParser(),
        integrity_guards=_Integrity(),
        perception_lane=PerceptionLane(),
        active_hooks=SimpleNamespace(
            stage_primary_native_image_observation=lambda **kwargs: staged.append(dict(kwargs)) or True,
        ),
    )
    capture = dispatch_action(
        kernel,
        _action("cp capture-source.png {output}"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        ExecutionLedger(),
    )[0]
    assert capture.success is True
    assert capture.payload["artifact_identity"]["sha256"] == hashlib.sha256(pixels).hexdigest()

    inspect = ActionRequest(
        action_id="inspect-capture",
        kind="inspect_artifact",
        capability_id="artifact_inspection",
        arguments={"path": "screen.png", "mode": "image"},
        intent="observe the exact captured surface pixels",
        expected_observation="same Primary receives the exact image bytes",
        if_fail_next="inspect capture custody",
    )
    perceived = dispatch_action(
        kernel, inspect, 2, _compiled(), executor, _env(tmp_path), ExecutionLedger()
    )[0]
    assert perceived.success is True
    assert perceived.payload["extraction_route"] == "same_primary_native_image"
    assert perceived.payload["native_primary_artifact_sha256"] == hashlib.sha256(pixels).hexdigest()
    assert staged and staged[0]["image_bytes"] == pixels
    assert staged[0]["artifact_path"] == "screen.png"


def test_pcr_provider_contract_accepts_generic_surface_capture_variant() -> None:
    from aether.pcr_provider_protocol import validate_pcr_inner_turn

    turn = validate_pcr_inner_turn({
        "kind": "act",
        "action": {
            "kind": "run_command",
            "arguments": {
                "command": "capture-tool --output {output}",
                "capture_surface": "display:0",
                "output_path": "surface.png",
                "timeout_s": 20,
            },
        },
    })
    assert turn["action"]["arguments"]["capture_surface"] == "display:0"
    assert turn["action"]["arguments"]["output_path"] == "surface.png"
