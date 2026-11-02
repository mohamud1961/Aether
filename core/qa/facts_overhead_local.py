"""Matched provider-free Core episodes measuring local facts overhead.

These are synthetic tasks, not replayed historical machines or Luna outcomes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

from aether.core import facts_probe
from aether.core.clm import ClmSettings
from aether.core.loop import CoreConfig, Trace, run_agent
from tests.core_fakes import LocalEnv
from tests.test_core_responses import ResponsesClient, provider, turn_events


async def episode(root: Path, enabled: bool) -> dict:
    work = root / "work"
    work.mkdir(parents=True)
    calls = [
        ("terminal", {"input": "printf 'alpha\\n' > answer.txt"}),
        ("read_file", {"path": "answer.txt"}),
        ("terminal", {"input": "cat answer.txt"}),
        ("edit_file", {"path": "answer.txt", "old_str": "alpha", "new_str": "beta"}),
        ("terminal", {"input": "cat answer.txt"}),
        ("finish", {"summary": "done"}),
    ]
    client = ResponsesClient([
        turn_events(i, call=(name, args, f"c{i}")) for i, (name, args) in enumerate(calls, 1)
    ])
    env = LocalEnv(work)
    config = CoreConfig(
        context="clm", clm=ClmSettings(mirror_path=str(root / "ctx" / "LIVE_CTX.txt"),
                                       history_path=str(root / "ctx" / "HISTORY.txt")),
        control_dir=str(root / "ctl"), end_processes="stop", managed_facts=enabled,
    )
    started = time.monotonic()
    result = await run_agent(
        env=env, task="Create answer.txt containing beta.", workdir=str(work),
        provider=provider(client, root / "calls"), timeout_s=600,
        trace=Trace(root / "trace.jsonl"), config=config,
    )
    elapsed = time.monotonic() - started
    lengths = [len(json.dumps(request.get("input", []), ensure_ascii=False, separators=(",", ":")))
               for request in client.requests]
    return {
        "status": result.status, "artifact_matches": (work / "answer.txt").read_bytes() == b"beta\n",
        "request_chars": lengths, "wall_s": round(elapsed, 4), "environment_execs": len(env.commands),
        "facts_probe_count": (result.extras.get("core_facts") or {}).get("probe_count", 0),
        "facts_probe_seconds": (result.extras.get("core_facts") or {}).get("probe_seconds", 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blocks", type=int, default=3, choices=range(1, 7))
    args = parser.parse_args()
    facts_probe.HOSTS = ()
    facts_probe.SYSTEM_PYTHON_PATHS = (os.path.realpath(sys.executable),)
    pairs = []
    with tempfile.TemporaryDirectory(prefix="codex-facts-overhead-") as temp:
        root = Path(temp)
        for index in range(args.blocks):
            off = asyncio.run(episode(root / str(index) / "off", False))
            on = asyncio.run(episode(root / str(index) / "onx", True))
            if (off["status"], on["status"]) != ("finished", "finished") or not (
                off["artifact_matches"] and on["artifact_matches"]
            ):
                raise RuntimeError("synthetic artifact or Core run failed")
            if len(off["request_chars"]) != len(on["request_chars"]):
                raise RuntimeError("treatment added or lost a model request")
            pairs.append({"off": off, "on": on})
            print(f"completed local block {index + 1}/{args.blocks}", flush=True)
    block_ratios = [sum(p["on"]["request_chars"]) / sum(p["off"]["request_chars"]) for p in pairs]
    request_ratios = sorted(
        on / off for p in pairs for off, on in zip(p["off"]["request_chars"], p["on"]["request_chars"])
    )
    files = ("facts.py", "facts_probe.py", "loop.py", "loop_records.py", "terminal.py", "repl.py")
    source = Path(__file__).resolve().parents[1] / "src/aether/core"
    report = {
        "pairs": pairs,
        "median_total_request_char_ratio": statistics.median(block_ratios),
        "p90_per_request_char_ratio": request_ratios[math.ceil(len(request_ratios) * .9) - 1],
        "median_wall_off_s": statistics.median(p["off"]["wall_s"] for p in pairs),
        "median_wall_on_s": statistics.median(p["on"]["wall_s"] for p in pairs),
        "median_environment_execs_off": statistics.median(p["off"]["environment_execs"] for p in pairs),
        "median_environment_execs_on": statistics.median(p["on"]["environment_execs"] for p in pairs),
        "source_sha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files},
        "scope": ["scripted local provider", "synthetic task and filesystem", "no public network",
                  "known local interpreter", "no historical machine restore", "no model or VM calls"],
    }
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "pairs"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
