"""Step-cited finishing: step numbers on results, a citation-shape check of the first finish (failed, stale,
write-only, missing and absent citations), an explicit completion assertion that is never punished for honesty,
and the named choices handed to the verifier without the solver's reasons. What it cannot see is pinned too."""

from __future__ import annotations

import asyncio
import json

from aether.core import evidence as E
from aether.core.calls import CallLog
from aether.core.clm import ClmSettings
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.tools import FINISH
from tests.core.core_fakes import LocalEnv, ScriptedClient
from tests.core.test_core_verify import PathClone, TASK, _turn

W = "/w"
STEPS = {
    1: E.step_fact("write_file", {"path": "colour.txt"}, "wrote", W),
    2: E.step_fact("terminal", {"input": "cat colour.txt"}, "blue", W),
    3: E.step_fact("read_file", {"path": "colour.txt"}, "1 blue", W),
    4: E.step_fact("read_file", {"path": "absent.txt"}, "error: FileNotFoundError", W),
    5: E.step_fact("edit_file", {"path": "./colour.txt"}, "edited", W),
    6: E.step_fact("read_file", {"path": "other.txt"}, "1 x", W),
}


def _problems(claims, steps=STEPS):
    return E.audit({"assertion": "complete", "claims": claims}, steps)[
        "citation_problems"
    ]


def test_well_formed_citations_pass():
    assert _problems("colour.txt holds blue [step 2]\n- one line [steps 2, 6]") == []
    assert _problems("x [steps 2-3]", {n: STEPS[n] for n in (1, 2, 3)}) == []


def test_each_citation_fault_is_named():
    assert "cites no step" in _problems("it works")[0]
    assert "do not exist (9)" in _problems("checked [step 9]")[0]
    assert "only file writes" in _problems("file written [steps 1, 5]")[0]
    assert "tool failed (4)" in _problems("absent.txt is fine [step 4]")[0]
    # step 3 read colour.txt; step 5 later edited it, so the read no longer describes the file
    assert (
        "changed by a later step (3)" in _problems("colour.txt holds blue [step 3]")[0]
    )
    assert _problems("other.txt holds x [step 6]") == []
    assert E.audit({"claims": "", "decisions": ""}, STEPS)["citation_problems"] == [
        "- no claims: list what holds for each requirement, with the steps that show it"
    ]


def test_what_the_citation_check_cannot_see():
    """Codex review controls: a red file cited as blue, an omitted second deliverable and a shell writer all pass.
    The check is about citation shape, never about whether a claim is supported."""
    red = {1: E.step_fact("read_file", {"path": "colour.txt"}, "1 red", W)}
    assert _problems("colour.txt holds blue [step 1]", red) == []
    shell_writer = {
        1: E.step_fact("terminal", {"input": "echo blue > colour.txt"}, "", W)
    }
    assert _problems("colour.txt holds blue [step 1]", shell_writer) == []


def test_honesty_is_never_a_citation_problem():
    row = E.audit(
        {
            "assertion": "incomplete",
            "claims": "inspected [step 2]",
            "unverified": "the colour is wrong",
        },
        STEPS,
    )
    assert row["citation_problems"] == [] and row["unverified"] == "the colour is wrong"


def test_the_verifier_gets_the_choices_without_their_reasons():
    row = E.audit(
        {
            "claims": "x [step 2]",
            "decisions": "address base 0x400000 | file addresses | the example output [step 3]",
        },
        STEPS,
    )
    q = E.open_questions(row)
    assert "address base 0x400000 / file addresses" in q and "example output" not in q


def _run(tmp_path, script, *, verify=False, evidence=True, timeout_s=900):
    box = tmp_path / "box"
    work, ctl = box / "work", box / "ctl"
    work.mkdir(parents=True)
    ctl.mkdir()
    client = ScriptedClient(script)
    provider = ChatProvider(
        client, model="scripted", params={}, log=CallLog(tmp_path / "calls.jsonl")
    )

    async def clone(env):
        return PathClone(box)

    config = CoreConfig(
        control_dir=str(ctl),
        verify=verify,
        evidence=evidence,
        make_clone=clone,
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
    return result, client


def _finish(call_id, claims, decisions="", unverified="", assertion="complete"):
    return _turn(
        "finish",
        {
            "assertion": assertion,
            "summary": "done",
            "claims": claims,
            "decisions": decisions,
            "unverified": unverified,
        },
        call_id,
    )


def test_a_complete_finish_with_a_citation_fault_is_shown_it_once(tmp_path):
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _finish("s2", "colour.txt holds blue [step 1]"),
        _turn("read_file", {"path": "colour.txt"}, "s3"),
        _finish("s4", "colour.txt holds blue [step 3]"),
    ]
    result, client = _run(tmp_path, script)
    assert result.status == "finished" and not client.script
    assert "[step 1; t=" in json.dumps(client.requests[1]["messages"][-1])
    finish = client.requests[0]["tools"][-1]["function"]
    assert finish["parameters"]["required"] == [
        "assertion",
        "summary",
        "claims",
        "decisions",
        "unverified",
    ]
    assert finish["parameters"]["properties"]["assertion"]["enum"] == [
        "complete",
        "incomplete",
        "uncertain",
    ]
    shown = json.dumps(client.requests[2]["messages"][-1])
    assert "citation check" in shown and "only file writes" in shown
    first, second = result.extras["evidence"]
    assert first["shown"] == "citation" and second["shown"] == ""
    assert second["citation_problems"] == []


def test_a_second_faulty_finish_ends_the_work(tmp_path):
    script = [_finish("s1", "it works"), _finish("s2", "it works")]
    result, client = _run(tmp_path, script)
    assert result.status == "finished" and len(client.requests) == 2
    first, second = result.extras["evidence"]
    assert first["shown"] == "citation" and not second["shown"]


def test_an_honest_incomplete_finish_with_time_left_is_asked_to_keep_working_once(
    tmp_path,
):
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "red\n"}, "s0"),
        _turn("read_file", {"path": "colour.txt"}, "s1"),
        _finish(
            "s2",
            "inspected [step 2]",
            unverified="colour is not blue",
            assertion="incomplete",
        ),
        _finish(
            "s3",
            "inspected [step 2]",
            unverified="colour is not blue",
            assertion="incomplete",
        ),
    ]
    result, client = _run(tmp_path, script)
    assert result.status == "finished" and not client.script
    shown = json.dumps(client.requests[3]["messages"][-1])
    assert "you report the work as incomplete" in shown and "citation" not in shown
    first, second = result.extras["evidence"]
    assert first["shown"] == "persist" and first["citation_problems"] == []
    assert second["assertion"] == "incomplete" and not second["shown"]


def test_an_honest_incomplete_finish_near_the_limit_takes_effect(tmp_path):
    script = [
        _turn("read_file", {"path": "colour.txt"}, "s1"),
        _finish("s2", "inspected [step 1]", assertion="uncertain"),
    ]
    result, client = _run(tmp_path, script, timeout_s=100)
    assert result.status == "finished" and len(client.requests) == 2
    assert result.extras["evidence"][0]["shown"] == ""


def test_the_verifier_is_handed_the_named_choices_and_runs_without_evidence_mode(
    tmp_path,
):
    script = [
        # (no terminal here: the fake clone cannot copy a terminal's named pipe)
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("read_file", {"path": "colour.txt"}, "s2"),
        _finish(
            "s3",
            "colour.txt holds blue [step 2]",
            decisions="spelling blue | Blue, BLUE | lower case in the task [step 2]",
        ),
        _turn(
            "finish",
            {"verdict": "no_defect_found", "evidence": "colour.txt is blue"},
            "v1",
        ),
    ]
    result, client = _run(tmp_path, script, verify=True)
    assert result.status == "finished" and not client.script
    brief = client.requests[3]["messages"][1]["content"]
    assert (
        "spelling blue / Blue, BLUE" in brief and "lower case in the task" not in brief
    )
    assert client.requests[3]["tools"][-1]["function"]["parameters"]["required"] == [
        "verdict",
        "evidence",
    ]
    assert "[step" not in json.dumps(client.requests[3]["messages"])
    assert result.extras["verification"]["status"] == "no_defect_found"


def test_off_by_default_the_finish_and_results_are_unchanged(tmp_path):
    script = [
        _turn("terminal", {"input": "echo blue > colour.txt"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
    ]
    result, client = _run(tmp_path, script, evidence=False)
    assert result.status == "finished" and "evidence" not in result.extras
    assert client.requests[0]["tools"][-1] == FINISH
    assert "[step" not in json.dumps(client.requests[1]["messages"])
