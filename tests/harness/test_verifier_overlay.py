"""Sandboxed verifier overlay: checks and fixtures execute against a copy,
the solver workspace is never mutated, and rollback is unconditional.
"""
from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.inspection_registry import register_inspection_results
from aether.ledger import ExecutionLedger
from aether.execution import CommandResult
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.verifier_inspector import (
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
)
from aether.verifier_overlay import VerifierOverlay
from aether.verifier_budget import VerifierPhaseBudget, VerifierPhaseState


def _env(root: str, hints: dict | None = None) -> EnvMap:
    return EnvMap(
        task_prompt="Produce out.txt.",
        workspace_root=root,
        capabilities={
            "shell": CapabilityDescriptor("shell", "Run commands"),
            "filesystem": CapabilityDescriptor("filesystem", "Files"),
        },
        grader_hints=dict(hints or {}),
    )


def _compiled(env: EnvMap, *, check_plan: tuple[str, ...] = ()) -> object:
    ir = RuntimeConfigIR(
        architect_summary="overlay test",
        solver_identity_prompt="solver",
        verifier_identity_prompt="verifier",
        selected_capabilities=("shell", "filesystem"),
        check_plan=check_plan,
    )
    return ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(ir, env)


def test_overlay_command_mutations_are_discarded_between_fresh_children() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "original.txt").write_text("solver data")
        executor = SubprocessExecutor(root)
        overlay = VerifierOverlay(executor, root)
        try:
            result = overlay.run_command(
                "cat original.txt && touch VERIFIER_MARKER && rm original.txt && echo mutated"
            )
            assert result["success"], result
            assert result["execution_isolation"] == "fresh_child_from_pristine_overlay"
            assert result["command_child_removed"] is True
            assert "solver data" in result["stdout"]

            # A later verifier command starts from the pristine copy, not from
            # the first command's mutated filesystem.
            check = overlay.run_command("ls")
            assert check["success"], check
            assert "VERIFIER_MARKER" not in check["stdout"]
            assert "original.txt" in check["stdout"]

            # The Solver workspace is also untouched.
            assert Path(root, "original.txt").read_text() == "solver data"
            assert not Path(root, "VERIFIER_MARKER").exists()
        finally:
            overlay.teardown()


def test_write_fixture_is_materialized_only_when_explicitly_selected() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "tool.py").write_text("import sys; print(sys.stdin.read().upper())")
        executor = SubprocessExecutor(root)
        overlay = VerifierOverlay(executor, root)
        fixture = overlay.write_fixture("fixtures/case1.txt", "verifier input\n")
        assert fixture.get("registered") is True, fixture
        assert fixture.get("written") is False, fixture
        assert fixture.get("success") is True, fixture
        assert fixture["materialization"] == "deferred_until_explicitly_bound_command"

        # Registration alone does not mutate the pristine copy or a command child.
        unbound = overlay.run_command("test ! -e fixtures/case1.txt")
        assert unbound["success"] is True, unbound
        assert unbound["materialized_fixture_paths"] == []

        bound = overlay.run_command(
            "python3 tool.py < fixtures/case1.txt",
            fixture_paths=("fixtures/case1.txt",),
        )
        assert bound["success"] is True, bound
        assert bound["materialized_fixture_paths"] == ["fixtures/case1.txt"]
        assert "VERIFIER INPUT" in bound["stdout"]

        # Fixture never appears in the Solver workspace or pristine copy.
        assert not Path(root, "fixtures").exists()
        overlay_root = overlay.overlay_root
        assert overlay_root and Path(overlay_root).exists()
        assert not Path(overlay_root, "fixtures", "case1.txt").exists()
        teardown = overlay.teardown()
        assert teardown["removed"] is True
        assert not Path(overlay_root).exists()
        assert overlay.teardown() == {"removed": False}


def test_overlay_command_keeps_decisive_tail_when_output_exceeds_inline_cap() -> None:
    with tempfile.TemporaryDirectory() as root:
        overlay = VerifierOverlay(SubprocessExecutor(root), root)
        try:
            result = overlay.run_command(
                "printf 'HEAD_MARKER\\n'; "
                "python3 -c \"print('x' * 5000)\"; "
                "printf 'DECISIVE_TOTALS=verified\\n'"
            )

            assert result["success"] is True
            assert result["stdout_truncated"] is True
            assert result["stdout_bytes"] > len(result["stdout"])
            assert "HEAD_MARKER" in result["stdout"]
            assert "DECISIVE_TOTALS=verified" in result["stdout"]
            assert "tail follows" in result["stdout"]
        finally:
            overlay.teardown()


def test_fixture_cannot_overwrite_existing_task_artifact() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "target.pyz").write_bytes(b"authoritative")
        overlay = VerifierOverlay(SubprocessExecutor(root), root)
        try:
            result = overlay.write_fixture("target.pyz", "")
            assert result["collision"] is True
            assert "collides with existing task entry" in result["error"]
            assert Path(root, "target.pyz").read_bytes() == b"authoritative"
            probe = overlay.run_command("cat target.pyz")
            assert probe["success"] is True
            assert probe["stdout"] == "authoritative"
        finally:
            overlay.teardown()


def test_duplicate_fixture_path_registration_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as root:
        overlay = VerifierOverlay(SubprocessExecutor(root), root)
        try:
            first = overlay.write_fixture("fixtures/input.txt", "one")
            second = overlay.write_fixture("fixtures/input.txt", "two")
            assert first["success"] is True
            assert "already registered" in second["error"]
            run = overlay.run_command("cat fixtures/input.txt", fixture_paths=("fixtures/input.txt",))
            assert run["stdout"] == "one"
        finally:
            overlay.teardown()


def test_only_explicitly_selected_fixture_paths_enter_command_child() -> None:
    with tempfile.TemporaryDirectory() as root:
        overlay = VerifierOverlay(SubprocessExecutor(root), root)
        try:
            assert overlay.write_fixture("fixtures/a.txt", "A")["success"] is True
            assert overlay.write_fixture("fixtures/b.txt", "B")["success"] is True
            run = overlay.run_command(
                "cat fixtures/a.txt; test ! -e fixtures/b.txt",
                fixture_paths=("fixtures/a.txt",),
            )
            assert run["success"] is True, run
            assert run["stdout"] == "A"
            assert run["materialized_fixture_paths"] == ["fixtures/a.txt"]
        finally:
            overlay.teardown()


def test_fixture_path_escapes_are_rejected() -> None:
    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)
        overlay = VerifierOverlay(executor, root)
        try:
            result = overlay.write_fixture("../escape.txt", "nope")
            assert "error" in result
            assert not Path(root).parent.joinpath("escape.txt").exists()
        finally:
            overlay.teardown()


def test_overlay_rejects_source_symlink_that_escapes_workspace() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "outside-link").symlink_to("/etc")
        overlay = VerifierOverlay(SubprocessExecutor(root), root)

        result = overlay.ensure()

        assert result["error"].startswith("overlay_symlink_escape_rejected")


def test_overlay_dispatches_app_paths_to_fresh_child_virtual_workspace_capability() -> None:
    class _VirtualExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def run_command_with_virtual_workspace(self, command: str, *, virtual_workspace_root: str, timeout_s: int) -> CommandResult:
            self.calls.append((command, virtual_workspace_root))
            return CommandResult(command=command, exit_code=0, stdout="mounted")

    class _ParentExecutor:
        def __init__(self, root: str) -> None:
            self.real = SubprocessExecutor(root)
            self.virtual_children: list[_VirtualExecutor] = []

        def run_command(self, command: str, *, timeout_s: int) -> CommandResult:
            return self.real.run_command(command, timeout_s=timeout_s)

        def for_workspace(self, workspace: str):
            if ".command_" in workspace:
                child = _VirtualExecutor()
                self.virtual_children.append(child)
                return child
            return self.real.for_workspace(workspace)

    with tempfile.TemporaryDirectory() as root:
        Path(root, "input.txt").write_text("source")
        parent = _ParentExecutor(root)
        overlay = VerifierOverlay(parent, root)
        try:
            result = overlay.run_command("cat /app/input.txt")

            assert result["success"] is True
            assert len(parent.virtual_children) == 1
            assert parent.virtual_children[0].calls == [("cat /app/input.txt", "/app")]
            assert result["command_child_removed"] is True
        finally:
            overlay.teardown()


def test_rerun_check_inspection_routes_through_overlay() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "out.txt").write_text("OK")
        env = _env(root, hints={"verify_commands": ["test -e out.txt && touch check_side_effect"]})
        _, eval_index = ConfigCompiler(CapabilityRegistry.from_envmap(env)).analyze_envmap(env)
        check_id = eval_index.checks[0].check_id
        compiled = _compiled(env, check_plan=(check_id,))
        executor = SubprocessExecutor(root)
        overlay = VerifierOverlay(executor, root)
        try:
            results = execute_verifier_inspection_requests(
                (VerifierInspectionRequest(request_id="r1", kind="rerun_check", check_id=check_id),),
                compiled=compiled,
                ledger=ExecutionLedger(),
                executor=executor,
                envmap=env,
                overlay=overlay,
            )
            assert results[0]["success"] is True
            assert results[0]["executed_in"] == "verifier_overlay"
            # The check's side effect stayed in the overlay.
            assert not Path(root, "check_side_effect").exists()
        finally:
            overlay.teardown()


def test_rerun_check_without_overlay_is_an_explicit_error_not_a_workspace_run() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "out.txt").write_text("OK")
        env = _env(root, hints={"verify_commands": ["touch must_not_exist"]})
        _, eval_index = ConfigCompiler(CapabilityRegistry.from_envmap(env)).analyze_envmap(env)
        check_id = eval_index.checks[0].check_id
        compiled = _compiled(env, check_plan=(check_id,))
        results = execute_verifier_inspection_requests(
            (VerifierInspectionRequest(request_id="r1", kind="rerun_check", check_id=check_id),),
            compiled=compiled,
            ledger=ExecutionLedger(),
            executor=SubprocessExecutor(root),
            envmap=env,
            overlay=None,
        )
        assert "error" in results[0]
        assert not Path(root, "must_not_exist").exists()


def test_overlay_result_budget_counts_observation_not_repeated_command() -> None:
    with tempfile.TemporaryDirectory() as root:
        overlay = VerifierOverlay(SubprocessExecutor(root), root)
        try:
            command = (
                "python3 - <<'PY'\n"
                "print('x' * 9000)\n"
                "PY\n# " + ("long-verifier-method " * 240)
            )
            result = overlay.run_command(command)

            assert result["success"] is True
            assert result["stdout_truncated"] is True
            assert "command" not in result
            assert result["command_bytes"] == len(command.encode("utf-8"))
            assert len(result["command_sha256"]) == 64
            # This is the exact failure boundary from the G-code control: a
            # bounded ~4 KB observation plus a multi-KB command must not be
            # rejected merely because the command was duplicated in the result.
            VerifierPhaseState(VerifierPhaseBudget()).validate_results(
                (result,), elapsed_s=0.1,
            )
        finally:
            overlay.teardown()


def test_registered_overlay_observation_with_long_method_fits_default_budget() -> None:
    with tempfile.TemporaryDirectory() as root:
        env = _env(root)
        compiled = _compiled(env)
        executor = SubprocessExecutor(root)
        overlay = VerifierOverlay(executor, root)
        ledger = ExecutionLedger()
        command = (
            "python3 - <<'PY'\n"
            "print('y' * 9000)\n"
            "PY\n# " + ("geometry-parser-step " * 240)
        )
        request = VerifierInspectionRequest(
            request_id="long-derived",
            kind="overlay_run_command",
            command=command,
        )
        try:
            raw_rows = execute_verifier_inspection_requests(
                (request,),
                compiled=compiled,
                ledger=ledger,
                executor=executor,
                envmap=env,
                overlay=overlay,
            )
            rows = register_inspection_results(
                (request,), raw_rows,
                ledger=ledger,
                step=4,
                requester="model_verifier",
                executor=executor,
                overlay=overlay,
                packet_signature="packet",
            )

            VerifierPhaseState(VerifierPhaseBudget()).validate_results(
                rows, elapsed_s=0.1,
            )
            assert rows[0]["stdout_truncated"] is True
            assert "command" not in rows[0]
            receipt = next(r for r in ledger.all_receipts() if r.kind == "inspection_record")
            assert receipt.payload["route_parameters"]["command"] == command
        finally:
            overlay.teardown()


class _F80IsolationCapableExecutor:
    """Unit-only executor proving overlay dispatch/metadata plumbing."""
    def __init__(self, root: str) -> None:
        self.real = SubprocessExecutor(root)
        self.isolated_calls: list[tuple[str, str]] = []

    def run_command(self, command: str, *, timeout_s: int) -> CommandResult:
        return self.real.run_command(command, timeout_s=timeout_s)

    def for_workspace(self, workspace: str):
        return self.real.for_workspace(workspace)

    def run_independent_verifier_command(self, command: str, *, workspace_root: str, timeout_s: int):
        self.isolated_calls.append((command, workspace_root))
        result = SubprocessExecutor(workspace_root).run_command(command, timeout_s=timeout_s)
        return {
            "result": result,
            "metadata": {
                "execution_isolation": "unit_independent_world",
                "isolation_backend": "unit_fake",
                "independent_isolation_verified": True,
                "isolation_cleanup_verified": True,
                "mount_namespace_private": True,
                "pid_namespace_private": True,
                "network_namespace_private": True,
            },
        }


def test_f80_required_overlay_dispatches_only_through_independent_runner() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "input.txt").write_text("solver")
        executor = _F80IsolationCapableExecutor(root)
        overlay = VerifierOverlay(executor, root, require_independent_isolation=True)
        try:
            result = overlay.run_command("cat input.txt; touch isolated-only")
            assert result["success"] is True, result
            assert result["stdout"] == "solver"
            assert result["independent_isolation_required"] is True
            assert result["independent_isolation_verified"] is True
            assert result["isolation_cleanup_verified"] is True
            assert result["execution_isolation"] == "unit_independent_world"
            assert result["isolation_backend"] == "unit_fake"
            assert len(executor.isolated_calls) == 1
            assert ".command_" in executor.isolated_calls[0][1]
            assert not Path(root, "isolated-only").exists()
        finally:
            overlay.teardown()


def test_f80_required_overlay_fails_closed_without_isolated_runner() -> None:
    with tempfile.TemporaryDirectory() as root:
        overlay = VerifierOverlay(SubprocessExecutor(root), root, require_independent_isolation=True)
        # On non-Linux the real executor reports the unavailable isolation
        # rather than falling back. On Linux this executor has the backend, so
        # use a deliberately stripped wrapper to prove the missing-method law.
        class _NoIsolation:
            def __init__(self, real): self.real = real
            def run_command(self, command: str, *, timeout_s: int): return self.real.run_command(command, timeout_s=timeout_s)
            def for_workspace(self, workspace: str): return self.real.for_workspace(workspace)
        overlay.teardown()
        overlay = VerifierOverlay(_NoIsolation(SubprocessExecutor(root)), root, require_independent_isolation=True)
        try:
            result = overlay.run_command("printf should-not-run")
            assert result["independent_isolation_required"] is True
            assert result["independent_isolation_verified"] is False
            assert "independent_isolation_unavailable" in result["error"]
            assert "should-not-run" not in str(result.get("stdout", ""))
        finally:
            overlay.teardown()


def test_f80_registry_requires_verified_isolation_for_persistent_executable_proof() -> None:
    request = VerifierInspectionRequest(request_id="iso", kind="rerun_check", check_id="check")
    executor = object()
    bad_ledger = ExecutionLedger()
    bad = register_inspection_results(
        (request,), ({
            "request_id": "iso", "kind": "rerun_check", "check_id": "check",
            "executed_in": "verifier_overlay", "observation_origin": "verifier_overlay",
            "exit_code": 0, "success": True,
            "independent_isolation_required": True,
            "independent_isolation_verified": False,
            "isolation_cleanup_verified": True,
        },),
        ledger=bad_ledger, step=1, requester="model_verifier", executor=executor,
        overlay=None, packet_signature="packet", require_independent_isolation=True,
    )[0]
    assert bad["observation_valid"] is False
    assert bad["admissibility"] == "exploratory"
    assert bad["eligible_for_proof"] is False
    assert bad["independent_isolation_required"] is True
    assert bad["independent_isolation_verified"] is False

    good_ledger = ExecutionLedger()
    good = register_inspection_results(
        (request,), ({
            "request_id": "iso", "kind": "rerun_check", "check_id": "check",
            "executed_in": "verifier_overlay", "observation_origin": "verifier_overlay",
            "exit_code": 0, "success": True,
            "independent_isolation_required": True,
            "independent_isolation_verified": True,
            "isolation_cleanup_verified": True,
            "execution_isolation": "unit_independent_world",
            "isolation_backend": "unit_fake",
        },),
        ledger=good_ledger, step=1, requester="model_verifier", executor=executor,
        overlay=None, packet_signature="packet", require_independent_isolation=True,
    )[0]
    assert good["observation_valid"] is True
    assert good["independent_isolation_verified"] is True
    assert good["execution_isolation"] == "unit_independent_world"


def test_f80_verified_isolated_negative_execution_remains_valid_observation() -> None:
    request = VerifierInspectionRequest(request_id="iso-neg", kind="rerun_check", check_id="check")
    ledger = ExecutionLedger()
    row = register_inspection_results(
        (request,), ({
            "request_id": "iso-neg", "kind": "rerun_check", "check_id": "check",
            "executed_in": "verifier_overlay", "observation_origin": "verifier_overlay",
            "exit_code": 1, "success": False,
            "independent_isolation_required": True,
            "independent_isolation_verified": True,
            "isolation_cleanup_verified": True,
            "execution_isolation": "unit_independent_world",
            "isolation_backend": "unit_fake",
        },),
        ledger=ledger, step=1, requester="model_verifier", executor=object(),
        overlay=None, packet_signature="packet", require_independent_isolation=True,
    )[0]
    assert row["observation_valid"] is True
    assert row["observed_outcome_success"] is False
    assert row["admissibility"] == "direct_admissible"
    assert row["eligible_for_proof"] is False


@pytest.mark.skipif(platform.system() != "Linux" or shutil.which("sudo") is None, reason="F80 namespace canary requires Linux sudo/unshare")
def test_f80_linux_namespace_hides_parent_pid_and_listener_and_rebinds_app() -> None:
    with tempfile.TemporaryDirectory() as root:
        Path(root, "authoritative.txt").write_text("SOURCE")
        parent = subprocess.Popen(["sleep", "60"])
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0)); listener.listen(1)
        port = listener.getsockname()[1]
        overlay = VerifierOverlay(SubprocessExecutor(root), root, require_independent_isolation=True)
        try:
            ready = overlay.ensure()
            assert not ready.get("error"), ready
            assert ready.get("created") is True, ready
            pristine_root = overlay.overlay_root
            assert pristine_root
            command = (
                f"test ! -e /proc/{parent.pid}/status; "
                "test \"$(cat /app/authoritative.txt)\" = SOURCE; "
                f"python3 -c \"import socket,sys;s=socket.socket();r=s.connect_ex(('127.0.0.1',{port}));print(r);sys.exit(0 if r else 9)\"; "
                f"printf solver-shadow > {root!r}/authoritative.txt; "
                f"printf pristine-shadow > {pristine_root!r}/authoritative.txt; "
                "printf isolated > /app/only-in-verifier.txt"
            )
            result = overlay.run_command(command)
            assert result["success"] is True, result
            assert result["independent_isolation_verified"] is True
            assert result["isolation_cleanup_verified"] is True
            assert result["mount_namespace_private"] is True
            assert result["pid_namespace_private"] is True
            assert result["network_namespace_private"] is True
            assert result["execution_isolation"] == "host_private_mount_pid_net_namespaces"
            assert not Path(root, "only-in-verifier.txt").exists()
            assert Path(root, "authoritative.txt").read_text() == "SOURCE"
            assert Path(pristine_root, "authoritative.txt").read_text() == "SOURCE"
        finally:
            overlay.teardown()
            listener.close()
            parent.terminate()
            try: parent.wait(timeout=3)
            except subprocess.TimeoutExpired: parent.kill(); parent.wait(timeout=3)


@pytest.mark.skipif(platform.system() != "Linux" or shutil.which("sudo") is None, reason="F80 namespace timeout canary requires Linux sudo/unshare")
def test_f80_linux_namespace_timeout_kills_isolated_pid_world() -> None:
    with tempfile.TemporaryDirectory() as root:
        overlay = VerifierOverlay(
            SubprocessExecutor(root), root,
            require_independent_isolation=True,
            max_command_timeout_s=30,
        )
        try:
            marker = "F80_TIMEOUT_" + uuid.uuid4().hex
            result = overlay.run_command(
                f"bash -c 'exec -a {marker} sleep 60'",
                timeout_s=1,
            )
            assert result["timed_out"] is True, result
            assert result["independent_isolation_verified"] is True
            assert result["isolation_cleanup_verified"] is True
            marker_bytes = marker.encode("utf-8")
            leaked: list[int] = []
            for proc_dir in Path("/proc").iterdir():
                if not proc_dir.name.isdigit():
                    continue
                try:
                    cmdline = (proc_dir / "cmdline").read_bytes()
                except OSError:
                    continue
                if marker_bytes in cmdline:
                    leaked.append(int(proc_dir.name))
            assert leaked == [], f"isolated process marker leaked after timeout: {leaked}"
        finally:
            overlay.teardown()
