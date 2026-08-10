from __future__ import annotations

import json
from typing import Any, Mapping

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.kernel_config import resolve_runtime
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.workbench_config import HarnessConfigIR, parse_harness_config_ir
from aether.workbench_hooks import WorkbenchArchitect
from tests.harness.test_architect_structured_output import _canonical_config
from tests.harness.test_kernel_config import _FakeHooks, _make_ir, _workbench_config_json


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Do the task.",
        workspace_root="/app",
        capabilities={
            "shell": CapabilityDescriptor(capability_id="shell", summary="Run commands"),
            "filesystem": CapabilityDescriptor(capability_id="filesystem", summary="Read/write files"),
        },
    )


class _CorrectingArchitect:
    def __init__(self, first: HarnessConfigIR, corrected: HarnessConfigIR | None) -> None:
        self.first = first
        self.corrected = corrected
        self.last_raw_output = json.dumps(_canonical_config())
        self.configure_calls = 0
        self.correct_calls = 0
        self.findings: list[str] = []
        self.previous_output = ""

    def configure(self, request: Mapping[str, Any]):
        self.configure_calls += 1
        return self.first, []

    def correct(self, request: Mapping[str, Any], *, previous_output: str, findings: list[str]):
        self.correct_calls += 1
        self.findings = list(findings)
        self.previous_output = previous_output
        return self.corrected, ([] if self.corrected is not None else ["correction failed"])


class _FailCompileOnce(ConfigCompiler):
    def __init__(self, registry: CapabilityRegistry) -> None:
        super().__init__(registry)
        self.compile_calls = 0

    def compile(self, *args: Any, **kwargs: Any):
        self.compile_calls += 1
        if self.compile_calls == 1:
            raise ValueError("proof_route_strength_insufficient: generated route")
        return super().compile(*args, **kwargs)


class _AlwaysFailCompile(ConfigCompiler):
    def __init__(self, registry: CapabilityRegistry) -> None:
        super().__init__(registry)
        self.compile_calls = 0

    def compile(self, *args: Any, **kwargs: Any):
        self.compile_calls += 1
        raise ValueError("proof_route_strength_insufficient: still invalid")


def test_compile_failure_triggers_exactly_one_model_correction_and_full_recompile() -> None:
    env = _env()
    config = parse_harness_config_ir(_workbench_config_json())
    architect = _CorrectingArchitect(config, config)
    compiler = _FailCompileOnce(CapabilityRegistry.from_envmap(env))

    resolved = resolve_runtime(
        env,
        compiler,
        _FakeHooks(_make_ir()),
        workbench_architect=architect,
    )

    assert resolved.compiled is not None
    assert architect.configure_calls == 1
    assert architect.correct_calls == 1
    assert compiler.compile_calls == 2
    assert architect.previous_output == architect.last_raw_output
    assert architect.findings == [
        "compile:ValueError:proof_route_strength_insufficient: generated route"
    ]
    assert resolved.repair_codes[0] == "workbench_architect_model_correction"
    assert resolved.config_invalid_blockers == ()


def test_corrected_config_that_still_fails_compilation_blocks_solver() -> None:
    env = _env()
    config = parse_harness_config_ir(_workbench_config_json())
    architect = _CorrectingArchitect(config, config)
    compiler = _AlwaysFailCompile(CapabilityRegistry.from_envmap(env))

    resolved = resolve_runtime(
        env,
        compiler,
        _FakeHooks(_make_ir()),
        workbench_architect=architect,
    )

    assert resolved.compiled is None
    assert architect.configure_calls == 1
    assert architect.correct_calls == 1
    assert compiler.compile_calls == 2
    assert "workbench_architect_corrected_config_invalid" in resolved.config_invalid_blockers
    assert "invalid config" in resolved.runtime_ir.architect_summary


def test_workbench_architect_correction_packet_is_complete_generic_and_bounded() -> None:
    outputs = [json.dumps(_canonical_config())]
    calls: list[list[dict[str, str]]] = []

    def model(messages: list[dict[str, str]], *, max_output_tokens: int) -> str:
        calls.append(messages)
        return outputs.pop(0)

    architect = WorkbenchArchitect(model)
    previous = json.dumps({"schema_version": "harness_config.v1", "visible_contract": []})
    config, errors = architect.correct(
        {"schema_version": "architect_request.v2", "task": {"prompt": "visible task"}},
        previous_output=previous,
        findings=["compile:ValueError:route too weak"],
    )

    assert config is not None
    assert errors == []
    assert architect.correction_calls == 1
    assert len(calls) == 1
    packet = json.loads(calls[0][1]["content"])
    assert packet["mode"] == "architect_generic_correction.v1"
    assert packet["previous_draft"] == json.loads(previous)
    assert packet["compiler_findings"] == ["compile:ValueError:route too weak"]
    assert packet["original_architect_request"]["task"]["prompt"] == "visible task"
    assert "observed_failure_codes" not in packet
    assert any("Re-read the visible task independently" in item for item in packet["review_contract"])
    assert any("live service or behavior" in item for item in packet["review_contract"])

    second, second_errors = architect.correct(
        {"schema_version": "architect_request.v2"},
        previous_output=previous,
        findings=["another"],
    )
    assert second is None
    assert second_errors == ["workbench architect replacement limit exhausted"]
    assert len(calls) == 1
