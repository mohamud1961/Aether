"""The browser tool runs model code beside the proven task container and reports substrate failures plainly."""

from __future__ import annotations

import asyncio

from aether.core import browser
from aether.core.loop import CoreConfig


class Env:
    pass


def test_the_tool_is_listed_before_finish():
    out = browser.with_tool([{"function": {"name": "terminal"}}, {"function": {"name": "finish"}}])
    assert [d["function"]["name"] for d in out] == ["terminal", "browser", "finish"]


def test_the_sidecar_joins_the_proven_container_network_and_expires(monkeypatch):
    calls = []

    async def host(argv, timeout_s):
        calls.append(argv)
        return 0, "", ""

    async def factory(env):
        return "c" * 64

    async def run(self, code, wait_s):
        return f"ran {code!r} within {wait_s:.0f}"

    monkeypatch.setattr(browser.Sidecar, "run", run)
    session = browser.BrowserSession(factory, Env(), host=host)
    out = asyncio.run(session.use({"code": "print(1)", "files": ["rel/path"]}, 500.0))
    start = calls[0]
    assert start[:3] == ["docker", "run", "-d"] and f"container:{'c' * 64}" in start
    assert start[-1] == str(500 + browser.GRACE_S) and "aether.browser=1" in start
    assert "not an absolute path" in out and "ran 'print(1)' within 120" in out


def test_a_sidecar_that_cannot_start_is_a_plain_tool_error():
    async def host(argv, timeout_s):
        return 1, "", "Unable to find image"

    async def factory(env):
        return "d" * 64

    session = browser.BrowserSession(factory, Env(), host=host)
    out = asyncio.run(session.use({"code": "x"}, 300.0))
    assert out.startswith("error: browser unavailable") and "Unable to find image" in out


def test_off_by_default():
    assert CoreConfig().browser is None
