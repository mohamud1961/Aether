from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

from aether.execution import CommandResult, run_stateful_command
from aether.harbor_executor import HarborEnvironmentExecutor
from aether.harbor_workspace_state import (
    RemotePathState,
    RemoteWorkspaceSnapshot,
    diff_remote_workspace_snapshots,
    parse_remote_workspace_snapshot,
    remote_workspace_snapshot_command,
)


ROOT = "/app"


def _path(
    path: str,
    *,
    size: int = 4,
    mtime: str = "2026-08-21 03:00:00.000000001 +0100",
    ctime: str = "2026-08-21 03:00:00.000000002 +0100",
    mode: str = "644",
    kind: str = "regular file",
) -> RemotePathState:
    return RemotePathState(
        path=path,
        kind=kind,
        size=size,
        mtime=mtime,
        ctime=ctime,
        mode=mode,
        uid="1000",
        gid="1000",
    )


def _snapshot(*entries: RemotePathState, backend: str = "gnu", precision: str = "nanosecond") -> RemoteWorkspaceSnapshot:
    return RemoteWorkspaceSnapshot(
        root=ROOT,
        entries=entries,
        stat_backend=backend,
        time_precision=precision,
    )


def test_remote_snapshot_command_is_bounded_stat_freshness_probe_not_artifact_hasher() -> None:
    command = remote_workspace_snapshot_command(ROOT, max_entries=7)
    assert "stat -c" in command
    assert "%y" in command and "%z" in command
    assert "__AETHER_REMOTE_WORKSPACE_STATE_V2__" in command
    assert "head -n 8" in command
    assert ".git" in command
    assert "node_modules" in command
    assert "sha256sum" not in command
    assert "shasum -a 256" not in command

    try:
        remote_workspace_snapshot_command("relative")
    except ValueError as exc:
        assert "absolute root" in str(exc)
    else:
        raise AssertionError("relative snapshot root must fail closed")


def test_parse_remote_snapshot_preserves_high_resolution_stat_rows() -> None:
    stdout = "\n".join([
        "__AETHER_REMOTE_WORKSPACE_STATE_V2__\tgnu\tnanosecond",
        "__AETHER_REMOTE_WORKSPACE_STAT__",
        "/app/a.txt\t4\t2026-08-21 03:00:00.000000001 +0100\t2026-08-21 03:00:00.000000002 +0100\t644\t1000\t1000\tregular file",
        "/app/link\t5\t2026-08-21 03:00:01.000000001 +0100\t2026-08-21 03:00:01.000000002 +0100\t777\t1000\t1000\tsymbolic link",
    ])
    snapshot = parse_remote_workspace_snapshot(stdout, root=ROOT)
    assert snapshot.available is True
    assert snapshot.truncated is False
    assert snapshot.stat_backend == "gnu"
    assert snapshot.time_precision == "nanosecond"
    assert [row.path for row in snapshot.entries] == ["a.txt", "link"]
    assert snapshot.by_path()["a.txt"].size == 4
    assert snapshot.by_path()["link"].kind == "symbolic link"


def test_parse_remote_snapshot_fails_closed_on_malformed_stat_row() -> None:
    stdout = "\n".join([
        "__AETHER_REMOTE_WORKSPACE_STATE_V2__\tgnu\tnanosecond",
        "__AETHER_REMOTE_WORKSPACE_STAT__",
        "/app/a.txt\t4\tmissing-fields",
    ])
    snapshot = parse_remote_workspace_snapshot(stdout, root=ROOT)
    assert snapshot.available is False
    assert snapshot.malformed_rows == 1
    assert "malformed" in snapshot.detail


def test_parse_remote_snapshot_reports_backend_unavailability_without_guessing() -> None:
    snapshot = parse_remote_workspace_snapshot(
        "__AETHER_REMOTE_WORKSPACE_STATE_UNAVAILABLE__\tstat_backend_missing\n",
        root=ROOT,
    )
    assert snapshot.available is False
    assert snapshot.detail == "stat_backend_missing"
    assert snapshot.entries == ()


def test_parse_remote_snapshot_marks_overflow_as_truncated() -> None:
    stdout = "\n".join([
        "__AETHER_REMOTE_WORKSPACE_STATE_V2__\tgnu\tnanosecond",
        "__AETHER_REMOTE_WORKSPACE_STAT__",
        "/app/a.txt\t4\t2026-08-21 03:00:00.1 +0100\t2026-08-21 03:00:00.2 +0100\t644\t1000\t1000\tregular file",
        "/app/b.txt\t4\t2026-08-21 03:00:00.1 +0100\t2026-08-21 03:00:00.2 +0100\t644\t1000\t1000\tregular file",
    ])
    snapshot = parse_remote_workspace_snapshot(stdout, root=ROOT, max_entries=1)
    assert snapshot.available is True
    assert snapshot.truncated is True
    assert [row.path for row in snapshot.entries] == ["a.txt"]


def test_diff_detects_created_removed_and_same_size_rewrite_from_high_resolution_ctime() -> None:
    before = _snapshot(
        _path("same.txt", size=4, ctime="2026-08-21 03:00:00.000000001 +0100"),
        _path("gone.txt", size=4),
    )
    after = _snapshot(
        _path("same.txt", size=4, ctime="2026-08-21 03:00:00.000000009 +0100"),
        _path("new.txt", size=3),
    )
    delta = diff_remote_workspace_snapshots(before, after)
    assert delta["mutation_detection_status"] == "complete"
    assert delta["created_paths"] == ["new.txt"]
    assert delta["removed_paths"] == ["gone.txt"]
    assert delta["content_changed_paths"] == []
    assert delta["metadata_changed_paths"] == ["same.txt"]
    assert delta["mutation_detection_basis"] == "bounded_stat_kind_size_mtime_ctime_mode_uid_gid"


def test_diff_detects_symlink_retarget_when_size_or_stat_identity_changes() -> None:
    before = _snapshot(_path("link", size=2, kind="symbolic link"))
    after = _snapshot(_path("link", size=3, kind="symbolic link"))
    delta = diff_remote_workspace_snapshots(before, after)
    assert delta["content_changed_paths"] == ["link"]
    assert delta["metadata_changed_paths"] == []


def test_bsd_second_precision_is_explicitly_coarse_even_when_no_delta_is_visible() -> None:
    before = _snapshot(_path("mode.txt", mode="644", mtime="10", ctime="11"), backend="bsd", precision="seconds")
    after = _snapshot(_path("mode.txt", mode="644", mtime="10", ctime="11"), backend="bsd", precision="seconds")
    delta = diff_remote_workspace_snapshots(before, after)
    assert delta["mutation_detection_status"] == "coarse"
    assert delta["content_changed_paths"] == []
    assert delta["metadata_changed_paths"] == []


def test_diff_preserves_metadata_only_change_without_claiming_content_change() -> None:
    before = _snapshot(_path("mode.txt", mode="644"))
    after = _snapshot(_path("mode.txt", mode="600"))
    delta = diff_remote_workspace_snapshots(before, after)
    assert delta["mutation_detection_status"] == "complete"
    assert delta["content_changed_paths"] == []
    assert delta["metadata_changed_paths"] == ["mode.txt"]


def test_diff_fails_closed_when_either_inventory_is_unavailable() -> None:
    before = RemoteWorkspaceSnapshot(root=ROOT, available=False, detail="no stat")
    after = RemoteWorkspaceSnapshot(root=ROOT, stat_backend="gnu", time_precision="nanosecond")
    delta = diff_remote_workspace_snapshots(before, after)
    assert delta["mutation_detection_status"] == "unavailable"
    assert delta["created_paths"] == []
    assert delta["removed_paths"] == []
    assert delta["content_changed_paths"] == []
    assert delta["mutation_actor_status"] == "mutation_actor_unknown"


def test_run_stateful_command_prefers_optional_tracked_executor_route() -> None:
    class Recorder:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str | None, int]] = []

        def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30):
            self.calls.append(("raw", command, cwd, timeout_s))
            return CommandResult(command=command, exit_code=1)

        def run_tracked_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30):
            self.calls.append(("tracked", command, cwd, timeout_s))
            return CommandResult(
                command=command,
                exit_code=0,
                produced_artifacts=("created.txt",),
                state_delta={"mutation_detection_status": "complete"},
            )

    recorder = Recorder()
    result = run_stateful_command(recorder, "touch created.txt", cwd="/app", timeout_s=19)
    assert result.success is True
    assert result.produced_artifacts == ("created.txt",)
    assert recorder.calls == [("tracked", "touch created.txt", "/app", 19)]


@dataclass
class _Completed:
    return_code: int
    stdout: str = ""
    stderr: str = ""


class _LocalAsyncEnvironment:
    async def exec(
        self,
        *,
        command: str,
        cwd: str | None,
        env: dict[str, str] | None,
        timeout_sec: int,
    ) -> _Completed:
        def _run() -> _Completed:
            completed = subprocess.run(
                ["/bin/sh", "-lc", command],
                cwd=cwd,
                env=None if env is None else {**dict(os.environ), **env},
                text=True,
                capture_output=True,
                timeout=timeout_sec,
            )
            return _Completed(completed.returncode, completed.stdout, completed.stderr)

        return await asyncio.to_thread(_run)

    async def upload_file(self, source: Path, destination: str) -> None:
        def _copy() -> None:
            target = Path(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        await asyncio.to_thread(_copy)

    async def download_file(self, source: str, destination: Path) -> None:
        await asyncio.to_thread(shutil.copyfile, source, destination)


def test_harbor_tracked_command_observes_real_rewrite_multi_create_remove_and_symlink_change() -> None:
    async def _main() -> None:
        with tempfile.TemporaryDirectory(prefix="aether-harbor-state-test-") as tmp:
            root = Path(tmp) / "workspace"
            state = Path(tmp) / "state"
            root.mkdir()
            (root / "same.txt").write_text("AAAA", encoding="utf-8")
            (root / "gone.txt").write_text("gone", encoding="utf-8")
            (root / "link").symlink_to("aa")
            executor = HarborEnvironmentExecutor(
                _LocalAsyncEnvironment(),
                event_loop=asyncio.get_running_loop(),
                workspace_root=str(root),
                local_state_dir=state,
            )
            try:
                result = await asyncio.to_thread(
                    executor.run_tracked_command,
                    "printf 'BBBBB' > same.txt; printf 'one' > one.txt; "
                    "printf 'two' > two.txt; rm gone.txt; rm link; ln -s bbb link",
                    cwd=str(root),
                    timeout_s=10,
                )
                assert result.success is True
                assert "same.txt" in result.modified_paths
                assert "link" in result.modified_paths
                assert set(result.produced_artifacts) == {"one.txt", "two.txt"}
                assert result.removed_paths == ("gone.txt",)
                assert result.state_delta["mutation_detection_status"] in {"complete", "coarse"}
                assert result.state_delta["before_time_precision"] in {"nanosecond", "seconds"}
                assert result.state_delta["after_time_precision"] in {"nanosecond", "seconds"}
                assert (root / "same.txt").read_text(encoding="utf-8") == "BBBBB"
                assert (root / "link").readlink() == Path("bbb")
            finally:
                await asyncio.to_thread(executor.close)

    asyncio.run(_main())


def test_harbor_environment_extension_tracks_tools_call_but_not_tools_list() -> None:
    executor = object.__new__(HarborEnvironmentExecutor)
    executor._mcp_servers = {
        "demo": {"name": "demo", "transport": "stdio", "command": "server"}
    }
    executor.workspace_root = "/app"
    executor._ensure_mcp_client = lambda: ("python3", "/tmp/client.py")
    calls: list[str] = []

    def raw(command: str, *, cwd: str | None = None, timeout_s: int = 30):
        del cwd, timeout_s
        calls.append("raw")
        return CommandResult(command=command, exit_code=0, stdout='{"ok":true,"result":[]}\n')

    def tracked(command: str, *, cwd: str | None = None, timeout_s: int = 30):
        del cwd, timeout_s
        calls.append("tracked")
        return CommandResult(
            command=command,
            exit_code=0,
            stdout='{"ok":true,"result":{"saved":true}}\n',
            produced_artifacts=("saved.txt",),
            state_delta={"mutation_detection_status": "complete", "created_paths": ["saved.txt"]},
        )

    executor.run_command = raw
    executor.run_tracked_command = tracked

    listed = HarborEnvironmentExecutor.call_environment_extension(
        executor, server_name="demo", operation="tools_list", timeout_s=5,
    )
    called = HarborEnvironmentExecutor.call_environment_extension(
        executor,
        server_name="demo",
        operation="tools_call",
        tool_name="save",
        arguments={"path": "saved.txt"},
        timeout_s=5,
    )
    assert listed["success"] is True
    assert called["success"] is True
    assert calls == ["raw", "tracked"]
    assert called["artifact_paths"] == ("saved.txt",)
    assert called["state_delta"]["mutation_detection_status"] == "complete"



def test_truncated_inventory_never_fabricates_created_or_removed_paths_from_prefix_drift() -> None:
    before = RemoteWorkspaceSnapshot(
        root=ROOT,
        entries=(_path("a.txt"),),
        available=True,
        truncated=True,
        stat_backend="gnu",
        time_precision="nanosecond",
    )
    after = RemoteWorkspaceSnapshot(
        root=ROOT,
        entries=(_path("b.txt"),),
        available=True,
        truncated=True,
        stat_backend="gnu",
        time_precision="nanosecond",
    )
    delta = diff_remote_workspace_snapshots(before, after)
    assert delta["mutation_detection_status"] == "truncated"
    assert delta["created_paths"] == []
    assert delta["removed_paths"] == []
    assert delta["path_set_delta_status"] == "unknown_due_truncation"



def test_harbor_tracked_command_preserves_post_action_delta_when_transport_raises() -> None:
    executor = object.__new__(HarborEnvironmentExecutor)
    before = _snapshot(_path("kept.txt"))
    after = _snapshot(_path("kept.txt"), _path("maybe-created.txt", size=3))
    snapshots = iter((before, after))
    executor._capture_remote_workspace_snapshot = lambda: next(snapshots)

    def broken_command(command: str, *, cwd: str | None = None, timeout_s: int = 30):
        del command, cwd, timeout_s
        raise RuntimeError("transport disappeared after action attempt")

    executor.run_command = broken_command
    result = HarborEnvironmentExecutor.run_tracked_command(
        executor, "possibly-mutating-command", cwd=ROOT, timeout_s=9,
    )
    assert result.success is False
    assert result.exit_code == 125
    assert result.produced_artifacts == ("maybe-created.txt",)
    assert result.state_delta["mutation_detection_status"] == "complete"
    assert result.state_delta["action_transport_status"] == "failed_after_action_attempt"
    assert result.state_delta["action_transport_error_type"] == "RuntimeError"
    assert result.provenance == ("harbor:BaseEnvironment.exec:transport_failure",)



def test_remote_snapshot_command_excludes_only_harbor_internal_state_not_task_local_tools() -> None:
    command = remote_workspace_snapshot_command(ROOT)
    assert f"{ROOT}/.aether/harbor_jobs" in command
    assert f"{ROOT}/.aether/harbor_terminals" in command
    assert f"{ROOT}/.aether/tools" not in command
