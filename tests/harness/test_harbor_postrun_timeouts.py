from __future__ import annotations

import asyncio

import pytest

from aether.harbor_task_environment import _bounded_harbor_await


def test_bounded_harbor_await_returns_completed_value():
    async def scenario():
        return await _bounded_harbor_await(
            asyncio.sleep(0, result="ok"),
            timeout_s=1,
            label="Harbor test operation",
        )

    assert asyncio.run(scenario()) == "ok"


def test_bounded_harbor_await_names_timeout_boundary():
    async def scenario():
        await _bounded_harbor_await(
            asyncio.sleep(10),
            timeout_s=0.01,
            label="Harbor task workspace download",
        )

    with pytest.raises(
        TimeoutError,
        match=r"Harbor task workspace download timed out after 0\.01s",
    ):
        asyncio.run(scenario())
