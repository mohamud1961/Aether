"""Generic durable phase journaling and run-status classification helpers."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PHASE_INITIALIZED = "initialized"
PHASE_AGENT_RUN_STARTED = "agent_run_started"
PHASE_AGENT_RUN_COMPLETED = "agent_run_completed"
PHASE_GRADER_RUN_STARTED = "grader_run_started"
PHASE_GRADER_RUN_COMPLETED = "grader_run_completed"

PHASE_SEQUENCE = (
    PHASE_INITIALIZED,
    PHASE_AGENT_RUN_STARTED,
    PHASE_AGENT_RUN_COMPLETED,
    PHASE_GRADER_RUN_STARTED,
    PHASE_GRADER_RUN_COMPLETED,
)
PHASE_INDEX = {phase: index for index, phase in enumerate(PHASE_SEQUENCE)}

FINAL_ROW_STATUSES = (
    "invalid_launch",
    "invalid_environment",
    "invalid_provider",
    "invalid_resource_killed",
    "invalid_grader",
    "pass",
    "fail",
)
SCORABLE_ROW_STATUSES = ("pass", "fail")


@dataclass(frozen=True)
class RunClassificationContext:
    stage: str
    error: BaseException | None = None
    exit_code: int | None = None
    status_code: int | None = None
    error_kind: str | None = None
    error_message: str | None = None
    stderr: str | None = None
    blocked_reason: str | None = None
    timed_out: bool = False
    killed: bool = False


@dataclass
class RunJournal:
    path: Path
    metadata: dict[str, Any] = field(default_factory=dict)

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        payload = dict(self.metadata)
        payload.update(record)
        append_jsonl_row(self.path, payload)
        return payload

    def last_row(self) -> dict[str, Any] | None:
        return last_jsonl_row(self.path)

    def rows(self) -> list[dict[str, Any]]:
        return read_jsonl_rows(self.path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_jsonl_row(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def last_jsonl_row(path: Path) -> dict[str, Any] | None:
    rows = read_jsonl_rows(path)
    return rows[-1] if rows else None


def build_phase_row(
    phase: str,
    *,
    phase_result: str | None = None,
    attempt: Any = None,
    attempt_label: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if phase not in PHASE_INDEX:
        raise ValueError(f"unknown phase: {phase!r}")
    row: dict[str, Any] = {
        "row_kind": "phase",
        "phase": phase,
        "phase_index": PHASE_INDEX[phase],
        "phase_result": phase_result or ("started" if phase.endswith("_started") else "completed"),
        "recorded_at": utc_now(),
    }
    if attempt is not None:
        row["attempt"] = attempt
    if attempt_label:
        row["attempt_label"] = attempt_label
    if details:
        row.update(details)
    return row


def build_result_row(
    *,
    row_status: str,
    classification_stage: str,
    attempt: Any = None,
    attempt_label: str | None = None,
    scoreable: bool | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if row_status not in FINAL_ROW_STATUSES:
        raise ValueError(f"unknown row_status: {row_status!r}")
    row: dict[str, Any] = {
        "row_kind": "result",
        "row_status": row_status,
        "classification_stage": classification_stage,
        "scoreable": is_scoreable_row_status(row_status) if scoreable is None else bool(scoreable),
        "recorded_at": utc_now(),
    }
    if attempt is not None:
        row["attempt"] = attempt
    if attempt_label:
        row["attempt_label"] = attempt_label
    if details:
        row.update(details)
    return row


def classify_run_status(context: RunClassificationContext) -> str:
    details = _error_details(context.error)
    status_code = context.status_code
    if status_code is None:
        status_code = _coerce_int(details.get("status_code"))
    error_kind = (context.error_kind or str(details.get("error_kind") or "")).strip().lower()
    message = _context_message(context=context, details=details)

    if context.stage == "grader":
        if context.exit_code in {0, 1} and _has_test_summary(message):
            return "pass" if context.exit_code == 0 else "fail"
        if _is_resource_killed(context=context, message=message):
            return "invalid_resource_killed"
        if _is_provider_error(status_code=status_code, message=message, error_kind=error_kind):
            return "invalid_provider"
        if _is_missing_grader_toolchain(context=context, message=message):
            return "invalid_grader"
        if context.exit_code == 0:
            return "pass"
        if context.exit_code is not None:
            return "fail"
        if _is_launch_error(message=message, error_kind=error_kind):
            return "invalid_launch"
        if _is_environment_error(message=message, error_kind=error_kind):
            return "invalid_environment"
        return "invalid_grader"

    if context.stage == "agent":
        if _is_provider_error(status_code=status_code, message=message, error_kind=error_kind):
            return "invalid_provider"
        if _is_resource_killed(context=context, message=message):
            return "invalid_resource_killed"
        if _is_launch_error(message=message, error_kind=error_kind):
            return "invalid_launch"
        if _is_environment_error(message=message, error_kind=error_kind):
            return "invalid_environment"
        return "invalid_environment"

    if context.stage == "launch":
        if _is_provider_error(status_code=status_code, message=message, error_kind=error_kind):
            return "invalid_provider"
        if _is_resource_killed(context=context, message=message):
            return "invalid_resource_killed"
        if _is_launch_error(message=message, error_kind=error_kind):
            return "invalid_launch"
        if _is_environment_error(message=message, error_kind=error_kind):
            return "invalid_environment"
        return "invalid_launch"

    if context.stage == "blocked":
        if _is_launch_error(message=message, error_kind=error_kind):
            return "invalid_launch"
        return "invalid_environment"

    if context.exit_code == 0:
        return "pass"
    if context.exit_code is not None:
        return "fail"
    return "invalid_environment"


def summarize_result_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {status: 0 for status in FINAL_ROW_STATUSES}
    by_attempt: dict[str, dict[str, int]] = {}
    total_rows = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("row_kind") not in {None, "result"}:
            continue
        status = str(row.get("row_status") or "").strip()
        if status not in FINAL_ROW_STATUSES:
            continue
        total_rows += 1
        status_counts[status] += 1
        attempt_bucket = _attempt_bucket_name(row)
        bucket = by_attempt.setdefault(attempt_bucket, _empty_status_counts())
        bucket[status] += 1
        bucket["total"] += 1

    scorable_rows = status_counts["pass"] + status_counts["fail"]
    score = (status_counts["pass"] / scorable_rows) if scorable_rows else None
    summary = {
        "total_rows": total_rows,
        "status_counts": status_counts,
        "scorable_rows": scorable_rows,
        "score_numerator": status_counts["pass"],
        "score_denominator": scorable_rows,
        "score": score,
        "by_attempt": by_attempt,
    }
    return summary


def is_scoreable_row_status(row_status: str) -> bool:
    return row_status in SCORABLE_ROW_STATUSES


def _empty_status_counts() -> dict[str, int]:
    payload = {status: 0 for status in FINAL_ROW_STATUSES}
    payload["total"] = 0
    return payload


def _attempt_bucket_name(row: dict[str, Any]) -> str:
    attempt_label = row.get("attempt_label")
    if isinstance(attempt_label, str) and attempt_label.strip():
        return attempt_label.strip()
    attempt = row.get("attempt")
    if isinstance(attempt, str) and attempt.strip():
        return attempt.strip()
    if isinstance(attempt, int) and not isinstance(attempt, bool):
        return f"Attempt {attempt}"
    return "unknown"


def _error_details(error: BaseException | None) -> dict[str, Any]:
    if error is None:
        return {}
    details = getattr(error, "details", None)
    if isinstance(details, dict):
        return dict(details)
    payload: dict[str, Any] = {}
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        payload["status_code"] = status_code
    error_kind = getattr(error, "error_kind", None)
    if isinstance(error_kind, str) and error_kind:
        payload["error_kind"] = error_kind
    response_body = getattr(error, "response_body", None)
    if isinstance(response_body, str) and response_body:
        payload["response_body"] = response_body
    return payload


def _context_message(*, context: RunClassificationContext, details: dict[str, Any]) -> str:
    parts: list[str] = []
    if context.error is not None:
        error_text = str(context.error).strip()
        if error_text:
            parts.append(error_text)
    if context.error_message:
        parts.append(context.error_message)
    if context.stderr:
        parts.append(context.stderr)
    if context.blocked_reason:
        parts.append(context.blocked_reason)
    for key in ("message", "response_body", "error_kind"):
        value = details.get(key)
        if isinstance(value, str) and value:
            parts.append(value)
    return "\n".join(parts).lower()


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _is_provider_error(*, status_code: int | None, message: str, error_kind: str) -> bool:
    if status_code is not None and 400 <= status_code < 500:
        return True
    if error_kind in {"provider_bad_request", "bad_request", "invalid_request"}:
        return True
    return any(
        needle in message
        for needle in (
            "bad request",
            "invalid request",
            "http 400",
            "status 400",
            "response status: 400",
        )
    )


_TEST_SUMMARY_PATTERN = re.compile(
    r"\b\d+\s+(?:passed|failed|error|errors)\b"
)


def _has_test_summary(message: str) -> bool:
    """True when the message contains a real test-runner summary line such as
    "1 failed in 7.12s" or "1 failed, 2 passed". A clean exit code (0 or 1)
    accompanied by such a summary is authoritative: pass/fail, never invalid.
    """

    return bool(_TEST_SUMMARY_PATTERN.search(message))


def _is_resource_killed(*, context: RunClassificationContext, message: str) -> bool:
    if context.timed_out or context.killed:
        return True
    if context.exit_code in {137, 143, -9, -15}:
        return True
    return any(
        needle in message
        for needle in (
            "timed out",
            "timeout",
            "killed",
            "terminated",
            "signal 9",
            "signal 15",
            "exit status 137",
            "exit code 137",
        )
    )


def _is_missing_grader_toolchain(*, context: RunClassificationContext, message: str) -> bool:
    if context.exit_code == 127:
        return True
    return any(
        needle in message
        for needle in (
            "command not found",
            "not found",
            "no such file or directory",
            "missing grader",
            "grader toolchain",
            "exit code 127",
        )
    )


def _is_launch_error(*, message: str, error_kind: str) -> bool:
    if error_kind in {"launch_error", "import_error", "bootstrap_error"}:
        return True
    return any(
        needle in message
        for needle in (
            "modulenotfounderror",
            "no module named",
            "importerror",
            "cannot open file",
            "bootstrap",
            "sys.path",
        )
    )


def _is_environment_error(*, message: str, error_kind: str) -> bool:
    if error_kind in {"environment_error", "runtime_unavailable", "sandbox_unavailable"}:
        return True
    return any(
        needle in message
        for needle in (
            "docker",
            "container",
            "sandbox",
            "runtime unavailable",
            "permission denied",
            "resource temporarily unavailable",
            "eagain",
            "file exists",
        )
    )
