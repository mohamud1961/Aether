#!/usr/bin/env python3
"""Persist a raw RAW_LEDGER_UPDATE/LEDGER_UPDATE block to the shared ledger inbox."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FIELDS = [
    "actor",
    "task",
    "event_type",
    "summary",
    "observations",
    "inference",
    "evidence_paths",
    "affected_components",
    "decision_change",
    "unresolved_questions",
    "confidence",
    "commit_message",
]

VALID_MARKERS = ("RAW_LEDGER_UPDATE", "LEDGER_UPDATE")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a raw RAW_LEDGER_UPDATE handoff file to tracking/ledger/inbox/."
    )
    parser.add_argument(
        "--source",
        default="agent_session",
        help="Short label for the update source. Default: agent_session",
    )
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Working directory to record in the handoff metadata. Default: current cwd",
    )
    return parser.parse_args()


def sanitize_slug(value: str, default: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or default


def extract_update_block(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    start_idx: int | None = None
    marker: str | None = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped in VALID_MARKERS:
            start_idx = idx
            marker = stripped
            break

    if start_idx is None or marker is None:
        raise ValueError(
            "Input does not contain a RAW_LEDGER_UPDATE or LEDGER_UPDATE block."
        )

    block = "\n".join(lines[start_idx:]).strip()
    if not block.startswith(marker):
        raise ValueError("Malformed raw ledger handoff block.")
    return block, marker


def parse_fields(block: str) -> dict[str, str]:
    lines = block.splitlines()
    if not lines or lines[0].strip() not in VALID_MARKERS:
        raise ValueError(
            "First non-empty line must be RAW_LEDGER_UPDATE or LEDGER_UPDATE."
        )

    fields: dict[str, list[str]] = {}
    current_key: str | None = None

    for line in lines[1:]:
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            key = key.strip()
            value = value.lstrip()
            current_key = key
            fields.setdefault(key, []).append(value)
        elif current_key is not None:
            fields[current_key].append(line)

    missing = [key for key in REQUIRED_FIELDS if key not in fields]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    return {key: "\n".join(value).strip() for key, value in fields.items()}


def build_output_path(repo_root: Path, actor: str, task: str, block: str) -> Path:
    now = datetime.now(timezone.utc)
    day_dir = repo_root / "tracking" / "ledger" / "inbox" / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(block.encode("utf-8")).hexdigest()[:10]
    actor_slug = sanitize_slug(actor, "unknown-actor")
    task_slug = sanitize_slug(task, "unknown-task")
    filename = f"{now.strftime('%H%M%S')}_{actor_slug}_{task_slug}_{digest}.md"
    return day_dir / filename


def render_file(
    block: str,
    marker: str,
    fields: dict[str, str],
    source: str,
    cwd: str,
    out_path: Path,
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
    return "\n".join(
        [
            "# Raw Ledger Update",
            "",
            f"- recorded_at_utc: {now}",
            f"- source: {source}",
            f"- cwd: {cwd}",
            f"- actor: {fields['actor']}",
            f"- task: {fields['task']}",
            f"- event_type: {fields['event_type']}",
            f"- raw_block_type: {marker}",
            f"- sha256: {digest}",
            f"- commit_message: {fields['commit_message']}",
            f"- handoff_file: {out_path.as_posix()}",
            "",
            "```text",
            block,
            "```",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    raw = sys.stdin.read()
    if not raw.strip():
        print("No input received on stdin.", file=sys.stderr)
        return 1

    try:
        block, marker = extract_update_block(raw)
        fields = parse_fields(block)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[3]
    out_path = build_output_path(repo_root, fields["actor"], fields["task"], block)
    rendered = render_file(block, marker, fields, args.source, args.cwd, out_path)
    out_path.write_text(rendered, encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
