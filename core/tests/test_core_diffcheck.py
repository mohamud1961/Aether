"""Offline component mechanics plus the public fail-closed admission path.

The scripted author tests do not establish author isolation or oracle correctness. The loop test checks that no
same-container author run occurs.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from aether.core import diffcheck, diffcheck_text
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
CHECK_WITH_SUPPORT = '''import argparse, importlib.util, sys
import reference
p = argparse.ArgumentParser(); p.add_argument("--candidate"); a = p.parse_args()
spec = importlib.util.spec_from_file_location("cand", a.candidate); m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for x in (0, 1, -3, 10**12):
    expected = reference.double(x); actual = m.double(x)
    if actual != expected:
        print(f"input: {x} / expected: {expected} / actual: {actual}"); sys.exit(1)
sys.exit(0)
'''
GOOD, BROKEN = "def double(x):\n    return 2 * x\n", "def double(x):\n    return x + 2\n"
REFERENCE = "def double(x):\n    return 2 * x\n"


class Rig:
    def __init__(self, root: Path, *, check: str = CHECK, broken: str = BROKEN, fail: bool = False,
                 remaining: float = 3600.0, status: str = "finished", support: str | None = None) -> None:
        self.root, self.dir, self.target = root, root / "dc", root / "app" / "double.py"
        self.dir.mkdir()
        self.target.parent.mkdir()
        self.rows: list[tuple[str, dict]] = []
        self.briefs: list[str] = []
        self.author_envs: list = []
        self.now = 0.0
        self.check, self.broken, self.fail = check, broken, fail
        self.status, self.support = status, support
        self.dc = DiffCheck(LocalEnv(root), f"Write {self.target} defining double(x).", str(self.dir),
                            lambda: remaining, lambda event, **data: self.rows.append((event, data)), self.author,
                            lambda: self.now)

    async def author(self, brief: str, timeout_s: float, env=None) -> None:
        self.briefs.append(brief)
        self.author_envs.append(env)
        if self.fail:
            raise RuntimeError("provider down")
        (self.dir / "check.py").write_text(self.check)
        (self.dir / "good_candidate.py").write_text(GOOD)
        (self.dir / "broken_candidate.py").write_text(self.broken)
        (self.dir / "target").write_text(f"{self.target}\n")
        if self.support is not None:
            (self.dir / "reference.py").write_text(self.support)
        return SimpleNamespace(status=self.status)

    async def prime_component(self) -> None:
        """Bypass public admission to test deterministic checker mechanics only."""
        self.dc.state = "authoring"
        brief = diffcheck_text.AUTHOR_BRIEF.format(dir=str(self.dir), task=self.dc.task, check_s=diffcheck.CHECK_S)
        self.dc.job = asyncio.create_task(self.author(brief, 10.0))
        await asyncio.gather(self.dc.job, return_exceptions=True)
        await self.dc._accept()

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
        await rig.prime_component()
        try:
            return await fn(rig)
        finally:
            await rig.dc.close()

    return asyncio.run(go())


def test_a_wrong_file_gets_only_a_provenance_unverified_candidate_check_result(tmp_path):
    async def go(rig):
        note = await rig.step("def double(x):\n    return x * x\n")
        assert "[candidate check result, provenance unverified:" in note and "disagrees" in note
        assert "input: 1 / expected: 2 / actual: 1" in note
        assert f"python3 {rig.dir}/check.py --candidate {rig.target}" in note
        assert "may be wrong" in note
        assert "does not establish oracle correctness" in note
        assert rig.dc.state == "ready" and "diffcheck_candidate_ready_unverified" in rig.events()
        assert rig.dc.summary()["validation"] == "two_sample_discrimination_only"

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
        assert "agrees with the check" in await rig.step(GOOD)
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


def test_public_start_fails_closed_and_never_launches_author(tmp_path):
    async def go():
        rig = Rig(tmp_path)
        await rig.dc.start()
        assert rig.dc.state == "unverified" and rig.dc.job is None and rig.briefs == []
        assert rig.events() == ["diffcheck_admission_blocked"]
        assert (await rig.step("def double(x):\n    return x * x\n")) == ""
        assert rig.dc.runs == []
        assert rig.dc.summary()["oracle_correctness"] == "unverified"
        assert rig.dc.summary()["validation"] == "not_run"

    asyncio.run(go())


def test_the_brief_does_not_claim_the_author_cannot_see_solver_files(tmp_path):
    async def go(rig):
        await rig.step()
        brief = rig.briefs[0]
        assert "author may see or change the candidate" in brief
        assert "prompt cannot enforce separation" in brief
        assert "only discrimination of those two samples" in brief
        assert "not correctness of the check's oracle" in brief

    run(go, tmp_path)


def test_deleted_check_is_restored_but_deleted_support_file_blocks_run(tmp_path):
    async def go(rig):
        (rig.dir / "check.py").unlink()
        note = await rig.step("def double(x):\n    return x * x\n")
        assert "disagrees" in note
        assert (rig.dir / "check.py").read_text() == CHECK
        assert "diffcheck_check_restored" in rig.events()

    run(go, tmp_path)


def test_changed_support_dependency_is_inconclusive(tmp_path):
    async def go(rig):
        (rig.dir / "reference.py").write_text("def double(x):\n    return x + 2\n")
        note = await rig.step("def double(x):\n    return x * x\n")
        assert "checker/support files changed or were deleted" in note
        assert rig.dc.runs == []

    run(go, tmp_path, check=CHECK_WITH_SUPPORT, support=REFERENCE)


def test_deleted_support_dependency_is_inconclusive(tmp_path):
    async def go(rig):
        (rig.dir / "reference.py").unlink()
        note = await rig.step("def double(x):\n    return x * x\n")
        assert "checker/support files changed or were deleted" in note
        assert rig.dc.runs == []

    run(go, tmp_path, check=CHECK_WITH_SUPPORT, support=REFERENCE)


def test_added_symlink_support_directory_is_inconclusive(tmp_path):
    async def go(rig):
        outside = rig.root / "outside"
        outside.mkdir()
        (outside / "reference.py").write_text(REFERENCE)
        (rig.dir / "linked-reference").symlink_to(outside, target_is_directory=True)
        note = await rig.step(GOOD)
        assert "checker/support files changed or were deleted" in note
        assert rig.dc.runs == []

    run(go, tmp_path)


def test_missing_candidate_is_inconclusive_not_agreement(tmp_path):
    async def go(rig):
        note = await rig.step()
        assert "candidate file is missing" in note
        assert rig.dc.runs == []

    run(go, tmp_path)


def test_candidate_snapshot_is_bounded(tmp_path):
    async def go(rig):
        note = await rig.step("x" * (diffcheck.MAX_CANDIDATE_BYTES + 1))
        assert "candidate exceeds 16777216 byte snapshot limit" in note
        assert rig.dc.runs == []

    run(go, tmp_path)


def test_candidate_snapshot_preserves_file_mode(tmp_path):
    async def go(rig):
        rig.target.write_text(GOOD)
        rig.target.chmod(0o751)
        rig.now += 61.0
        assert await rig.dc.after_action() == ""
        assert rig.dc.runs[-1]["exit"] == 0

    check = "\n".join([
        "import argparse, os, pathlib, sys",
        "p=argparse.ArgumentParser(); p.add_argument('--candidate'); a=p.parse_args()",
        "name=pathlib.Path(a.candidate).name",
        "if name.startswith('good_candidate'): sys.exit(0)",
        "if name.startswith('broken_candidate'):",
        "    print('input: 1 / expected: 2 / actual: 3'); sys.exit(1)",
        "if '.aether-diffcheck-' in name and os.stat(a.candidate).st_mode & 0o777 != 0o751:",
        "    sys.exit(2)",
        "sys.exit(0)",
    ])
    run(go, tmp_path, check=check)


def test_changed_candidate_during_subprocess_check_is_discarded(tmp_path):
    async def go(rig):
        marker = rig.root / "checker-started"
        slow_check = CHECK.replace(
            "bad = 0",
            f"from pathlib import Path\nimport time\nPath({str(marker)!r}).write_text('started')\n"
            "time.sleep(0.25)\nbad = 0",
        )
        rig.check = slow_check
        rig.dc.state = "authoring"
        brief = diffcheck_text.AUTHOR_BRIEF.format(dir=str(rig.dir), task=rig.dc.task, check_s=diffcheck.CHECK_S)
        rig.dc.job = asyncio.create_task(rig.author(brief, 10.0))
        await asyncio.gather(rig.dc.job, return_exceptions=True)
        await rig.dc._accept()
        marker.unlink(missing_ok=True)  # ignore the marker from two-sample validation
        task = asyncio.create_task(rig.step("def double(x):\n    return x * x\n"))
        for _ in range(200):
            if marker.exists():
                break
            await asyncio.sleep(0.005)
        assert marker.exists(), "checker subprocess did not start"
        rig.target.write_text(GOOD)
        note = await task
        assert "candidate changed during check" in note
        assert rig.dc.runs[-1]["status"] == "inconclusive_changed_during_check"
        assert "disagrees" not in note

    run(go, tmp_path)


def test_checker_changed_during_run_is_restored_and_result_discarded(tmp_path):
    async def go(rig):
        note = await rig.step("def double(x):\n    return x * x\n")
        assert "checker source changed during check" in note, (note, rig.rows, rig.dc.runs)
        assert rig.dc.runs[-1]["status"] == "inconclusive_checker_inputs_changed"
        assert (rig.dir / "check.py").read_text() == rig.check

    check = "\n".join([
        "import argparse, pathlib, sys",
        "p=argparse.ArgumentParser(); p.add_argument('--candidate'); a=p.parse_args()",
        "name=pathlib.Path(a.candidate).name",
        "if name.startswith('good_candidate'): sys.exit(0)",
        "if '.aether-diffcheck-' in a.candidate:",
        "    pathlib.Path(__file__).write_text('changed')",
        "print('input: 1 / expected: 2 / actual: 1')",
        "sys.exit(1)",
    ])
    run(go, tmp_path, check=check)


def test_cancelled_author_is_not_accepted(tmp_path):
    async def go():
        rig = Rig(tmp_path)
        rig.dc.state = "authoring"

        async def wait_forever():
            await asyncio.Future()

        rig.dc.job = asyncio.create_task(wait_forever())
        rig.dc.job.cancel()
        await asyncio.sleep(0)
        await rig.dc.after_action()
        assert rig.dc.state == "cancelled" and rig.dc.runs == []
        assert "diffcheck_author_cancelled" in rig.events()

    asyncio.run(go())


def test_author_timeout_status_is_not_accepted(tmp_path):
    async def go(rig):
        assert rig.dc.state == "failed" and rig.dc.runs == []
        event = next(data for name, data in rig.rows if name == "diffcheck_author_inconclusive")
        assert event["status"] == "timeout"

    run(go, tmp_path, status="timeout")


def test_checker_inconclusive_status_is_recorded_once_per_artifact(tmp_path):
    async def go(rig):
        note = await rig.step(GOOD)
        assert "checker exited inconclusively (2)" in note
        assert rig.dc.runs[-1]["status"] == "inconclusive"
        assert await rig.step(advance=61.0) == ""
        assert len(rig.dc.runs) == 1

    check = '''import os,sys
name=os.path.basename(sys.argv[sys.argv.index("--candidate")+1])
if name.startswith("good_candidate"): sys.exit(0)
if name.startswith("broken_candidate"):
    print("input: 1 / expected: 2 / actual: 3"); sys.exit(1)
sys.exit(2)
'''
    run(go, tmp_path, check=check)


def test_checker_timeout_is_reported_as_inconclusive(tmp_path):
    async def go(rig):
        original = diffcheck.CHECK_S
        diffcheck.CHECK_S = 0.01
        try:
            note = await rig.step(GOOD)
            assert "checker timed out" in note
            assert rig.dc.runs[-1]["status"] == "inconclusive"
            assert await rig.step(advance=61.0) == ""
            assert len(rig.dc.runs) == 1
        finally:
            diffcheck.CHECK_S = original
            # LocalEnv waits are cancelled; let the tiny fixture process exit before cleanup.
            await asyncio.sleep(0.35)

    check = '''import os,sys,time
name=os.path.basename(sys.argv[sys.argv.index("--candidate")+1])
if name.startswith("good_candidate"): sys.exit(0)
if name.startswith("broken_candidate"):
    print("input: 1 / expected: 2 / actual: 3"); sys.exit(1)
time.sleep(0.25)
'''
    run(go, tmp_path, check=check)


def test_flag_and_author_configuration():
    config = build_config(environ={**BASE, diffcheck.DIFFCHECK_ENV: "on"})
    assert config.diffcheck and not build_config(environ=BASE).diffcheck
    author = author_config(config)
    assert author.role == diffcheck.AUTHOR_ROLE and not author.diffcheck and not author.verify
    assert not author.record and author.reviews.finish is False
    assert author.control_dir.endswith("-diffcheck") and author.clm.mirror_path.startswith(author.control_dir)


# ---- through the loop: same-container author is blocked before any model call ----

from aether.core.calls import CallLog  # noqa: E402
from aether.core.clm import ClmSettings  # noqa: E402
from aether.core.loop import CoreConfig, Trace, run_agent  # noqa: E402
from aether.core.provider import ChatProvider  # noqa: E402
from tests.core_fakes import ScriptedClient, chunk, tool_chunk  # noqa: E402


def _turn(name, args, call_id):
    return [tool_chunk(name, args, call_id=call_id), chunk(finish="tool_calls"),
            chunk(usage={"prompt_tokens": 10, "completion_tokens": 3})]


class RoleClient:
    """Keeps an author script available so an accidental author call is observable."""

    def __init__(self, solver: list, author: list) -> None:
        self.solver, self.author = ScriptedClient(solver), ScriptedClient(author)
        self.chat = type("C", (), {"completions": type("D", (), {"create": self._create})()})()

    async def _create(self, **kwargs):
        mine = any("author may see or change the candidate" in str(m.get("content")) for m in kwargs["messages"])
        return await (self.author if mine else self.solver).chat.completions.create(**kwargs)


def test_the_loop_blocks_the_shared_environment_author(tmp_path):
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
    assert result.status == "finished" and not client.solver.script
    assert client.author.script  # the author model script was not consumed
    shown = [m["content"] for r in client.solver.requests for m in r["messages"] if m.get("role") == "tool"]
    assert not any("candidate check" in c for c in shown)
    assert result.extras["diffcheck"]["state"] == "unverified"
    assert result.extras["diffcheck"]["provenance"] == "unverified"
    assert result.extras["diffcheck"]["runs"] == []
    assert set(provider.log.by_role) == {"worker"}


class Box(LocalEnv):
    """Stands in for the author's own container: every command it runs is recorded apart from the solver's."""

    closed = False

    async def close(self) -> None:
        self.closed = True


def isolated(tmp_path, fn, **kw):
    async def go():
        rig = Rig(tmp_path, **kw)
        box = Box(tmp_path)
        async def factory(timeout_s):
            return box
        rig.dc._box_factory = factory
        await rig.dc.start()
        await asyncio.gather(rig.dc.job, return_exceptions=True)
        try:
            return await fn(rig, box)
        finally:
            await rig.dc.close()
        assert box.closed

    return asyncio.run(go())


def _checks(env):
    return [c for c in env.commands if "check.py --candidate" in c]


def test_isolated_author_works_in_its_box_and_the_check_runs_only_there(tmp_path):
    async def go(rig, box):
        assert rig.author_envs == [box] and "you will never see their work" in rig.briefs[0]
        note = await rig.step("def double(x):\n    return x * x\n")
        assert note.startswith("[independent check:") and "disagrees" in note and "input: 1" in note
        assert _checks(box) and not _checks(rig.dc.env)
        assert "diffcheck_ready" in rig.events() and rig.dc.summary()["provenance"] == "isolated_clone"

    isolated(tmp_path, go)


def test_isolated_finish_with_a_disagreeing_file_is_held_once(tmp_path):
    async def go(rig, box):
        rig.target.write_text("def double(x):\n    return x * x\n")
        first = await rig.dc.at_finish()
        assert "disagrees" in first and "has not taken effect" in first
        assert await rig.dc.at_finish() == ""  # a second finish always takes effect

    isolated(tmp_path, go)


def test_isolated_finish_holds_when_the_disagreement_was_already_shown(tmp_path):
    async def go(rig, box):
        assert "disagrees" in await rig.step("def double(x):\n    return x * x\n")
        held = await rig.dc.at_finish()
        assert "disagrees" in held and "has not taken effect" in held

    isolated(tmp_path, go)


def test_isolated_finish_with_an_agreeing_file_takes_effect(tmp_path):
    async def go(rig, box):
        rig.target.write_text(GOOD)
        assert await rig.dc.at_finish() == ""
        assert rig.dc.runs[-1]["status"] == "agrees"

    isolated(tmp_path, go)


def test_isolated_box_failure_is_traced_and_the_run_goes_on(tmp_path):
    async def go():
        rig = Rig(tmp_path)
        async def factory(timeout_s):
            raise RuntimeError("docker commit failed")
        rig.dc._box_factory = factory
        await rig.dc.start()
        assert rig.dc.state == "failed" and rig.briefs == [] and "diffcheck_box_failed" in rig.events()
        assert await rig.dc.at_finish() == ""

    asyncio.run(go())


MULTILINE_CHECK = CHECK.replace('print(f"input: {x} / expected: {2 * x} / actual: {got}")',
                                'print(f"input: {x}\\nexpected: {2 * x}\\nactual: {got}")')


def test_isolated_finish_holds_on_a_disagreement_printed_one_field_per_line(tmp_path):
    async def go(rig, box):
        rig.target.write_text("def double(x):\n    return x * x\n")
        held = await rig.dc.at_finish()
        assert "disagrees" in held and "expected: 2" in held and "has not taken effect" in held

    assert MULTILINE_CHECK != CHECK
    isolated(tmp_path, go, check=MULTILINE_CHECK)
