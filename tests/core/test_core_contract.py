"""Acceptance contract: the writer's trial (unfinished state + its own example), sentence coverage, finish holds,
disputes with harness-run evidence, and the loop integration."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
import uuid

from aether.core import contract as C
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core.core_fakes import LocalEnv, ScriptedClient, call

TASK = "Write a word of exactly 5 letters into out.txt in the working directory.\nUse lowercase letters only."


def _provider(script):
    client = ScriptedClient(script)
    return ChatProvider(client, model="glm", params={"tool_choice": "required", "parallel_tool_calls": False}), client


class FakeClone(LocalEnv):
    """A local directory standing in for a container clone; siblings are copies of it."""
    closed: list[str] = []

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        # in a real clone the working directory has the same path in every container
        return await super().exec(command, cwd=str(self.root), env=env, timeout_sec=timeout_sec)

    async def sibling(self) -> "FakeClone":
        copy = self.root.parent / f"sib-{uuid.uuid4().hex[:6]}"
        shutil.copytree(self.root, copy)
        return FakeClone(copy)

    async def close(self) -> None:
        FakeClone.closed.append(str(self.root))


LEN5 = "test \"$(tr -d '\\n' < out.txt | wc -c | tr -d ' ')\" -eq 5"
LOWER = "grep -qx '[a-z]*' out.txt"
EXAMPLE = "printf 'abcde\\n' > out.txt"


def _submit(checks, context=(), example=EXAMPLE, call_id="s1"):
    return call("submit_checks", {"checks": [dict(zip(("requirement", "command", "sentences"), c)) for c in checks],
                                  "context_sentences": list(context), "example": example}, call_id)


def test_sentences_join_wrapped_lines_and_split_list_items():
    text = "Recover the file.\nIt was in /app and\nwas deleted.\n- It is 23 characters long\n1) Save it. Then stop."
    assert C.sentences(text) == ["Recover the file.", "It was in /app and was deleted.",
                                 "- It is 23 characters long", "1) Save it.", "Then stop."]


def test_a_check_that_passes_before_the_work_or_cannot_run_is_sent_back(tmp_path):
    root = tmp_path / "pristine"; root.mkdir()
    provider, client = _provider([
        _submit([("5 letters", "true", [1]), ("lowercase", "nosuchtool out.txt", [2])]),  # vacuous + broken
        _submit([("5 letters", LEN5, [1]), ("lowercase", LOWER, [2])], call_id="s2")])
    rows = []
    contract = asyncio.run(C.write(provider, FakeClone(root), task=TASK, workdir=str(root), log=rows.append))
    feedback = client.requests[1]["messages"][-1]["content"]
    assert "passes before any work was done" in feedback and "cannot run" in feedback
    assert [c.command for c in contract.checks] == [LEN5, LOWER] and contract.turns == 2
    assert not (root / "out.txt").exists()  # the example ran in a sibling, never in the untouched clone


def test_every_sentence_must_be_enforced_or_marked_context(tmp_path):
    root = tmp_path / "pristine"; root.mkdir()
    provider, client = _provider([_submit([("5 letters", LEN5, [1])]),
                                  _submit([("5 letters", LEN5, [1]), ("lowercase", LOWER, [2])], call_id="s2")])
    asyncio.run(C.write(provider, FakeClone(root), task=TASK, workdir=str(root)))
    assert "neither enforced by a check nor listed as context: [2]" in client.requests[1]["messages"][-1]["content"]


def test_a_check_failing_on_the_writers_example_is_reported_but_kept_after_the_last_round(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "MAX_ROUNDS", 2)
    root = tmp_path / "pristine"; root.mkdir()
    wrong = "test \"$(tr -d '\\n' < out.txt | wc -c | tr -d ' ')\" -eq 4"  # off by one: the example catches it
    provider, client = _provider([_submit([("5 letters", wrong, [1]), ("lowercase", LOWER, [2])]),
                                  _submit([("5 letters", wrong, [1]), ("lowercase", LOWER, [2])], call_id="s2")])
    contract = asyncio.run(C.write(provider, FakeClone(root), task=TASK, workdir=str(root)))
    assert "fails on your example of a finished state" in client.requests[1]["messages"][-1]["content"]
    assert len(contract.checks) == 2 and contract.unconfirmed[0]["check"] == "5 letters"


def _contract():
    return C.Contract(checks=[C.Check(1, "5 letters", LEN5), C.Check(2, "lowercase", LOWER)])


def test_finish_holds_on_a_failing_check_and_a_valid_dispute_with_evidence_voids_it(tmp_path):
    work = tmp_path / "work"; work.mkdir(); (work / "out.txt").write_text("Hello\n")

    async def clone(_env):
        return FakeClone(work)
    held = asyncio.run(C.finish_checks(_provider([])[0], LocalEnv(work), _contract(), task=TASK, workdir=str(work),
                                       disputes=[], make_clone=clone, remaining_s=lambda: 300))
    assert held["status"] == "hold" and [r.check.id for r in held["failed"]] == [2]
    assert "lowercase" in C.feedback(held["failed"], {}) and "do not change correct work" in C.feedback([], {})
    ruling = call("ruling", {"valid": False, "task_sentence": "Use lowercase letters only.", "reason": "x"}, "r1")
    provider, client = _provider([ruling])
    out = asyncio.run(C.finish_checks(provider, LocalEnv(work), c := _contract(), task=TASK, workdir=str(work),
                                      disputes=[{"check": 2, "task_sentence": "s", "reason": "r",
                                                 "evidence_command": "cat out.txt"}],
                                      make_clone=clone, remaining_s=lambda: 300))
    seen = client.requests[0]["messages"][-1]["content"]
    assert "EVIDENCE (run by the harness" in seen and "Hello" in seen  # real output, not the worker's claim
    assert out["status"] == "pass" and [x.id for x in c.checks] == [1] and c.voided[0]["check"] == 2


def test_a_rejected_dispute_keeps_the_hold_and_says_why(tmp_path):
    work = tmp_path / "work"; work.mkdir(); (work / "out.txt").write_text("Hello\n")

    async def clone(_env):
        return FakeClone(work)
    provider, _ = _provider([call("ruling", {"valid": True, "task_sentence": "Use lowercase letters only.",
                                             "reason": "stated"}, "r1")])
    out = asyncio.run(C.finish_checks(provider, LocalEnv(work), _contract(), task=TASK, workdir=str(work),
                                      disputes=[{"check": 2, "task_sentence": "none", "reason": "r"}],
                                      make_clone=clone, remaining_s=lambda: 300))
    assert out["status"] == "hold" and "your dispute was rejected" in C.feedback(out["failed"], out["rulings"])


def _is_writer(request):
    return any(t["function"]["name"] == "submit_checks" for t in request.get("tools") or [])


def _routed(writer_script, worker_script):
    """One client serving the contract writer and the worker, which run concurrently, from separate scripts."""
    client = ScriptedClient([])
    writer, worker = list(writer_script), list(worker_script)

    async def create(**kwargs):
        client.requests.append(kwargs)
        from tests.core.core_fakes import _Stream
        return _Stream((writer if _is_writer(kwargs) else worker).pop(0))
    client.chat.completions.create = create
    return ChatProvider(client, model="glm", params={"tool_choice": "required", "parallel_tool_calls": False}), client


def test_the_loop_pins_the_contract_and_holds_the_finish_until_the_checks_pass(tmp_path):
    work = tmp_path / "work"; work.mkdir()
    pristine = tmp_path / "pristine"; pristine.mkdir()
    clones = iter([FakeClone(pristine), FakeClone(work), FakeClone(work)])

    async def make_clone(_env):
        return next(clones)
    script = [
        _submit([("5 letters", LEN5, [1]), ("lowercase", LOWER, [2])]),          # contract writer (background)
        call("write_file", {"path": "out.txt", "content": "Hello\n"}, "w1"),     # worker
        call("finish", {"summary": "done"}, "w2"),                                # held: not lowercase
        call("write_file", {"path": "out.txt", "content": "hello\n"}, "w3"),
        call("finish", {"summary": "done"}, "w4")]
    provider, client = _routed(script[:1], script[1:])
    config = CoreConfig(contract=True, make_clone=make_clone, control_dir=str(tmp_path / "ctl"))
    result = asyncio.run(run_agent(env=LocalEnv(work), task=TASK, workdir=str(work), provider=provider, timeout_s=900,
                                   trace=Trace(tmp_path / "t.jsonl"), config=config))
    assert result.status == "finished" and [r["status"] for r in result.reviews] == ["hold", "pass"]
    worker = [r for r in client.requests if not _is_writer(r)]
    after_hold = json.dumps(worker[2]["messages"])
    assert "[acceptance checks]" in after_hold and "failed in a copy of your final state" in after_hold
    assert (work / "out.txt").read_text() == "hello\n"
    rows = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert any(r["event"] == "contract" and r["ok"] for r in rows)
    finish_tool = next(t for t in worker[0]["tools"] if t["function"]["name"] == "finish")
    assert "disputes" in finish_tool["function"]["parameters"]["properties"]


def test_without_a_contract_the_finish_proceeds_and_says_so(tmp_path):
    work = tmp_path / "work"; work.mkdir()

    async def broken(_env):
        raise RuntimeError("docker commit failed")
    provider, _ = _provider([call("finish", {"summary": "x"}, "w1")])
    config = CoreConfig(contract=True, make_clone=broken, control_dir=str(tmp_path / "ctl"))
    result = asyncio.run(run_agent(env=LocalEnv(work), task=TASK, workdir=str(work), provider=provider, timeout_s=900,
                                   trace=Trace(tmp_path / "t.jsonl"), config=config))
    rows = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert result.status == "finished"
    assert any(r["event"] == "contract" and not r["ok"] and "docker commit failed" in r["error"] for r in rows)
    assert any(r["event"] == "finish" and r.get("reason") == "no_contract" for r in rows)
