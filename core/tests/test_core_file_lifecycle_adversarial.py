"""Whole-tool adversarial cases for file type and model-visible delivery effects."""

from __future__ import annotations

import asyncio
import json
import shlex
import stat
from pathlib import Path

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


class BoundedFifoEnv(LocalEnv):
    def __init__(self, root):
        super().__init__(root)
        self.fifo_download_attempts = 0

    async def download_file(self, source_path, target_path):
        if Path(source_path).is_fifo():
            self.fifo_download_attempts += 1
            raise TimeoutError("bounded synthetic FIFO read would wait for a writer")
        return await super().download_file(source_path, target_path)


def _run_fifo_operation(
    work: Path, control: Path, trace: Path, operation: str, env=None, path="pipe"
):
    action_id = "fifo-action"
    if operation == "write_file":
        action = call(
            operation, {"path": path, "content": "replacement bytes\n"}, action_id
        )
    else:
        action = call(
            operation,
            {"path": path, "old_str": "source", "new_str": "replacement"},
            action_id,
        )
    client = ScriptedClient([action, call("finish", {"summary": "Done"}, "finish")])
    env = env or BoundedFifoEnv(work)
    result = asyncio.run(
        run_agent(
            env=env,
            task="Perform the requested file operation.",
            workdir=str(work),
            provider=ChatProvider(client, model="offline-script", params={}),
            timeout_s=30,
            trace=Trace(trace),
            config=CoreConfig(control_dir=str(control), record=False),
        )
    )
    returned = [
        m["content"]
        for m in client.requests[1]["messages"]
        if m.get("role") == "tool" and m.get("tool_call_id") == action_id
    ]
    assert len(returned) == 1
    return result, returned[0], env


@pytest.mark.parametrize("operation", ["write_file", "edit_file"])
def test_file_tools_do_not_replace_or_open_a_fifo_and_report_the_refusal(
    tmp_path, operation
):
    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    control.mkdir()
    pipe = work / "pipe"
    import os

    os.mkfifo(pipe)

    result, visible, env = _run_fifo_operation(
        work, control, tmp_path / "trace.jsonl", operation
    )

    assert stat.S_ISFIFO(pipe.lstat().st_mode), (
        f"{operation} must not silently replace a special file"
    )
    assert visible.startswith("error:") and "regular file" in visible.lower(), visible
    assert env.fifo_download_attempts == 0, (
        "edit_file must reject before opening a FIFO for download"
    )
    assert result.status == "finished"


def _run_write_with_env(work, control, env, content, trace, path="artifact.bin"):
    client = ScriptedClient(
        [
            call("write_file", {"path": path, "content": content}, "write"),
            call("finish", {"summary": "Done"}, "finish"),
        ]
    )
    result = asyncio.run(
        run_agent(
            env=env,
            task=f"Write the requested bytes to {path}.",
            workdir=str(work),
            provider=ChatProvider(client, model="offline-script", params={}),
            timeout_s=30,
            trace=Trace(trace),
            config=CoreConfig(control_dir=str(control), record=False),
        )
    )
    tool_result = [
        m["content"]
        for m in client.requests[1]["messages"]
        if m.get("role") == "tool" and m.get("tool_call_id") == "write"
    ]
    assert len(tool_result) == 1
    return result, tool_result[0]


class PartialUpload(LocalEnv):
    async def upload_file(self, source_path, target_path):
        Path(target_path).write_bytes(Path(source_path).read_bytes()[:17])
        raise ConnectionError("synthetic interruption after partial staged transfer")


def test_interrupted_large_upload_preserves_existing_artifact_and_reports_failure(
    tmp_path,
):
    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    control.mkdir()
    target = work / "artifact.bin"
    target.write_bytes(b"PREVIOUS-CORRECT-VERSION")
    content = "new-data-" * 6000  # cross the real inline/upload boundary

    result, visible = _run_write_with_env(
        work, control, PartialUpload(work), content, tmp_path / "partial-upload.jsonl"
    )

    assert visible.startswith("error:") and "partial staged transfer" in visible, (
        visible
    )
    assert target.read_bytes() == b"PREVIOUS-CORRECT-VERSION"
    assert not list(work.glob("artifact.bin.aether-*.tmp"))
    assert result.status == "finished"


class HashToolsFail(LocalEnv):
    def __init__(self, root):
        super().__init__(root)
        self.tools = root / "hash-fail-bin"
        self.tools.mkdir()
        for name in ("sha256sum", "shasum"):
            tool = self.tools / name
            tool.write_text(
                "#!/bin/sh\necho 'synthetic hash utility failure' >&2\nexit 67\n"
            )
            tool.chmod(0o700)

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        prefix = "PATH=" + shlex.quote(str(self.tools)) + ':"$PATH"; '
        return await super().exec(
            prefix + command, cwd=cwd, env=env, timeout_sec=timeout_sec
        )


def test_failure_of_both_hash_utilities_cannot_report_a_write_success(tmp_path):
    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    control.mkdir()
    target = work / "artifact.bin"
    target.write_bytes(b"OLD-CORRECT")

    result, visible = _run_write_with_env(
        work,
        control,
        HashToolsFail(work),
        "NEW-CORRUPT-CANDIDATE",
        tmp_path / "hash-failure.jsonl",
    )

    assert visible.startswith("error:") and "integrity failure" in visible, visible
    assert target.read_bytes() == b"OLD-CORRECT"
    assert not list(work.glob("artifact.bin.aether-*.tmp"))
    assert result.status == "finished"


class PivotDestinationToFifo(BoundedFifoEnv):
    def __init__(self, root, target):
        super().__init__(root)
        self.target = target
        self.pivoted = False

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        if not self.pivoted and "mv -fT" in command:
            self.pivoted = True
            self.target.unlink()
            __import__("os").mkfifo(self.target)
        return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec)


def test_fifo_swap_at_commit_is_not_silently_replaced_or_reported_successful(tmp_path):
    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    control.mkdir()
    target = work / "pipe"
    target.write_bytes(b"old regular file")
    env = PivotDestinationToFifo(work, target)

    result, visible, env = _run_fifo_operation(
        work, control, tmp_path / "race.jsonl", "write_file", env=env
    )

    assert env.pivoted, "fault injection must run at the commit boundary"
    assert stat.S_ISFIFO(target.lstat().st_mode), (
        "commit must preserve the concurrently installed special file"
    )
    assert visible.startswith("error:") and "regular file" in visible.lower(), visible
    assert result.status == "finished"


class PivotParentSymlinkAtCommit(LocalEnv):
    """Move a parent symlink after staging but before the commit command."""

    def __init__(self, root, alias):
        super().__init__(root)
        self.alias = alias
        self.outside = root / "outside"
        self.pivoted = False

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        if not self.pivoted and "mv -fT" in command:
            self.pivoted = True
            self.alias.unlink()
            self.alias.symlink_to(self.outside, target_is_directory=True)
        return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec)


def test_parent_symlink_pivot_does_not_strand_stage_or_claim_success(tmp_path):
    work, control = tmp_path / "work", tmp_path / "control"
    real_parent, outside = work / "real", work / "outside"
    work.mkdir()
    control.mkdir()
    real_parent.mkdir()
    outside.mkdir()
    alias = work / "alias"
    alias.symlink_to(real_parent, target_is_directory=True)
    env = PivotParentSymlinkAtCommit(work, alias)
    content = "candidate payload\n"

    result, visible = _run_write_with_env(
        work,
        control,
        env,
        content,
        tmp_path / "parent-pivot.jsonl",
        path="alias/artifact.bin",
    )

    assert env.pivoted, "fault injection must run at the commit boundary"
    stranded = list(real_parent.glob("artifact.bin.aether-*.tmp"))
    assert not stranded, f"parent symlink pivot stranded staged files: {stranded}"
    assert (real_parent / "artifact.bin").read_bytes() == content.encode()
    assert not (outside / "artifact.bin").exists(), "pivot must not redirect the commit"
    assert visible.startswith("error:"), (
        f"changed request path must not be acknowledged as success: {visible}"
    )
    assert result.status == "finished"


@pytest.mark.parametrize("operation", ["write_file", "edit_file"])
def test_atomic_replacement_of_a_hardlink_is_disclosed_and_path_local(
    tmp_path, operation
):
    import os

    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    control.mkdir()
    requested, alias = work / "requested.txt", work / "hardlink-alias.txt"
    requested.write_bytes(b"old payload\n")
    os.link(requested, alias)
    old_inode = requested.stat().st_ino
    action_id = "hardlink-action"
    if operation == "write_file":
        action = call(
            operation, {"path": requested.name, "content": "new payload\n"}, action_id
        )
        expected = b"new payload\n"
    else:
        action = call(
            operation,
            {"path": requested.name, "old_str": "old", "new_str": "new"},
            action_id,
        )
        expected = b"new payload\n"
    client = ScriptedClient([action, call("finish", {"summary": "Done"}, "finish")])
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="Update only the requested path.",
            workdir=str(work),
            provider=ChatProvider(client, model="offline-script", params={}),
            timeout_s=30,
            trace=Trace(tmp_path / f"hardlink-{operation}.jsonl"),
            config=CoreConfig(control_dir=str(control), record=False),
        )
    )
    returned = [
        m["content"]
        for m in client.requests[1]["messages"]
        if m.get("role") == "tool" and m.get("tool_call_id") == action_id
    ]
    assert len(returned) == 1 and not returned[0].startswith("error:"), returned
    schema = next(
        t["function"]
        for t in client.requests[0]["tools"]
        if t["function"]["name"] == operation
    )
    assert "hard-linked alias" in schema["description"]
    assert requested.read_bytes() == expected
    assert alias.read_bytes() == b"old payload\n"
    assert requested.stat().st_ino != old_inode and alias.stat().st_ino == old_inode
    assert result.status == "finished"


@pytest.mark.parametrize("operation", ["write_file", "edit_file"])
@pytest.mark.parametrize("via_symlink", [False, True])
def test_directory_write_edit_refusal_is_visible_and_preserves_directory(
    tmp_path, operation, via_symlink
):
    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    control.mkdir()
    directory = work / "real-directory"
    directory.mkdir()
    path = work / "pipe"
    if via_symlink:
        path.symlink_to(directory, target_is_directory=True)
    else:
        path = directory

    result, visible, _ = _run_fifo_operation(
        work,
        control,
        tmp_path / f"directory-{operation}-{via_symlink}.jsonl",
        operation,
        path=str(path),
    )

    assert path.is_dir()
    assert visible.startswith("error:") and "directory" in visible.lower(), visible
    assert list(directory.iterdir()) == []
    assert result.status == "finished"


def test_failed_transfer_reports_a_stage_that_could_not_be_removed(tmp_path):
    from types import SimpleNamespace

    class FailedStageCleanup(LocalEnv):
        async def upload_file(self, source_path, target_path):
            Path(target_path).write_bytes(b"partial")
            raise OSError("injected interrupted upload")

        async def exec(self, command, **kwargs):
            if command.startswith("rm -f ") and ".aether-" in command:
                return SimpleNamespace(
                    return_code=1, stdout="", stderr="injected permission denial"
                )
            return await super().exec(command, **kwargs)

    work = tmp_path / "work"
    work.mkdir()
    control = tmp_path / "ctl"
    control.mkdir()
    target = work / "artifact.txt"
    target.write_text("old")
    client = ScriptedClient(
        [
            call(
                "write_file", {"path": "artifact.txt", "content": "x" * 54000}, "write"
            ),
            call("finish", {"summary": "stop after error"}, "finish"),
        ]
    )
    trace = tmp_path / "trace.jsonl"
    asyncio.run(
        run_agent(
            env=FailedStageCleanup(work),
            task="Write artifact.txt",
            workdir=str(work),
            provider=ChatProvider(client, model="scripted", params={}),
            timeout_s=30,
            trace=Trace(trace),
            config=CoreConfig(control_dir=str(control)),
        )
    )
    rows = [json.loads(s) for s in trace.read_text().splitlines()]
    output = next(
        r["result"]
        for r in rows
        if r["event"] == "tool" and r.get("name") == "write_file"
    )
    assert target.read_text() == "old" and list(work.glob("*.aether-*.tmp"))
    assert "interrupted upload" in output and "staging cleanup" in output.lower(), (
        output
    )
