from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from aether.artifact_transform import execute_artifact_transform
from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger
from aether.pcr_provider_protocol import PCR_ACTION_ARGUMENT_VARIANTS
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import ActionRequest, EnvMap, FIXED_KERNEL_TOOL_SURFACE


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
    return EnvMap(task_prompt="transform", workspace_root=str(tmp_path))


def _action(command: str, *, source: str = "source.bin", output: str = "view.bin") -> ActionRequest:
    return ActionRequest(
        action_id="xform",
        kind="run_command",
        capability_id="shell",
        arguments={
            "command": command,
            "source_path": source,
            "output_path": output,
        },
        intent="derive an exact view",
        expected_observation="content-addressed derivative",
        if_fail_next="inspect command failure",
    )


def test_transform_reuses_run_command_instead_of_growing_fixed_tool_surface() -> None:
    assert "transform_artifact" not in FIXED_KERNEL_TOOL_SURFACE
    variants = PCR_ACTION_ARGUMENT_VARIANTS["run_command"]
    argument_sets = [list(row["properties"]) for row in variants]
    assert ["command", "source_path", "output_path"] in argument_sets
    assert ["command", "source_path", "output_path", "timeout_s"] in argument_sets


def test_transform_records_exact_source_command_and_derivative_identity(tmp_path: Path) -> None:
    (tmp_path / "source.bin").write_bytes(b"exact-source\x00bytes")
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_artifact_transform(
        _kernel(),
        _action("cp {source} {output}"),
        3,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is True
    assert receipt.kind == "run_command"
    assert receipt.payload["action_kind"] == "run_command"
    derivation = receipt.payload["artifact_derivation"]
    assert derivation["source"]["sha256"] == derivation["derivative"]["sha256"]
    assert derivation["source"]["path"] == "source.bin"
    assert derivation["derivative"]["path"] == "view.bin"
    assert derivation["transform"] == "task_local_command"
    assert receipt.payload["transform_authority"].endswith("not_semantic_truth")
    assert receipt.payload["artifact_handle"] == derivation["derivative"]["handle"]
    assert (tmp_path / "view.bin").read_bytes() == b"exact-source\x00bytes"


def test_kernel_dispatch_routes_provenance_bound_run_command_without_new_tool(tmp_path: Path) -> None:
    (tmp_path / "source.txt").write_text("source\n", encoding="utf-8")
    executor = SubprocessExecutor(str(tmp_path))
    action = _action("cat {source} > {output}", source="source.txt", output="derived.txt")
    receipts = dispatch_action(
        _kernel(), action, 2, _compiled(), executor, _env(tmp_path), ExecutionLedger()
    )
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.success is True
    assert receipt.kind == "run_command"
    assert receipt.payload["artifact_derivation"]["source"]["path"] == "source.txt"
    assert receipt.payload["artifact_derivation"]["derivative"]["path"] == "derived.txt"
    assert (tmp_path / "derived.txt").read_text(encoding="utf-8") == "source\n"


def test_transform_requires_both_placeholders_before_execution(tmp_path: Path) -> None:
    (tmp_path / "source.bin").write_bytes(b"source")
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_artifact_transform(
        _kernel(),
        _action("cp {source} view.bin"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is False
    assert receipt.failure_class == "action_validation"
    assert not (tmp_path / "view.bin").exists()


def test_transform_refuses_in_place_source_overwrite(tmp_path: Path) -> None:
    (tmp_path / "source.bin").write_bytes(b"source")
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_artifact_transform(
        _kernel(),
        _action("cp {source} {output}", output="source.bin"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is False
    assert receipt.failure_class == "action_validation"
    assert (tmp_path / "source.bin").read_bytes() == b"source"


def test_successful_command_without_declared_output_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "source.bin").write_bytes(b"source")
    executor = SubprocessExecutor(str(tmp_path))
    receipt = execute_artifact_transform(
        _kernel(),
        _action("true # {source} {output}"),
        1,
        _compiled(),
        executor,
        _env(tmp_path),
        timeout_s=30,
        timeout_note="test",
    )
    assert receipt.success is False
    assert receipt.failure_class == "missing_artifact"


def test_transform_module_contains_no_benchmark_specific_media_or_cad_strategy() -> None:
    import inspect
    import aether.artifact_transform as module

    source = inspect.getsource(module).lower()
    for forbidden in ("pdftotext", "ffmpeg", "freecad", "qemu", "medical-claims-processing"):
        assert forbidden not in source
