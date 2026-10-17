"""Field-aware view (AETHER_CORE_VIEW): changed delimited files shown as literal named fields; off is the baseline."""

import asyncio
import json

import pytest

from aether.core import harbor_agent as adapter
from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.view import render
from tests.core.core_fakes import LocalEnv, ScriptedClient, chunk, tool_chunk


def _turn(name, args, call_id):
    return [
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(usage={"prompt_tokens": 5, "completion_tokens": 2}),
    ]


def _run(tmp_path, script, view):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    (work / "before.csv").write_text("a,b\n1,2\n")  # present before the run, never changed
    client = ScriptedClient(script)
    provider = ChatProvider(client, model="scripted", params={}, log=CallLog(tmp_path / "calls"))
    env = LocalEnv(work)
    result = asyncio.run(
        run_agent(
            env=env,
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=300,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), view=view),
        )
    )
    rows = [json.loads(x) for x in (tmp_path / "trace.jsonl").read_text().splitlines()]
    return result, client, rows, env, work


def _results(rows):
    return [r["result"] for r in rows if r["event"] == "tool"]


def test_render_matches_the_stage1_field_display():
    # byte-identical to tools/aether_program/view_probe.py render(..., "field") for the same file
    assert render("/app/learned_dag.csv", "to,from\nH,J\nN,J\n", 2) == (
        "[view] /app/learned_dag.csv: CSV with header fields (to, from), 2 rows\nrow 1: to=H, from=J\nrow 2: to=N, from=J"
    )


def test_render_caps_rows_values_and_names_extra_fields():
    text = "x\tyy\n" + "".join(f"{i}\t{'v' * 50}\n" for i in range(20)) + "z\n"
    out = render("/w/t.tsv", text, 45).splitlines()
    assert out[0] == "[view] /w/t.tsv: TSV with header fields (x, yy), 45 rows"
    assert out[1] == "row 1: x=0, yy=" + "v" * 37 + "..."
    assert len(out) == 22 and out[-1] == "... 25 more rows"
    assert render("/w/r.csv", "a\n1,2\n", 1).splitlines()[1] == "row 1: a=1, field2=2"
    assert render("/w/e.csv", "", 0) == "[view] /w/e.csv: empty"


def test_view_shows_only_files_the_call_changed(tmp_path):
    script = [
        _turn("write_file", {"path": "learned_dag.csv", "content": "to,from\nB,A\n"}, "c1"),
        _turn("write_file", {"path": "learned_dag.csv", "content": "to,from\nB,A\n"}, "c2"),  # same bytes
        _turn("terminal", {"input": "mkdir -p sub/deep && printf 'p,q\\n1,2\\n' > sub/s.csv && "
                                    "printf 'p\\n1\\n' > sub/deep/no.csv && printf 'x\\n' > n.txt"}, "c3"),
        _turn("read_file", {"path": "learned_dag.csv"}, "c4"),
        _turn("finish", {"summary": "done"}, "c5"),
    ]
    result, client, rows, _, work = _run(tmp_path, script, view=True)
    assert result.status == "finished"
    r = _results(rows)
    assert r[0].endswith(f"\n\n[view] {work}/learned_dag.csv: CSV with header fields (to, from), 1 rows\nrow 1: to=B, from=A")
    assert "[view]" not in r[1]  # unchanged content
    assert f"[view] {work}/sub/s.csv: CSV with header fields (p, q), 1 rows\nrow 1: p=1, q=2" in r[2]
    assert "no.csv" not in r[2] and "n.txt" not in r[2] and "before.csv" not in "".join(r)  # depth, type, prior
    assert "[view]" not in r[3]  # read_file is not viewed
    # the model saw exactly the traced result
    assert client.requests[1]["messages"][-1]["content"].startswith(r[0])
    assert result.extras["view_files_shown"] == 2


def test_view_caps_files_and_counts_the_rest(tmp_path):
    cmd = " && ".join(f"printf 'k\\n{i}\\n' > f{i}.csv" for i in range(5))
    script = [_turn("terminal", {"input": cmd}, "c1"), _turn("finish", {"summary": "done"}, "c2")]
    _, _, rows, _, _ = _run(tmp_path, script, view=True)
    out = _results(rows)[0]
    assert out.count("[view] ") == 4 and "f0.csv" in out and "f3.csv" not in out
    assert out.endswith("[view] 2 more changed delimited files not shown")


def test_view_off_is_the_unchanged_baseline(tmp_path):
    script = [
        _turn("write_file", {"path": "learned_dag.csv", "content": "to,from\nB,A\n"}, "c1"),
        _turn("finish", {"summary": "done"}, "c2"),
    ]
    result, client, rows, env, _ = _run(tmp_path, script, view=False)
    assert result.status == "finished"
    assert not any("cksum" in c for c in env.commands)  # no listing ran
    assert not any("[view]" in json.dumps(req["messages"]) for req in client.requests)
    assert "view_files_shown" not in result.extras
    assert not any(r["event"] == "view_error" for r in rows)


def test_view_env_defaults_off_and_rejects_unknown():
    base = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "on",
            "AETHER_CORE_IMAGES": "on"}
    assert adapter.build_config(environ=base).view is False
    assert adapter.build_config(environ={**base, "AETHER_CORE_VIEW": "on"}).view is True
    with pytest.raises(adapter.ConfigError):
        adapter.build_config(environ={**base, "AETHER_CORE_VIEW": "yes"})
