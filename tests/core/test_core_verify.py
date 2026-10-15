"""The one independent finish check: a fresh-context run of the same model on a clone, its verdict, and what the
solver sees (defect_found: the evidence, work continues; otherwise the finish takes effect), bound to the delivered state."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
import uuid

from aether.core import verify as V
from aether.core.calls import CallLog
from aether.core.clm import ClmSettings
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core import receipt
from aether.core.tools import (
    BASE_PROMPT,
    CONTRADICTION_RULE,
    FINISH,
    VERDICT_FINISH,
    VERIFIER_INTRO,
    system_prompt,
)
from tests.core.core_fakes import LocalEnv, ScriptedClient, chunk, tool_chunk

TASK = "Write the word blue into colour.txt in the working directory."


def _turn(name, args, call_id):
    return [
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(usage={"prompt_tokens": 10, "completion_tokens": 3}),
    ]


class PathClone(LocalEnv):
    """A copy of the whole box standing in for a container clone: the same absolute paths (mapped to the copy),
    a separate filesystem. ``made`` lists every clone; ``closed`` the ones closed."""

    made: list["PathClone"] = []

    def __init__(self, original: Path) -> None:
        copy = original.parent / f"clone-{uuid.uuid4().hex[:6]}"
        shutil.copytree(original, copy, symlinks=True)
        super().__init__(copy)
        self.original, self.closed = str(original), False
        PathClone.made.append(self)

    def _map(self, text):
        return (
            None if text is None else str(text).replace(self.original, str(self.root))
        )

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        return await super().exec(
            self._map(command), cwd=self._map(cwd), env=env, timeout_sec=timeout_sec
        )

    async def upload_file(self, source_path, target_path):
        await super().upload_file(source_path, self._map(target_path))

    async def download_file(self, source_path, target_path):
        await super().download_file(self._map(source_path), target_path)

    async def close(self) -> None:
        self.closed = True


def _run(tmp_path, script, *, timeout_s=900, make_clone=None):
    box = tmp_path / "box"
    work, ctl = box / "work", box / "ctl"
    work.mkdir(parents=True, exist_ok=True)
    ctl.mkdir()
    (ctl / "solver_notes.txt").write_text("the solver's private context\n")
    client = ScriptedClient(script)
    provider = ChatProvider(
        client, model="scripted", params={}, log=CallLog(tmp_path / "calls.jsonl")
    )

    async def clone(env, timeout_s=None):
        return PathClone(box)

    config = CoreConfig(
        control_dir=str(ctl),
        verify=True,
        make_clone=make_clone or clone,
        clm=ClmSettings(
            mirror_path=f"{ctl}/ctx/LIVE_CTX.txt", history_path=f"{ctl}/ctx/HISTORY.txt"
        ),
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task=TASK,
            workdir=str(work),
            provider=provider,
            timeout_s=timeout_s,
            trace=Trace(tmp_path / "logs" / "core_trace.jsonl"),
            config=config,
        )
    )
    return result, client, provider, box


def test_a_refutation_goes_back_to_the_solver_with_the_evidence_and_its_next_finish_ends_the_work(
    tmp_path,
):
    PathClone.made.clear()
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "red\n"}, "s1"),
        _turn("finish", {"summary": "wrote the colour"}, "s2"),
        # the verifier, in the clone: it reads the state, then refutes
        _turn("terminal", {"input": "cat colour.txt; ls ../ctl 2>&1 | head -3"}, "v1"),
        _turn(
            "finish",
            {
                "verdict": "defect_found",
                "evidence": "colour.txt says red; the task asks for blue",
            },
            "v2",
        ),
        # the solver acts on it and finishes; there is no second check
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s3"),
        _turn("finish", {"summary": "fixed"}, "s4"),
    ]
    result, client, provider, box = _run(tmp_path, script)
    assert result.status == "finished" and not client.script
    assert (box / "work" / "colour.txt").read_text() == "blue\n"

    # the verifier's first request: the brief with the task, and nothing of the solver's turns or summary
    first = client.requests[2]["messages"]
    seen = json.dumps(first)
    assert (
        TASK in seen
        and "wrote the colour" not in seen
        and "s1" not in seen
        and len(first) == 2
    )
    # an assessor's prompt, not the solver's; a neutral brief that lists what the work produced
    system, brief = first[0]["content"], first[1]["content"]
    assert system.startswith(VERIFIER_INTRO) and "complete the task" not in system
    assert CONTRADICTION_RULE in system
    assert "colour.txt" in brief and "Do not open them until" in brief
    assert "complete" not in brief.replace(TASK, "") and "claim" not in brief
    assert [t["function"]["name"] for t in client.requests[2]["tools"]][-1] == "finish"
    assert client.requests[2]["tools"][-1] == VERDICT_FINISH

    # it worked in the clone: the solver's files were removed there, never in the original; the clone was closed
    (clone,) = PathClone.made
    assert (
        not (clone.root / "ctl").exists()
        and (box / "ctl" / "solver_notes.txt").exists()
    )
    assert "No such file" in json.dumps(client.requests[3]["messages"][-1])
    assert clone.closed

    # the solver saw the evidence as the result of its finish
    shown = json.dumps(client.requests[4]["messages"][-1])
    assert (
        "defect found" in shown
        and "the task asks for blue" in shown
        and "no second check" in shown
    )

    row = result.extras["verification"]
    assert (
        row["status"] == "defect_found"
        and row["steps"] == 2
        and row["usage"]["input"] == 20
    )
    # each run reports its own calls; the row's totals include both
    assert result.usage["input"] == 40 and provider.log.usage()["input"] == 60
    assert set(provider.log.by_role) == {"worker", "verifier"}
    events = [
        json.loads(x)["event"]
        for x in (tmp_path / "logs" / "core_trace.jsonl").read_text().splitlines()
    ]
    assert events.count("verification") == 1
    assert (tmp_path / "logs" / V.TRACE_FILE).exists()


def test_a_confirmation_ends_the_work_at_the_first_finish(tmp_path):
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn(
            "finish",
            {"verdict": "no_defect_found", "evidence": "colour.txt is blue"},
            "v1",
        ),
    ]
    result, client, _, _ = _run(tmp_path, script)
    assert result.status == "finished" and not client.script
    assert result.extras["verification"]["status"] == "no_defect_found"
    assert result.extras["finish_args"] == {"summary": "done"}


def test_a_verdict_outside_its_choices_is_refused_like_any_invalid_call(tmp_path):
    script = [
        _turn("finish", {"summary": "done"}, "s1"),
        _turn("finish", {"verdict": "probably", "evidence": "unsure"}, "v1"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "checked"}, "v2"),
    ]
    result, client, _, _ = _run(tmp_path, script)
    assert "expected one of" in json.dumps(client.requests[2]["messages"][-1])
    assert result.extras["verification"]["status"] == "no_defect_found"


def test_no_check_when_too_little_time_is_left_to_act_on_one(tmp_path):
    script = [_turn("finish", {"summary": "done"}, "s1")]
    result, client, _, _ = _run(tmp_path, script, timeout_s=V.VERIFY_MIN_REMAINING_S)
    assert result.status == "finished" and len(client.requests) == 1
    assert result.extras["verification"]["status"] == "skipped"


def test_a_failed_clone_never_holds_the_finish(tmp_path):
    async def broken(env, timeout_s=None):
        raise OSError("docker commit failed")

    script = [_turn("finish", {"summary": "done"}, "s1")]
    result, client, _, _ = _run(tmp_path, script, make_clone=broken)
    row = result.extras["verification"]
    assert result.status == "finished" and len(client.requests) == 1
    assert row["status"] == "error" and "docker commit failed" in row["reason"]


def test_the_verifier_runs_without_reviews_contract_receipt_self_check_or_a_check_of_its_own():
    config = V.verifier_config(
        CoreConfig(
            verify=True, self_check=True, receipt=True, control_dir="/tmp/.aether"
        )
    )
    assert (config.verify, config.self_check, config.receipt, config.contract) == (
        False,
    ) * 4
    assert config.role == "verifier" and config.reviews.finish is False
    assert config.control_dir == "/tmp/.aether-verifier"
    assert config.clm.mirror_path.startswith("/tmp/.aether-verifier/")


def test_self_check_adds_one_paragraph_and_the_solver_keeps_its_own_finish():
    base = system_prompt(python_version="", clm=False)
    checked = system_prompt(python_version="", clm=False, self_check=True)
    assert (
        checked.startswith(base)
        and "could have failed if you were wrong" in checked[len(base) :]
    )
    assert FINISH["function"]["parameters"]["required"] == ["summary"]


def test_the_baseline_solver_prompt_is_unchanged_by_the_verifier_and_self_check():
    """Byte-identical to the prompt every earlier board ran (L1, L2, N1 arms a and e); change only with a new board."""
    import hashlib

    assert hashlib.sha256(BASE_PROMPT.encode()).hexdigest()[:16] == "e5fc67589187ff27"
    checked = system_prompt(python_version="", clm=False, self_check=True)
    assert CONTRADICTION_RULE in checked and "independent assessor" not in checked


def test_produced_files_cannot_be_listed_without_the_start_marker(tmp_path):
    import pytest

    work = tmp_path / "w"
    work.mkdir()
    with pytest.raises(OSError):
        asyncio.run(
            receipt.changed(LocalEnv(work), str(work), str(tmp_path / "no-ctl"))
        )


# Codex review controls (15 Oct), reversed: each reproduced a defect on 52283b6cc.


def test_a_verifier_that_repairs_its_copy_cannot_certify_the_original(tmp_path):
    PathClone.made.clear()
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "red\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "v1"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "it is blue"}, "v2"),
        _turn("finish", {"summary": "kept as is"}, "s3"),
    ]
    result, client, _, box = _run(tmp_path, script)
    row = result.extras["verification"]
    assert (
        row["status"] == "void_candidate_modified"
        and row["finding"] == "no_defect_found"
    )
    assert row["clone_changes"]["modified"] == ["./colour.txt"]
    shown = json.dumps(client.requests[4]["messages"][-1])
    assert "void" in shown and "colour.txt" in shown and "it is blue" in shown
    assert (
        box / "work" / "colour.txt"
    ).read_text() == "red\n"  # the graded state is untouched
    assert (
        result.status == "finished" and not client.script and PathClone.made[0].closed
    )


def test_new_scratch_files_in_the_copy_do_not_void_the_finding(tmp_path):
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn("write_file", {"path": "check.log", "content": "ok\n"}, "v1"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "blue"}, "v2"),
    ]
    result, client, _, _ = _run(tmp_path, script)
    row = result.extras["verification"]
    assert row["status"] == "no_defect_found" and row["clone_changes"]["created"]
    assert result.status == "finished" and not client.script


def test_a_finding_is_stale_when_the_original_changed_during_the_check(tmp_path):
    async def clone_then_background_write(env, timeout_s=None):
        made = PathClone(tmp_path / "box")
        (tmp_path / "box" / "work" / "colour.txt").write_text("green\n")
        return made

    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "blue"}, "v1"),
    ]
    result, _, _, _ = _run(tmp_path, script, make_clone=clone_then_background_write)
    row = result.extras["verification"]
    assert row["status"] == "stale_original_changed" and row["original_changed"]
    assert result.status == "finished"


def test_undetermined_holds_nothing(tmp_path):
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn("finish", {"verdict": "undetermined", "evidence": "no network"}, "v1"),
    ]
    result, client, _, _ = _run(tmp_path, script)
    assert result.extras["verification"]["status"] == "undetermined"
    assert result.status == "finished" and len(client.requests) == 3


def test_a_slow_clone_cannot_take_the_solvers_time(tmp_path, monkeypatch):
    """52283b6cc: clone set-up ran outside the check's budget and the run timed out with the finish lost."""
    monkeypatch.setattr(V, "VERIFY_MAX_S", 0.5)

    async def slow(env, timeout_s=None):
        await asyncio.sleep(3)
        return PathClone(tmp_path / "box")

    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
    ]
    result, client, _, _ = _run(tmp_path, script, make_clone=slow)
    row = result.extras["verification"]
    assert result.status == "finished" and len(client.requests) == 2
    assert row["status"] == "error" and "did not end within" in row["reason"]
    assert row["elapsed_s"] < 2


def test_a_cancelled_check_is_recorded(tmp_path):
    import pytest

    async def cancelled(env, timeout_s=None):
        raise asyncio.CancelledError()

    script = [_turn("finish", {"summary": "done"}, "s1")]
    with pytest.raises(asyncio.CancelledError):
        _run(tmp_path, script, make_clone=cancelled)
    events = [
        json.loads(x)
        for x in (tmp_path / "logs" / "core_trace.jsonl").read_text().splitlines()
    ]
    (row,) = [e for e in events if e["event"] == "verification"]
    assert row["status"] == "cancelled"
