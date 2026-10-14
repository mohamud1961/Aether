#!/usr/bin/env bash
# Replays every file under ops/ (plain and gzip) in seq order, then writes the two out/ files.
set -euo pipefail
mkdir -p out
python3 - <<'PY'

import csv, glob, gzip, json, re
from pathlib import Path

def parse(line):
    out = {}
    for tok in line.split():
        k, sep, v = tok.partition("=")
        if sep:
            out[k] = v
    return out

def read_events(paths):
    events = []
    for p in paths:
        opener = gzip.open if p.endswith(".gz") else open
        with opener(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    events.append(parse(line))
    return events

def run(events, sort_events=True, ignore_rollback=False, lenient=False):
    if sort_events:
        events = sorted(events, key=lambda e: int(e["seq"]))
    state, snaps = {}, {}
    for e in events:
        if e.get("kind") != "cfg":
            continue
        op = e.get("op")
        if op == "set":
            if e.get("status") == "applied" and e.get("dry_run") != "true":
                state[e["key"]] = e["value"]
        elif op == "checkpoint":
            snaps[e["name"]] = dict(state)
        elif op == "rollback" and not ignore_rollback:
            if e["to"] in snaps:
                state = dict(snaps[e["to"]])
            elif not lenient:
                raise SystemExit("rollback target missing: " + e["to"])
    return state, snaps

ALL = sorted(glob.glob("ops/*.log")) + sorted(glob.glob("ops/*.log.gz"))

def write_outputs(state, c3):
    Path("out").mkdir(exist_ok=True)
    Path("out/final_state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    changed = sorted(k for k in state if state[k] != c3.get(k))
    Path("out/changed_since_c3.json").write_text(json.dumps({"changed_keys": changed}, indent=2) + "\n", encoding="utf-8")

events = read_events(ALL)
state, snaps = run(events)
write_outputs(state, snaps["C3"])
PY
python3 checks/shape_check.py
