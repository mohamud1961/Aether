"""Replay admitted historical events without executing commands or exposing payloads."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import stat
import statistics
from typing import Any

from aether.core import facts as facts_module
from aether.core import facts_probe, facts_workspace
from aether.core.facts import Facts
from qa import replay_corpus

MANIFEST_SHA = "9759c8eac285fd5582206ed8d0852b38d4a0c24c00e87f7c85d1a40b64c2b025"
STUDIES = ("y12", "y13", "y14", "y15", "y17", "y18")
DENIED = ("rolling-shutter", "extract-elf", "make-doom", "sanitize-git-repo",
          "openssl-selfsigned-cert", "feal-linear-cryptanalysis", "configure-git-webserver")
DENIED_COMPONENTS = {"test", "tests", "solution", "solutions", "verifier", "verifiers", "grader", "graders"}
MAX_BYTES = 40_000_000


def read_source(path: Path, expected: str, root: Path, mirror: Path, leaf: str) -> bytes:
    if not path.is_absolute() or path.name != leaf or path.parent.name != "agent":
        raise ValueError("unexpected source name")
    relative = path.relative_to(root)
    if any(part.lower() in DENIED_COMPONENTS for part in relative.parts):
        raise ValueError("protected source component")
    if any(name in str(relative).lower() for name in DENIED):
        raise ValueError("excluded task family")
    peer = mirror / relative
    for base, rel in ((root, relative), (mirror, relative)):
        cursor = base
        for part in rel.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError("linked source path")
    peer_stat = peer.stat(follow_symlinks=False)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 2 or before.st_uid != os.getuid()
                or before.st_size > MAX_BYTES or (before.st_dev, before.st_ino) != (peer_stat.st_dev, peer_stat.st_ino)):
            raise ValueError("source or mirror identity changed")
        data = bytearray()
        while True:
            part = os.read(fd, 1_048_576)
            if not part:
                break
            data.extend(part)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if ((before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or len(data) != before.st_size
            or hashlib.sha256(data).hexdigest() != expected):
        raise ValueError("source changed or digest mismatch")
    return bytes(data)


class NoHistoricalEnvironment:
    async def exec(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("historical commands and probes must not execute")


async def unknown_probe(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": False, "reason": "historical environment not restored"}


def request_lengths(rows: list[dict[str, Any]]) -> tuple[list[int], int]:
    calls = replay_corpus.parse_call_log(rows)
    lengths, unresolved = [], 0
    for seq, start in sorted(calls["starts"].items()):
        if start.get("role") != "worker" or not calls["ends"].get(seq, {}).get("ok"):
            continue
        request, misses = replay_corpus.expand_request(start.get("request") or {}, calls["blobs"])
        items = request.get("input") or request.get("messages")
        if misses or not isinstance(items, list):
            unresolved += 1
            continue
        lengths.append(len(json.dumps(items, ensure_ascii=False, separators=(",", ":"))))
    return lengths, unresolved


async def replay_one(events: list[dict[str, Any]]) -> dict[str, int]:
    service = Facts(NoHistoricalEnvironment(), "/historical-state-unavailable", lambda: 600,
                    lambda *_a, **_k: None, terminal_state=lambda _name: None,
                    python_state=lambda: {"foreground": "unknown", "variables": "not inspected"}, hosts=())
    await service.start()
    names, checked = Counter(), 0
    for event in events:
        if event.get("event") != "tool":
            continue
        name = event.get("name")
        args = event.get("args") if isinstance(event.get("args"), dict) else {}
        result = event.get("result")
        if not isinstance(name, str) or not isinstance(result, str):
            raise ValueError("tool event has unsupported shape")
        checked += 1
        names[name] += 1
        await service.after_action(checked, name, args, result)
        receipt = service.events[-1]
        expected = hashlib.sha256(result.encode("utf-8", errors="surrogatepass")).hexdigest() if len(result) <= 256_000 else None
        if (receipt["step"] != checked or receipt["tool"] != name or receipt["tool_output_sha256"] != expected
                or receipt["workspace_status"] != "unknown"):
            raise ValueError("facts receipt mismatch or invented workspace state")
    if service.record()["initial_workspace"]["status"] != "unknown" or service.shared_known:
        raise ValueError("historical state asserted as observed")
    if names["python"] and (service.python_session or {}).get("foreground") != "unknown":
        raise ValueError("historical Python state asserted as observed")
    return {"events": checked, "terminal": names["terminal"], "python": names["python"],
            "service_faults": service.internal_failures}


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    data = sorted(values)
    return data[min(len(data) - 1, int((len(data) - 1) * fraction))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--mirror", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--all", action="store_true", help="use all previously admitted runs")
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError("frozen manifest changed")
    manifest = json.loads(raw)
    if args.all:
        selected = sorted(manifest["runs"], key=lambda r: (r["study"], r["run_id"]))
        if len(selected) != 128 or len({r["run_id"] for r in selected}) != 128:
            raise ValueError("frozen complete selection unavailable")
    else:
        selected = []
        for study in STUDIES:
            bucket = sorted((r for r in manifest["runs"] if r.get("study") == study), key=lambda r: r["run_id"])
            if len(bucket) < 4:
                raise ValueError("predeclared study sample unavailable")
            selected.extend(bucket[:4])
    root, mirror = args.root.resolve(strict=True), args.mirror.resolve(strict=True)
    original_probe = facts_probe.probe
    facts_probe.probe = unknown_probe
    results, all_lengths = [], []
    try:
        for entry in selected:
            try:
                trace = read_source(Path(entry["trace"]), entry["trace_sha256"], root, mirror, "core_trace.jsonl")
                calls = read_source(Path(entry["calls"]), entry["calls_sha256"], root, mirror, "core_calls.jsonl")
                events, bad_trace = replay_corpus.read_jsonl(trace)
                call_rows, bad_calls = replay_corpus.read_jsonl(calls)
                if bad_trace or bad_calls:
                    raise ValueError("malformed historical log")
                state = asyncio.run(replay_one(events))
                lengths, unresolved = request_lengths(call_rows)
                if not lengths or state["service_faults"]:
                    raise ValueError("missing requests or state-service fault")
                all_lengths.extend(lengths)
                results.append({"run_id": entry["run_id"], "study": entry["study"], "status": "valid",
                                **state, "requests": len(lengths), "unresolved_requests": unresolved,
                                "median_request_chars": statistics.median(lengths)})
            except (OSError, ValueError, KeyError, TypeError) as exc:
                results.append({"run_id": entry["run_id"], "study": entry["study"],
                                "status": "invalid", "reason": type(exc).__name__})
    finally:
        facts_probe.probe = original_probe
    sensitivity = {}
    for size in (128, 512, 1024):
        ratios = [1 + size / n for n in all_lengths if n]
        sensitivity[str(size)] = {"median": statistics.median(ratios) if ratios else None,
                                  "p90": percentile(ratios, .9)}
    report = {"manifest_sha256": MANIFEST_SHA, "selected": len(selected),
              "valid": sum(row["status"] == "valid" for row in results), "runs": results,
              "service_source_sha256": {Path(module.__file__).name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                                        for module in (facts_module, facts_probe, facts_workspace)},
              "historical_request_count": len(all_lengths),
              "median_request_chars": statistics.median(all_lengths) if all_lengths else None,
              "hypothetical_fixed_note_char_ratios": sensitivity,
              "scope": ["historical environments, processes and file states not restored",
                        "no recorded commands executed", "no hidden labels, task results or model calls",
                        "note ratios are hypothetical, not measured treatment overhead or provider tokens"]}
    with args.output.open("x") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "runs"}, indent=2))


if __name__ == "__main__":
    main()
