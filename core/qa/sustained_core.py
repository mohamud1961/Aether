#!/usr/bin/env python3
"""Sustained real Core loop, real local effects, scripted provider; no model/Harbor.

Run from outside checkout with installed Core and test support on PYTHONPATH.
Every receipt reports actual elapsed wall time. --seconds is active episode work,
not the lifetime requested of a sleeping child. No short run is a long-run pass.
"""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import resource
import shlex
import statistics
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from aether.core.calls import CallLog
from aether.core.clm import ClmSettings
from aether.core.harbor_agent import _write_record
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.conftest import cwds
from tests.core_fakes import LocalEnv, StatusError, _Stream, call, chunk


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def sample(root, turns, started, baseline_pids):
    pid = os.getpid()
    raw = subprocess.check_output(["ps", "-axo", "pid=,ppid=,rss="], text=True)
    rows = {
        int(f[0]): (int(f[1]), int(f[2]))
        for line in raw.splitlines()
        if len(f := line.split()) == 3
    }
    children = {pid}
    while True:
        more = {p for p, (parent, _) in rows.items() if parent in children}
        if more <= children:
            break
        children.update(more)
    located = cwds(set(rows) - baseline_pids)
    owned_cwd = sum(
        1
        for value in located.values()
        if Path(value).resolve() == root.resolve()
        or root.resolve() in Path(value).resolve().parents
    )
    owned_files = [p for p in root.rglob("*") if p.is_file()]
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    child_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "host_self_cpu_s": cpu.ru_utime + cpu.ru_stime,
        "reaped_child_cpu_s": child_cpu.ru_utime + child_cpu.ru_stime,
        "file_bytes": sum(p.stat().st_size for p in owned_files),
        "owned_cwd_processes": owned_cwd,
        "turns": turns,
        "elapsed_s": time.monotonic() - started,
        "rss_kib": rows[pid][1],
        "descendants": len(children) - 1,
        "fd_count": len(os.listdir("/dev/fd")) if Path("/dev/fd").is_dir() else None,
        "threads": threading.active_count(),
        "async_tasks": len(asyncio.all_tasks()),
        "files": len(owned_files),
    }


class FixtureEnvironment(LocalEnv):
    def __init__(self, work, scratch):
        super().__init__(work)
        self.scratch = scratch

    async def exec(self, command, **kwargs):
        return await super().exec(
            "export TMPDIR=" + shlex.quote(str(self.scratch)) + "; " + command, **kwargs
        )


class Client:
    def __init__(self, root, seconds, min_turns, mode):
        self.root, self.seconds, self.min_turns, self.mode = (
            root,
            seconds,
            min_turns,
            mode,
        )
        self.started = time.monotonic()
        self.turns = 0
        self.attempts = 0
        self.checkpoints = 0
        self.latencies = []
        self.health = []
        self.last_started = self.started
        self.python_count = 0
        self.faulted = set()
        self.previous = None
        self.observations = []
        self.request_sizes = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.expected_artifact = ""
        self.expected_edits = 0
        self.plan = []
        self.baseline_pids = {
            int(p)
            for p in subprocess.check_output(["ps", "-axo", "pid="], text=True).split()
        }

    def inspect_previous(self, packet):
        if not self.previous:
            return
        identity, name, args = self.previous
        if name == "view_image":
            import base64
            import io

            from PIL import Image

            attached = [
                part["image_url"]["url"]
                for message in packet["messages"]
                if isinstance(message.get("content"), list)
                for part in message["content"]
                if part.get("type") == "image_url"
            ]
            require(attached, "image tool succeeded without a provider-visible image")
            image = Image.open(
                io.BytesIO(base64.b64decode(attached[-1].split(",", 1)[1]))
            )
            require(
                image.size == (1, 1)
                and image.convert("RGB").getpixel((0, 0))
                == (((int(identity.split("-")[1]) - 5) // 16) % 256, 17, 231),
                "provider-visible image pixels corrupted",
            )
        results = [
            m
            for m in packet["messages"]
            if m.get("role") == "tool" and m.get("tool_call_id") == identity
        ]
        # Explicit context edits may remove the just-observed tool turn. Trace is
        # the full oracle; check all other next-observation packets here as well.
        if results:
            text = results[-1]["content"]
            self.observations.append(
                {
                    "id": identity,
                    "name": name,
                    "sha256": hashlib.sha256(str(text).encode()).hexdigest(),
                }
            )
            if name == "python" and "SOAK_COUNTER" in args.get("code", ""):
                require(
                    f"SOAK_COUNTER {self.python_count}" in str(text),
                    "persistent Python state lost",
                )
            if name == "read_history":
                require("history MSG 1;" in str(text), "history identity lost")
        self.previous = None

    async def create(self, **packet):
        self.attempts += 1
        if "tools" not in packet:
            self.checkpoints += 1
            return _Stream(
                [
                    chunk(
                        content="[your notes] Continue prescribed local mechanical fixture; source remains in original history. No correctness inferred."
                    ),
                    chunk(finish="stop"),
                ]
            )
        self.inspect_previous(packet)
        self.request_sizes.append(len(json.dumps(packet, ensure_ascii=False)))
        if self.turns and self.turns % 67 == 0 and self.turns not in self.faulted:
            self.faulted.add(self.turns)
            raise StatusError(
                429, "scripted transient rate limit", headers={"retry-after": "0"}
            )
        if self.turns % 20 == 0:
            point = sample(self.root, self.turns, self.started, self.baseline_pids)
            self.health.append(point)
            with (self.root / "health.jsonl").open("a") as stream:
                stream.write(json.dumps(point) + "\n")
        step = self.turns
        phase = (step - 5) % 16
        cycle = max(0, (step - 5) // 16)
        if (
            step >= self.min_turns
            and phase == 0
            and time.monotonic() - self.started >= self.seconds
        ):
            name, args = (
                "finish",
                {
                    "summary": "Scripted sustained fixture complete; artifact independently checked by host."
                },
            )
        elif step == 0:
            name, args = "read_file", {"path": "source.txt"}
        elif step == 1:
            name, args = (
                "terminal",
                {
                    "name": "service",
                    "input": "python3 -u heartbeat.py > heartbeat.log 2>&1 & echo $! > service.pid; echo SERVICE_STARTED",
                },
            )
        elif step == 2:
            name, args = "python", {"code": "counter=0; print('PYTHON_READY')"}
        elif step == 3:
            name, args = (
                "terminal",
                {
                    "name": "build",
                    "input": "sleep 4; printf 'INITIAL_BUILD_DONE\\n'",
                    "wait_s": 0.1,
                },
            )
        elif step == 4:
            name, args = (
                "terminal",
                {
                    "name": "other",
                    "input": "export SOAK_STATE=preserved; echo PARALLEL_READY",
                },
            )
        elif phase == 0:
            self.expected_artifact = f"version-{cycle}-α雪\n"
            name, args = (
                "write_file",
                {"path": "artifact.txt", "content": f"draft-{cycle}\n"},
            )
        elif phase == 1:
            name, args = (
                "edit_file",
                {
                    "path": "artifact.txt",
                    "old_str": f"draft-{cycle}\n",
                    "new_str": self.expected_artifact,
                },
            )
            self.expected_edits += 1
        elif phase == 2:
            name, args = (
                "terminal",
                {
                    "input": "python3 build.py && python3 -c \"from pathlib import Path;import hashlib;d=Path('artifact.txt').read_bytes();print('CHECK_SHA',hashlib.sha256(d).hexdigest())\""
                },
            )
        elif phase == 3:
            name, args = "read_file", {"path": "artifact.txt"}
        elif phase == 4:
            self.python_count += 1
            name, args = "python", {"code": "counter+=1; print('SOAK_COUNTER',counter)"}
        elif phase == 5:
            name, args = (
                "terminal",
                {
                    "name": "other",
                    "input": f"printf 'STATE-%s\\n' \"$SOAK_STATE\"; printf 'SOAK-MARK-{cycle}\\n'",
                },
            )
        elif phase == 6:
            name, args = (
                "terminal",
                {"input": "printf 'DELIBERATE_FAILURE\\n' >&2; false"},
            )
        elif phase == 7:
            name, args = "terminal", {"input": "printf 'PRODUCTIVE_REPAIR\\n'"}
        elif phase == 8:
            name, args = (
                "terminal",
                {
                    "input": f"python3 -c \"from pathlib import Path; Path('pixel.ppm').write_text('P3\\n1 1\\n255\\n{cycle % 256} 17 231\\n'); print('α雪-output-'*3000); print('FULL_LOG_END_{cycle}')\""
                },
            )
        elif phase == 9:
            name, args = (
                "write_file",
                {
                    "path": str(self.root / "ctx" / "LIVE_CTX.txt"),
                    "content": f"[[CTX_TURN 0 role=user]]\n[your notes] fixture cycle {cycle}; original source is MSG1; do not infer artifact correctness.",
                },
            )
        elif phase == 10:
            name, args = "read_history", {"message_id": 1, "offset": 0, "limit": 12000}
        elif phase == 11:
            name, args = (
                "read_history",
                {"message_id": 1, "offset": 12000, "limit": 12000},
            )
        elif phase == 12:
            name, args = (
                "read_history",
                {"message_id": 1, "offset": 24000, "limit": 12000},
            )
        elif phase == 13:
            name, args = "view_image", {"path": "pixel.ppm"}
        elif phase == 14:
            name, args = "terminal", {"name": "build", "input": "", "wait_s": 0.1}
        else:
            name, args = (
                "terminal",
                {
                    "input": "python3 -c \"from pathlib import Path;print('HEARTBEAT',Path('heartbeat').read_text()); print('TREE',len(list(Path('tree').glob('*'))))\""
                },
            )
        identity = f"soak-{step}"
        self.plan.append((identity, name, args))
        self.previous = identity, name, args
        self.turns += 1
        now = time.monotonic()
        self.latencies.append(now - self.last_started)
        self.last_started = now
        return _Stream(
            call(name, args, identity, reasoning="deterministic local mechanics only")
        )


def expected_bundle(cycle):
    return {
        "version": f"version-{cycle}-α雪",
        "rows": [{"id": i, "value": str(i)} for i in range(1200)],
    }


def validate_trace(rows, plan):
    models = [r for r in rows if r["event"] == "model"]
    actual = [c for r in models for c in r.get("tool_calls", [])]
    tools = [r for r in rows if r["event"] == "tool"]
    require(
        len(actual) == len(plan) == len(tools),
        "missing/duplicated action or observation",
    )
    ids = [c["id"] for c in actual]
    require(
        ids == [p[0] for p in plan] and len(set(ids)) == len(ids),
        "operation identity/order corrupted",
    )
    for (identity, name, args), action, observation in zip(plan, actual, tools):
        require(
            action["function"]["name"] == name == observation["name"],
            "tool name/order changed",
        )
        require(
            json.loads(action["function"]["arguments"]) == args == observation["args"],
            "tool arguments changed",
        )
        text = str(observation["result"])
        if name in (
            "write_file",
            "edit_file",
            "read_file",
            "read_history",
            "python",
            "view_image",
        ):
            require(not text.startswith("error:"), f"required {name} action failed")
        if name == "write_file":
            require(text.startswith("wrote "), "write acknowledgement missing")
        if name == "edit_file":
            require(text.startswith("edited "), "edit acknowledgement missing")
        if name == "view_image":
            require(
                text.startswith("[image ") and "PPM 1x1 RGB; shown below]" in text,
                "image observation missing or incorrect",
            )
        if name == "python" and "SOAK_COUNTER" in args.get("code", ""):
            cycle = (int(identity.split("-")[1]) - 5) // 16
            require(
                f"SOAK_COUNTER {cycle + 1}" in text,
                "persistent Python trace state lost",
            )
        if name == "terminal" and "CHECK_SHA" in args.get("input", ""):
            cycle = (int(identity.split("-")[1]) - 5) // 16
            expected = hashlib.sha256(f"version-{cycle}-α雪\n".encode()).hexdigest()
            require(
                expected in text and "[exit 0 " in text,
                "independent intermediate artifact check failed",
            )
            bundle = expected_bundle(cycle)
            bundle_hash = hashlib.sha256(
                json.dumps(
                    bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            require(
                f"BUILD_SHA {bundle_hash}" in text,
                "independent rebuild artifact check failed",
            )
        if name == "terminal" and "DELIBERATE_FAILURE" in args.get("input", ""):
            require(
                "DELIBERATE_FAILURE" in text and "[exit 1 " in text,
                "false-success for failed command",
            )
        if name == "terminal" and "STATE-%s" in args.get("input", ""):
            require("STATE-preserved" in text, "persistent shell state lost")
        if name == "terminal" and "print('TREE'" in args.get("input", ""):
            require("TREE 1200" in text, "large artifact tree changed during episode")
        if name == "read_file" and args["path"] == "artifact.txt":
            cycle = (int(identity.split("-")[1]) - 5) // 16
            require(f"version-{cycle}-α雪" in text, "artifact readback differs")


def negative_trace_controls(rows, plan):
    from copy import deepcopy

    controls = []
    for mode in (
        "duplicate_action_id",
        "false_success",
        "corrupt_artifact_check",
        "failed_image",
        "failed_edit",
    ):
        bad = deepcopy(rows)
        if mode == "duplicate_action_id":
            model = [r for r in bad if r["event"] == "model"]
            model[1]["tool_calls"][0]["id"] = model[0]["tool_calls"][0]["id"]
        elif mode in ("failed_image", "failed_edit"):
            target = next(
                r
                for r in bad
                if r["event"] == "tool"
                and r["name"]
                == ("view_image" if mode == "failed_image" else "edit_file")
            )
            target["result"] = "error: injected required tool failure"
        else:
            needle = "DELIBERATE_FAILURE" if mode == "false_success" else "CHECK_SHA"
            target = next(
                r for r in bad if r["event"] == "tool" and needle in str(r.get("args"))
            )
            target["result"] = "[exit 0] invented-success"
        try:
            validate_trace(bad, plan)
        except RuntimeError:
            controls.append(mode)
        else:
            raise RuntimeError("oracle accepted known bad trace: " + mode)
    return controls


async def episode(folder, seconds, min_turns, mode):
    folder.mkdir(parents=True, exist_ok=False)
    work = folder / "work"
    work.mkdir()
    scratch = folder / "sandbox-tmp"
    scratch.mkdir()
    host_scratch = folder / "host-tmp"
    host_scratch.mkdir()
    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = str(host_scratch)
    (work / "tree").mkdir()
    for i in range(1200):
        (work / "tree" / f"{i:05d}").write_text(str(i))
    (work / "source.txt").write_text("ANCHOR-α-" + ("x" * 30000) + "-TAIL-雪\n")
    (work / "pixel.ppm").write_bytes(b"P3\n1 1\n255\n255 0 0\n")
    (work / "heartbeat.py").write_text(
        "import time\nfrom pathlib import Path\ni=0\nwhile True:\n i+=1\n Path('heartbeat').write_text(str(i))\n time.sleep(.1)\n"
    )
    (work / "build.py").write_text(
        "from pathlib import Path\nimport json,hashlib\nrows=[{'id':int(p.name),'value':p.read_text()} for p in sorted(Path('tree').iterdir())]\nobj={'version':Path('artifact.txt').read_text().rstrip('\\n'),'rows':rows}\nraw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()\nPath('compiled.json').write_bytes(raw)\nprint('BUILD_SHA',hashlib.sha256(raw).hexdigest())\n"
    )
    client = Client(folder, seconds, min_turns, mode)

    async def no_delay(_):
        await asyncio.sleep(0)

    provider = ChatProvider(
        client,
        model="scripted-offline-no-inference",
        params={},
        sleep=no_delay,
        log=CallLog(folder / "calls.jsonl"),
    )
    config = CoreConfig(
        context="clm",
        repl=True,
        images=True,
        record=True,
        end_processes="stop",
        control_dir=str(folder / "ctl"),
        evidence_presentation=mode,
        clm=ClmSettings(
            budget_tokens=16000,
            keep_recent_tokens=2000,
            mirror_path=str(folder / "ctx" / "LIVE_CTX.txt"),
            history_path=str(folder / "ctx" / "HISTORY.txt"),
            attest_original_history=mode == "history_index",
        ),
    )
    started = time.monotonic()
    result = await run_agent(
        env=FixtureEnvironment(work, scratch),
        task="Perform the prescribed local mechanical fixture; preserve source bytes and produce artifact.txt.",
        workdir=str(work),
        provider=provider,
        timeout_s=seconds + 300,
        trace=Trace(folder / "trace.jsonl"),
        config=config,
    )
    elapsed = time.monotonic() - started
    after_cleanup = sample(folder, client.turns, client.started, client.baseline_pids)
    _write_record(
        folder / "logs",
        result,
        started=time.time() - elapsed,
        workdir=str(work),
        config=config,
        review=None,
        provider=provider,
    )
    rows = [json.loads(s) for s in (folder / "trace.jsonl").read_text().splitlines()]
    tools = [r for r in rows if r["event"] == "tool"]
    validate_trace(rows, client.plan)
    negative_controls = negative_trace_controls(rows, client.plan)
    require(result.status == "finished", f"run status {result.status}: {result.error}")
    require(
        elapsed >= seconds and client.turns >= min_turns,
        "episode duration/turn floor not reached",
    )
    require(not result.extras["cleanup_errors"], str(result.extras["cleanup_errors"]))
    require(
        (work / "artifact.txt").read_text() == client.expected_artifact,
        "wrong final artifact",
    )
    require(
        json.loads((work / "compiled.json").read_text())
        == expected_bundle(client.expected_edits - 1),
        "final rebuilt data artifact incorrect",
    )
    require(
        int((work / "heartbeat").read_text()) >= max(1, int(seconds * 4)),
        "service did not remain productive",
    )
    require(
        any(r["event"] == "context_edit" and r.get("accepted") for r in rows),
        "no real context mutation",
    )
    history = [
        r["result"].split("\n", 1)[1] for r in tools if r.get("name") == "read_history"
    ]
    require(len(history) >= 3, "missing history pages")
    require(len(history) % 3 == 0, "incomplete history paging round")
    for start in range(0, len(history), 3):
        recovered = json.loads("".join(history[start : start + 3]))
        require(
            "ANCHOR-α-" in recovered["content"] and "-TAIL-雪" in recovered["content"],
            "earlier source history round lost bytes",
        )
    source = json.loads("".join(history[-3:]))
    require(
        "ANCHOR-α-" in source["content"] and "-TAIL-雪" in source["content"],
        "source pages lost/corrupt",
    )
    failures = [
        r
        for r in tools
        if r.get("name") == "terminal" and "DELIBERATE_FAILURE" in r.get("result", "")
    ]
    require(
        failures and all("[exit 1 " in r["result"] for r in failures),
        "failed shell command misreported",
    )
    # The full source output must survive clipping in an actual terminal log.
    logs = list((folder / "ctl").rglob("*.log")) + list((folder / "ctl").rglob("log"))
    main_log = (folder / "ctl/term/main/out.log").read_text(errors="replace")
    other_log = (folder / "ctl/term/other/out.log").read_text(errors="replace")
    for cycle in range(client.expected_edits):
        require(
            f"FULL_LOG_END_{cycle}" in main_log and f"SOAK-MARK-{cycle}" in other_log,
            "documented accumulated log lost a cycle marker",
        )
    require(
        {p.name for p in (work / "tree").iterdir()}
        == {f"{i:05d}" for i in range(1200)},
        "large tree lost entries",
    )
    for i in range(1200):
        require(
            (work / "tree" / f"{i:05d}").read_text() == str(i),
            "large tree bytes corrupted",
        )
    health = client.health + [after_cleanup]
    baseline = client.health[min(3, len(client.health) - 1)]
    steady = client.health[3:] or client.health
    require(
        health[-1]["fd_count"] <= baseline["fd_count"] + 8,
        "unexplained file descriptor growth",
    )
    require(
        health[-1]["threads"] <= baseline["threads"] + 2, "unexplained thread growth"
    )
    require(
        health[-1]["async_tasks"] <= baseline["async_tasks"] + 3,
        "unexplained async task growth",
    )
    require(
        health[-1]["descendants"] <= 2 and health[-1]["owned_cwd_processes"] == 0,
        "owned subprocesses remained after cleanup",
    )
    # Retained raw history is intentional; a gross 150MiB bound catches runaway
    # growth without claiming constant memory in a growing recorded transcript.
    require(
        health[-1]["rss_kib"] - baseline["rss_kib"] < 150 * 1024,
        "unexplained gross RSS growth",
    )
    require(
        max(r["descendants"] for r in steady) <= baseline["descendants"] + 8
        and max(r["owned_cwd_processes"] for r in steady)
        <= baseline["owned_cwd_processes"] + 8,
        "process accumulation",
    )
    require(
        health[-1]["files"] - baseline["files"] < client.turns * 3 + 100,
        "temporary-file accumulation",
    )
    first = statistics.median(client.latencies[20:120] or client.latencies)
    last = statistics.median(client.latencies[-100:])
    require(last < max(3.0, first * 4), "gross sustained latency degradation")
    require(not list(folder.rglob("*.aether-*.tmp")), "staging files leaked")
    require(
        not list(scratch.iterdir()) and not list(host_scratch.iterdir()),
        "temporary directories leaked",
    )
    require(
        sum(p.is_file() for p in work.rglob("*")) <= 1210,
        "unexpected task-tree file accumulation",
    )
    service = int((work / "service.pid").read_text())
    check = subprocess.run(
        ["ps", "-p", str(service), "-o", "stat="], capture_output=True, text=True
    )
    require(
        not check.stdout.strip() or check.stdout.strip().startswith("Z"),
        "heartbeat service survived stop cleanup",
    )
    if seconds >= 60:
        require(client.checkpoints > 0, "long episode did not exercise checkpoints")
    evidence_hashes = {}
    for path in [
        folder / "trace.jsonl",
        folder / "calls.jsonl",
        folder / "logs" / "aether_run_record.json",
        work / "artifact.txt",
        work / "compiled.json",
        *logs,
    ]:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        evidence_hashes[str(path.relative_to(folder))] = digest.hexdigest()
    summary = {
        "evidence_sha256": evidence_hashes,
        "mode": mode,
        "elapsed_s": elapsed,
        "scripted_tool_turns": client.turns,
        "trace_tool_events": len(tools),
        "attempts": client.attempts,
        "injected_retry_faults": len(client.faulted),
        "checkpoints": client.checkpoints,
        "accepted_edits": sum(
            r["event"] == "context_edit" and bool(r.get("accepted")) for r in rows
        ),
        "negative_controls": negative_controls,
        "health_thresholds": {
            "fd_growth": 8,
            "thread_growth": 2,
            "async_task_growth": 3,
            "post_cleanup_descendants": 2,
            "rss_growth_kib": 150 * 1024,
            "latency_limit_s": max(3.0, first * 4),
        },
        "status": result.status,
        "cleanup_errors": result.extras["cleanup_errors"],
        "final_artifact_sha256": hashlib.sha256(
            (work / "artifact.txt").read_bytes()
        ).hexdigest(),
        "heartbeat_ticks": int((work / "heartbeat").read_text()),
        "health": health,
        "request_bytes_max": max(client.request_sizes),
        "latency_first_100_median_s": statistics.median(client.latencies[:100]),
        "latency_last_100_median_s": statistics.median(client.latencies[-100:]),
        "scope": "actual local Core loop; scripted provider; no model/native Harbor; not historical environment replay",
    }
    (folder / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "health"}), flush=True)
    tempfile.tempdir = previous_tempdir
    return summary


async def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seconds", type=float, default=600)
    p.add_argument("--min-turns", type=int, default=1000)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--mode", choices=["off", "history_index"])
    args = p.parse_args()
    require(
        args.seconds > 0 and args.min_turns >= 16 and args.repeats > 0,
        "invalid stress bounds",
    )
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    unhandled = []
    loop = asyncio.get_running_loop()

    def observe_unhandled(loop, context):
        unhandled.append(
            {
                "message": context.get("message"),
                "exception": str(context.get("exception")),
            }
        )
        loop.default_exception_handler(context)

    loop.set_exception_handler(observe_unhandled)
    try:
        for i in range(args.repeats):
            rows.append(
                await episode(
                    args.out / f"episode-{i}",
                    args.seconds,
                    args.min_turns,
                    args.mode or ("off" if i % 2 == 0 else "history_index"),
                )
            )
    except BaseException as exc:
        import traceback

        (args.out / "FAILURE.json").write_text(
            json.dumps(
                {
                    "exception": type(exc).__name__,
                    "detail": str(exc),
                    "traceback": traceback.format_exc(),
                    "completed_episodes": len(rows),
                },
                indent=2,
            )
            + "\n"
        )
        raise
    await asyncio.sleep(0)
    require(not unhandled, "unhandled async exceptions: " + str(unhandled))
    (args.out / "SUMMARY.json").write_text(
        json.dumps(
            {
                "platform": platform.platform(),
                "core_module": __import__("aether.core", fromlist=["x"]).__file__,
                "episodes": [
                    {k: v for k, v in r.items() if k != "health"} for r in rows
                ],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
