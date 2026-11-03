"""The final-state bank (AETHER_CORE_KEEP_FINAL=1): off by default; on, it commits the proven task container and
records the running processes; a failure is written down, never raised."""

from __future__ import annotations

import asyncio
import json
import types

import pytest

pytest.importorskip("harbor")
from aether.core import keep_final as K


class _Env:
    session_id = "Trial__ABC"


def _patch(monkeypatch, commit_code=0, fail_identify=False):
    calls = []

    async def host(argv, timeout):
        calls.append(argv)
        return commit_code, "", "boom" if commit_code else ""

    async def lookup(project):
        calls.append(["lookup", project])
        return "c" * 64

    async def ident(env, host_, known):
        if fail_identify:
            raise RuntimeError("not proven")
        return known

    async def run(env, cmd):
        return types.SimpleNamespace(stdout="1\t/\tnginx -g daemon off;\n7\t/app\tpython3 server.py\nbad\n", code=0)

    monkeypatch.setattr(K, "host_run", host)
    monkeypatch.setattr(K, "compose_container", lookup)
    monkeypatch.setattr(K, "identify", ident)
    monkeypatch.setattr(K, "run", run)
    return calls


def test_off_by_default_writes_nothing(tmp_path, monkeypatch):
    calls = _patch(monkeypatch)
    asyncio.run(K.keep(_Env(), {}, tmp_path))
    assert not calls and not (tmp_path / "bank.json").exists()


def test_on_commits_the_proven_container_unlabelled_and_records_processes(tmp_path, monkeypatch):
    calls = _patch(monkeypatch)
    asyncio.run(K.keep(_Env(), {K.KEEP_ENV: "1"}, tmp_path))
    row = json.loads((tmp_path / "bank.json").read_text())
    commit = [c for c in calls if c[:2] == ["docker", "commit"]][0]
    assert commit[-2:] == ["c" * 64, row["image"]] and "LABEL com.docker.compose.project=" in commit
    assert row["committed"] is True and row["image"].startswith("aether-bank:")
    assert row["processes"] == [["1", "/", "nginx -g daemon off;"], ["7", "/app", "python3 server.py"]]


@pytest.mark.parametrize("code,fail", [(1, False), (0, True)])
def test_a_failure_is_recorded_not_raised(tmp_path, monkeypatch, code, fail):
    _patch(monkeypatch, commit_code=code, fail_identify=fail)
    asyncio.run(K.keep(_Env(), {K.KEEP_ENV: "1"}, tmp_path))
    row = json.loads((tmp_path / "bank.json").read_text())
    assert row.get("committed") is not True and row["error"]
