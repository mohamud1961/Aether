"""Kill a browser call at every host command and every step, and check the operation contract (real Linux processes).

The browser tool drives a sidecar through ``docker exec`` and ``docker cp``. Here those commands run as local
processes (``local_host``), so the operation protocol (code file, detached runner, start token, polls) is exercised for
real without Docker. Each host call after arming is a kill point: cut before it runs, cut before each simple command of
its script (bash DEBUG trap), or run with its reply lost. The detached runner itself is never cut: that is an executor
death, reported as an unknown effect, not a controller fault.

The simulated model re-sends the identical call after any failure or unclear reply until it sees the result. At every
kill point the code runs at most once, at least once within a few turns, and its output reaches the model exactly once.
"""

import asyncio
import base64
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest

from aether.core import browser, browser_ops

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
TURNS = 8


async def local_host(argv, timeout_s):
    """``docker exec [-d] NAME cmd...`` and ``docker cp SRC NAME:DST`` as local processes."""
    if argv[:2] == ["docker", "cp"]:
        paths = [arg.split(":")[-1] for arg in argv[2:]]
        shutil.copyfile(*paths)
        return 0, "", ""
    assert argv[:2] == ["docker", "exec"], argv
    rest = argv[2:]
    detach = rest[0] == "-d"
    command = rest[2:] if detach else rest[1:]
    if detach:
        subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0, "", ""
    proc = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(proc.communicate(), timeout_s)
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


class CutHost:
    """After ``armed``: discovery counts each non-detached script's simple commands; fault mode cuts host call
    ``target`` before its ``cut``-th command (0: before the call runs at all), then loses its reply."""

    def __init__(self, root, target=None, cut=None):
        self.root, self.target, self.cut = root, target, cut
        self.armed, self.fired, self.index = False, False, 0
        self.counts: list[int] = []

    def _traced(self, argv, i, cut):
        sh = argv.index("sh")
        if argv[sh + 1] != "-c" or "-d" in argv[:sh]:
            return None
        counter = shlex.quote(str(self.root / f".host-{i}.n"))
        stop = f'[ "$n" -ge {cut} ] && exit 99; ' if cut else ""
        trap = f"n=$((n+1)); echo $n > {counter}; {stop}"
        return [*argv[:sh], "bash", "-c", f"n=0; trap {shlex.quote(trap)} DEBUG; " + argv[sh + 2], *argv[sh + 3:]]

    async def __call__(self, argv, timeout_s):
        if not self.armed or self.fired:
            return await local_host(argv, timeout_s)
        i, self.index = self.index, self.index + 1
        traced = self._traced(argv, i, None) if argv[:2] == ["docker", "exec"] else None
        if self.target is None:
            result = await local_host(traced or argv, timeout_s)
            counter = self.root / f".host-{i}.n"
            self.counts.append(int(counter.read_text()) if traced and counter.exists() else 0)
            return result
        if i != self.target:
            return await local_host(argv, timeout_s)
        self.fired = True
        if self.cut:
            await local_host(self._traced(argv, i, self.cut) if traced else argv, timeout_s)
        raise ConnectionError(f"the controller lost host call {i}")


async def scenario(tmp_path, target=None, cut=None, wait_s=10.0, delay=1):
    host = CutHost(tmp_path, target, cut)
    effects = tmp_path / "effects"
    code = f"open({str(effects)!r}, 'a').write('x')\nimport time\ntime.sleep({delay})\nprint('effect-' + 'done')"
    session = browser.BrowserSession(None, None, host=host)
    car = browser.Sidecar("c" * 64, host)
    car.started, car.runs.ops_dir = True, str(tmp_path / "ops")
    session.sidecar = car
    shown = []
    host.armed = True
    out = await session.use({"code": code, "wait_s": wait_s}, 300.0)
    shown.append(out)
    host.fired = True
    for _ in range(TURNS):
        if any("effect-done" in o for o in shown):
            break
        shown.append(await session.use({"code": code, "wait_s": max(wait_s, 3.0)}, 300.0))
    return {"effects": len(effects.read_text()) if effects.exists() else 0,
            "delivered": sum(o.count("effect-done") for o in shown), "shown": shown, "counts": host.counts}


def sweep(tmp_path):
    (tmp_path / "discover").mkdir()
    found = asyncio.run(scenario(tmp_path / "discover"))
    assert (found["effects"], found["delivered"]) == (1, 1), found["shown"]
    points = [(t, k) for t, n in enumerate(found["counts"]) for k in range(0, n + 2)]
    failures = []
    for i, (target, cut) in enumerate(points):
        case = tmp_path / f"p{i}"
        case.mkdir()
        got = asyncio.run(scenario(case, target, cut))
        if (got["effects"], got["delivered"]) != (1, 1):
            failures.append((target, cut, got["effects"], got["delivered"], got["shown"][-1][-200:]))
    return found["counts"], points, failures


def test_every_browser_call_kill_point_runs_the_code_once_and_delivers_it_once(tmp_path):
    counts, points, failures = sweep(tmp_path)
    print("OPSM-BROWSER tracked", len(counts), "host calls", len(points), "kill points", len(failures), "broken")
    assert len(counts) >= 4 and len(points) >= 10
    assert not failures, f"{len(failures)}/{len(points)} kill points broke the contract: {failures}"


def test_a_run_that_outlives_its_wait_is_shown_later_and_never_run_twice(tmp_path):
    got = asyncio.run(scenario(tmp_path, wait_s=1.0, delay=3))  # the tool waits at least 1 s
    assert "still running after" in got["shown"][0]
    assert (got["effects"], got["delivered"]) == (1, 1), got["shown"]


def test_without_tracking_the_sweep_finds_a_second_run(tmp_path, monkeypatch):
    """Known-bad: forgetting tracked runs before each call (the untracked tool) repeats the code's effect."""
    original = browser.BrowserSession.use

    async def forgetful(self, args, remaining_s):
        if self.sidecar is not None:
            self.sidecar.runs.open.clear()
        return await original(self, args, remaining_s)

    monkeypatch.setattr(browser.BrowserSession, "use", forgetful)
    _, points, failures = sweep(tmp_path)
    print("OPSM-BROWSER untracked", len(points), "kill points", sum(f[2] > 1 for f in failures), "doubled",
          len(failures), "broken")
    assert any(f[2] > 1 for f in failures), "no kill point repeated the effect without tracking"


def test_runs_record_their_ops_in_the_declared_directory():
    assert browser_ops.OPS_DIR == "/tmp/.aether-ops"


def test_screenshot_transfer_failure_retries_the_image_without_repeating_the_action(tmp_path):
    if not browser.images.available():
        pytest.skip("requires image support")
    from PIL import Image

    effects = tmp_path / "effects"
    filename = tmp_path.name + ".png"
    code = (
        f"open({str(effects)!r}, 'a').write('x')\n"
        "from PIL import Image\n"
        f"Image.new('RGB', (25, 25), 'red').save('/tmp/{filename}')\n"
        "print('effect-complete')"
    )

    async def go():
        lost = False

        async def lose_first_download(argv, timeout_s):
            nonlocal lost
            if not lost and argv[:2] == ["docker", "cp"] and ":" in argv[2]:
                lost = True
                return 1, "", "transfer lost"
            return await local_host(argv, timeout_s)

        session = browser.BrowserSession(None, None, host=lose_first_download)
        car = browser.Sidecar("c" * 64, lose_first_download)
        car.started, car.runs.ops_dir = True, str(tmp_path / "ops")
        session.sidecar = car
        args = {"code": code, "screenshot": filename, "wait_s": 10}
        first = await session.use(args, 30)
        # The model can continue interacting with the browser between retries.
        Image.new("RGB", (25, 25), "blue").save(Path("/tmp", filename))
        second = await session.use(args, 30)
        return lost, first, second, session.image

    try:
        lost, first, second, image = asyncio.run(go())
        assert lost and "screenshot unavailable" in first
        assert effects.read_text() == "x"  # An independent file records each execution of the code.
        assert "effect-complete" not in first and "effect-complete" in second
        assert image and image[1].startswith("data:image/")
        data = base64.b64decode(image[1].split(",", 1)[1])
        with Image.open(io.BytesIO(data)) as received:
            assert received.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
    finally:
        Path("/tmp", filename).unlink(missing_ok=True)
