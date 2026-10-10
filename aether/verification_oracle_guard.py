"""Factual observation: a passing verification was edited after it reported failure.

Mechanical attribution only.  Changed paths come from receipts that already
carry them: ``write_file`` receipts name their path, and ``run_command``
receipts carry the executor's before/after workspace-snapshot diff.  A shell
edit (``sed -i``, heredoc, ``python - <<EOF``) is therefore attributable only
when that snapshot diff reports ``complete`` detection.  Any receipt in the
window whose effect on the workspace cannot be established this way makes the
observation unavailable; the guard never guesses.
"""
from __future__ import annotations

import posixpath
import re
import shlex
from typing import Any, Mapping, Sequence

from .kernel_dispatch import has_failure_signature, is_verification_command

_VERIFICATION_NAME_RE = re.compile(
    r"(?ix)^(?:test_.*|.*_test\..*|(?:verify|validate|check)(?:[_.-].*)?|"
    r".*[_.-](?:verify|validate|check|test|tests)\.[A-Za-z0-9]+)$"
)
_VERIFICATION_DIRS = frozenset({"test", "tests"})
_FILE_TOKEN_RE = re.compile(r"^[^\s=<>|&;]+\.[A-Za-z0-9]{1,5}$")

_MASKED_VERIFICATION_FAILURE_RE = re.compile(
    r"(?im)(?:^FAIL[ \t]+\S|^[ \t]*[1-9][0-9]*[ \t]+FAILURES?\b)"
)


def _payload(receipt: Any) -> Mapping[str, Any]:
    value = getattr(receipt, "payload", None)
    return value if isinstance(value, Mapping) else {}


def _norm(path: str) -> str:
    return posixpath.normpath(str(path).strip()).lstrip("/")


def command_file_basenames(command: str) -> frozenset[str]:
    """Basenames of file-like arguments in a shell command (best effort, lexical)."""
    try:
        tokens = shlex.split(str(command or ""), posix=True)
    except ValueError:
        tokens = str(command or "").split()
    return frozenset(
        posixpath.basename(token) for token in tokens
        if _FILE_TOKEN_RE.match(token) and not token.startswith("-")
    )


def is_verification_path(path: str) -> bool:
    parts = _norm(path).split("/")
    return bool(
        _VERIFICATION_NAME_RE.match(parts[-1])
        or any(part.lower() in _VERIFICATION_DIRS for part in parts[:-1])
    )


def reported_failure(receipt: Any) -> bool:
    """Nonzero exit, unsuccessful receipt, or a strong failure marker in output."""
    payload = _payload(receipt)
    if getattr(receipt, "success", True) is not True:
        return True
    code = payload.get("exit_code")
    if isinstance(code, int) and not isinstance(code, bool) and code != 0:
        return True
    output = f"{payload.get('stdout_full') or payload.get('stdout') or ''}\n" \
             f"{payload.get('stderr_full') or payload.get('stderr') or ''}"
    if has_failure_signature(output):
        return True
    # A shell pipeline may mask the verifier's real exit status. The executor
    # already records that exact mechanical integrity risk. Only under that
    # flag, accept conservative verifier-style failure lines broader than the
    # global strong-failure regex.
    if (
        str(payload.get("verification_integrity_risk") or "")
        == "verification_exit_status_masked_by_pipeline"
    ):
        return bool(_MASKED_VERIFICATION_FAILURE_RE.search(output))
    return False


def _is_verification_run(
    receipt: Any, *, extra_oracle_names: frozenset[str] = frozenset(),
) -> bool:
    if getattr(receipt, "kind", "") != "run_command":
        return False
    command = str(_payload(receipt).get("command") or "")
    return bool(
        is_verification_command(command)
        or (command_file_basenames(command) & extra_oracle_names)
    )


def _newly_solver_created_command_names(
    receipts: Sequence[Any], passing: Any,
) -> frozenset[str]:
    """Return passing-command file names that the Solver demonstrably created.

    A write_file receipt omits before_bytes/before_content_hash only when the
    Executor existence probe found no prior file.  Shell actions may instead
    expose exact created_paths through a complete workspace delta.  This is a
    custody fact, not a filename heuristic.
    """
    command_names = command_file_basenames(
        str(_payload(passing).get("command") or "")
    )
    if not command_names:
        return frozenset()
    created: set[str] = set()
    for receipt in receipts:
        if receipt is passing or getattr(receipt, "receipt_id", None) == getattr(
            passing, "receipt_id", object()
        ):
            break
        payload = _payload(receipt)
        if getattr(receipt, "kind", "") == "write_file":
            path = str(payload.get("path") or "").strip()
            if (
                path
                and "before_bytes" not in payload
                and "before_content_hash" not in payload
            ):
                created.add(posixpath.basename(_norm(path)))
        delta = payload.get("state_delta")
        if isinstance(delta, Mapping):
            status = str(
                delta.get("workspace_mutation_detection_status")
                or delta.get("mutation_detection_status")
                or ""
            )
            if status == "complete":
                created.update(
                    posixpath.basename(_norm(str(path)))
                    for path in (delta.get("created_paths") or ())
                    if str(path).strip()
                )
    return frozenset(command_names & created)


def _same_oracle(failed: Any, passing: Any) -> bool:
    a = str(_payload(failed).get("command") or "")
    b = str(_payload(passing).get("command") or "")
    if " ".join(a.split()) == " ".join(b.split()):
        return True
    return bool(command_file_basenames(a) & command_file_basenames(b))


def _changed_paths(receipt: Any) -> set[str] | None:
    """Paths this receipt changed, or ``None`` when its workspace effect is unknown."""
    payload = _payload(receipt)
    paths: set[str] = set()
    for key in ("modified_paths", "artifact_paths", "removed_paths"):
        paths.update(_norm(p) for p in (payload.get(key) or ()))
    delta = payload.get("state_delta")
    if isinstance(delta, Mapping):
        status = str(
            delta.get("workspace_mutation_detection_status")
            or delta.get("mutation_detection_status") or ""
        )
        if status != "complete":
            return None
        for key in ("content_changed_paths", "metadata_changed_paths",
                    "created_paths", "removed_paths"):
            paths.update(_norm(p) for p in (delta.get(key) or ()))
        return paths
    kind = getattr(receipt, "kind", "")
    if kind == "run_command":
        return None
    if kind == "write_file":
        if payload.get("path"):
            paths.add(_norm(str(payload["path"])))
        return paths or None
    if getattr(receipt, "state_change", False) and not paths:
        return None
    return paths


def oracle_edit_observation(
    receipts: Sequence[Any], passing: Any,
) -> dict[str, Any] | None:
    """Describe an edit-after-failure of the check that now passes, or ``None``.

    ``None`` also means "not attributable"; callers must not infer the opposite.
    """
    ordered = list(receipts)
    try:
        end = next(i for i, r in enumerate(ordered) if r is passing or
                   getattr(r, "receipt_id", None) == getattr(passing, "receipt_id", object()))
    except StopIteration:
        return None
    extra_oracle_names = _newly_solver_created_command_names(
        ordered[: end + 1], passing
    )
    if not _is_verification_run(
        passing, extra_oracle_names=extra_oracle_names
    ):
        return None

    failed: list[Any] = []
    start = -1
    for pos in range(end - 1, -1, -1):
        r = ordered[pos]
        if (
            not _is_verification_run(r, extra_oracle_names=extra_oracle_names)
            or not _same_oracle(r, passing)
        ):
            continue
        if not reported_failure(r):
            touched = _changed_paths(r)
            if touched is None or touched:
                # A command that also changed files is not a clean earlier pass;
                # its changes are accounted for in the window below.
                continue
            break
        failed.append(r)
        start = pos
    if not failed:
        return None

    changed: set[str] = set()
    for r in ordered[start + 1:end + 1]:
        part = _changed_paths(r)
        if part is None:
            return None
        changed |= part
    if not changed:
        return None
    oracle_names: set[str] = set(extra_oracle_names)
    for r in (passing, *failed):
        oracle_names |= {
            name for name in command_file_basenames(str(_payload(r).get("command") or ""))
            if is_verification_command(name)
        }
    verification = sorted(
        p for p in changed
        if posixpath.basename(p) in oracle_names or is_verification_path(p)
    )
    other = sorted(changed - set(verification))
    if other or not verification:
        return None
    failed_ids = [str(r.receipt_id) for r in reversed(failed)]
    return {
        "edited_after_reported_failure": True,
        "failed_receipt_ids": failed_ids,
        "verification_files_changed": verification,
        "other_files_changed": [],
        "observation": (
            "The passing verification command had reported failure earlier "
            f"(receipt {', '.join(failed_ids)}). Since that failure, the only workspace "
            f"files changed were verification files ({', '.join(verification)}); no other "
            "file changed. This is a mechanical observation of file changes, not a "
            "judgment about the task."
        ),
    }


__all__ = ["command_file_basenames", "is_verification_path", "oracle_edit_observation",
           "reported_failure"]
