"""A21: the outside-workspace state witness in a real Core loop (real shell, scripted model).

Falsifier from the plan: an edit outside the workspace whose original must be restored. The model overwrites a
config file by absolute path with write_file, changes a config under the copied root with the shell, then tries to
put both originals back from where the witness keeps them. With the witness on, both are restored byte for byte and
the tool result and task message name the copies. Known-bad (switch off): nothing was kept, the restore commands
find nothing, and both files stay changed.
"""

import asyncio
import json
import shutil
import uuid
from pathlib import Path

import pytest

from aether.core import outside_witness
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


@pytest.fixture
def outside_root():
    """A writable directory outside /tmp: the witness ignores scratch paths, and pytest's tmp_path is under /tmp on
    Linux. The test tree is writable in both the Linux container and a local checkout."""
    root = Path(__file__).resolve().parent / f".witness-{uuid.uuid4().hex[:8]}"
    root.mkdir()
    yield root
    shutil.rmtree(root, ignore_errors=True)


def scenario(tmp_path, outside, on: bool):
    work, srv, root = tmp_path / "work", outside / "srv", outside / "sysconf"
    for d in (work, srv, root):
        d.mkdir()
    (srv / "app.conf").write_text("port=80\n")
    (root / "svc.conf").write_text("mode=safe\n")
    control = tmp_path / "control"
    kept_app = f"{control}/witness{srv}/app.conf"
    kept_svc = f"{control}/outside{root}/svc.conf"
    client = ScriptedClient([
        call("write_file", {"path": str(srv / "app.conf"), "content": "port=broken\n"}, "w"),
        call("terminal", {"input": f"printf 'mode=broken\\n' > {root}/svc.conf", "wait_s": 5}, "s"),
        call("terminal", {"input": f"cp {kept_app} {srv}/app.conf; cp {kept_svc} {root}/svc.conf; true", "wait_s": 5}, "r"),
        call("finish", {"summary": "restored"}, "f"),
    ])
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Change the configs, then restore them.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), trace=Trace(trace), timeout_s=60,
        config=CoreConfig(outside_witness=on, outside_roots=(str(root),), control_dir=str(control)),
    ))
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    return result, rows, (srv / "app.conf").read_text(), (root / "svc.conf").read_text(), kept_app, client


def test_with_the_witness_both_outside_originals_can_be_restored(tmp_path, outside_root):
    result, rows, app, svc, kept_app, client = scenario(tmp_path, outside_root, on=True)
    assert result.status == "finished", result.error
    assert (app, svc) == ("port=80\n", "mode=safe\n")
    write = next(r for r in rows if r.get("event") == "tool" and r.get("name") == "write_file")
    assert kept_app in write["result"]  # the first write names where the original is
    start = next(r for r in rows if r.get("event") == "outside_witness" and "roots" in r)
    assert start["roots"][0]["copied"] is True
    assert f"/outside{outside_root}/sysconf" in json.dumps(client.requests[0]["messages"])  # the task names the root copy


def test_known_bad_without_the_witness_the_outside_edits_cannot_be_undone(tmp_path, outside_root):
    result, rows, app, svc, _, _ = scenario(tmp_path, outside_root, on=False)
    assert result.status == "finished", result.error
    assert (app, svc) == ("port=broken\n", "mode=broken\n")
    assert not any(r.get("event") == "outside_witness" for r in rows)


def test_first_write_only_and_scope(tmp_path, outside_root):
    async def go():
        env = LocalEnv(tmp_path)
        (outside_root / "x.conf").write_text("a")
        w = outside_witness.Witness(env, str(tmp_path / "work"), str(tmp_path / "ctl"), roots=())
        first = await w.before_write(str(outside_root / "x.conf"))
        (outside_root / "x.conf").write_text("b")
        second = await w.before_write(str(outside_root / "x.conf"))
        absent = await w.before_write(str(outside_root / "new.conf"))
        inside = await w.before_write(str(tmp_path / "work" / "f"))
        scratch = await w.before_write("/tmp/elsewhere.conf")
        return first, second, absent, inside, scratch

    first, second, absent, inside, scratch = asyncio.run(go())
    assert "kept at" in first and second == "" and "did not exist" in absent and inside == "" and scratch == ""
    kept = (tmp_path / "ctl" / "witness").joinpath(*str(outside_root / "x.conf").strip("/").split("/"))
    assert kept.read_text() == "a"
