"""Validate and render historical records with real source files, never invented scores."""

import json
import os
from pathlib import Path

LABELS = {"pre-registered", "development", "replay", "invalid", "single run"}


def render(root):
    records = []
    for path in sorted(Path(root).glob("*.json")):
        r = json.loads(path.read_text())
        if (
            set(r) != {"question", "arms", "n", "result", "label", "source"}
            or r["label"] not in LABELS
        ):
            raise ValueError(f"invalid record {path}")
        if not (path.parent / r["source"]).resolve().is_file():
            raise ValueError(f"missing source {path}")
        records.append(r)
    lines = [
        "# Results registry",
        "",
        "Historical evidence; not calibration of the packaged runner.",
        "",
        "| Question | Arms | N | Result | Evidence | Source |",
        "|---|---|---:|---|---|---|",
    ]
    for r in records:
        values = [
            str(r[k]).replace("|", "\\|").replace("\n", " ")
            for k in ["question", "arms", "n", "result", "label", "source"]
        ]
        values[-1] = (
            f"[source]({os.path.relpath((Path(root) / r['source']).resolve(), Path(root).resolve().parent)})"
        )
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"
