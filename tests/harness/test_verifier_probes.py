"""Generic verifier probes: live service/port/process and media/artifact
inspection, all read-only, all executed through the run's executor substrate.
"""
from __future__ import annotations

import http.server
import socket
import tempfile
import threading
from pathlib import Path

import pytest

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.execution import CommandResult
from aether.ledger import ExecutionLedger, Receipt
from aether.providers.azure_model import _VERIFIER_DIRECT_TURN_SCHEMA
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.verifier_inspector import (
    VerifierInspectionProtocolError,
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
    parse_verifier_inspection_requests,
)
from aether.verifier_probes import (
    inspect_artifact_probe,
    probe_http,
    probe_port,
    probe_process,
)

# 1x1 transparent PNG.
_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f030005fe02fea72d1e480000000049454e44ae426082"
)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _ScriptedExecutor:
    def __init__(self, results: tuple[CommandResult, ...]) -> None:
        self._results = list(results)

    def run_command(self, command: str, *, timeout_s: int = 30) -> CommandResult:
        assert self._results, command
        return self._results.pop(0)


def test_probe_port_open_and_closed() -> None:
    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        open_port = server.getsockname()[1]
        try:
            result = probe_port(executor, f"127.0.0.1:{open_port}")
            assert result["state"] == "open", result
        finally:
            server.close()
        closed = probe_port(executor, str(_free_port()))
        assert closed["state"] == "closed", closed
        bad = probe_port(executor, "not-a-port")
        assert "error" in bad


def test_probe_http_live_server_and_unreachable() -> None:
    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/missing":
                    body = b"NEGATIVE_HTTP_MARKER"
                    self.send_response(404)
                else:
                    body = b"SERVICE_BODY_MARKER"
                    self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = probe_http(executor, f"http://127.0.0.1:{port}/")
            assert result["reachable"] is True
            assert result["status"] == 200
            assert result["response_observed"] is True
            assert "SERVICE_BODY_MARKER" in result["body_head"]
            negative = probe_http(executor, f"http://127.0.0.1:{port}/missing")
            assert negative["reachable"] is True
            assert negative["response_observed"] is True
            assert negative["status"] == 404
            assert "NEGATIVE_HTTP_MARKER" in negative["body_head"]
        finally:
            server.shutdown()
        dead = probe_http(executor, f"http://127.0.0.1:{_free_port()}/")
        assert dead["reachable"] is False


def test_probe_process_finds_live_process() -> None:
    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)
        # This test's own interpreter is a guaranteed-live python process.
        result = probe_process(executor, "python")
        if result.get("state") == "unknown":
            assert result["running"] is False
            assert "tool_unavailable" in result["error"]
            return
        assert result["running"] is True
        assert result["match_count"] >= 1
        missing = probe_process(executor, "definitely_not_a_process_name_xyz123")
        assert missing["running"] is False


def test_probe_process_falls_back_to_procfs_when_pgrep_and_ps_are_missing() -> None:
    executor = _ScriptedExecutor(
        (
            CommandResult(command="pgrep", exit_code=127, stderr="pgrep: command not found\n"),
            CommandResult(command="ps", exit_code=127, stderr="ps: command not found\n"),
            CommandResult(
                command="python3",
                exit_code=0,
                stdout="42 python3 -m flask run\n99 worker --serve\n",
            ),
        )
    )
    result = probe_process(executor, "python")
    assert result["running"] is True
    assert result["match_count"] == 2
    assert result["matches"][0].startswith("42 python3")
    assert "error" not in result


def test_probe_process_procfs_fallback_reports_truthfully_when_procfs_unavailable() -> None:
    executor = _ScriptedExecutor(
        (
            CommandResult(command="pgrep", exit_code=127, stderr="pgrep: command not found\n"),
            CommandResult(command="ps", exit_code=127, stderr="ps: command not found\n"),
            CommandResult(command="python3", exit_code=5, stdout="AETHER_PROC_UNAVAILABLE\n"),
        )
    )
    result = probe_process(executor, "python")
    assert result["state"] == "unknown"
    assert result["running"] is False
    assert result["match_count"] == 0
    assert result["error"] == "tool_unavailable: process listing unavailable"


def test_probe_process_reports_unknown_when_process_listing_is_denied() -> None:
    executor = _ScriptedExecutor(
        (
            CommandResult(
                command="pgrep",
                exit_code=0,
                stderr="pgrep: Cannot get process list\nsysmon request failed with error: sysmond service not found\n",
            ),
            CommandResult(command="ps", exit_code=0, stderr="ps: operation not permitted\n"),
            CommandResult(command="python3", exit_code=5, stdout="AETHER_PROC_UNAVAILABLE\n"),
        )
    )
    result = probe_process(executor, "python")
    assert result["state"] == "unknown"
    assert result["running"] is False
    assert result["match_count"] == 0
    assert "tool_unavailable" in result["error"]


def test_inspect_artifact_probe_binary_and_text() -> None:
    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)
        png = Path(root, "image.png")
        png.write_bytes(_PNG_BYTES)
        result = inspect_artifact_probe(executor, "image.png")
        assert result["exists"] is True
        assert "png" in result["file_type"].lower() or "image" in result["file_type"].lower()
        assert result["size_bytes"] == str(len(_PNG_BYTES))
        assert len(result["sha256"]) == 64

        Path(root, "notes.txt").write_text("ARTIFACT_TEXT_MARKER\nline two\n")
        text = inspect_artifact_probe(executor, "notes.txt")
        assert text["exists"] is True
        assert "ARTIFACT_TEXT_MARKER" in text.get("content_head", "")

        missing = inspect_artifact_probe(executor, "no_such_file.bin")
        assert missing["exists"] is False


def test_probe_kinds_dispatch_through_inspector_and_never_mutate() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "artifact.txt").write_text("data")
        env = EnvMap(
            task_prompt="Serve the thing.",
            workspace_root=root,
            capabilities={
                "shell": CapabilityDescriptor("shell", "Run commands"),
                "filesystem": CapabilityDescriptor("filesystem", "Files"),
            },
        )
        ir = RuntimeConfigIR(
            architect_summary="probe test",
            solver_identity_prompt="solver",
            verifier_identity_prompt="verifier",
            selected_capabilities=("shell", "filesystem"),
        )
        compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(ir, env)
        executor = SubprocessExecutor(root)
        before = sorted(p.name for p in Path(root).iterdir())
        results = execute_verifier_inspection_requests(
            (
                VerifierInspectionRequest(request_id="p1", kind="probe_process", target="python"),
                VerifierInspectionRequest(request_id="p2", kind="probe_port", target=str(_free_port())),
                VerifierInspectionRequest(request_id="p3", kind="inspect_artifact", path="artifact.txt"),
            ),
            compiled=compiled,
            ledger=ExecutionLedger(),
            executor=executor,
            envmap=env,
        )
        by_id = {row["request_id"]: row for row in results}
        if by_id["p1"].get("state") == "unknown":
            assert by_id["p1"]["running"] is False
            assert "tool_unavailable" in by_id["p1"]["error"]
        else:
            assert by_id["p1"]["running"] is True
        assert by_id["p2"]["state"] == "closed"
        assert by_id["p3"]["exists"] is True
        assert all(row.get("read_only") for row in results)
        assert sorted(p.name for p in Path(root).iterdir()) == before


def test_inspection_request_parser_accepts_first_json_object_only() -> None:
    raw = (
        '{"kind":"inspect","requests":[{"kind":"read_file","path":"out.txt","request_id":"r1"}]}'
        '{"verdict":"uncertain_missing_evidence","confidence":"high","summary":"later object"}'
    )
    requests = parse_verifier_inspection_requests(raw)
    assert len(requests) == 1
    assert requests[0].kind == "read_file"
    assert requests[0].path == "out.txt"


def test_inspection_request_parser_aliases_run_check_to_rerun_check() -> None:
    requests = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{"kind": "run_check", "check_id": "c1", "request_id": "r1"}],
    })
    assert requests[0].kind == "rerun_check"


def test_inspection_request_parser_rejects_overfull_or_untyped_overlay_requests() -> None:
    with pytest.raises(ValueError, match="maximum of 12"):
        parse_verifier_inspection_requests({
            "kind": "inspect",
            "requests": [
                {"kind": "read_file", "path": f"file-{index}", "request_id": f"r-{index}"}
                for index in range(13)
            ],
        })

    with pytest.raises(ValueError, match="top-level kind='overlay_run_command'"):
        parse_verifier_inspection_requests({
            "kind": "inspect",
            "requests": [{
                "request_id": "derive",
                "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
            }],
        })


def test_overlay_command_request_requires_provenance_bound_plan_and_execution() -> None:
    with pytest.raises(ValueError, match="verification_plan object"):
        parse_verifier_inspection_requests({
            "kind": "inspect",
            "requests": [{
                "kind": "overlay_run_command",
                "request_id": "derive",
                "command": "python3 derive.py",
            }],
        })

    with pytest.raises(ValueError, match="authoritative_source_refs"):
        parse_verifier_inspection_requests({
            "kind": "inspect",
            "requests": [{
                "kind": "overlay_run_command",
                "request_id": "derive",
                "verification_plan": {
                    "claim": "The reported values match the source data.",
                    "authoritative_source_refs": None,
                    "method_summary": "Parse the structured field.",
                    "proxy_risk": "Free text can look similar.",
                },
                "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
            }],
        })


def test_v3_overlay_command_rejects_legacy_source_refs_without_derived_binding() -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_verifier_inspection_requests({
            "kind": "inspect",
            "requests": [{
                "request_id": "derive",
                "kind": "overlay_run_command",
                "verification_plan": {
                    "claim": "check value",
                    "authoritative_source_refs": ["inspection:old"],
                    "method_summary": "parse it",
                    "proxy_risk": "proxy risk",
                },
                "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
            }],
        }, require_derived_contract=True)
    assert "verification_plan.evidence_mode" in str(exc_info.value)
    assert "verification_plan.basis" in str(exc_info.value)
    assert "verification_plan.bound_input_refs" in str(exc_info.value)
    assert "verification_plan.authoritative_structure" in str(exc_info.value)
    assert "authoritative_source_refs is legacy-only in V3" in str(exc_info.value)

    request = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "kind": "overlay_run_command",
            "request_id": "derive",
                "verification_plan": {
                    "claim": "The reported values match the source data.",
                    "authoritative_source_refs": ["inspection:1:0:source"],
                    "authoritative_structure": "the observed structured field",
                    "method_summary": "Parse that field directly and aggregate it.",
                    "proxy_risk": "Free-text may contain value-like tokens.",
                },
            "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
        }],
    })[0]

    assert request.authoritative_source_refs == ("inspection:1:0:source",)
    assert request.method_summary == "Parse that field directly and aggregate it."
    assert request.proxy_risk == "Free-text may contain value-like tokens."


def test_v3_overlay_command_accepts_only_the_canonical_derived_shape() -> None:
    request = parse_verifier_inspection_requests({
        "kind": "inspect",
        "requests": [{
            "kind": "overlay_run_command",
            "request_id": "derive",
            "verification_plan": {
                "evidence_mode": "derived",
                "claim": "The reported values match the source data.",
                "authoritative_structure": "the observed structured field",
                "method_summary": "Parse the observed field directly and aggregate it.",
                "proxy_risk": "Free-text may contain value-like tokens.",
                "basis": [{"ref": "inspection:1:0:source", "supported_fact": "field layout"}],
                "bound_input_refs": ["inspection:1:0:source"],
            },
            "execution": {"kind": "overlay_run_command", "command": "python3 derive.py"},
        }],
    }, require_derived_contract=True)[0]

    assert request.evidence_mode == "derived"
    assert request.authoritative_source_refs == ()
    assert request.authoritative_structure == "the observed structured field"
    assert request.basis_refs == ("inspection:1:0:source",)


def test_read_file_inspection_supports_globbed_paths() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "logs").mkdir()
        Path(root, "logs", "a.log").write_text("A\n")
        Path(root, "logs", "b.log").write_text("B\n")
        env = EnvMap(
            task_prompt="t",
            workspace_root=root,
            capabilities={
                "shell": CapabilityDescriptor("shell", "Run commands"),
                "filesystem": CapabilityDescriptor("filesystem", "Files"),
            },
        )
        ir = RuntimeConfigIR(
            architect_summary="s",
            solver_identity_prompt="solver",
            verifier_identity_prompt="verifier",
            selected_capabilities=("shell", "filesystem"),
        )
        compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(ir, env)
        results = execute_verifier_inspection_requests(
            (VerifierInspectionRequest(request_id="r", kind="read_file", path="logs/*.log", limit=2),),
            compiled=compiled,
            ledger=ExecutionLedger(),
            executor=SubprocessExecutor(root),
            envmap=env,
        )
        assert sorted(results[0]["matched_paths"]) == ["logs/a.log", "logs/b.log"]
        assert [row["excerpt"] for row in results[0]["matches"]] == ["A\n", "B\n"]


def test_read_file_inspection_supports_offset_paging() -> None:
    with tempfile.TemporaryDirectory() as root:
        content = "A" * 5000 + "WINDOW_MARKER" + "B" * 5000
        Path(root, "big.txt").write_text(content)
        env = EnvMap(
            task_prompt="t",
            workspace_root=root,
            capabilities={
                "shell": CapabilityDescriptor("shell", "Run commands"),
                "filesystem": CapabilityDescriptor("filesystem", "Files"),
            },
        )
        ir = RuntimeConfigIR(
            architect_summary="s",
            solver_identity_prompt="solver",
            verifier_identity_prompt="verifier",
            selected_capabilities=("shell", "filesystem"),
        )
        compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(ir, env)
        results = execute_verifier_inspection_requests(
            (VerifierInspectionRequest(request_id="r", kind="read_file", path="big.txt", offset=5000),),
            compiled=compiled,
            ledger=ExecutionLedger(),
            executor=SubprocessExecutor(root),
            envmap=env,
        )
        assert results[0]["bytes"] == len(content)
        assert results[0]["offset"] == 5000
        assert results[0]["excerpt"].startswith("WINDOW_MARKER")


def test_verifier_can_read_command_output_handles() -> None:
    with tempfile.TemporaryDirectory() as root:
        env = EnvMap(
            task_prompt="t",
            workspace_root=root,
            capabilities={
                "shell": CapabilityDescriptor("shell", "Run commands"),
                "filesystem": CapabilityDescriptor("filesystem", "Files"),
            },
        )
        ir = RuntimeConfigIR(
            architect_summary="s",
            solver_identity_prompt="solver",
            verifier_identity_prompt="verifier",
            selected_capabilities=("shell", "filesystem"),
        )
        compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(ir, env)
        ledger = ExecutionLedger()
        ledger.record(Receipt(
            receipt_id="step-5:a-1:cmd",
            step=5,
            kind="run_command",
            success=True,
            summary="command exit=0",
            payload={
                "stdout_handle": "5:a-1:stdout",
                "stdout_full": "OUTPUT_TOML\njump_takeoff_frame_number = 107\nSPOT_AUDIT frame 104 score=10.9\n",
                "stderr_handle": "5:a-1:stderr",
                "stderr_full": "",
            },
        ))

        results = execute_verifier_inspection_requests(
            (VerifierInspectionRequest(request_id="r", kind="read_output", handle="5:a-1:stdout", span=200),),
            compiled=compiled,
            ledger=ledger,
            executor=SubprocessExecutor(root),
            envmap=env,
        )

        assert results[0]["source_receipt_id"] == "step-5:a-1:cmd"
        assert results[0]["stream"] == "stdout"
        assert "SPOT_AUDIT frame 104" in results[0]["excerpt"]
        assert results[0]["read_only"] is True


def test_verifier_read_output_uses_spooled_full_stream() -> None:
    with tempfile.TemporaryDirectory() as root:
        spool = Path(root, "stdout.spool")
        spool.write_text("A" * 5000 + "FRAME_TRANSCRIPT_MARKER" + "B" * 5000)
        env = EnvMap(
            task_prompt="t",
            workspace_root=root,
            capabilities={
                "shell": CapabilityDescriptor("shell", "Run commands"),
                "filesystem": CapabilityDescriptor("filesystem", "Files"),
            },
        )
        ir = RuntimeConfigIR(
            architect_summary="s",
            solver_identity_prompt="solver",
            verifier_identity_prompt="verifier",
            selected_capabilities=("shell", "filesystem"),
        )
        compiled = ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(ir, env)
        ledger = ExecutionLedger()
        ledger.record(Receipt(
            receipt_id="step-5:a-1:cmd",
            step=5,
            kind="run_command",
            success=True,
            summary="command exit=0",
            payload={
                "stdout_handle": "5:a-1:stdout",
                "stdout_full": "TRUNCATED",
                "stdout_overflow_path": str(spool),
            },
        ))

        results = execute_verifier_inspection_requests(
            (VerifierInspectionRequest(request_id="r", kind="read_output", handle="5:a-1:stdout", offset=5000, span=80),),
            compiled=compiled,
            ledger=ledger,
            executor=SubprocessExecutor(root),
            envmap=env,
        )

        assert results[0]["bytes"] == spool.stat().st_size
        assert results[0]["offset"] == 5000
        assert results[0]["excerpt"].startswith("FRAME_TRANSCRIPT_MARKER")


def test_inspect_artifact_probe_reports_file_mode_and_owner() -> None:
    """Permissions are first-class verifiable state (live gap: a correct
    openssl run could not be verified because no read-only surface exposed
    the key file's mode 600)."""
    import os

    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)
        key = Path(root, "server.key")
        key.write_text("PRIVATE KEY")
        os.chmod(key, 0o600)
        result = inspect_artifact_probe(executor, "server.key")
        assert result["exists"] is True
        assert result["mode"] == "600", result
        assert result["owner"]
        assert result["mtime_epoch"].isdigit()


def _archived_harmony_read_report_request():
    return {
        "kind": "inspect",
        "requests": [{
            "check_id": "report_file_exact_content",
            "clause_ids": ["report_file_exact_content"],
            "handle": "file:report.txt",
            "kind": "read_file",
            "limit": 1,
            "offset": 0,
            "path": "report.txt",
            "receipt_kind": "artifact",
            "request_id": "read-report",
            "verification_plan": {
                "authoritative_structure": "the bytes of report.txt",
                "basis": [{
                    "ref": "inspection:state-inspection-handles",
                    "supported_fact": "the workspace snapshot includes a handle for report.txt",
                }],
                "bound_input_refs": ["inspection:state-inspection-handles"],
                "claim": "report.txt contains exactly the single line status: ready, with an optional trailing newline",
                "clause_ids": ["report_file_exact_content"],
                "evidence_mode": "direct",
                "method_summary": "read the file contents directly and compare against the required exact line",
                "proxy_risk": "filename and byte size could match while the actual bytes differ",
            },
        }],
    }


def test_direct_read_file_accepts_schema_valid_descriptive_clause_tags() -> None:
    request = parse_verifier_inspection_requests(_archived_harmony_read_report_request())[0]
    assert request.kind == "read_file"
    assert request.path == "report.txt"
    assert request.clause_ids == ("report_file_exact_content",)


def test_archived_harmony_file_verifier_inspection_parses_without_correction() -> None:
    requests = parse_verifier_inspection_requests(_archived_harmony_read_report_request())
    assert len(requests) == 1
    assert requests[0].request_id == "read-report"
    assert requests[0].clause_ids == ("report_file_exact_content",)


def test_provider_schema_requires_nullable_proof_ids_on_every_inspection_request() -> None:
    request_schema = _VERIFIER_DIRECT_TURN_SCHEMA["$defs"]["inspection_request"]
    assert "proof_ids" in request_schema["required"]
    assert "proof_ids" in request_schema["properties"]



def test_v3_overlay_command_rejects_conflicting_legacy_command_surface() -> None:
    payload = {
        "kind": "inspect",
        "requests": [{
            "kind": "overlay_run_command",
            "request_id": "derive",
            "command": "python3 wrong-surface.py",
            "verification_plan": {
                "evidence_mode": "derived",
                "claim": "independent behavior matches",
                "authoritative_structure": "observed source bytes",
                "method_summary": "execute an independent behavioral check",
                "proxy_risk": "a proxy may agree accidentally",
                "basis": [{"ref": "inspection:1:0:source", "supported_fact": "source observed"}],
                "bound_input_refs": ["inspection:1:0:source"],
            },
            "execution": {
                "kind": "overlay_run_command",
                "command": "python3 -c 'print(1)'",
            },
        }],
    }
    with pytest.raises(VerifierInspectionProtocolError) as exc_info:
        parse_verifier_inspection_requests(payload, require_derived_contract=True)
    assert "top-level command is legacy-only in V3" in str(exc_info.value)
