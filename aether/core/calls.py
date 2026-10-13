"""Every model call, exactly: what was sent, what came back, and what it cost, by role.

The provider owns this log; nothing else counts attempts or tokens for the record.

On disk (``core_calls.jsonl``) each request is stored content-addressed: every distinct message, tool list and
parameter set is written once as a ``blob`` row, and each attempt is a ``call`` row naming the blobs it sent.
A 300-turn run therefore costs roughly its new messages, not 300 copies of the history, and ``requests()``
rebuilds every request byte-for-byte (``tests/test_core_calls.py`` checks it against what the client received).

Unknown is never written as zero: usage fields the provider did not report are absent from that call's
``usage`` and listed under ``usage_missing``; an attempt that failed has unknown usage.
"""
from __future__ import annotations

import hashlib
import json
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
        self.seq = 0
        self.by_role: dict[str, dict[str, int]] = {}
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, role: str, attempt: int, request: dict[str, Any], outcome: dict[str, Any]) -> None:
        """One attempt. ``request`` is exactly what was passed to the client; ``outcome`` has ``ok`` and, when
        known, ``usage`` (fields actually reported), ``response_id``, ``response_model``, ``finish_reason``, or
        ``error``/``status``."""
        self.seq += 1
        usage = outcome.get("usage") or {}
        missing = [f for f in USAGE_FIELDS if f not in usage]
        totals = self.by_role.setdefault(role, {"attempts": 0, "failed": 0, "usage_unknown": 0,
                                                **{f: 0 for f in USAGE_FIELDS}})
        totals["attempts"] += 1
        totals["failed"] += not outcome.get("ok")
        totals["usage_unknown"] += bool(missing)
        for f in USAGE_FIELDS:
            totals[f] += int(usage.get(f, 0))
        if self._path is None:
            return
        rows: list[dict[str, Any]] = []
        refs: dict[str, Any] = {}
        for name, value in request.items():
            if name == "messages":
                refs[name] = [self._blob(m, rows) for m in value]
            elif name in ("tools", "params"):
                refs[name] = self._blob(value, rows)
            else:
                refs[name] = value
        rows.append({"kind": "call", "seq": self.seq, "role": role, "attempt": attempt, "request": refs,
                     "usage_missing": missing, **outcome})
        with self._path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(_canonical(row) + "\n")

    def _blob(self, value: Any, rows: list[dict[str, Any]]) -> str:
        text = _canonical(value)
        key = _key(text)
        if key not in self._seen:
            self._seen.add(key)
            rows.append({"kind": "blob", "key": key, "value": json.loads(text)})
        return key

    def totals(self) -> dict[str, Any]:
        """Per-role counts plus an ``all`` row. A token total is a lower bound when ``usage_unknown`` > 0."""
        out: dict[str, Any] = {role: dict(t) for role, t in self.by_role.items()}
        out["all"] = {k: sum(t[k] for t in self.by_role.values())
                      for k in ("attempts", "failed", "usage_unknown", *USAGE_FIELDS)}
        return out


def requests(path: Path) -> Iterator[dict[str, Any]]:
    """Rebuild every logged call with its full request (``request`` holds the exact client arguments)."""
    blobs: dict[str, Any] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row["kind"] == "blob":
                blobs[row["key"]] = row["value"]
                continue
            refs = dict(row["request"])
            if "messages" in refs:
                refs["messages"] = [blobs[k] for k in refs["messages"]]
            for name in ("tools", "params"):
                if name in refs:
                    refs[name] = blobs[refs[name]]
            params = refs.pop("params", {}) or {}
            yield {**row, "request": {**refs, **params}}
