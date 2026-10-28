"""AETHER_CORE_OPEN_ISSUES: a finish that lists open issues with time left is returned once; the next one ends."""

from __future__ import annotations

import dataclasses
import json

from aether.core.open_issues import hold, with_field
from aether.core.tools import tools
from tests.core_fakes import call
from tests.test_core_v2 import _clm_config, _run


def test_finish_schema_requires_open_issues_only_when_on():
    plain = next(t for t in tools(python=False) if t["function"]["name"] == "finish")
    assert "open_issues" not in plain["function"]["parameters"]["properties"]
    on = next(t for t in with_field(tools(python=False)) if t["function"]["name"] == "finish")
    assert "open_issues" in on["function"]["parameters"]["required"]


def test_hold_only_with_listed_issues_and_time_left():
    assert hold({"summary": "s", "open_issues": []}, 500, 900) is None
    assert hold({"summary": "s", "open_issues": ["x unchecked"]}, 30, 900) is None  # no time left
    text = hold({"summary": "s", "open_issues": ["x unchecked"]}, 500, 900)
    assert "x unchecked" in text and "500s remain" in text


def test_a_finish_with_open_issues_is_returned_once_then_ends(tmp_path):
    script = [
        call("finish", {"summary": "done", "open_issues": ["output not compared to the example"]}, "c0"),
        call("terminal", {"input": "echo checked"}, "c1"),
        call("finish", {"summary": "done", "open_issues": ["still not sure"]}, "c2"),
    ]
    config = dataclasses.replace(_clm_config(tmp_path), open_issues=True)
    result, rows, client = _run(tmp_path, script, config=config)
    assert result.status == "finished"
    held = [r for r in rows if r["event"] == "open_issues"]
    assert [r["held"] for r in held] == [True]  # the second finish ends the run without another hold
    assert len(client.requests) == 3
    assert "finish not taken yet" in json.dumps(client.requests[1]["messages"])
