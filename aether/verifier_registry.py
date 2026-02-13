from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Any

from .event_log import EventLog
from .hashing import hash_canonical_json
from .tool_gateway import ToolGateway, ToolResult
from .verifier_plan import VerifierDefinition, VerifierPlan


@dataclass(frozen=True)
class VerifierrunResult:
    name: str
    exit_code: Optional[int]
    stdout_ref: str
    stderr_ref: str
    truncation: Dict[str, Dict[str, Any]]
    result: str
    event_id: str
    verifier_diagnostics: Dict[str, Any] = field(default_factory=dict)


_VERIFIER_DIAGNOSTICS_SCHEMA = "verifier_diagnostics.v1"
_MAX_FAILED_TESTS = 8
_MAX_EXCERPT_CHARS = 240


class VerifierRegistry:
    def __init__(self, verifiers: Sequence[VerifierDefinition], event_log: EventLog) -> None:
        self._verifiers = list(verifiers)
        self.event_log = event_log

    def select_plan(
        self,
        *,
        task_spec: Dict[str, str],
        step_id: Optional[int] = None,
        timestamp: str,
        cwd: str,
    ) -> VerifierPlan:
        if not self._verifiers:
            return VerifierPlan(verifiers=[])

        verifiers = sorted(self._verifiers, key=lambda v: v.name)
        plan = VerifierPlan(verifiers=verifiers)

        self.event_log.append_event(
            {
                "event_type": "verifier_plan",
                "step_id": step_id,
                "timestamp": timestamp,
                "cwd": cwd,
                "verifier_plan": [v.name for v in verifiers],
                "task_spec": task_spec,
            }
        )
        return plan

    def run_plan(
        self,
        *,
        plan: VerifierPlan,
        tool_gateway: ToolGateway,
        timestamp: str,
        cwd: Path,
        workspace_fingerprint_hash: Optional[str] = None,
    ) -> List[VerifierrunResult]:
        results: List[VerifierrunResult] = []
        stage_a_results: List[Dict[str, Any]] = []

        for verifier in plan.verifiers:
            params_hash = hash_canonical_json(
                {
                    "command": verifier.command,
                    "timeout_ms": verifier.timeout_ms,
                }
            )
            stage_a_ok, stage_a_reason = _stage_a_precheck(verifier)
            stage_a_pass = stage_a_ok
            stage_a_result = "pass" if stage_a_ok else "fail"
            self.event_log.append_event(
                {
                    "event_type": "VERIFIER_run",
                    "timestamp": timestamp,
                    "cwd": cwd.as_posix(),
                    "verifier_id": verifier.name,
                    "params_hash": params_hash,
                    "verifier_stage": "A",
                }
            )
            self.event_log.append_event(
                {
                    "event_type": "verifier_result",
                    "timestamp": timestamp,
                    "cwd": cwd.as_posix(),
                    "verifier_id": verifier.name,
                    "params_hash": params_hash,
                    "verifier_stage": "A",
                    "pass": stage_a_pass,
                    "verifier_run": True,
                    "verifier_result": stage_a_result,
                    "workspace_fingerprint_hash": workspace_fingerprint_hash,
                    "precheck_reason": stage_a_reason,
                    "artifact_refs": [],
                    "verifier_diagnostics": _diagnostics_unavailable(
                        reason_code=f"stage_a_precheck:{stage_a_reason}"
                    ),
                }
            )
            stage_a_results.append({"verifier": verifier.name, "pass": stage_a_pass, "reason": stage_a_reason})
            if not stage_a_ok:
                results.append(
                    VerifierrunResult(
                        name=verifier.name,
                        exit_code=None,
                        stdout_ref="",
                        stderr_ref="",
                        truncation={"stdout": {"unknown": True}, "stderr": {"unknown": True}},
                        result="fail",
                        event_id="",
                        verifier_diagnostics=_diagnostics_unavailable(
                            reason_code=f"stage_a_precheck:{stage_a_reason}"
                        ),
                    )
                )
                continue

            self.event_log.append_event(
                {
                    "event_type": "VERIFIER_run",
                    "timestamp": timestamp,
                    "cwd": cwd.as_posix(),
                    "verifier_id": verifier.name,
                    "params_hash": params_hash,
                    "verifier_stage": "B",
                }
            )
            tool_result = tool_gateway.execute(
                tool_name=verifier.name,
                tool_args={"command": verifier.command},
                timestamp=timestamp,
                cwd=cwd,
                timeout_ms=verifier.timeout_ms,
                plan_id="verifier_plan",
                plan_version_id=1,
                plan_step_id=verifier.name,
            )
            result = _derive_verifier_result(tool_result)
            diagnostics = _derive_verifier_diagnostics(
                tool_result=tool_result,
                verifier_result=result,
                artifact_store=getattr(tool_gateway, "artifact_store", None),
            )
            results.append(
                VerifierrunResult(
                    name=verifier.name,
                    exit_code=tool_result.exit_code,
                    stdout_ref=tool_result.stdout_ref,
                    stderr_ref=tool_result.stderr_ref,
                    truncation=tool_result.truncation,
                    result=result,
                    event_id=tool_result.event["event_id"],
                    verifier_diagnostics=diagnostics,
                )
            )

            self.event_log.append_event(
                {
                    "event_type": "verifier_result",
                    "timestamp": timestamp,
                    "cwd": cwd.as_posix(),
                    "verifier_id": verifier.name,
                    "params_hash": params_hash,
                    "verifier_stage": "B",
                    "pass": result == "pass",
                    "tool_name": verifier.name,
                    "tool_args": {"command": verifier.command},
                    "exit_code": tool_result.exit_code,
                    "artifact_refs": [tool_result.stdout_ref, tool_result.stderr_ref],
                    "verifier_run": True,
                    "verifier_result": result,
                    "workspace_fingerprint_hash": workspace_fingerprint_hash,
                    "verifier_diagnostics": diagnostics,
                }
            )

        stage_c_status = _aggregate_stage_c_status(results)
        self.event_log.append_event(
            {
                "event_type": "verifier_result",
                "timestamp": timestamp,
                "cwd": cwd.as_posix(),
                "verifier_id": "__stage_c__",
                "verifier_stage": "C",
                "pass": stage_c_status == "pass",
                "verifier_run": True,
                "verifier_result": stage_c_status,
                "workspace_fingerprint_hash": workspace_fingerprint_hash,
                "artifact_refs": _collect_stage_c_artifact_refs(results),
                "stage_a_results": stage_a_results,
                "verifier_diagnostics": _aggregate_stage_c_diagnostics(results),
            }
        )

        return results


def _derive_verifier_result(tool_result: ToolResult) -> str:
    stdout_unknown = tool_result.truncation.get("stdout", {}).get("unknown")
    stderr_unknown = tool_result.truncation.get("stderr", {}).get("unknown")
    if stdout_unknown or stderr_unknown:
        return "unknown"
    if isinstance(tool_result.exit_code, str) and tool_result.exit_code.upper() == "TIMEOUT":
        return "unknown"
    if tool_result.exit_code is None:
        return "unknown"
    return "pass" if tool_result.exit_code == 0 else "fail"


def _derive_verifier_diagnostics(
    *,
    tool_result: ToolResult,
    verifier_result: str,
    artifact_store: Any,
) -> Dict[str, Any]:
    if verifier_result == "pass":
        return _diagnostics_available(source="none", failed_tests=[], reason_code="verifier_pass")

    stdout_meta = tool_result.truncation.get("stdout")
    stderr_meta = tool_result.truncation.get("stderr")
    if not isinstance(stdout_meta, dict) or not isinstance(stderr_meta, dict):
        return _diagnostics_unavailable(reason_code="missing_truncation_metadata")
    if bool(stdout_meta.get("unknown")) or bool(stderr_meta.get("unknown")):
        return _diagnostics_unavailable(reason_code="truncation_unknown")

    if not isinstance(tool_result.stdout_ref, str) or not tool_result.stdout_ref:
        return _diagnostics_unavailable(reason_code="missing_stdout_ref")
    if not isinstance(tool_result.stderr_ref, str) or not tool_result.stderr_ref:
        return _diagnostics_unavailable(reason_code="missing_stderr_ref")
    if artifact_store is None or not hasattr(artifact_store, "read_bytes"):
        return _diagnostics_unavailable(reason_code="missing_artifact_store")

    try:
        stdout_text = artifact_store.read_bytes(tool_result.stdout_ref).decode("utf-8", errors="replace")
        stderr_text = artifact_store.read_bytes(tool_result.stderr_ref).decode("utf-8", errors="replace")
    except Exception:
        return _diagnostics_unavailable(reason_code="artifact_read_error")

    ctrf_payload = _parse_ctrf_payload(stdout_text, stderr_text)
    if ctrf_payload is not None:
        ctrf_tests = _extract_failed_tests_from_ctrf(ctrf_payload)
        if ctrf_tests:
            return _diagnostics_available(source="ctrf_json", failed_tests=ctrf_tests, reason_code="parsed")
        declared_failed = _extract_declared_ctrf_failed_count(ctrf_payload)
        if declared_failed > 0:
            return _diagnostics_unavailable(reason_code="ctrf_failed_without_tests")

    pytest_tests = _extract_failed_tests_from_pytest_output(stdout_text, stderr_text)
    if pytest_tests:
        return _diagnostics_available(source="pytest_text", failed_tests=pytest_tests, reason_code="parsed")
    return _diagnostics_unavailable(reason_code="no_parseable_failures")


def _diagnostics_available(*, source: str, failed_tests: List[Dict[str, str]], reason_code: str) -> Dict[str, Any]:
    normalized_tests: List[Dict[str, str]] = []
    for test in failed_tests[:_MAX_FAILED_TESTS]:
        name = _normalize_test_name(test.get("name", ""))
        if not name:
            continue
        normalized_tests.append(
            {
                "name": name,
                "message_excerpt": _clean_excerpt(test.get("message_excerpt", "")),
                "assertion_excerpt": _clean_excerpt(test.get("assertion_excerpt", "")),
            }
        )
    return {
        "schema_version": _VERIFIER_DIAGNOSTICS_SCHEMA,
        "availability": "available",
        "reason_code": reason_code,
        "source": source,
        "failed_count": len(normalized_tests),
        "failed_tests": normalized_tests,
    }


def _diagnostics_unavailable(*, reason_code: str) -> Dict[str, Any]:
    return {
        "schema_version": _VERIFIER_DIAGNOSTICS_SCHEMA,
        "availability": "unavailable",
        "reason_code": reason_code,
        "source": "none",
        "failed_count": 0,
        "failed_tests": [],
    }


def _parse_ctrf_payload(stdout_text: str, stderr_text: str) -> Optional[Dict[str, Any]]:
    for text in (stdout_text, stderr_text):
        stripped = text.strip()
        if not stripped:
            continue
        if not (stripped.startswith("{") and stripped.endswith("}")):
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("results"), dict):
            return parsed
    return None


def _extract_declared_ctrf_failed_count(payload: Dict[str, Any]) -> int:
    summary = payload.get("results", {}).get("summary", {})
    failed_value = summary.get("failed")
    if isinstance(failed_value, int) and failed_value >= 0:
        return failed_value
    return 0


def _extract_failed_tests_from_ctrf(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    tests = payload.get("results", {}).get("tests", [])
    if not isinstance(tests, list):
        return []

    failed: List[Dict[str, str]] = []
    for test in tests:
        if not isinstance(test, dict):
            continue
        status = str(test.get("status", "")).lower()
        if status in {"passed", "pass"}:
            continue
        raw_status = str(test.get("raw_status", "")).lower()
        if status not in {"failed", "fail", "error"} and raw_status not in {
            "failed",
            "call_failed",
            "error",
        }:
            continue
        trace = str(test.get("trace", ""))
        failed.append(
            {
                "name": _normalize_test_name(str(test.get("name", ""))),
                "message_excerpt": _clean_excerpt(str(test.get("message", ""))),
                "assertion_excerpt": _extract_assertion_excerpt(trace),
            }
        )

    return [entry for entry in failed if entry.get("name")]


def _extract_failed_tests_from_pytest_output(stdout_text: str, stderr_text: str) -> List[Dict[str, str]]:
    summary_pattern = re.compile(r"^FAILED\s+(\S+)(?:\s+-\s+(.*))?$", re.MULTILINE)
    summaries = summary_pattern.findall(f"{stdout_text}\n{stderr_text}")
    if not summaries:
        return []

    assertion_lines: List[str] = []
    for stream_text in (stdout_text, stderr_text):
        for line in stream_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("E       assert "):
                assertion_lines.append(_clean_excerpt(stripped[8:]))

    failed_tests: List[Dict[str, str]] = []
    for idx, (raw_name, raw_message) in enumerate(summaries[:_MAX_FAILED_TESTS]):
        name = _normalize_test_name(raw_name)
        if not name:
            continue
        assertion_excerpt = assertion_lines[idx] if idx < len(assertion_lines) else ""
        failed_tests.append(
            {
                "name": name,
                "message_excerpt": _clean_excerpt(raw_message),
                "assertion_excerpt": _clean_excerpt(assertion_excerpt),
            }
        )
    return failed_tests


def _extract_assertion_excerpt(trace: str) -> str:
    if not isinstance(trace, str) or not trace:
        return ""
    for line in trace.splitlines():
        stripped = line.strip()
        if stripped.startswith("E       assert "):
            return _clean_excerpt(stripped[8:])
    for line in trace.splitlines():
        stripped = line.strip()
        if stripped.startswith("E       AssertionError:"):
            return _clean_excerpt(stripped[8:])
    return ""


def _normalize_test_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    normalized = name.strip()
    if normalized.startswith("../"):
        normalized = normalized[3:]
    return normalized


def _clean_excerpt(value: str) -> str:
    if not isinstance(value, str):
        return ""
    collapsed = " ".join(value.strip().split())
    if len(collapsed) <= _MAX_EXCERPT_CHARS:
        return collapsed
    return collapsed[: _MAX_EXCERPT_CHARS - 3] + "..."


def _stage_a_precheck(verifier: VerifierDefinition) -> tuple[bool, str]:
    if not isinstance(verifier.command, list) or not verifier.command:
        return False, "missing_command"
    if not all(isinstance(part, str) and part for part in verifier.command):
        return False, "invalid_command_argv"
    if verifier.timeout_ms is not None and (not isinstance(verifier.timeout_ms, int) or verifier.timeout_ms <= 0):
        return False, "invalid_timeout_ms"
    return True, "ok"


def _aggregate_stage_c_status(results: Sequence[VerifierrunResult]) -> str:
    if not results:
        return "pass"
    statuses = {result.result for result in results}
    if "unknown" in statuses:
        return "unknown"
    if "fail" in statuses:
        return "fail"
    return "pass"


def _aggregate_stage_c_diagnostics(results: Sequence[VerifierrunResult]) -> Dict[str, Any]:
    failed_tests: List[Dict[str, str]] = []
    seen_names: set[str] = set()
    sources: List[str] = []
    had_unavailable = False

    for result in results:
        diagnostics = result.verifier_diagnostics if isinstance(result.verifier_diagnostics, dict) else {}
        source = diagnostics.get("source")
        if isinstance(source, str) and source and source not in sources:
            sources.append(source)
        if diagnostics.get("availability") == "unavailable":
            had_unavailable = True
        for test in diagnostics.get("failed_tests", []):
            if not isinstance(test, dict):
                continue
            name = _normalize_test_name(str(test.get("name", "")))
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            failed_tests.append(
                {
                    "name": name,
                    "message_excerpt": _clean_excerpt(str(test.get("message_excerpt", ""))),
                    "assertion_excerpt": _clean_excerpt(str(test.get("assertion_excerpt", ""))),
                }
            )
            if len(failed_tests) >= _MAX_FAILED_TESTS:
                break
        if len(failed_tests) >= _MAX_FAILED_TESTS:
            break

    if failed_tests:
        return {
            "schema_version": _VERIFIER_DIAGNOSTICS_SCHEMA,
            "availability": "available",
            "reason_code": "aggregated",
            "source": ",".join(sources) if sources else "none",
            "failed_count": len(failed_tests),
            "failed_tests": failed_tests,
        }
    if had_unavailable:
        return _diagnostics_unavailable(reason_code="upstream_unavailable")
    return _diagnostics_available(source="none", failed_tests=[], reason_code="no_failures")


def _collect_stage_c_artifact_refs(results: Sequence[VerifierrunResult]) -> List[str]:
    refs: List[str] = []
    for result in results:
        if isinstance(result.stdout_ref, str) and result.stdout_ref:
            refs.append(result.stdout_ref)
        if isinstance(result.stderr_ref, str) and result.stderr_ref:
            refs.append(result.stderr_ref)
    return sorted(set(refs))
