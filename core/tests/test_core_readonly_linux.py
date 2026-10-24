# ruff: noqa: F811 - pytest fixtures imported from test_core_faults_linux are used as test arguments
"""The verifier's read-only clone at the real boundary: a docker commit started with a read-only root filesystem.

Every write path the verifier's tools have is tried against the delivered files (shell redirect, rename, replace,
remove, link, chmod, touch, a remount, the Core terminal, the Python REPL and its write helper): each must fail and
the manifest must not change. Scratch (/tmp, /var/tmp) keeps what the work left there and is writable, so a build
from a copy works, and a repaired scratch copy is recorded (the attribution control). The clone's volumes go with
it. Needs Linux and a docker daemon (the VM); see test_core_faults_linux.
"""

from __future__ import annotations

import json
import subprocess

from aether.core import binding as B
from aether.core import boundary as BD
from aether.core import clone as C
from aether.core.calls import CallLog
from aether.core.clm import ClmSettings
from aether.core.files import Files
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from aether.core.repl import Repl
from aether.core.terminal import Terminals
from tests.core_fakes import ScriptedClient, chunk, tool_chunk
from tests.test_core_faults_linux import _go, box, image, pytestmark  # noqa: F401

WRITES = [
    "echo blue > /app/colour.txt",
    "echo blue >> /app/colour.txt",
    "mv /app/colour.txt /app/moved.txt",
    "cp /etc/hostname /app/colour.txt",
    "rm -f /app/colour.txt",
    "ln -sf /etc/hostname /app/colour.txt",
    "chmod 777 /app/colour.txt",
    "touch /app/new.txt",
    "mkdir /app/newdir",
    "truncate -s 0 /app/colour.txt",
    "mount -o remount,rw /",
    "python3 -c \"open('/app/colour.txt','w').write('blue')\"",
    "python3 -c \"import os; os.replace('/app/run.sh','/app/colour.txt')\"",
]


def test_a_read_only_clone_refuses_every_write_to_the_delivered_files(box):
    async def go():
        await box.exec(
            "mkdir -p /app/sub && echo red > /app/colour.txt && printf '#!/bin/sh\\necho ok\\n' > /app/run.sh "
            "&& chmod 755 /app/run.sh && echo left > /tmp/work_note.txt"
        )
        before = await B.manifest(box, "/app")
        clone = await C.Clone.create(box, read_only=True, timeout_s=300)
        try:
            probed = await BD.probe(clone, "/app")
            failed = {}
            for command in WRITES:
                failed[command] = (await clone.exec(command)).return_code != 0
            terms = Terminals(
                clone, "/app", lambda: 1000.0, control_dir="/tmp/.aether-verifier"
            )
            shown = await terms.use(input="echo blue > /app/colour.txt")
            await terms.close()
            repl = Repl(
                clone, "/app", lambda: 1000.0, None, base="/tmp/.aether-verifier/repl"
            )
            await repl.start()
            repl_out = await repl.run(
                "write('/app/colour.txt', 'blue')\nopen('/app/colour.txt', 'w')"
            )
            await repl.close()
            try:
                await Files(clone, "/app").write("colour.txt", "blue")
                files_refused = False
            except Exception:  # noqa: BLE001 - any refusal
                files_refused = True
            after = await B.manifest(clone, "/app")
            # the check starts: scratch files from here on are the check's (the cut-off of scratch_copies)
            since = await BD.clock(clone)
            # scratch: what the work left is there, writable, and a build from a copy runs
            note = (await clone.exec("cat /tmp/work_note.txt")).stdout.strip()
            build = await clone.exec(
                "mkdir -p /tmp/b && cp /app/run.sh /tmp/b/ && sh /tmp/b/run.sh > /tmp/b/out && cat /tmp/b/out "
                "&& echo x > /var/tmp/x"
            )
            # the attribution control: a repaired copy in scratch, after the marker
            await clone.exec(
                "mkdir -p /tmp/w && cp -p /app/colour.txt /tmp/w/ && cp /app/run.sh /tmp/w/run.sh "
                "&& echo 'echo fixed' >> /tmp/w/run.sh"
            )
            copies = await BD.scratch_copies(clone, before, C.SCRATCH, since)
            volumes = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{range .Mounts}}{{.Name}} {{end}}",
                    clone.name,
                ],
                capture_output=True,
                text=True,
            ).stdout.split()
        finally:
            await clone.close()
        original = await B.manifest(box, "/app")
        return (
            probed,
            failed,
            shown,
            repl_out,
            files_refused,
            before,
            after,
            note,
            build,
            copies,
            volumes,
            original,
        )

    (
        probed,
        failed,
        shown,
        repl_out,
        files_refused,
        before,
        after,
        note,
        build,
        copies,
        volumes,
        original,
    ) = _go(go())
    assert probed["boundary"] == "read_only", probed
    assert all(failed.values()), [c for c, ok in failed.items() if not ok]
    assert "[exit 0 " not in shown and "Read-only file system" in shown, shown
    assert "Read-only file system" in repl_out, repl_out
    assert files_refused
    assert after.entries == before.entries == original.entries
    assert note == "left"
    assert build.return_code == 0 and build.stdout.strip() == "ok", build
    # exact copies: the build's run.sh and the cp -p'd colour.txt; the repaired run.sh diverges; the work's own
    # /tmp/work_note.txt predates the check and is not counted
    assert copies["same"] == 2 and copies["diverging"] == ["/tmp/w/run.sh"], copies
    assert len(volumes) == 2
    for volume in volumes:  # removed with the clone
        assert (
            subprocess.run(
                ["docker", "volume", "inspect", volume], capture_output=True
            ).returncode
            != 0
        )


def test_a_bound_read_only_defect_returns_its_evidence_and_the_solver_repairs(box, tmp_path):
    """Full Core loop on the real docker clone: a genuinely bound read-only defect goes back exactly once.

    No clone is injected (``CoreConfig.make_clone`` stays None, so production ``clone.Clone.create`` runs with the
    verifier's ``read_only=True``) and nothing states the boundary: ``boundary.probe`` measures it inside the
    container. The verifier's refutation of the delivered red is therefore a bare ``defect_found`` rather than
    ``_writable``/``_unbound``/``_partial``: it must reach the solver as the result of its first finish, the solver's
    next turn must repair the delivered file, and its following finish must end the work with no second check.

    Linux and a docker daemon only (the VM); this is not run on the macOS development host.
    """

    def turn(name, args, call_id):
        return [
            tool_chunk(name, args, call_id=call_id),
            chunk(finish="tool_calls"),
            chunk(usage={"prompt_tokens": 10, "completion_tokens": 3}),
        ]

    script = [
        turn("write_file", {"path": "/app/colour.txt", "content": "red\n"}, "s1"),
        turn("finish", {"summary": "wrote the colour"}, "s2"),
        turn("terminal", {"input": "cat /app/colour.txt"}, "v1"),
        turn(
            "finish",
            {
                "verdict": "defect_found",
                "evidence": "colour.txt says red; the task asks for blue",
            },
            "v2",
        ),
        turn("write_file", {"path": "/app/colour.txt", "content": "blue\n"}, "s3"),
        turn("finish", {"summary": "fixed"}, "s4"),
    ]
    client = ScriptedClient(script)
    provider = ChatProvider(
        client, model="scripted", params={}, log=CallLog(tmp_path / "calls.jsonl")
    )
    result = _go(
        run_agent(
            env=box,
            task="Write the word blue into /app/colour.txt.",
            workdir="/app",
            provider=provider,
            timeout_s=900,
            trace=Trace(tmp_path / "logs" / "core_trace.jsonl"),
            config=CoreConfig(
                control_dir="/tmp/.aether-core",
                verify=True,
                clm=ClmSettings(
                    mirror_path="/tmp/.aether-core/ctx/LIVE_CTX.txt",
                    history_path="/tmp/.aether-core/ctx/HISTORY.txt",
                ),
            ),
        )
    )
    row = result.extras["verification"]
    assert result.status == "finished" and not client.script
    # measured, not stated: the probe really saw a read-only delivered tree in this clone
    assert row["boundary"] == "read_only", row["boundary_detail"]
    assert row["status"] == "defect_found" and row["finding"] == "defect_found"
    assert row["clone_changes"] == {"modified": [], "deleted": [], "created": []}
    # the evidence was the result of the solver's first finish, so it is in the solver's next request
    shown = json.dumps(client.requests[4]["messages"][-1])
    assert "defect found" in shown and "the task asks for blue" in shown
    # the repair landed in the delivered tree, and the second finish ended the work (no second check)
    assert _go(box.exec("cat /app/colour.txt")).stdout.strip() == "blue"
    assert result.extras["finish_args"] == {"summary": "fixed"}
    events = [
        json.loads(line)["event"]
        for line in (tmp_path / "logs" / "core_trace.jsonl").read_text().splitlines()
    ]
    assert events.count("verification") == 1
    assert len(client.requests) == 6  # s1, s2, v1, v2, s3, s4


def test_a_writable_clone_is_probed_as_writable(box):
    async def go():
        clone = await C.Clone.create(box, timeout_s=300)
        try:
            return await BD.probe(clone, "/app")
        finally:
            await clone.close()

    assert _go(go())["boundary"] == "writable"
