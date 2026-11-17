"""AETHER_CORE_WEB_SEARCH=on: the provider's hosted web_search tool beside Core's tools (G7 fin, 17 Nov).

Known-bads each test must refuse: the hosted tool sent while the switch is off; missing while on; a search the
provider ran inside a turn not counted; a search call item replayed as input (store=false cannot resolve it)."""

import asyncio
from types import SimpleNamespace

from aether.core.calls import CallLog
from aether.core.provider import Turn
from aether.core.responses import ResponsesProvider, input_items
from tests.test_core_responses_falsifiers import Client, done_item, event

TOOL = {"type": "function", "function": {"name": "terminal", "parameters": {"type": "object", "properties": {}}}}


def provider(tmp_path, rows=(), **kw):
    log = CallLog(tmp_path / f"calls{len(list(tmp_path.iterdir()))}")
    return ResponsesProvider(Client(list(rows)), model="m", params={}, log=log, **kw)


def test_hosted_search_is_sent_only_when_switched_on(tmp_path):
    off = provider(tmp_path)._request([], [TOOL], 20, None)["tools"]
    assert {"type": "web_search"} not in off and len(off) == 1
    on = provider(tmp_path, web_search=True)._request([], [TOOL], 20, None)["tools"]
    assert on[-1] == {"type": "web_search"} and len(on) == 2


def test_searches_inside_a_turn_are_counted_and_not_replayed(tmp_path):
    rows = [event("response.output_item.done", item=done_item(type="web_search_call", id="ws_1", status="completed")),
            event("response.output_item.done", item=done_item(type="web_search_call", id="ws_2", status="completed")),
            event("response.output_text.delta", delta="Article 279a: delta for a call option is ..."),
            event("response.completed", response=SimpleNamespace(id="r", model="m", status="completed", usage=None))]
    p = provider(tmp_path, rows, web_search=True)
    turn = Turn()
    asyncio.run(p._stream_once(p._request([], [TOOL], 20, None), turn))
    assert turn.web_searches == 2 and turn.tool_calls == [] and turn.finish_reason == "stop"
    items = input_items([turn.assistant_message()])
    assert all(i.get("type") != "web_search_call" for i in items)
    assert items[-1]["role"] == "assistant" and "279a" in items[-1]["content"]


def test_the_switch_needs_the_responses_shape():
    import pytest

    from aether.core import harbor_agent as ha

    assert ha.WEB_SEARCH_ENV == "AETHER_CORE_WEB_SEARCH"
    src = open(ha.__file__).read()
    assert "needs the Responses request shape (a hosted provider tool)" in src
    with pytest.raises(Exception):
        ha._choice({ha.WEB_SEARCH_ENV: "maybe"}, ha.WEB_SEARCH_ENV, ha.REPL_MODES, "off")


class _Ctx:
    def __init__(self):
        self.calls = []

    def calibrate(self, chars, tokens):
        self.calls.append((chars, tokens))


def test_a_search_turn_does_not_recalibrate_the_token_estimate():
    """G10c: hosted search results bill as input but are never replayed; calibrating on them shrank chars-per-token
    and fired a checkpoint after every search turn (43/43). Known-bad: the old call site calibrated every turn."""
    from aether.core.loop_context import calibrate

    ctx = _Ctx()
    calibrate(ctx, 40_000, Turn(usage={"input": 30_000}, web_searches=3))
    assert ctx.calls == []
    calibrate(ctx, 40_000, Turn(usage={"input": 12_000}))
    assert ctx.calls == [(40_000, 12_000)]
    calibrate(None, 40_000, Turn(usage={"input": 12_000}))  # no managed context: nothing to correct


def test_the_tool_is_withdrawn_once_the_run_reaches_its_search_limit(tmp_path):
    """AETHER_CORE_WEB_SEARCH_MAX: G10c ran 350 searches in one row. Known-bad: an unlimited provider keeps offering
    the tool after the same two searches; a limit below 1 is refused."""
    import pytest

    rows = [event("response.output_item.done", item=done_item(type="web_search_call", id="ws_1", status="completed")),
            event("response.output_item.done", item=done_item(type="web_search_call", id="ws_2", status="completed")),
            event("response.completed", response=SimpleNamespace(id="r", model="m", status="completed", usage=None))]
    for limit, offered in ((2, False), (3, True), (None, True)):
        p = provider(tmp_path, list(rows), web_search=True, web_search_max=limit)
        assert {"type": "web_search"} in p._request([], [TOOL], 20, None)["tools"]
        asyncio.run(p._stream_once(p._request([], [TOOL], 20, None), Turn()))
        assert p.web_searches == 2
        assert ({"type": "web_search"} in p._request([], [TOOL], 20, None)["tools"]) is offered
    with pytest.raises(ValueError):
        provider(tmp_path, web_search=True, web_search_max=0)
