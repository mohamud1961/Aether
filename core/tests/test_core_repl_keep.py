"""End of run with end_processes "keep": a service the model started from python keeps running (28 Oct homolog)."""

import asyncio
import os
import signal
import time

from aether.core.repl import Repl

from tests.core_fakes import LocalEnv


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    state = os.popen(f"ps -o stat= -p {pid}").read().strip()
    return bool(state) and not state.startswith("Z")


def _start_child(tmp_path):
    async def go():
        repl = Repl(LocalEnv(tmp_path), str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "repl"))
        assert await repl.start()
        out = await repl.run(
            "import subprocess,sys\n"
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True)\n"
            "print('child', p.pid)"
        )
        child = int(out.split("child ")[1].split()[0])
        kernel = repl.pid
        return repl, kernel, child
    return asyncio.run(go())


def test_keep_leaves_a_detached_child_of_the_repl_running(tmp_path):
    repl, kernel, child = _start_child(tmp_path)
    try:
        asyncio.run(repl.close(keep=True))
        time.sleep(0.5)
        # known-bad (before the fix): close() stopped the whole tree, so the model's service died with the run
        assert _alive(child)
        assert repl.cleanup_receipt["status"] == "retained"
        assert any(line.startswith(f"{child} ") for line in repl.cleanup_receipt["observed_processes"])
    finally:
        for pid in (child, kernel):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_without_keep_close_still_stops_the_tree(tmp_path):
    repl, kernel, child = _start_child(tmp_path)
    try:
        asyncio.run(repl.close())
        time.sleep(0.5)
        assert not _alive(child) and not _alive(kernel)
    finally:
        for pid in (child, kernel):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
