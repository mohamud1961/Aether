"""Task-declared skills listed at start (real shell, real Core loop)."""

import asyncio
import json
import os

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")


def run(tmp_path, skills_dir):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    client = ScriptedClient([call("finish", {"summary": "looked."}, "done")])
    asyncio.run(run_agent(
        env=LocalEnv(work), task="Improve the page.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(tmp_path / "trace.jsonl"),
        timeout_s=60, config=CoreConfig(skills_dir=skills_dir, control_dir=str(tmp_path / "control")),
    ))
    first = "\n".join(str(m["content"]) for m in client.requests[0]["messages"] if m["role"] == "user")
    rows = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return first, [r for r in rows if r["event"] == "skills"]


def test_declared_skills_are_listed_with_name_description_and_path(tmp_path):
    root = tmp_path / "skills"
    (root / "web-perf").mkdir(parents=True)
    (root / "web-perf" / "SKILL.md").write_text(
        "---\nname: web-performance\ndescription: Measure and fix layout shift with Lighthouse\n---\n# Steps\nrun it\n")
    (root / "plain").mkdir()
    (root / "plain" / "SKILL.md").write_text("# no front matter\n")
    (root / "linked").mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("---\nname: smuggled\ndescription: must not appear\n---\n")
    os.symlink(outside, root / "linked" / "SKILL.md")
    first, (row,) = run(tmp_path, str(root))
    assert f"Skills provided by this environment in {root}" in first
    assert f"- web-performance: Measure and fix layout shift with Lighthouse ({root}/web-perf/SKILL.md)" in first
    assert f"- plain: (no description) ({root}/plain/SKILL.md)" in first
    assert "smuggled" not in first and "# Steps" not in first  # links not followed; bodies not inlined
    assert row["ok"] and row["skills"] == 2


def test_missing_directory_adds_nothing(tmp_path):
    first, (row,) = run(tmp_path, str(tmp_path / "absent"))
    assert "Skills provided" not in first and row["ok"] and row["present"] is False


def test_unset_adds_nothing(tmp_path):
    first, rows = run(tmp_path, None)
    assert "Skills provided" not in first and not rows
