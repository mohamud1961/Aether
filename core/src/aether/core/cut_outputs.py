"""D18 evidence: keep the full output behind every cut terminal result next to the run's trace (opt-in).

A terminal result longer than the view is shown as head + tail; the middle stays only in the terminal's log inside the
environment, which is gone after the run. Without it nobody can later tell whether the hidden middle held the line
that mattered (D18 census: 5,477 cuts, none recoverable). With ``keep_cut_outputs`` on, the run's end copies each cut
span (the exact byte range the model was shown head and tail of) into ``<trace dir>/cut_outputs/``, with an index.
Never model-visible. Bounded: at most ``SPAN_CAP`` bytes per span and ``TOTAL_CAP`` per run; a span beyond either is
recorded as truncated, and a span that cannot be read is recorded with its error, never silently dropped.
"""

from __future__ import annotations

import base64
import json
import shlex
from pathlib import Path

from .env import Environment, run

SPAN_CAP = 2_000_000
TOTAL_CAP = 20_000_000


async def keep(env: Environment, out_dir: Path, spans: list[tuple[str, int, int]]) -> dict:
    """spans: (log path in the environment, start byte, end byte) of each cut result. Returns the index written."""
    rows, used = [], 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for n, (log, start, end) in enumerate(spans):
        want = max(0, end - start)
        take = min(want, SPAN_CAP, max(0, TOTAL_CAP - used))
        row = {"n": n, "log": log, "start": start, "end": end, "bytes": want, "kept": 0, "truncated": take < want}
        if take:
            q = shlex.quote(log)  # a pipe's status is base64's, so a vanished log must be refused before it
            res = await run(env, f"[ -f {q} ] || exit 13; tail -c +{start + 1} {q} | head -c {take} | base64", timeout_s=30)
            try:
                if res.code != 0:
                    raise RuntimeError("log missing" if res.code == 13 else f"exit {res.code}")
                raw = base64.b64decode("".join(res.stdout.split()), validate=True)
                name = f"cut_{n:04d}.txt"
                (out_dir / name).write_bytes(raw)
                row.update(file=name, kept=len(raw), truncated=len(raw) < want)
                used += len(raw)
            except (RuntimeError, ValueError) as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    index = {"spans": rows, "kept_bytes": used, "span_cap": SPAN_CAP, "total_cap": TOTAL_CAP}
    (out_dir / "index.json").write_text(json.dumps(index, indent=1))
    return index
