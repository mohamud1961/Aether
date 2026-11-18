"""Join provider logs, model turns, tool results and grades for a single Core trial.

Every receipt is one JSON object ``{"schema", "kind", "id", "parent", "source", "fields"}``:

- ``spend``  id = provider response id; provider-reported usage from the calls log ``end`` rows;
- ``model``  id = the turn's response id (``turn-<n>`` when the provider gave none); parent = its spend receipt;
- ``effect`` id = the tool call id; this is a Core tool-result event, not independent proof of an external effect.
  ``fields.delivery`` is the tag reported in the trace for the owner's operation record;
- ``grade``  id = the trial; parent = none; ``fields.reward`` from Harbor's ``result.json``.

The chain detects missing provider outcomes, response IDs, tool-result IDs and grades. It does not reconcile the
protected spend ledger or establish whether a backend performed an effect once; use those independent receipts.

Usage: python3 tools/receipt_chain.py TRIAL_DIR [--receipts out.jsonl]
TRIAL_DIR holds ``result.json`` and ``agent/core_trace.jsonl`` (and ``agent/core_calls.jsonl`` when recorded).
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys

SCHEMA = "aether.receipt.v1"


def _jsonl(path: str):
    if not os.path.exists(path):
        return
    with open(path, errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            if line.strip():
                yield n, json.loads(line)


def receipt(kind: str, ident: str, parent: str | None, source: str, **fields) -> dict:
    return {"schema": SCHEMA, "kind": kind, "id": ident, "parent": parent, "source": source, "fields": fields}


def build(trial: str) -> tuple[list[dict], list[str]]:
    """Receipts for one trial, and the list of chain breaks (empty = the chain holds)."""
    agent = os.path.join(trial, "agent")
    receipts, breaks = [], []
    calls_path, trace_path = os.path.join(agent, "core_calls.jsonl"), os.path.join(agent, "core_trace.jsonl")
    spend, starts, ends = {}, set(), set()
    for n, row in _jsonl(calls_path):
        if row.get("kind") == "start":
            if row.get("seq") in starts:
                breaks.append(f"provider attempt {row.get('seq')} has duplicate starts")
            starts.add(row.get("seq"))
        elif row.get("kind") == "end":
            seq, rid = row.get("seq"), row.get("response_id")
            if seq in ends:
                breaks.append(f"provider attempt {seq} has duplicate outcomes")
            ends.add(seq)
            if not rid:
                breaks.append(f"provider attempt {seq} has no response id")
            elif rid in spend:
                breaks.append(f"response {rid} appears in multiple provider outcomes")
            else:
                spend[rid] = receipt("spend", rid, None, f"core_calls.jsonl:{n}",
                                     usage=row.get("usage"), ok=row.get("ok"), seq=seq)
            if not row.get("ok") or not isinstance(row.get("usage"), dict) or not row["usage"]:
                breaks.append(f"provider attempt {seq} has incomplete usage or outcome")
    breaks += [f"provider attempt {seq} has no outcome" for seq in sorted(starts - ends, key=str)]
    breaks += [f"provider outcome {seq} has no start" for seq in sorted(ends - starts, key=str)]
    receipts += spend.values()
    asked, turns, executed = {}, 0, collections.Counter()
    for n, event in _jsonl(trace_path):
        if event.get("event") == "model":
            turns += 1
            rid = event.get("response_id")
            ident = rid or f"turn-{turns}"
            if not rid:
                breaks.append(f"model turn {turns} has no response id")
            elif rid not in spend:
                breaks.append(f"model turn {turns} ({rid}) has no spend receipt")
            receipts.append(receipt("model", ident, rid if rid in spend else None, f"core_trace.jsonl:{n}",
                                    usage=event.get("usage"), calls=len(event.get("tool_calls") or [])))
            for call in event.get("tool_calls") or []:
                if call.get("id") in asked:
                    breaks.append(f"tool call id {call.get('id')} asked by two turns")
                asked[call.get("id")] = ident
        elif event.get("event") == "tool":
            cid = event.get("call_id")
            if not cid:
                breaks.append(f"unidentified tool result at core_trace.jsonl:{n}")
                continue
            executed[cid] += 1
            if cid not in asked:
                breaks.append(f"effect {event.get('name')} ({cid}) has no asking model turn")
            receipts.append(receipt("effect", cid, asked.get(cid), f"core_trace.jsonl:{n}", name=event.get("name"),
                                    delivery=event.get("delivery")))
    breaks += [f"tool call {cid} executed {k} times" for cid, k in executed.items() if k > 1]
    if not os.path.exists(calls_path):
        breaks.append("no calls log: spend not recorded for this trial")
    if not executed and turns:
        breaks.append("trace has no identified effects (written before H1, or no tool ran)")
    result_path = os.path.join(trial, "result.json")
    if os.path.exists(result_path):
        with open(result_path) as fh:
            result = json.load(fh)
        reward = ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        if type(reward) not in (int, float) or not math.isfinite(reward):
            breaks.append("no finite numeric grade in result.json")
        else:
            receipts.append(receipt("grade", os.path.basename(os.path.normpath(trial)), None, "result.json", reward=reward))
    else:
        breaks.append("no grade (result.json missing)")
    return receipts, breaks


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("trial")
    ap.add_argument("--receipts")
    args = ap.parse_args(argv[1:])
    receipts, breaks = build(args.trial)
    if args.receipts:
        with open(args.receipts, "x") as fh:
            fh.writelines(json.dumps(r, sort_keys=True) + "\n" for r in receipts)
    kinds = collections.Counter(r["kind"] for r in receipts)
    print(json.dumps({"receipts": dict(kinds), "breaks": breaks,
                      "scope": "Core log joins only; verify provider charges and external effects independently"}, indent=1))
    return 1 if breaks else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
