"""Measure a source-grounded initial-note counterfactual on admitted requests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics

from aether.core.facts import Facts
from qa import replay_corpus
from qa.replay_facts_history import MANIFEST_SHA, NoHistoricalEnvironment, percentile, read_source


def observed_names(items):
    for item in items:
        if not isinstance(item, dict) or item.get("role") != "user" or not isinstance(item.get("content"), str):
            continue
        content = item["content"]
        if "Environment, measured by the harness" not in content:
            continue
        available = re.findall(r"(?m)^\s*available:\s*([^\n]*)", content)
        missing = re.findall(r"(?m)^\s*not found on PATH:\s*([^\n]*)", content)
        if len(available) != 1 or len(missing) != 1:
            raise ValueError("initial availability was ambiguous")
        yes, no = available[0].split(), missing[0].split()
        if len(yes) + len(no) < 10 or len(set(yes + no)) != len(yes) + len(no):
            raise ValueError("initial availability was incomplete")
        if not all(re.fullmatch(r"[A-Za-z0-9_+.-]{1,64}", n) for n in yes + no):
            raise ValueError("unsafe command name")
        return yes, no
    raise ValueError("initial environment brief unavailable")


def note_for(yes, no):
    service = Facts(NoHistoricalEnvironment(), "/historical-unavailable", lambda: 600,
                    lambda *_a, **_k: None, hosts=())
    status = {name: "resolved; exact path unmeasured" for name in yes}
    status.update({name: None for name in no})
    snapshot = {"commands": status, "versions": {}, "network": {}, "host_available_memory_kib": None,
                "files": [], "files_complete": False, "workspace": None}
    return service._initial(snapshot, 0) + "\nOther command names and later changes were not measured."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--mirror", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError("manifest digest mismatch")
    manifest = json.loads(raw)
    if len(manifest["runs"]) != 128:
        raise ValueError("selection differs from the frozen corpus")
    root, mirror = args.root.resolve(strict=True), args.mirror.resolve(strict=True)
    rows, ratios = [], []
    for entry in sorted(manifest["runs"], key=lambda r: (r["study"], r["run_id"])):
        try:
            raw_calls = read_source(Path(entry["calls"]), entry["calls_sha256"], root, mirror, "core_calls.jsonl")
            call_rows, bad = replay_corpus.read_jsonl(raw_calls)
            if bad:
                raise ValueError("malformed call log")
            calls = replay_corpus.parse_call_log(call_rows)
            inputs = []
            for seq, start in sorted(calls["starts"].items()):
                if start.get("role") != "worker" or not calls["ends"].get(seq, {}).get("ok"):
                    continue
                request, misses = replay_corpus.expand_request(start.get("request") or {}, calls["blobs"])
                items = request.get("input") or request.get("messages")
                if misses or not isinstance(items, list):
                    raise ValueError("unresolved request")
                inputs.append(items)
            if not inputs:
                raise ValueError("no worker requests")
            yes, no = observed_names(inputs[0])
            note = {"role": "user", "content": note_for(yes, no)}
            off, on = [], []
            for items in inputs:
                if len(items) < 2 or items[0].get("role") != "system" or items[1].get("role") != "user":
                    raise ValueError("unsupported pinned request shape")
                off.append(len(json.dumps(items, ensure_ascii=False, separators=(",", ":"))))
                on.append(len(json.dumps(items[:2] + [note] + items[2:], ensure_ascii=False,
                                         separators=(",", ":"))))
            ratios.extend(b / a for a, b in zip(off, on))
            rows.append({"run_id": entry["run_id"], "study": entry["study"], "status": "valid",
                         "requests": len(off), "observed_command_names": len(yes) + len(no),
                         "note_chars": len(note["content"]), "sum_ratio": sum(on) / sum(off)})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            rows.append({"run_id": entry["run_id"], "study": entry["study"],
                         "status": "invalid", "reason": type(exc).__name__})
    valid = [row for row in rows if row["status"] == "valid"]
    result = {"manifest_sha256": MANIFEST_SHA, "valid": len(valid), "selected": len(rows),
              "requests": len(ratios), "median_run_sum_ratio": statistics.median(x["sum_ratio"] for x in valid)
              if valid else None, "p90_request_ratio": percentile(ratios, .9), "runs": rows,
              "scope": ["initial statuses taken only from the run's captured brief",
                        "hypothetical additive note, with no live state updates or model calls",
                        "characters are not provider tokens, cache cost, cloud cost, or task success"]}
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "runs"}, indent=2))


if __name__ == "__main__":
    main()
