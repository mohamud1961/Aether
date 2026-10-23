"""The differential check (AETHER_CORE_DIFFCHECK): a check written from the task alone, accepted only if it separates
its own good and broken candidates, run by the harness on the solver's file. Real files, real python3 processes;
the author is scripted (it writes the files a model would write). Each test fails without the mechanism."""

from __future__ import annotations

import asyncio
from pathlib import Path

from aether.core import diffcheck
from aether.core.diffcheck import DiffCheck, author_config
from aether.core.harbor_agent import build_config
from tests.core_fakes import LocalEnv

BASE = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}

# A check for "write /…/double.py defining double(x) = 2x": loads the candidate, compares with the reference.
CHECK = '''import argparse, importlib.util, sys
p = argparse.ArgumentParser(); p.add_argument("--candidate"); a = p.parse_args()
try:
    spec = importlib.util.spec_from_file_location("cand", a.candidate); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
except Exception as e:
    print(f"input: import / expected: module loads / actual: {type(e).__name__}: {e}"); sys.exit(1)
bad = 0
for x in (0, 1, -3, 10**12):
    got = m.double(x)
    if got != 2 * x:
        print(f"input: {x} / expected: {2 * x} / actual: {got}"); bad += 1
sys.exit(1 if bad else 0)
'''
GOOD, BROKEN = "def double(x):\n    return 2 * x\n", "def double(x):\n    return x + 2\n"


class Rig:
    def __init__(self, root: Path, *, check: str = CHECK, broken: str = BROKEN, fail: bool = False,
                 remaining: float = 3600.0) -> None:
        self.root, self.dir, self.target = root, root / "dc", root / "app" / "double.py"
        self.dir.mkdir()
        self.target.parent.mkdir()
        self.rows: list[tuple[str, dict]] = []
        self.briefs: list[str] = []
        self.now = 0.0
        self.check, self.broken, self.fail = check, broken, fail
        self.dc = DiffCheck(LocalEnv(root), f"Write {self.target} defining double(x).", str(self.dir),
                            lambda: remaining, lambda event, **data: self.rows.append((event, data)), self.author,
                            lambda: self.now)

    async def author(self, brief: str, timeout_s: float) -> None:
        self.briefs.append(brief)
        if self.fail:
            raise RuntimeError("provider down")
        (self.dir / "check.py").write_text(self.check)
        (self.dir / "good_candidate.py").write_text(GOOD)
        (self.dir / "broken_candidate.py").write_text(self.broken)
        (self.dir / "target").write_text(f"{self.target}\n")

    async def step(self, content: str | None = None, advance: float = 61.0) -> str:
        if content is not None:
            self.target.write_text(content)
        self.now += advance
        await asyncio.sleep(0)
        return await self.dc.after_action()

    def events(self) -> list[str]:
        return [e for e, _ in self.rows]


def run(fn, tmp_path, **kw):
    async def go():
        rig = Rig(tmp_path, **kw)
        rig.dc.start()
        try:
            return await fn(rig)
        finally:
            await rig.dc.close()

    return asyncio.run(go())


def test_a_wrong_file_gets_the_checks_own_disagreement_and_the_command_to_rerun_it(tmp_path):
    async def go(rig):
        note = await rig.step("def double(x):\n    return x * x\n")
        assert "[independent check: " in note and "disagrees" in note
        assert "input: 1 / expected: 2 / actual: 1" in note
        assert f"python3 {rig.dir}/check.py --candidate {rig.target}" in note
        assert "can be wrong" in note
        assert rig.dc.state == "ready" and "diffcheck_ready" in rig.events()

    run(go, tmp_path)


def test_a_correct_file_gets_nothing(tmp_path):
    async def go(rig):
        assert await rig.step(GOOD) == ""
        assert rig.dc.runs and rig.dc.runs[-1]["exit"] == 0

    run(go, tmp_path)


def test_the_same_disagreement_is_said_once_and_agreement_after_it_once(tmp_path):
    async def go(rig):
        assert "disagrees" in await rig.step("def double(x):\n    return x * x\n")
        assert await rig.step("def double(x):\n    return x * x  # same behaviour\n") == ""
        assert "now agrees" in await rig.step(GOOD)
        assert await rig.step(GOOD + "# still right\n") == ""

    run(go, tmp_path)


def test_unchanged_files_are_not_rerun_and_changes_wait_for_the_gap(tmp_path):
    async def go(rig):
        assert "disagrees" in await rig.step("def double(x):\n    return 0\n")
        assert await rig.step(advance=1.0) == "" and len(rig.dc.runs) == 1  # same content: not re-run
        assert await rig.step("def double(x):\n    return 1\n", advance=5.0) == ""  # changed, inside the gap
        assert len(rig.dc.runs) == 1
        assert "disagrees" in await rig.step(advance=61.0)  # the change is picked up once the gap has passed
        assert len(rig.dc.runs) == 2

    run(go, tmp_path)


def test_a_check_that_cannot_separate_its_own_candidates_is_never_shown(tmp_path):
    async def go(rig):
        assert await rig.step("def double(x):\n    return x * x\n") == ""
        assert rig.dc.state == "rejected" and rig.dc.runs == []
        assert any(e == "diffcheck_rejected" for e in rig.events())

    run(go, tmp_path, broken=GOOD)  # the "broken" candidate is correct: the check exits 0 on it


def test_a_check_that_always_fails_is_never_shown(tmp_path):
    async def go(rig):
        assert await rig.step("def double(x):\n    return x * x\n") == ""
        assert rig.dc.state == "rejected"

    run(go, tmp_path, check="import sys\nprint('input: - / expected: - / actual: -')\nsys.exit(1)\n")


def test_a_check_edited_in_the_container_is_restored_before_it_runs(tmp_path):
    async def go(rig):
        await rig.step("def double(x):\n    return x * x\n")
        (rig.dir / "check.py").write_text("import sys\nsys.exit(0)\n")  # refitted to pass anything
        note = await rig.step("def double(x):\n    return x + x + 1\n")
        assert "disagrees" in note and "diffcheck_check_restored" in rig.events()
        assert (rig.dir / "check.py").read_text() == CHECK

    run(go, tmp_path)


def test_an_author_failure_is_traced_and_says_nothing(tmp_path):
    async def go(rig):
        assert await rig.step("def double(x):\n    return x * x\n") == ""
        assert rig.dc.state == "failed" and "diffcheck_author_failed" in rig.events()

    run(go, tmp_path, fail=True)


def test_no_author_when_too_little_time_is_left(tmp_path):
    async def go(rig):
        assert rig.dc.job is None and rig.events() == ["diffcheck_skipped"]

    run(go, tmp_path, remaining=200.0)


def test_the_brief_is_the_task_alone_and_forbids_the_solvers_files(tmp_path):
    async def go(rig):
        await rig.step()
        brief = rig.briefs[0]
        assert brief.endswith(f"The task:\nWrite {rig.target} defining double(x).")
        assert "do not open it or depend on it" in brief and "nothing outside" in brief

    run(go, tmp_path)


def test_flag_and_author_configuration():
    config = build_config(environ={**BASE, diffcheck.DIFFCHECK_ENV: "on"})
    assert config.diffcheck and not build_config(environ=BASE).diffcheck
    author = author_config(config)
    assert author.role == diffcheck.AUTHOR_ROLE and not author.diffcheck and not author.verify
    assert not author.record and author.reviews.finish is False
    assert author.control_dir.endswith("-diffcheck") and author.clm.mirror_path.startswith(author.control_dir)


# ---- through the loop: the author is a second Core run on the same provider, its note reaches the solver ----

from aether.core.calls import CallLog  # noqa: E402
from aether.core.clm import ClmSettings  # noqa: E402
from aether.core.loop import CoreConfig, Trace, run_agent  # noqa: E402
from aether.core.provider import ChatProvider  # noqa: E402
from tests.core_fakes import ScriptedClient, chunk, tool_chunk  # noqa: E402


def _turn(name, args, call_id):
    return [tool_chunk(name, args, call_id=call_id), chunk(finish="tool_calls"),
            chunk(usage={"prompt_tokens": 10, "completion_tokens": 3})]


class RoleClient:
    """Serves the author's script to requests whose task is the author's brief, the solver's script otherwise."""

    def __init__(self, solver: list, author: list) -> None:
        self.solver, self.author = ScriptedClient(solver), ScriptedClient(author)
        self.chat = type("C", (), {"completions": type("D", (), {"create": self._create})()})()

    async def _create(self, **kwargs):
        mine = any("Someone else is working on the task" in str(m.get("content")) for m in kwargs["messages"])
        return await (self.author if mine else self.solver).chat.completions.create(**kwargs)


def test_the_loop_runs_the_author_and_shows_the_disagreement_in_the_solvers_next_result(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir()
    ctl.mkdir()
    target, dc = work / "double.py", f"{ctl}/diffcheck"
    task = f"Write {target} defining double(x), which returns twice x."
    author = [_turn("write_file", {"path": f"{dc}/{name}", "content": text}, f"a{i}") for i, (name, text) in
              enumerate((("check.py", CHECK), ("good_candidate.py", GOOD), ("broken_candidate.py", BROKEN),
                         ("target", f"{target}\n")))] + [_turn("finish", {"summary": "check validated"}, "a9")]
    solver = [_turn("write_file", {"path": str(target), "content": "def double(x):\n    return x * x\n"}, "s1")]
    solver += [_turn("terminal", {"input": "sleep 1"}, f"s{i}") for i in range(2, 6)]
    solver += [_turn("finish", {"summary": "done"}, "s9")]
    client = RoleClient(solver, author)
    provider = ChatProvider(client, model="scripted", params={}, log=CallLog(tmp_path / "calls.jsonl"))
    config = CoreConfig(control_dir=str(ctl), diffcheck=True,
                        clm=ClmSettings(mirror_path=f"{ctl}/ctx/LIVE_CTX.txt", history_path=f"{ctl}/ctx/HISTORY.txt"))
    result = asyncio.run(run_agent(env=LocalEnv(work), task=task, workdir=str(work), provider=provider,
                                   timeout_s=900, trace=Trace(tmp_path / "logs" / "core_trace.jsonl"), config=config))
    assert result.status == "finished" and not client.solver.script and not client.author.script
    shown = [m["content"] for r in client.solver.requests for m in r["messages"] if m.get("role") == "tool"]
    assert any("disagrees" in c and "input: 1 / expected: 2 / actual: 1" in c for c in shown)
    assert not any("Someone else is working" in str(m.get("content")) for r in client.solver.requests
                   for m in r["messages"])  # the solver never sees the author's brief
    assert result.extras["diffcheck"]["state"] == "ready" and result.extras["diffcheck"]["shown"] >= 1
    assert set(provider.log.by_role) == {"worker", diffcheck.AUTHOR_ROLE}
    assert (tmp_path / "logs" / diffcheck.TRACE_FILE).exists()
