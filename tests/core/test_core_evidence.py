"""Evidence-linked finishing: step numbers on results, claims that cite them, named open choices, a mechanical
audit of the first finish shown once, and the choices handed to the verifier without the solver's reasons."""

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

STEPS = {1: "write_file", 2: "terminal", 3: "python", 4: "finish"}


def test_a_claim_with_a_real_observation_passes_and_every_gap_is_named():
    row = E.audit(
        {
            "claims": "colour.txt holds blue [step 2]\n- it is one line [steps 2-3]",
            "decisions": "none",
            "unverified": "None.",
        },
        STEPS,
    )
    assert row["problems"] == [] and row["claims"] == 2 and row["decisions"] == 0

    bad = E.audit(
        {
            "claims": "it works\nfile written [step 1]\nchecked [step 9]",
            "decisions": "address base 0x400000 | file addresses | the example output",
            "unverified": "the antigen sequence",
        },
        STEPS,
    )
    text = "\n".join(bad["problems"])
    assert "claim cites no step: it works" in text
    assert "only file writes" in text and "file written" in text
    assert "do not exist (9)" in text
    assert "decision cites no step: address base" in text
    assert "not shown: the antigen sequence" in text
    assert len(bad["problems"]) == 5


def test_no_claims_is_a_problem():
    assert E.audit({"claims": "", "decisions": "", "unverified": ""}, STEPS)[
        "problems"
    ] == [
        "- no claims: list what holds for each requirement, with the steps that show it"
    ]


def test_the_verifier_gets_the_choices_without_their_reasons():
    row = E.audit(
        {
            "claims": "x [step 2]",
            "decisions": "address base 0x400000 | file addresses | the example output [step 3]",
            "unverified": "",
        },
        STEPS,
    )
    q = E.open_questions(row)
    assert "address base 0x400000 / file addresses" in q and "example output" not in q


def _run(tmp_path, script, *, verify=False, evidence=True):
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
            timeout_s=900,
            trace=Trace(tmp_path / "logs" / "core_trace.jsonl"),
            config=config,
        )
    )
    return result, client


def _finish(call_id, claims, decisions="", unverified=""):
    return _turn(
        "finish",
        {
            "summary": "done",
            "claims": claims,
            "decisions": decisions,
            "unverified": unverified,
        },
        call_id,
    )


def test_an_uncited_finish_is_shown_its_gaps_once_and_the_next_finish_ends_the_work(
    tmp_path,
):
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _finish("s2", "colour.txt holds blue [step 1]"),
        _turn("terminal", {"input": "cat colour.txt"}, "s3"),
        _finish("s4", "colour.txt holds blue [step 3]"),
    ]
    result, client = _run(tmp_path, script)
    assert result.status == "finished" and not client.script
    # results carry their step numbers; the finish asks for claims, decisions and gaps
    assert "[step 1; t=" in json.dumps(client.requests[1]["messages"][-1])
    finish = client.requests[0]["tools"][-1]["function"]
    assert finish["parameters"]["required"] == [
        "summary",
        "claims",
        "decisions",
        "unverified",
    ]
    assert "Evidence: every tool result shows its step number" in json.dumps(
        client.requests[0]["messages"][0]
    )
    shown = json.dumps(client.requests[2]["messages"][-1])
    assert "evidence audit" in shown and "only file writes" in shown
    first, second = result.extras["evidence"]
    assert first["shown"] and not second["shown"] and second["problems"] == []


def test_a_finish_with_gaps_is_shown_only_once(tmp_path):
    script = [
        _finish("s1", "it works"),
        _finish("s2", "it works", unverified="the colour"),
    ]
    result, client = _run(tmp_path, script)
    assert result.status == "finished" and len(client.requests) == 2
    first, second = result.extras["evidence"]
    assert first["shown"] and not second["shown"] and second["problems"]


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
            "finish", {"verdict": "confirmed", "evidence": "colour.txt is blue"}, "v1"
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
    assert result.extras["verification"]["status"] == "confirmed"


def test_off_by_default_the_finish_and_results_are_unchanged(tmp_path):
    script = [
        _turn("terminal", {"input": "echo blue > colour.txt"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
    ]
    result, client = _run(tmp_path, script, evidence=False)
    assert result.status == "finished" and "evidence" not in result.extras
    assert client.requests[0]["tools"][-1] == FINISH
    assert "[step" not in json.dumps(client.requests[1]["messages"])
