"""The environment brief reports what the container has, as measured, and says nothing when the probe fails."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aether.core import env_brief
from aether.core.harbor_agent import build_config
from tests.core_fakes import LocalEnv

BASE = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}


def test_the_brief_lists_present_and_missing_tools_and_the_working_tree(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "data.bin").write_bytes(b"12345")
    monkeypatch.setattr(env_brief, "TOOLS", ("sh", "no-such-tool-aether"))
    brief, row = asyncio.run(env_brief.take(LocalEnv(tmp_path), str(tmp_path / "app")))
    assert row["ok"] and brief.startswith("(Environment, measured by the harness")
    assert "available: sh" in brief and "not found on PATH: no-such-tool-aether" in brief
    assert "package managers:" in brief and "package servers:" in brief  # whether software can be installed
    assert "./data.bin (5 B)" in brief
    # machine size, what lies outside the working directory, what already runs (values depend on the host)
    assert "\nmachine: cpus " in brief and "disk free:" in brief
    assert f"\noutside {tmp_path / 'app'} (non-standard or non-empty):" in brief
    assert "\nrunning processes: " in brief


def test_a_failed_probe_gives_no_brief():
    class Broken:
        async def exec(self, command, cwd=None, env=None, timeout_sec=None):
            return SimpleNamespace(return_code=127, stdout="", stderr="sh: not found")

    brief, row = asyncio.run(env_brief.take(Broken(), "/app"))
    assert brief == "" and not row["ok"]


def test_the_flag_is_off_by_default():
    assert build_config(environ=BASE).env_brief is False
    assert build_config(environ={**BASE, "AETHER_CORE_ENV_BRIEF": "on"}).env_brief is True
