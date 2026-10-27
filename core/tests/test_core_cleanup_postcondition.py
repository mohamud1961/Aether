"""Real owned processes + independently observed cleanup, no native containers."""

import asyncio
import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from aether.core.env import stop_process_tree
from tests.core_fakes import LocalEnv


def spawn(root, code):
    ready = root / "ready"
    p = subprocess.Popen(
        [sys.executable, "-c", code, str(ready)], start_new_session=True
    )
    deadline = time.monotonic() + 5
    while not ready.exists() and p.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    if not ready.exists():
        p.kill()
        p.wait()
        raise RuntimeError("test process did not start")
    return p


def dispose(p):
    if p.poll() is None:
        os.killpg(p.pid, signal.SIGKILL)
    p.wait(timeout=5)


def test_sigterm_ignoring_owned_process_is_really_stopped(tmp_path):
    p = spawn(
        tmp_path,
        "import signal,time,sys;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(sys.argv[1]).touch();time.sleep(120)",
    )
    try:
        asyncio.run(stop_process_tree(LocalEnv(tmp_path), [p.pid]))
        deadline = time.monotonic() + 3
        while p.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert p.poll() is not None, (
            "cleanup returned success while owned process survived"
        )
    finally:
        dispose(p)


def test_transport_zero_is_not_a_cleanup_postcondition(tmp_path):
    class SilentTransport:
        async def exec(self, **kwargs):
            return SimpleNamespace(return_code=0, stdout="", stderr="")

    p = spawn(
        tmp_path,
        "import time,sys;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(120)",
    )
    try:
        with pytest.raises(OSError, match="unverified|unavailable|postcondition"):
            asyncio.run(stop_process_tree(SilentTransport(), [p.pid]))
        assert p.poll() is None
    finally:
        dispose(p)


def test_absent_parent_cannot_confirm_its_detached_child_stopped(tmp_path):
    child_file = tmp_path / "child"
    code = "import subprocess,sys;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'],start_new_session=True);Path(sys.argv[1]).write_text(str(p.pid))"
    parent = subprocess.Popen(
        [sys.executable, "-c", code, str(child_file)], start_new_session=True
    )
    parent.wait(timeout=5)
    child = int(child_file.read_text())
    try:
        with pytest.raises(OSError, match="unverified"):
            asyncio.run(stop_process_tree(LocalEnv(tmp_path), [parent.pid]))
        os.kill(child, 0)
    finally:
        os.kill(child, signal.SIGKILL)


def test_changed_launch_identity_prevents_signalling_another_process(tmp_path):
    p = spawn(
        tmp_path,
        "import time,sys;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(120)",
    )
    try:
        with pytest.raises(OSError, match="identity.*changed|unverified"):
            asyncio.run(
                stop_process_tree(
                    LocalEnv(tmp_path),
                    [p.pid],
                    identities={str(p.pid): "different birth identity"},
                )
            )
        assert p.poll() is None
    finally:
        dispose(p)


def test_signal_denial_reports_survivor_and_partial_effect_evidence(tmp_path):
    import shlex

    from aether.core.env import ProcessCleanupError

    class DeniedSignal(LocalEnv):
        async def exec(self, command, **kwargs):
            # Rewrite only the Python observer; the shell fallback tail runs only when python3 is absent (rc 127).
            command, sep, tail = command.partition("; __aether_rc=")
            words = shlex.split(command)
            if len(words) > 5 and words[0] == "python3" and words[5] == "stop":
                # Explicit syscall fault injection; target is an independently
                # observed real local process, not a fabricated process table.
                words[2] = (
                    "import os\ndef denied(*args):raise PermissionError('injected denial')\nos.kill=denied\n"
                    + words[2]
                )
                command = shlex.join(words)
            return await super().exec(command + sep + tail, **kwargs)

    p = spawn(
        tmp_path,
        "import time,sys;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(120)",
    )
    try:
        with pytest.raises(ProcessCleanupError) as error:
            asyncio.run(stop_process_tree(DeniedSignal(tmp_path), [p.pid]))
        assert error.value.receipt["status"] == "still_running"
        assert p.pid in error.value.receipt["still_running"]
        assert any(
            e["error"] == "PermissionError"
            for e in error.value.receipt["signal_errors"]
        )
        assert p.poll() is None
    finally:
        dispose(p)


def test_unavailable_enumeration_does_not_report_empty_retained_services(tmp_path):
    from aether.core.env import list_process_tree

    class SilentTransport:
        async def exec(self, **kwargs):
            return SimpleNamespace(return_code=0, stdout="", stderr="")

    with pytest.raises(OSError, match="unverified"):
        asyncio.run(list_process_tree(SilentTransport(), [999999]))


def test_observed_children_and_grandchildren_are_stopped(tmp_path):
    import json

    child_code = "import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(120)'],start_new_session=True);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(120)"
    code = f"import subprocess,sys,time,json;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c',{child_code!r},sys.argv[1]+'-grand'],start_new_session=True);q=Path(sys.argv[1]+'-grand');\nwhile not q.exists():time.sleep(.01)\nPath(sys.argv[1]).write_text(json.dumps([p.pid,int(q.read_text())]));time.sleep(120)"
    p = spawn(tmp_path, code)
    children = json.loads((tmp_path / "ready").read_text())
    try:
        receipt = asyncio.run(stop_process_tree(LocalEnv(tmp_path), [p.pid]))
        assert set([p.pid, *children]) <= set(receipt["observed"])
        for pid in children:
            status = subprocess.run(
                ["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True
            ).stdout.strip()
            assert not status or status.startswith("Z")
    finally:
        dispose(p)
        for pid in children:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_zombie_is_exited_not_a_successfully_running_process(tmp_path):
    p = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    try:
        deadline = time.monotonic() + 5
        status = ""
        while time.monotonic() < deadline:
            status = subprocess.run(
                ["ps", "-p", str(p.pid), "-o", "stat="], capture_output=True, text=True
            ).stdout.strip()
            if status.startswith("Z"):
                break
            time.sleep(0.02)
        if not status.startswith("Z"):
            pytest.skip("host reaped process before zombie observation")
        receipt = asyncio.run(stop_process_tree(LocalEnv(tmp_path), [p.pid]))
        assert receipt["status"] == "confirmed_stopped" and not receipt["still_running"]
    finally:
        p.wait(timeout=5)


def test_final_account_exposes_unverified_cleanup_without_destroying_work(tmp_path):
    import shlex

    from aether.core.loop import CoreConfig, Trace, run_agent
    from aether.core.provider import ChatProvider
    from tests.core_fakes import ScriptedClient, call

    class NoCleanupReceipt(LocalEnv):
        async def exec(self, command, **kwargs):
            words = shlex.split(command)
            if len(words) > 5 and words[0] == "python3" and words[5] == "stop":
                return SimpleNamespace(
                    return_code=0, stdout="", stderr="simulated lost receipt"
                )
            return await super().exec(command, **kwargs)

    script = [
        call("terminal", {"input": "printf correct > artifact.txt"}, "write"),
        call("finish", {"summary": "artifact made"}, "finish"),
    ]
    result = asyncio.run(
        run_agent(
            env=NoCleanupReceipt(tmp_path),
            task="Create artifact.txt",
            workdir=str(tmp_path),
            provider=ChatProvider(ScriptedClient(script), model="scripted", params={}),
            timeout_s=30,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), end_processes="stop"),
        )
    )
    assert (
        result.status == "finished"
        and (tmp_path / "artifact.txt").read_text() == "correct"
    )
    assert (
        result.extras["cleanup_errors"]
        and "cleanup incomplete or unverified" in result.final_account
    )


@pytest.mark.parametrize("fault", ["enumeration", "python_missing", "timeout"])
def test_observer_faults_preserve_unverified_outcome_for_real_process(tmp_path, fault):
    import asyncio
    import shlex

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)
    ps = bin_dir / "ps"
    ps.write_text("#!/bin/sh\nexit 3\n")
    ps.chmod(0o755)

    class BrokenObserver(LocalEnv):
        async def exec(self, command, **kwargs):
            if command.startswith("python3 -c "):
                if fault == "timeout":
                    raise TimeoutError("injected observer timeout")
                if fault == "enumeration":
                    # Linux enumerates /proc without invoking ps. Inject the
                    # fault at that actual syscall as well as the ps fallback.
                    command, sep, tail = command.partition("; __aether_rc=")
                    words = shlex.split(command)
                    words[2] = (
                        "import os\n_original_listdir=os.listdir\n"
                        "def _denied_listdir(path):\n"
                        " if path=='/proc':raise PermissionError('injected enumeration denial')\n"
                        " return _original_listdir(path)\n"
                        "os.listdir=_denied_listdir\n" + words[2]
                    )
                    command = shlex.join(words) + sep + tail
                path = bin_dir if fault == "enumeration" else tmp_path / "missing-bin"
                command = "PATH=" + shlex.quote(str(path)) + " " + command
            return await super().exec(command, **kwargs)

    p = spawn(
        tmp_path,
        "import time,sys;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(120)",
    )
    try:
        if fault == "python_missing" and os.path.isdir("/proc/1"):
            # Without python3 the shell observer takes over through /proc: a real, verified stop.
            receipt = asyncio.run(stop_process_tree(BrokenObserver(tmp_path), [p.pid]))
            assert receipt["status"] == "confirmed_stopped" and "shell observer" in receipt["coverage"], receipt
            p.wait(timeout=5)
        else:
            with pytest.raises(OSError, match="unverified"):
                asyncio.run(stop_process_tree(BrokenObserver(tmp_path), [p.pid]))
            assert p.poll() is None
    finally:
        dispose(p)


@pytest.mark.skipif(os.path.isdir("/proc/1"), reason="fakes ps output; with /proc the command is read from cmdline")
def test_empty_command_text_cannot_hide_a_live_retained_process(tmp_path):
    import shlex
    import shutil

    from aether.core.env import list_process_tree

    binary = shutil.which("ps")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)
    fake = bin_dir / "ps"
    fake.write_text(
        '#!/bin/sh\ncase "$*" in *command=*) exit 0;; *) exec '
        + shlex.quote(binary)
        + ' "$@";; esac\n'
    )
    fake.chmod(0o755)

    class MissingCommands(LocalEnv):
        async def exec(self, command, **kwargs):
            if command.startswith("python3 -c "):
                command = "PATH=" + shlex.quote(str(bin_dir)) + " " + command
            return await super().exec(command, **kwargs)

    p = spawn(
        tmp_path,
        "import time,sys;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(120)",
    )
    try:
        with pytest.raises(OSError, match="unverified|observation failed"):
            asyncio.run(list_process_tree(MissingCommands(tmp_path), [p.pid]))
        assert p.poll() is None
    finally:
        dispose(p)



@pytest.mark.skipif(not os.path.isdir("/proc/1"), reason="the /proc observer exists only on Linux")
def test_a_retained_process_is_listed_without_ps(tmp_path):
    import shlex

    from aether.core.env import list_process_tree

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)  # the observer's PATH holds python3 and no ps

    class NoPs(LocalEnv):
        async def exec(self, command, **kwargs):
            if command.startswith("python3 -c "):
                command = "PATH=" + shlex.quote(str(bin_dir)) + " " + command
            return await super().exec(command, **kwargs)

    p = spawn(
        tmp_path,
        "import subprocess,time,sys;from pathlib import Path;"
        "c=subprocess.Popen(['sleep','117']);Path(sys.argv[1]).touch();time.sleep(120)",
    )
    try:
        listed = asyncio.run(list_process_tree(NoPs(tmp_path), [p.pid]))
        assert [row.split(" ", 1)[1] for row in listed] == ["sleep 117"]
    finally:
        dispose(p)  # its group holds the sleep child too
