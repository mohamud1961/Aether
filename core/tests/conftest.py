"""Every test stops the processes it left behind, and only those.

Core keeps a run's processes by default (END_PROCESSES=keep): in a task container they die with it, but these tests
run Core on the host, where each terminal shell and REPL server outlived its test. One full suite left ~60, and
repeated runs exhausted the process table (42 tests then failed with "fork failed").

Ownership, not command matching: a process is this test's if it appeared during the test and either descends from
this pytest process or works inside this pytest session's own temp directory (a terminal's shell cds into its
workdir, and keeps it after its run.sh exits or a test kills it and it is orphaned to init). Its descendants go with
it. Matching Core's shared /tmp/.aether directory or its wrapper commands would also select another session's Core
run. Never pytest itself or its ancestors. (Not by process group: a terminal's shell starts in a group of its own.)
"""

from __future__ import annotations

import os
from pathlib import Path
import signal
import shutil
import subprocess
import time

import pytest


def processes() -> dict[int, tuple[int, int, str]]:
    """pid -> (ppid, pgid, command) for every live process visible to this user (zombies are already dead)."""
    ps = subprocess.Popen(
        ["ps", "-ww", "-axo", "pid=,ppid=,pgid=,stat=,command="],
        stdout=subprocess.PIPE,
        text=True,
    )
    out = ps.communicate()[0]
    table = {}
    for line in out.splitlines():
        parts = line.split(None, 4)
        if (
            len(parts) == 5
            and parts[0].isdigit()
            and int(parts[0]) != ps.pid
            and not parts[3].startswith("Z")
        ):
            table[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[4])
    return table


def cwds(pids: set[int]) -> dict[int, str]:
    """pid -> working directory, for those of ``pids`` that can be read (/proc on Linux, lsof elsewhere)."""
    if not pids:
        return {}
    if Path("/proc/self/cwd").exists():
        found = {}
        for pid in pids:
            try:
                found[pid] = os.readlink(f"/proc/{pid}/cwd")
            except OSError:
                pass
        return found
    # The macOS system lsof is normally /usr/sbin/lsof, absent from the
    # intentionally reduced PATH of the local Gateway test runner. Preserve
    # process ownership cleanup instead of silently skipping leaked shells.
    lsof = shutil.which("lsof")
    if not lsof and Path("/usr/sbin/lsof").is_file():
        lsof = "/usr/sbin/lsof"
    if not lsof:
        raise RuntimeError(
            "test process cleanup unavailable: lsof not installed and /proc absent"
        )
    out = subprocess.run(
        [lsof, "-a", "-d", "cwd", "-Fpn", "-p", ",".join(map(str, sorted(pids)))],
        capture_output=True,
        text=True,
    ).stdout
    found, pid = {}, None
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid is not None:
            found[pid] = line[1:]
    return found


def leftovers(before: set[int], root: str) -> list[int]:
    """Processes started since ``before`` that this pytest owns (see the module docstring), and every descendant."""
    table = processes()
    protected, pid = set(), os.getpid()
    while (
        pid > 1 and pid not in protected
    ):  # pytest and its ancestors are never touched
        protected.add(pid)
        pid = table.get(pid, (1, 0, ""))[0]
    new = {p for p in table if p not in before and p not in protected}
    mine = set()
    for p in new:
        q = table[p][0]
        while q > 1 and q not in mine and q != os.getpid():
            q = table.get(q, (1, 0, ""))[0]
        if q == os.getpid() or q in mine:
            mine.add(p)
    root = os.path.realpath(root)
    mine |= {
        p
        for p, d in cwds(new - mine).items()
        if os.path.realpath(d) == root or os.path.realpath(d).startswith(root + os.sep)
    }
    found, frontier = set(mine), set(mine)
    while frontier:
        frontier = {
            p
            for p, (ppid, _, _) in table.items()
            if ppid in frontier and p not in found | protected
        }
        found |= frontier
    return sorted(found)


def stop(pids: list[int]) -> None:
    if not pids:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in pids:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(0.2)


@pytest.fixture(autouse=True)
def stop_leftover_processes(tmp_path_factory):
    before = set(processes())
    yield
    stop(leftovers(before, str(tmp_path_factory.getbasetemp())))


def _installed_import_gate():
    """Pin installed Core before collection-time legacy path bootstraps run."""
    import hashlib
    import importlib
    import json
    import sys

    expected = os.environ.get("AETHER_CORE_TEST_PACKAGE_ROOT")
    if not expected:
        return
    package = importlib.import_module("aether.core")
    root = Path(expected).resolve()
    if Path(package.__file__).resolve().parent != root:
        pytest.exit("installed Core gate imported a source checkout", returncode=2)
    observed = []
    for name, module in list(sys.modules.items()):
        if name != "aether.core" and not name.startswith("aether.core."):
            continue
        origin = getattr(module, "__file__", None)
        if not origin or not Path(origin).resolve().is_relative_to(root):
            pytest.exit("installed Core module origin mismatch: " + name, returncode=2)
        observed.append(
            {
                "module": name,
                "origin": str(Path(origin).resolve()),
                "sha256": hashlib.sha256(Path(origin).read_bytes()).hexdigest(),
            }
        )
    receipt = os.environ.get("AETHER_CORE_IMPORT_RECEIPT")
    if receipt:
        Path(receipt).write_text(
            json.dumps(
                {
                    "expected_package_root": str(root),
                    "modules": observed,
                    "all_loaded_core_modules_from_installed_package": True,
                },
                indent=2,
            )
            + "\n"
        )


def pytest_sessionstart(session):
    _installed_import_gate()


def pytest_collection_finish(session):
    _installed_import_gate()
    if os.environ.get("AETHER_CORE_TEST_PACKAGE_ROOT"):
        import sys

        source = Path(__file__).resolve().parents[1] / "src"
        sys.path[:] = [p for p in sys.path if Path(p).resolve() != source]


def pytest_sessionfinish(session, exitstatus):
    _installed_import_gate()


# Feature-on regression (plan §7 change 1): AETHER_CORE_TEST_SUBSTRATE=on runs every test with the substrate switches
# on by default, so a test that never mentions them exercises them: operation tracking and adoption for terminals,
# Python and MCP (terminal_events / preserve_existing / track_operations / adopt) and the tool deadline. Tests that
# pass a value explicitly keep it. Model-facing switches stay as each test sets them.
if os.environ.get("AETHER_CORE_TEST_SUBSTRATE") == "on":
    from aether.core import loop as _loop, mcp as _mcp, repl as _repl, terminal as _terminal

    def _defaulting(cls, *names):
        original = cls.__init__

        def __init__(self, *args, **kwargs):
            for name in names:
                kwargs.setdefault(name, True)
            original(self, *args, **kwargs)

        cls.__init__ = __init__

    _defaulting(_loop.CoreConfig, "terminal_events")
    _defaulting(_terminal.Terminals, "preserve_existing")
    _defaulting(_repl.Repl, "track_operations")
    _defaulting(_mcp.Mcp, "adopt")
