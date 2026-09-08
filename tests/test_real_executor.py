"""Tests for SubprocessExecutor against a real temporary workspace."""
from __future__ import annotations

import os
import time
from pathlib import Path
import tempfile

import pytest

from aether.real_executor import (
    SubprocessExecutor, _snapshot_local_stats, _diff_local_stat_snapshots,
)
from aether.runtime_ir import EnvMap, CapabilityDescriptor


@pytest.fixture()
def workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture()
def executor(workspace: str) -> SubprocessExecutor:
    return SubprocessExecutor(workspace, default_timeout_s=30)


class TestReadWriteRoundtrip:
    def test_write_then_read(self, executor: SubprocessExecutor, workspace: str) -> None:
        executor.write_file("hello.txt", "world")
        content = executor.read_file("hello.txt")
        assert content == "world"

    def test_write_nested(self, executor: SubprocessExecutor) -> None:
        executor.write_file("sub/dir/file.txt", "nested")
        assert executor.read_file("sub/dir/file.txt") == "nested"

    def test_write_overwrites_a_read_only_existing_file(
        self, executor: SubprocessExecutor, workspace: str,
    ) -> None:
        """Regression for the openssl-selfsigned-cert environment bug found while
        verifying the Slice A repair-slice rerun: the workspace is bind-mounted
        into a Docker container that runs as root, so a run_command executed via
        docker exec can create/overwrite a file at this path as root before a
        later write_file call runs. Reproduced empirically on the VM: plain
        open(path, "w") on a file this process doesn't have write permission on
        raises PermissionError even though this process owns the enclosing
        directory (overwriting file CONTENTS needs permission on the file, not
        the directory). Approximated here with chmod 0o444 (unwritable by the
        owner) rather than true cross-UID ownership, since creating a root-owned
        file from a non-root test process isn't portable -- this reproduces the
        same permission-denied-on-write failure class the real bug hit.
        """
        path = os.path.join(workspace, "check_cert.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("original")
        os.chmod(path, 0o444)  # read-only, as a root-written file would appear
        if os.access(path, os.W_OK):
            pytest.skip("running as a user that bypasses file permission bits (e.g. root)")

        executor.write_file("check_cert.py", "overwritten")

        assert executor.read_file("check_cert.py") == "overwritten"

    def test_read_missing_raises(self, executor: SubprocessExecutor) -> None:
        with pytest.raises(FileNotFoundError):
            executor.read_file("nonexistent.txt")


class TestRunCommand:
    def test_echo(self, executor: SubprocessExecutor) -> None:
        result = executor.run_command("echo hi")
        assert result.exit_code == 0
        assert result.success
        assert "hi" in result.stdout

    def test_creates_file_in_produced_artifacts(
        self, executor: SubprocessExecutor, workspace: str
    ) -> None:
        result = executor.run_command("echo content > newfile.txt")
        assert result.exit_code == 0
        assert "newfile.txt" in result.produced_artifacts
        assert os.path.isfile(os.path.join(workspace, "newfile.txt"))

    def test_false_command(self, executor: SubprocessExecutor) -> None:
        result = executor.run_command("false")
        assert not result.success
        assert result.exit_code != 0

    def test_timeout(self, workspace: str) -> None:
        executor = SubprocessExecutor(workspace, default_timeout_s=30)
        result = executor.run_command("sleep 5", timeout_s=1)
        assert result.exit_code == 124
        assert not result.success
        assert "timed out" in result.stderr

    def test_modified_paths(self, executor: SubprocessExecutor) -> None:
        executor.write_file("existing.txt", "original")
        result = executor.run_command("echo modified > existing.txt")
        assert result.exit_code == 0
        assert "existing.txt" in result.modified_paths


class TestExistsAndGlob:
    def test_exists_true(self, executor: SubprocessExecutor) -> None:
        executor.write_file("present.txt", "here")
        assert executor.exists("present.txt")

    def test_exists_false(self, executor: SubprocessExecutor) -> None:
        assert not executor.exists("absent.txt")

    def test_glob_matches(self, executor: SubprocessExecutor) -> None:
        executor.write_file("a.py", "a")
        executor.write_file("b.py", "b")
        executor.write_file("c.txt", "c")
        matches = executor.glob("*.py")
        assert "a.py" in matches
        assert "b.py" in matches
        assert "c.txt" not in matches


class TestProcessLifecycle:
    def test_launch_probe_stop(self, executor: SubprocessExecutor) -> None:
        handle = executor.launch_process("sleeper", "sleep 60")
        assert handle.live
        assert handle.process_id.startswith("proc-")

        probe = executor.probe_process(handle.process_id)
        assert probe.live

        stopped = executor.stop_process(handle.process_id)
        assert stopped

        probe_after = executor.probe_process(handle.process_id)
        assert not probe_after.live

    def test_probe_not_found(self, executor: SubprocessExecutor) -> None:
        probe = executor.probe_process("nonexistent-id")
        assert not probe.live
        assert "not found" in probe.detail


class TestTerminalLifecycle:
    def test_host_terminal_is_real_tty_and_cursor_exact(
        self, executor: SubprocessExecutor, workspace: str, tmp_path,
    ) -> None:
        command = (
            "if [ -t 0 ] && [ -t 1 ]; then echo TTY=1; else echo TTY=0; fi; "
            "echo QUESTION; read answer; echo ANSWER=$answer; "
            "printf 'artifact=%s\\n' \"$answer\" > terminal-result.txt"
        )
        handle = executor.start_terminal_session("host", command)
        assert handle.live
        assert handle.process_group_id == handle.pid
        assert handle.session_leader_id == handle.pid

        first_deadline = time.monotonic() + 15.0
        first_chunks: list[str] = []
        first = executor.terminal_read(handle.session_id, max_bytes=4096, wait_ms=1000)
        first_chunks.append(first.output)
        while "QUESTION" not in "".join(first_chunks) and time.monotonic() < first_deadline:
            first = executor.terminal_read(handle.session_id, max_bytes=4096, wait_ms=1000)
            first_chunks.append(first.output)
        first_output = "".join(first_chunks)
        assert "TTY=1" in first_output
        assert "QUESTION" in first_output
        assert first.cursor == sum(len(chunk.encode("utf-8")) for chunk in first_chunks)

        sent = executor.terminal_send(handle.session_id, "hello")
        assert sent.bytes_sent == 6
        second_deadline = time.monotonic() + 15.0
        second_chunks: list[str] = []
        second = executor.terminal_read(handle.session_id, max_bytes=4096, wait_ms=1000)
        second_chunks.append(second.output)
        while "ANSWER=hello" not in "".join(second_chunks) and time.monotonic() < second_deadline:
            second = executor.terminal_read(handle.session_id, max_bytes=4096, wait_ms=1000)
            second_chunks.append(second.output)
        assert "ANSWER=hello" in "".join(second_chunks)
        created = set(sent.state_delta.get("created_paths", ())) | set(
            second.state_delta.get("created_paths", ())
        )
        assert "terminal-result.txt" in created
        assert executor.terminal_wait(handle.session_id, timeout_s=10).live is False
        assert Path(workspace, "terminal-result.txt").read_text() == "artifact=hello\n"

        manifest = executor.export_spools(str(tmp_path / "spools"))
        assert "files" in manifest and "manifest_path" in manifest
        terminal_manifest = manifest["terminal_transcripts"]
        assert terminal_manifest["file_count"] == 1
        raw = Path(terminal_manifest["files"][0]["stored_path"]).read_text(
            encoding="utf-8", errors="replace"
        )
        assert "QUESTION" in raw and "ANSWER=hello" in raw
        executor.close()

    def test_host_terminal_close_fails_send_after_exact_group_shutdown(
        self, executor: SubprocessExecutor,
    ) -> None:
        handle = executor.start_terminal_session("closable", "sleep 300")
        assert handle.live
        closed = executor.terminal_close(handle.session_id)
        assert not closed.live
        assert closed.process_generation == handle.process_generation
        with pytest.raises(RuntimeError, match="not live"):
            executor.terminal_send(handle.session_id, "x")
        executor.close()


class TestInspectArtifact:
    def test_text_mode(self, executor: SubprocessExecutor) -> None:
        executor.write_file("data.json", '{"key": "value"}')
        inspection = executor.inspect_artifact("data.json", "text")
        assert inspection.success
        assert "key" in inspection.extracted_text
        assert inspection.metadata.get("backend") == "basic"

    def test_missing_file(self, executor: SubprocessExecutor) -> None:
        inspection = executor.inspect_artifact("nope.bin", "binary")
        assert not inspection.success

    def test_binary_mode(self, executor: SubprocessExecutor, workspace: str) -> None:
        path = os.path.join(workspace, "blob.bin")
        with open(path, "wb") as fh:
            fh.write(b"\x00\x01\x02\x03")
        inspection = executor.inspect_artifact("blob.bin", "binary")
        assert inspection.success
        assert inspection.metadata.get("backend") == "basic"
        assert "size_bytes" in inspection.metadata


class TestRefreshEnvmap:
    def test_refresh_picks_up_new_file(self, executor: SubprocessExecutor) -> None:
        envmap = EnvMap(
            task_prompt="test",
            workspace_root="/fake",
            capabilities={
                "shell": CapabilityDescriptor(
                    capability_id="shell",
                    summary="run commands",
                )
            },
        )
        executor.write_file("new_file.txt", "hi")
        refreshed = executor.refresh_envmap(envmap)
        assert "new_file.txt" in refreshed.visible_files
        # Capabilities carried over.
        assert "shell" in refreshed.capabilities


class TestPathSafety:
    def test_path_escape_fails_closed(self, executor: SubprocessExecutor, workspace: str) -> None:
        with pytest.raises(PermissionError, match="escapes workspace"):
            executor.write_file("../../etc/passwd", "nope")
        assert not os.path.exists(os.path.join(workspace, "passwd"))



def test_local_stat_freshness_detects_same_size_rewrite_without_content_hash(tmp_path: Path) -> None:
    target = tmp_path / "same.txt"
    target.write_text("AAAA", encoding="utf-8")
    before = _snapshot_local_stats(str(tmp_path), max_entries=10)
    target.write_text("BBBB", encoding="utf-8")
    after = _snapshot_local_stats(str(tmp_path), max_entries=10)
    modified, produced, removed, delta = _diff_local_stat_snapshots(before, after)
    assert modified == ("same.txt",)
    assert produced == () and removed == ()
    assert delta["mutation_detection_status"] == "complete"
    assert delta["mutation_detection_basis"] == "bounded_stat_kind_size_mtime_ctime_mode_uid_gid"


def test_local_stat_truncation_never_fabricates_created_or_removed_from_prefix_drift(tmp_path: Path) -> None:
    before_root = tmp_path / "before"
    after_root = tmp_path / "after"
    before_root.mkdir(); after_root.mkdir()
    (before_root / "a.txt").write_text("a", encoding="utf-8")
    (before_root / "z.txt").write_text("z", encoding="utf-8")
    (after_root / "b.txt").write_text("b", encoding="utf-8")
    (after_root / "z.txt").write_text("z", encoding="utf-8")
    before = _snapshot_local_stats(str(before_root), max_entries=1)
    after = _snapshot_local_stats(str(after_root), max_entries=1)
    modified, produced, removed, delta = _diff_local_stat_snapshots(before, after)
    assert modified == ()
    assert produced == () and removed == ()
    assert delta["mutation_detection_status"] == "truncated"
    assert delta["path_set_delta_status"] == "unknown_due_truncation"



def test_managed_process_observer_captures_async_workspace_write(executor: SubprocessExecutor, workspace: str) -> None:
    import time
    handle = executor.launch_process(
        "async-writer", "sleep 0.05; printf done > async-process.txt"
    )
    deadline = time.monotonic() + 15.0
    observed: set[str] = set()
    while "async-process.txt" not in observed and time.monotonic() < deadline:
        time.sleep(0.03)
        delta = executor.observe_process_state(handle.process_id)
        observed.update(delta.get("created_paths", ()))
        observed.update(delta.get("metadata_changed_paths", ()))
    assert "async-process.txt" in observed
    assert Path(workspace, "async-process.txt").read_text() == "done"
