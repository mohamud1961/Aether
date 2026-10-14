"""Strict JSONL persistence helpers for trial rows and traces."""

from pathlib import Path
from typing import Any
import json
import os


class TrialFileError(ValueError):
    """Malformed trial persistence."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse complete lines. An unterminated last line was never fully written and is ignored."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").split("\n")
    lines.pop()  # "" when the file ends with a newline, otherwise an unterminated tail
    records: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise TrialFileError(f"{path}:{number}: not valid JSON ({exc})") from exc
        if not isinstance(record, dict):
            raise TrialFileError(f"{path}:{number}: record is not a JSON object")
        records.append(record)
    return records


def _append_line(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _trim_partial_tail(path: Path) -> None:
    if not path.exists():
        return
    data = path.read_bytes()
    if not data or data.endswith(b"\n"):
        return
    path.write_bytes(data[: data.rfind(b"\n") + 1])
