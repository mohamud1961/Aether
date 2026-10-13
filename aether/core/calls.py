"""Every model call made through the provider, from every role: what was sent, what came back, what it cost.

The provider owns this log; nothing else counts its attempts or tokens. The reviewer is not a provider call: it has its
own journal (``core_reviewer_journal.jsonl``) and the run record reports the two side by side.

On disk (``core_calls.jsonl``) each attempt is a ``start`` row written before the request is sent and one
``end`` row (ok, failed or cancelled) with the same ``seq``. A start with no end is an attempt whose outcome is
unknown (the process died mid-call); ``requests()`` reports it as such, never as a success or a failure. Values are
stored content-addressed: every distinct message, tool list, parameter set and response is one ``blob`` row, so
a 300-turn run costs roughly its new messages, not 300 copies of the history.

What is exact and what is not: ``requests()`` rebuilds each request byte-for-byte as passed to the client (checked
in ``tests/test_core_truth.py``). The response is as the provider assembled it from the stream (content,
reasoning, tool calls; on a failed or cancelled attempt, whatever had streamed), not the raw wire bytes.

Unknown is never written as zero: usage fields the provider did not report are absent from that attempt's
``usage`` and listed under ``usage_missing``; an attempt that did not complete has unknown usage.
"""
from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path
from typing import Any, Iterator

USAGE_FIELDS = ("input", "cached", "output", "reasoning")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:20]


class CallLog:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._seen: set[str] = set()
        self._open: dict[int, str] = {}  # seq -> role, for attempts without an end row yet
        self.seq = 0
        self.by_role: dict[str, dict[str, int]] = {}
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def start(self, *, role: str, attempt: int, request: dict[str, Any]) -> int:
        """Record an attempt before it is sent; returns its ``seq`` for ``end``."""
        self.seq += 1
        self._open[self.seq] = role
        self._totals(role)["attempts"] += 1
        rows: list[dict[str, Any]] = []
        refs = {name: ([self._blob(m, rows) for m in value] if name == "messages" else
                       self._blob(value, rows) if name in ("tools", "params") else value)
                for name, value in request.items()}
        rows.append({"kind": "start", "seq": self.seq, "role": role, "attempt": attempt, "request": refs})
        self._write(rows)
        return self.seq

    def end(self, seq: int, outcome: dict[str, Any]) -> None:
        """The attempt's outcome: ``ok`` (True/False), ``error`` (``cancelled`` for a cancelled call), ``usage``
        (fields actually reported), ``response`` ({content, reasoning, tool_calls}, partial when not ok) and
        provider identities when known."""
        role = self._open.pop(seq)
        usage = outcome.get("usage") or {}
        missing = [f for f in USAGE_FIELDS if f not in usage]
        totals = self._totals(role)
        totals["failed"] += not outcome.get("ok")
        totals["cancelled"] += outcome.get("error") == "cancelled"
        totals["usage_unknown"] += bool(missing)
        for f in USAGE_FIELDS:
            totals[f] += int(usage.get(f, 0))
        rows: list[dict[str, Any]] = []
        row = {"kind": "end", "seq": seq, "usage_missing": missing,
               **{k: (self._blob(v, rows) if k == "response" else v) for k, v in outcome.items()}}
        rows.append(row)
        self._write(rows)

    def _totals(self, role: str) -> dict[str, int]:
        return self.by_role.setdefault(role, {"attempts": 0, "failed": 0, "cancelled": 0, "usage_unknown": 0,
                                              **{f: 0 for f in USAGE_FIELDS}})

    def _write(self, rows: list[dict[str, Any]]) -> None:
        if self._path is None:
            return
        with self._path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(_canonical(row) + "\n")
            fh.flush()

    def _blob(self, value: Any, rows: list[dict[str, Any]]) -> str:
        text = _canonical(value)
        key = _key(text)
        if key not in self._seen:
            self._seen.add(key)
            rows.append({"kind": "blob", "key": key, "value": json.loads(text)})
        return key

    def totals(self) -> dict[str, Any]:
        """Per-role counts plus an ``all`` row. Token totals are lower bounds when ``usage_unknown`` > 0 or an
        attempt is still ``open`` (no outcome recorded)."""
        keys = ("attempts", "failed", "cancelled", "usage_unknown", *USAGE_FIELDS)
        out: dict[str, Any] = {role: dict(t) for role, t in self.by_role.items()}
        out["all"] = {k: sum(t[k] for t in self.by_role.values()) for k in keys}
        out["all"]["open"] = len(self._open)
        return out


def requests(path: Path) -> Iterator[dict[str, Any]]:
    """Every logged attempt, in order, with its full request (``request`` holds the exact client arguments) and
    its outcome; an attempt with no end row has ``ok`` None and ``error`` "no outcome recorded"."""
    blobs: dict[str, Any] = {}
    starts: dict[int, dict[str, Any]] = {}
    ends: dict[int, dict[str, Any]] = {}
    truncated = False
    with path.open("rb") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                if line.endswith(b"\n"):
                    raise  # corruption of a committed row must not be hidden
                truncated = True
                warnings.warn(f"{path}: incomplete final log record; recovering committed attempts", RuntimeWarning)
                break
            if row["kind"] == "blob":
                blobs[row["key"]] = row["value"]
            elif row["kind"] == "start":
                starts[row["seq"]] = row
            else:
                ends[row["seq"]] = row
    for seq, start in sorted(starts.items()):
        refs = dict(start["request"])
        if "messages" in refs:
            refs["messages"] = [blobs[k] for k in refs["messages"]]
        for name in ("tools", "params"):
            if name in refs:
                refs[name] = blobs[refs[name]]
        params = refs.pop("params", {}) or {}
        end = dict(ends.get(seq) or {"ok": None, "error": "no outcome recorded", "usage_missing": list(USAGE_FIELDS)})
        if "response" in end:
            end["response"] = blobs[end["response"]]
        end.pop("kind", None)
        yield {"seq": seq, "role": start["role"], "attempt": start["attempt"], "request": {**refs, **params},
               **end, "log_truncated": truncated}
