from aether.pcr_verifier_prompt import PCR_VERIFIER_SEMANTIC_GUIDE
from aether.providers.azure_model import (
    _PCR_VERIFIER_DIRECT_TURN_SCHEMA,
    _PCR_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION,
    _VERIFIER_DIRECT_TURN_SCHEMA,
)


def test_thin_verifier_declares_disposable_world_fidelity_without_task_ontology() -> None:
    guide = PCR_VERIFIER_SEMANTIC_GUIDE
    assert "overlay is a filesystem snapshot" in guide
    assert "no parent processes, listeners, or network" in guide
    assert "Use live probes for live process/port/HTTP truth" in guide
    assert "raw_user_task" in guide
    assert "Prove the actual final boundary" in guide
    assert "Independently measure quantitative requirements" in guide
    assert "discriminating end-to-end interaction or state" in guide
    assert "provided generator, validator, reference, patch, specification, or transformation" in guide


def test_thin_verifier_declares_typed_direct_locator_semantics_at_tool_boundary() -> None:
    guide = _PCR_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION
    assert "probe_http=full http(s) URL" in guide
    assert "inside the current task/executor environment" in guide
    assert "DNS-resolution failure" in guide
    assert "does not establish directory contents" in guide
    assert "probe_port=port or host:port" in guide
    assert "observe_existing_process=actual command-line regex" in guide
    assert "Never use observe_existing_process for files, ports, or HTTP" in guide


def test_thin_verifier_schema_structurally_prevents_multi_ref_strength_laundering() -> None:
    pcr_defs = _PCR_VERIFIER_DIRECT_TURN_SCHEMA["$defs"]
    assert pcr_defs["completion_evidence"]["properties"]["inspection_refs"]["maxItems"] == 1
    assert pcr_defs["finding"]["properties"]["supporting_inspection_ids"]["maxItems"] == 1
    assert "maxItems" not in _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["completion_evidence"]["properties"]["inspection_refs"]
    assert "maxItems" not in _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["finding"]["properties"]["supporting_inspection_ids"]
    assert "at most one inspection ref" in _PCR_VERIFIER_NATIVE_TOOL_RESPONSE_INSTRUCTION


class _ProbeResult:
    def __init__(self, *, stdout: str = "", stderr: str = "", exit_code: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


class _MergedDiagnosticProcessExecutor:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def run_command(self, command: str, *, timeout_s: int = 30):
        self.commands.append(command)
        if command.startswith("pgrep "):
            # Reproduces Harbor transports that merge a missing-tool shell
            # diagnostic into stdout while preserving an overall zero exit via
            # the probe's `|| true` wrapper.
            return _ProbeResult(stdout="bash: line 1: pgrep: command not found\n")
        if command.startswith("ps ax "):
            return _ProbeResult(stdout="321 nginx: master process nginx -g daemon off;\n")
        raise AssertionError(f"unexpected probe command: {command}")


def test_process_probe_never_treats_merged_missing_tool_diagnostic_as_live_process() -> None:
    from aether.verifier_probes import probe_process

    executor = _MergedDiagnosticProcessExecutor()
    result = probe_process(executor, "nginx")

    assert result["running"] is True
    assert result["match_count"] == 1
    assert result["matches"] == ["321 nginx: master process nginx -g daemon off;"]
    assert len(executor.commands) == 2
    assert executor.commands[0].startswith("pgrep ")
    assert executor.commands[1].startswith("ps ax ")
    assert all("command not found" not in row for row in result["matches"])


class _BothListingsMergedUnavailableExecutor:
    def __init__(self, *, proc_stdout: str = "", proc_exit: int = 0) -> None:
        self.commands: list[str] = []
        self.proc_stdout = proc_stdout
        self.proc_exit = proc_exit

    def run_command(self, command: str, *, timeout_s: int = 30):
        self.commands.append(command)
        if command.startswith("pgrep "):
            return _ProbeResult(stdout="sh: pgrep: command not found\n")
        if command.startswith("ps ax "):
            return _ProbeResult(stdout="sh: ps: command not found\n")
        if command.startswith("python3 -c "):
            return _ProbeResult(stdout=self.proc_stdout, exit_code=self.proc_exit)
        raise AssertionError(f"unexpected probe command: {command}")


def test_process_probe_falls_through_merged_missing_tools_to_procfs_result() -> None:
    from aether.verifier_probes import probe_process

    executor = _BothListingsMergedUnavailableExecutor(
        proc_stdout="777 nginx: worker process\n", proc_exit=0,
    )
    result = probe_process(executor, "nginx")

    assert result["running"] is True
    assert result["matches"] == ["777 nginx: worker process"]
    assert len(executor.commands) == 3
    assert executor.commands[-1].startswith("python3 -c ")


def test_process_probe_reports_unknown_when_all_listing_routes_are_unavailable() -> None:
    from aether.verifier_probes import probe_process

    executor = _BothListingsMergedUnavailableExecutor(
        proc_stdout="AETHER_PROC_UNAVAILABLE\n", proc_exit=5,
    )
    result = probe_process(executor, "nginx")

    assert result["running"] is False
    assert result["state"] == "unknown"
    assert result["match_count"] == 0
    assert result["matches"] == []
    assert result["error"] == "tool_unavailable: process listing unavailable"
    assert len(executor.commands) == 3
