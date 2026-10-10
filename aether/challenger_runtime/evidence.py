"""Aether-side mechanical facts: scratch paths, solver evidence views, check status."""
from __future__ import annotations

import posixpath
import re
from typing import Any, Iterable, Mapping

from ..ledger import ExecutionLedger, Receipt

NO_EVIDENCE_REF = "none"
NO_EVIDENCE_VIEW = "(the solver cited no usable evidence for this criterion)"
EVIDENCE_KINDS = frozenset({
    "run_command", "read_file", "read_file_page", "write_file", "inspect_artifact",
    "artifact_inspection", "inspect_diff", "read_output", "grep_output",
})
MAX_VIEW_CHARS = 600
MAX_LISTED_EVIDENCE = 15

_SCRATCH_DIRS = frozenset({"tmp", "scratch", ".scratch", "__pycache__", ".pytest_cache", "node_modules"})
_SCRATCH_NAME = re.compile(
    r"^(scratch|tmp|temp|debug|repro|reproduce|try|check|verify|test)([_\-.]|$)"
    r"|(_test|_scratch|_debug)\.[a-z0-9]+$",
    re.IGNORECASE,
)
_HARMLESS_REDIRECT = re.compile(r"\d*>\s*/dev/null|&>\s*/dev/null|\d*>&\d+")
_MUTATING = re.compile(
    r">|\btee\b|\brm\s|\bmv\s|\bcp\s|\bchmod\b|\bchown\b|\btruncate\b|\bdd\s"
    r"|\bsed\s+(-[a-z]*i|--in-place)"
    r"|\bgit\s+(checkout|reset|apply|commit|stash|clean|restore|rm|mv|merge|rebase)\b"
    r"|\b(pip3?|apt(-get)?|npm|yarn|cargo|gem)\s+(install|add|remove|uninstall)\b",
)


def is_scratch_path(path: str, workspace_root: str) -> bool:
    """Conservative: only clearly throwaway, test, or out-of-workspace files are scratch."""
    raw = str(path).strip()
    if raw.startswith("/") and workspace_root:
        root = workspace_root.rstrip("/") + "/"
        if not (raw + "/").startswith(root):
            return True
    parts = [part for part in posixpath.normpath(raw).split("/") if part]
    if any(part.lower() in _SCRATCH_DIRS for part in parts[:-1]):
        return True
    return bool(parts) and bool(_SCRATCH_NAME.search(parts[-1]))


def looks_mutating(command: str) -> bool:
    """True when a diagnostic command plainly writes; such a check is not run."""
    return bool(_MUTATING.search(_HARMLESS_REDIRECT.sub(" ", command)))


def _view(receipt: Receipt) -> str:
    payload: Mapping[str, Any] = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    body = ""
    for key in ("stdout", "content", "excerpt", "text"):
        if payload.get(key):
            body = str(payload[key])
            break
    err = str(payload.get("stderr") or "")
    text = f"{receipt.kind}: {receipt.summary}"
    if body:
        text += f"\n{body}"
    if err:
        text += f"\nstderr: {err}"
    return text[:MAX_VIEW_CHARS * 4]


def evidence_receipts(ledger: ExecutionLedger) -> list[Receipt]:
    return [r for r in ledger.all_receipts() if r.kind in EVIDENCE_KINDS]


def evidence_listing(ledger: ExecutionLedger) -> list[str]:
    """Recent solver-visible evidence refs, one line each, for the card prompt."""
    return [
        f"{r.receipt_id} | {r.summary[:160]}"
        for r in evidence_receipts(ledger)[-MAX_LISTED_EVIDENCE:]
    ]


def evidence_views(ledger: ExecutionLedger, refs: Iterable[str]) -> dict[str, str]:
    """Views for the refs that exist in the ledger, plus the explicit no-evidence marker."""
    by_id = {r.receipt_id: r for r in evidence_receipts(ledger)}
    views = {NO_EVIDENCE_REF: NO_EVIDENCE_VIEW}
    for ref in refs:
        if ref in by_id:
            views[ref] = _view(by_id[ref])
    return views


def command_run_status(ledger: ExecutionLedger, command: str) -> str:
    """Aether-owned record of whether an exact command ran, and with what exit code."""
    wanted = command.strip()
    runs = [
        r for r in ledger.all_receipts()
        if r.kind == "run_command" and str((r.payload or {}).get("command", "")).strip() == wanted
    ]
    if not runs:
        return "Aether record: this exact command has not been run."
    last = runs[-1]
    return f"Aether record: last run exit_code={last.payload.get('exit_code')} (evidence {last.receipt_id})."
