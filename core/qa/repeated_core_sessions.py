import asyncio
import gc
import importlib.util
import json
import os
import subprocess
from pathlib import Path

from aether.core.clm import ClmContext
from aether.core.loop import _Session
from aether.core.repl import Repl
from aether.core.terminal import Terminals

source = Path(__file__).with_name("sustained_core.py")
spec = importlib.util.spec_from_file_location("repeated_sustained", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
import argparse

parser = argparse.ArgumentParser(
    description="Sequential installed Core sessions with GC and descriptor state audit"
)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--seconds", type=float, default=60)
parser.add_argument("--turns", type=int, default=128)
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
if args.repeats < 2 or args.seconds < 1 or args.turns < 21:
    parser.error("repeat audit requires >=2 sessions, positive duration and >=21 turns")
root = args.out
root.mkdir(exist_ok=False)
targets = (_Session, ClmContext, Terminals, Repl)


def state():
    gc.collect()
    counts = {
        kind.__name__: sum(type(obj) is kind for obj in gc.get_objects())
        for kind in targets
    }
    rss = int(
        subprocess.check_output(
            ["ps", "-p", str(os.getpid()), "-o", "rss="], text=True
        ).strip()
    )
    return {
        "live_core_objects_after_gc": counts,
        "rss_kib_after_gc": rss,
        "fds": len(os.listdir("/dev/fd")),
        "async_tasks": len(asyncio.all_tasks()),
    }


async def main():
    baseline = state()
    rows = []
    for i in range(args.repeats):
        summary = await module.episode(
            root / f"episode-{i}",
            args.seconds,
            args.turns,
            "off" if i == 0 else "history_index",
        )
        after = state()
        if (
            after["live_core_objects_after_gc"]
            != baseline["live_core_objects_after_gc"]
        ):
            raise RuntimeError("Core object retained across sessions")
        if (
            after["fds"] > baseline["fds"] + 2
            or after["async_tasks"] > baseline["async_tasks"]
        ):
            raise RuntimeError("cross-session resource accumulation")
        rows.append(
            {
                "episode": i,
                "elapsed_s": summary["elapsed_s"],
                "tool_turns": summary["scripted_tool_turns"],
                "after_gc": after,
            }
        )
    result = {
        "scope": "sequential real Core episodes in ONE process; explicit GC separates unreachable context cycles from live leaks; RSS allocator retention is not constant-space proof",
        "baseline": baseline,
        "episodes": rows,
    }
    (root / "REPEATED_SESSION_GC.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


try:
    asyncio.run(main())
except BaseException as exc:
    (root / "FAILURE.json").write_text(
        json.dumps({"error": type(exc).__name__, "detail": str(exc)}) + "\n"
    )
    raise
