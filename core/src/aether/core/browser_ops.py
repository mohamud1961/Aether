"""Browser code runs as tracked operations in the sidecar (operations.py applied to the ``browser`` tool).

Before, each call piped the model's code into one ``docker exec`` and waited for its stdout. If that exec's reply was
lost, or the host wait expired, nothing recorded whether the code had run or what it printed. The process inside the
sidecar kept going, and a retry started a second run against the task's servers while the first might still be acting.

Now each call is run ``<n>`` with these records in ``OPS_DIR`` in the sidecar:

- ``code_<n>.py`` the code, copied in before launch.
- ``pid_<n>``     the runner shell, written before it tries the token, so a taken token always has a pid to check.
- ``start_<n>``   the start token (symlink): the runner takes it as ``run`` and runs the code only if that succeeded;
  Core takes it as ``revoked`` when it lost the launch and must know for certain that the code never ran.
- ``out_<n>``     everything the code printed.
- ``done_<n>``    its exit status, written last.

The runner is detached and bounded by its own ``timeout``, so a host wait that ends early loses nothing: the result
is shown at the next browser use. An identical call (same code, files and screenshot) made while a run is tracked
attaches to it instead of running the code again.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from . import operations
from .clone import HostRun

OPS_DIR = "/tmp/.aether-ops"
POLL_SLICE_S = 10
_LAUNCH = (
    'cd "$1" || exit 4; echo $$ > "pid_$2"; command ln -s run "start_$2" 2>/dev/null || exit 0; cd /tmp; '
    'PYTHONPATH="$1${PYTHONPATH:+:$PYTHONPATH}" timeout -k 5 "$3" python3 "$1/code_$2.py" > "$1/out_$2" 2>&1; echo $? > "$1/done_$2.tmp"; '
    'mv -f "$1/done_$2.tmp" "$1/done_$2"'
)
_POLL = (
    'cd "$1" 2>/dev/null || { echo GONE; exit 0; }; i=0; '
    'while [ "$i" -lt "$3" ] && [ ! -f "done_$2" ]; do sleep 0.2; i=$((i+1)); done; '
    'token=$(readlink "start_$2" 2>/dev/null); '
    'if [ -f "done_$2" ]; then echo DONE; cat "done_$2"; '
    'elif [ "$token" = run ]; then kill -0 "$(cat "pid_$2" 2>/dev/null)" 2>/dev/null && echo RUNNING || echo GONE; '
    'elif [ -z "$token" ]; then echo RUNNING; else echo GONE; fi'  # no token yet: the runner is starting
)
_REVOKE = f'cd "$1" || exit 4; command ln -s {operations.REVOKED} "start_$2" 2>/dev/null; readlink "start_$2"'


def key(args: dict[str, Any]) -> str:
    """Identity of a call for attaching retries: what would run, with which inputs."""
    blob = json.dumps([args.get("code", ""), args.get("files") or [], args.get("screenshot")], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class Runs:
    """Tracked browser runs of one sidecar. ``open`` holds runs whose result the model has not been shown."""

    def __init__(self, name: str, host: HostRun, ops_dir: str = OPS_DIR) -> None:
        self.name, self.host, self.ops_dir = name, host, ops_dir
        self.seq = 0
        self.open: dict[int, dict[str, Any]] = {}

    async def _sh(self, script: str, *args: str, timeout: float = 30, detach: bool = False) -> tuple[int, str, str]:
        argv = ["docker", "exec", *(["-d"] if detach else []), self.name, "sh", "-c", script, "core-browser-op", *args]
        return await self.host(argv, timeout)

    async def install(self, module: str, source: str) -> None:
        """Put ``<module>.py`` in the ops directory, which is on every run's PYTHONPATH."""
        status, _, err = await self._sh('mkdir -p "$1"', self.ops_dir)
        if status == 0:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / f"{module}.py"
                path.write_text(source)
                status, _, err = await self.host(
                    ["docker", "cp", str(path), f"{self.name}:{self.ops_dir}/{module}.py"], 60)
        if status != 0:
            raise OSError(f"browser module {module} could not be installed: {err.strip()[:200]}")

    async def launch(self, code: str, life_s: float, call_key: str) -> int:
        """Copy the code in and start its detached runner. Tracked from before the first write, so a lost reply leaves
        the run to be resolved by the token, never re-run."""
        self.seq += 1
        n = self.seq
        self.open[n] = {"key": call_key, "launched": False}
        status, _, err = await self._sh('mkdir -p "$1"', self.ops_dir)
        if status != 0:
            del self.open[n]  # nothing was written for this run
            raise OSError(f"browser run directory could not be created: {err.strip()[:200]}")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "code.py"
            source.write_text(code)
            status, _, err = await self.host(["docker", "cp", str(source), f"{self.name}:{self.ops_dir}/code_{n}.py"], 60)
        if status != 0:
            raise OSError(f"browser code could not be copied in: {err.strip()[:200]}")
        status, _, err = await self._sh(_LAUNCH, self.ops_dir, str(n), str(max(1, int(life_s))), detach=True)
        if status != 0:
            raise RuntimeError(f"browser run could not be launched: {err.strip()[:200]}")
        self.open[n]["launched"] = True
        return n

    async def resolve(self, n: int) -> str | None:
        """For a run whose launch reply was lost: ``run`` (the runner took it) or ``revoked`` (cancelled now; never
        ran). None when the records cannot be read."""
        status, out, _ = await self._sh(_REVOKE, self.ops_dir, str(n))
        token = out.strip()
        if status != 0 or token not in (operations.RUN, operations.REVOKED):
            return None
        if token == operations.REVOKED:
            del self.open[n]
        else:
            self.open[n]["launched"] = True
        return token

    async def collect(self, n: int, wait_s: float) -> str | None:
        """Wait up to ``wait_s`` for run ``n``. Its output and status once finished (it is then no longer open), a
        statement when its runner is gone without a result, or None while it still runs."""
        waited = 0.0
        while True:
            slice_s = min(POLL_SLICE_S, max(0.0, wait_s - waited))
            status, out, err = await self._sh(_POLL, self.ops_dir, str(n), str(int(slice_s * 5)),
                                              timeout=slice_s + 30)
            if status != 0:
                raise RuntimeError(f"browser run #{n} could not be observed: {err.strip()[:200]}")
            word, _, rest = out.strip().partition("\n")
            if word == "DONE":
                exit_code = rest.strip()
                status, text, err = await self._sh('cat "$1/out_$2"', self.ops_dir, str(n))
                if status != 0:
                    raise RuntimeError(f"browser run #{n} output could not be read: {err.strip()[:200]}")
                del self.open[n]
                return _clip(text) + ("" if exit_code == "0" else f"\n[browser command exit status {exit_code}]")
            if word == "GONE":
                del self.open[n]
                return (f"[browser run #{n} ended without a result: its runner is gone. Whether its code had any "
                        "effect is unknown; check before running it again.]")
            waited += slice_s
            if waited >= wait_s:
                return None


MAX_OUT = 12_000


def _clip(text: str) -> str:
    if len(text) <= MAX_OUT:
        return text
    half = MAX_OUT // 2
    return f"{text[:half]}\n[... {len(text) - MAX_OUT} characters omitted ...]\n{text[-half:]}"
