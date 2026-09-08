from __future__ import annotations

from aether.compiler_prefix import pcr_model_environment_probe
from aether.environment_probe import probe_environment
from aether.execution import CommandResult, MemoryExecutor
from aether.resource_probe import probe_live_resources


class _ResourceExecutor(MemoryExecutor):
    def __init__(self) -> None:
        super().__init__(workspace_root="/app")
        self.command_history = []

    def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30) -> CommandResult:
        del cwd, timeout_s
        self.command_history.append(command)
        if command.startswith("for c in "):
            return CommandResult(
                command=command,
                exit_code=0,
                stdout="python3\t/usr/bin/python3\nnvidia-smi\t/usr/bin/nvidia-smi\n",
            )
        if "path_rest=\"${PATH}:\"" in command:
            return CommandResult(command=command, exit_code=0, stdout="")
        if "import importlib.util" in command:
            return CommandResult(
                command=command,
                exit_code=0,
                stdout='{"executable":"/usr/bin/python3","version":"3.11.0","modules":{}}',
            )
        if "pkgutil.iter_modules" in command:
            return CommandResult(command=command, exit_code=0, stdout='{"modules":[]}')
        if "site_packages" in command:
            return CommandResult(command=command, exit_code=0, stdout="{}")
        if "-m pip --version" in command:
            return CommandResult(command=command, exit_code=1)
        if "curl -Is" in command:
            return CommandResult(command=command, exit_code=1)
        if "getconf _NPROCESSORS_ONLN" in command:
            return CommandResult(command=command, exit_code=0, stdout="16\n")
        if "/sys/fs/cgroup/cpu.max" in command:
            return CommandResult(command=command, exit_code=0, stdout="800000 100000\n")
        if "/proc/meminfo" in command:
            return CommandResult(command=command, exit_code=0, stdout=str(64 * 1024**3) + "\n")
        if "/sys/fs/cgroup/memory.max" in command:
            return CommandResult(command=command, exit_code=0, stdout=str(24 * 1024**3) + "\n")
        if command.startswith("df -Pk"):
            return CommandResult(command=command, exit_code=0, stdout="104857600 26214400 78643200\n")
        if command.startswith("nvidia-smi --query-gpu"):
            return CommandResult(
                command=command,
                exit_code=0,
                stdout="0, NVIDIA H100 80GB HBM3, 81559\n1, NVIDIA H100 80GB HBM3, 81559\n",
            )
        return CommandResult(command=command, exit_code=0, stdout="")


class _NoGpuExecutor(_ResourceExecutor):
    def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30) -> CommandResult:
        if command.startswith("for c in "):
            return CommandResult(command=command, exit_code=0, stdout="python3\t/usr/bin/python3\n")
        return super().run_command(command, cwd=cwd, timeout_s=timeout_s)


def test_live_resource_probe_reports_effective_container_limits_and_gpu_identity() -> None:
    executor = _ResourceExecutor()
    resources = probe_live_resources(
        executor,
        workspace_root="/app",
        command_names={"nvidia-smi": {"available": True, "path": "/usr/bin/nvidia-smi"}},
    )
    assert resources["schema_version"] == "resource_probe.v1"
    assert resources["authority"] == "live_environment_observation"
    assert resources["cpu"]["logical_cores"] == 16
    assert resources["cpu"]["cgroup_v2_quota_cores"] == 8.0
    assert resources["cpu"]["effective_cores"] == 8.0
    assert resources["memory"]["visible_total_bytes"] == 64 * 1024**3
    assert resources["memory"]["cgroup_v2_limit_bytes"] == 24 * 1024**3
    assert resources["memory"]["effective_limit_bytes"] == 24 * 1024**3
    assert resources["storage"]["workspace_total_bytes"] == 104857600 * 1024
    assert resources["storage"]["workspace_available_bytes"] == 78643200 * 1024
    assert resources["gpu"]["status"] == "probed_present"
    assert resources["gpu"]["device_count"] == 2
    assert resources["gpu"]["devices"][0] == {
        "index": 0,
        "name": "NVIDIA H100 80GB HBM3",
        "memory_total_mib": 81559,
    }


def test_gpu_command_unavailable_is_unknown_capacity_not_false_zero_devices() -> None:
    resources = probe_live_resources(
        _NoGpuExecutor(),
        workspace_root="/app",
        command_names={"nvidia-smi": {"available": False, "path": ""}},
    )
    assert resources["gpu"] == {
        "status": "command_unavailable",
        "backend": "nvidia-smi",
        "device_count": None,
        "devices": [],
    }


def test_environment_probe_includes_live_resources_without_task_semantic_routing() -> None:
    probe = probe_environment(_ResourceExecutor(), workspace_root="/app")
    assert probe["resources"]["gpu"]["device_count"] == 2
    assert probe["resources"]["cpu"]["effective_cores"] == 8.0
    assert "instruction" not in probe["resources"]
    assert "task" not in probe["resources"]


def test_pcr_projection_preserves_resource_truth_exactly() -> None:
    probe = probe_environment(_ResourceExecutor(), workspace_root="/app")
    projected = pcr_model_environment_probe(probe)
    assert projected["resources"] == probe["resources"]


def test_live_resource_probe_has_no_benchmark_or_task_specific_strategy() -> None:
    from pathlib import Path
    source = (Path(__file__).parents[1] / "aether" / "resource_probe.py").read_text(encoding="utf-8").lower()
    for forbidden in (
        "frontier-bench",
        "medical-claims-processing",
        "exam-pdf-eval",
        "freecad-spring-clip",
        "satb-audio-transcription",
    ):
        assert forbidden not in source
