"""Seeded full-loop file roundtrips with independent byte oracles and negatives."""

import asyncio
import json
import random

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


def test_seeded_path_and_unicode_content_survive_actual_tool_roundtrips(tmp_path):
    seed = 20261025
    rng = random.Random(seed)
    work = tmp_path / "work"
    work.mkdir()
    alphabet = [
        "α",
        "雪",
        " ",
        "\t",
        "\n",
        "\\",
        "\u00a0",
        "\u0085",
        "[exit 0]",
        '"',
        "'",
        "$",
        "`",
    ]
    scripts = []
    expected = {}
    for i in range(24):
        name = f"{i:02d}-" + "".join(rng.choice(alphabet) for _ in range(4)) + ".txt"
        payload = f"CASE-{i}-" + "".join(
            rng.choice(["α", "雪", "\n", "\t", "\\", "literal $()"]) for _ in range(60)
        )
        scripts.extend(
            [
                call("write_file", {"path": name, "content": payload}, f"w{i}"),
                call(
                    "edit_file",
                    {"path": name, "old_str": f"CASE-{i}-", "new_str": f"EDITED-{i}-"},
                    f"e{i}",
                ),
                call("read_file", {"path": name}, f"r{i}"),
            ]
        )
        expected[name] = payload.replace(f"CASE-{i}-", f"EDITED-{i}-", 1).encode()
    scripts.extend(
        [
            call("read_file", {"path": "missing", "num_lines": True}, "bad-bool"),
            call(
                "write_file",
                {"path": "must-not-exist", "content": "invalid", "unexpected": "no"},
                "bad-extra",
            ),
            call("finish", {"summary": f"seeded fixture {seed}"}, "finish"),
        ]
    )
    trace = tmp_path / "trace.jsonl"
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="Exercise the prescribed file fixture.",
            workdir=str(work),
            provider=ChatProvider(ScriptedClient(scripts), model="scripted", params={}),
            timeout_s=120,
            trace=Trace(trace),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), end_processes="stop"),
        )
    )
    assert result.status == "finished" and not result.extras["cleanup_errors"]
    assert set(p.name for p in work.iterdir()) == set(expected)
    for name, content in expected.items():
        assert (work / name).read_bytes() == content, f"seed={seed} file={name!r}"
    rows = [json.loads(line) for line in trace.read_text().split("\n") if line]
    errors = [
        row
        for row in rows
        if row["event"] == "tool" and str(row.get("result")).startswith("error:")
    ]
    assert len(errors) == 2 and not (work / "must-not-exist").exists()


def test_newline_terminated_parent_directory_keeps_exact_write_identity(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    parent = work / "parent\n" / "child\n"
    parent.mkdir(parents=True)
    trace = tmp_path / "trace.jsonl"
    name = "parent\n/child\n/result.txt"
    asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="Write the named result.",
            workdir=str(work),
            provider=ChatProvider(
                ScriptedClient(
                    [
                        call(
                            "write_file",
                            {"path": name, "content": "exact bytes"},
                            "write",
                        ),
                        call("finish", {"summary": "done"}, "finish"),
                    ]
                ),
                model="scripted",
                params={},
            ),
            timeout_s=30,
            trace=Trace(trace),
            config=CoreConfig(control_dir=str(tmp_path / "ctl")),
        )
    )
    rows = [json.loads(s) for s in trace.read_text().split("\n") if s]
    observation = next(
        r["result"]
        for r in rows
        if r["event"] == "tool" and r.get("name") == "write_file"
    )
    assert (parent / "result.txt").read_bytes() == b"exact bytes"
    assert not observation.startswith("error:"), observation
