"""Fork instrument: matched continuations at the first finish, on clones, never touching the original (see fork)."""

import asyncio
import tarfile

import pytest

from aether.core import fork
from aether.core import harbor_agent as adapter
from aether.core.calls import CallLog
from aether.core.clm import ClmSettings
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, _Stream, chunk, tool_chunk
from tests.test_core_verify import PathClone


def _turn(name, args, call_id):
    return [
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(usage={"prompt_tokens": 5, "completion_tokens": 2}),
    ]


class _Router:
    """Serves the solver's script, or an arm's, by what the newest message answers (the arms run in parallel)."""

    def __init__(self, scripts, markers=None):
        self.scripts, self.requests, self.markers = {k: list(v) for k, v in scripts.items()}, [], markers or {}
        from types import SimpleNamespace

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        texts = [str(m.get("content", "")) for m in kwargs["messages"] if m.get("role") == "tool"]
        arm = "solver"
        named = [a for m, a in self.markers.items() if any(m in t for t in texts)]
        if named:
            arm = named[0]
        elif any(fork.RECORD_HEAD in t for t in texts):
            arm = "c"
        elif any(fork.CONTINUE in t for t in texts):
            arm = "b"
        return _Stream(self.scripts[arm].pop(0))


def _run(tmp_path, timeout_s=900, context="project", fork_arms=(), markers=None):
    box = tmp_path / "box"
    work, ctl = box / "work", box / "ctl"
    work.mkdir(parents=True)
    ctl.mkdir()
    ans = str(work / "ans.txt")
    client = _Router(
        {
            "solver": [
                _turn("write_file", {"path": ans, "content": "wrong\n"}, "s1"),
                _turn("finish", {"summary": "verified ans.txt is right"}, "s2"),
            ],
            "b": [
                _turn("write_file", {"path": ans, "content": "b-fix\n"}, "b1"),
                _turn("finish", {"summary": "b"}, "b2"),
            ],
            "c": [
                _turn("write_file", {"path": ans, "content": "c-fix\n"}, "c1"),
                _turn("finish", {"summary": "c"}, "c2"),
            ],
            **{a: [_turn("write_file", {"path": ans, "content": f"{a}-fix\n"}, f"{a}1"), _turn("finish", {"summary": a}, f"{a}2")] for a in (markers or {}).values()},
        },
        markers,
    )
    provider = ChatProvider(client, model="scripted", params={}, log=CallLog(tmp_path / "calls.jsonl"))
    made = []

    async def clone(env, timeout_s=None, read_only=False):
        made.append(read_only)
        return PathClone(box)

    result = asyncio.run(
        run_agent(
            env=LocalEnv(box),
            task="write the answer to ans.txt",
            workdir=str(work),
            provider=provider,
            timeout_s=timeout_s,
            trace=Trace(tmp_path / "logs" / "core_trace.jsonl"),
            config=CoreConfig(
                control_dir=str(ctl),
                fork=True,
                fork_arms=fork_arms,
                make_clone=clone,
                context=context,
                clm=ClmSettings(mirror_path=f"{ctl}/ctx/LIVE_CTX.txt", history_path=f"{ctl}/ctx/HISTORY.txt"),
            ),
        )
    )
    return result, client, work, tmp_path / "logs", made


def _member(path, name="./ans.txt"):
    with tarfile.open(path) as t:
        return t.extractfile(name).read().decode()


@pytest.mark.parametrize("context", ["project", "clm"])
def test_the_arms_continue_on_writable_clones_and_the_run_keeps_its_own_outcome(tmp_path, context):
    (tmp_path / "logs").mkdir()
    result, client, work, logs, made = _run(tmp_path, context=context)
    assert result.status == "finished"
    assert (work / "ans.txt").read_text() == "wrong\n"  # nothing reached the original
    row = result.extras["fork"]
    assert made == [False, False]
    assert row["b"]["finished_again"] and row["c"]["finished_again"]
    assert _member(row["a"]["export"]) == "wrong\n"
    assert _member(row["b"]["export"]) == "b-fix\n"
    assert _member(row["c"]["export"]) == "c-fix\n"


@pytest.mark.parametrize("context", ["project", "clm"])
def test_b_is_the_bare_continuation_and_c_adds_only_the_harness_record(tmp_path, context):
    (tmp_path / "logs").mkdir()
    _, client, _, _, _ = _run(tmp_path, context=context)
    first = {}
    for req in client.requests:
        last = req["messages"][-1]
        if last.get("role") == "tool" and fork.CONTINUE in str(last["content"]):
            arm = "c" if fork.RECORD_HEAD in last["content"] else "b"
            first.setdefault(arm, req["messages"])
    b, c = first["b"], first["c"]
    assert b[-1]["content"] == fork.CONTINUE
    assert b[-1]["tool_call_id"] == "s2" == c[-1]["tool_call_id"]  # each answers the solver's finish call
    assert b[:-1] == c[:-1]  # the same history up to the finish
    record = c[-1]["content"]
    assert record.startswith(fork.CONTINUE + "\n\n" + fork.RECORD_HEAD)
    assert "## Observed by the harness" in record and "## The model's account" not in record
    assert "verified ans.txt is right" in record  # quoted only as a flagged claim, never as its account


def test_no_fork_with_too_little_time(tmp_path):
    (tmp_path / "logs").mkdir()
    result, _, _, _, made = _run(tmp_path, timeout_s=fork.FORK_MIN_S + 20)
    assert result.extras["fork"]["status"] == "skipped" and made == []


def test_the_fork_is_off_unless_set_and_never_with_the_verifier():
    required = {
        adapter.REVIEW_ENV: "off",
        adapter.CONTEXT_ENV: "project",
        adapter.REPL_ENV: "off",
        adapter.IMAGES_ENV: "off",
    }
    assert adapter.build_config(environ=required).fork is False
    assert adapter.build_config(environ={**required, adapter.FORK_ENV: "on"}).fork is True
    with pytest.raises(adapter.ConfigError):
        adapter.build_config(environ={**required, adapter.FORK_ENV: "on", adapter.VERIFY_ENV: "once"})


def test_named_arms_replace_b_and_c_and_each_adds_only_its_text(tmp_path):
    (tmp_path / "logs").mkdir()
    arms = (("ctl", ""), ("cue", "MARK-cue look again"), ("ev", "MARK-ev a note"))
    markers = {"MARK-cue": "cue", "MARK-ev": "ev"}
    # the bare control is routed by CONTINUE alone, as "b"
    result, client, work, _, made = _run(tmp_path, fork_arms=arms, markers=markers)
    row = result.extras["fork"]
    assert (work / "ans.txt").read_text() == "wrong\n" and made == [False] * 3
    assert set(row) >= {"a", "ctl", "cue", "ev"} and "b" not in row and "c" not in row
    assert _member(row["ctl"]["export"]) == "b-fix\n"
    assert _member(row["cue"]["export"]) == "cue-fix\n" and _member(row["ev"]["export"]) == "ev-fix\n"
    last = {}
    for req in client.requests:
        m = req["messages"][-1]
        if m.get("role") == "tool" and fork.CONTINUE in str(m["content"]):
            last.setdefault(m["content"], m)
    assert set(last) == {fork.CONTINUE, f"{fork.CONTINUE}\n\nMARK-cue look again", f"{fork.CONTINUE}\n\nMARK-ev a note"}
    assert not any(fork.RECORD_HEAD in t for t in last)


def test_named_arms_load_from_a_file_and_bad_files_are_config_errors(tmp_path):
    required = {
        adapter.REVIEW_ENV: "off",
        adapter.CONTEXT_ENV: "project",
        adapter.REPL_ENV: "off",
        adapter.IMAGES_ENV: "off",
        adapter.FORK_ENV: "on",
    }
    good = tmp_path / "arms.json"
    good.write_text('[{"name": "ctl", "text": ""}, {"name": "ev", "text": "note"}]')
    cfg = adapter.build_config(environ={**required, fork.ARMS_ENV: str(good)})
    assert cfg.fork_arms == (("ctl", ""), ("ev", "note"))
    assert adapter.build_config(environ=required).fork_arms == ()
    for bad in ('[{"name": "a", "text": ""}]', '[{"name": "x", "text": ""}, {"name": "x", "text": "y"}]', "[]",
                '[{"name": "Bad", "text": ""}]', '[{"name": "ok"}]', "not json"):
        good.write_text(bad)
        with pytest.raises(adapter.ConfigError):
            adapter.build_config(environ={**required, fork.ARMS_ENV: str(good)})
    with pytest.raises(adapter.ConfigError):
        adapter.build_config(environ={**required, fork.ARMS_ENV: str(tmp_path / "missing.json")})
