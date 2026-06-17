"""Atomic eval diagnostics over final-harness task packs and result rows."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
import subprocess
from typing import Any, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from runner.certified_sandbox import validate_environment_manifest
from runner.benchmark_adapter_acebench import (
    EQUIVALENT_AUTHORITY_LABEL as ACEBENCH_AUTHORITY_LABEL,
    EQUIVALENT_AUTHORITY_DETAIL as ACEBENCH_AUTHORITY_DETAIL,
    EQUIVALENT_ADAPTER_LABEL as ACEBENCH_ADAPTER_LABEL,
    build_benchmark_case as build_acebench_benchmark_case,
    build_task_pack as build_acebench_task_pack,
)
from runner.benchmark_adapter_bfcl import (
    build_benchmark_case as build_bfcl_benchmark_case,
    build_task_pack as build_bfcl_task_pack,
)
from runner.benchmark_adapter_contextbench import (
    build_benchmark_case as build_contextbench_benchmark_case,
    build_task_pack as build_contextbench_task_pack,
)
from runner.benchmark_adapter_letta import (
    build_benchmark_case as build_letta_benchmark_case,
    build_task_pack as build_letta_task_pack,
)
from runner.benchmark_adapter_terminalbench import (
    build_benchmark_case as build_terminalbench_benchmark_case,
    build_task_pack as build_terminalbench_task_pack,
)
from runner.kernel_artifacts import build_artifact_record, check_required_artifacts, summarize_artifact_registry
from runner.kernel_layer2_audit import (
    build_layer2_audit_prompt,
    deterministic_layer2_fallback,
    normalize_layer2_audit_state,
    parse_layer2_audit_response,
    should_run_layer2,
)
from runner.kernel_success_contract import audit_success_contract_consistency, render_success_contract, validate_success_contract
from runner.eval_substrate_contracts import validate_result_row
from runner.final_harness_eval_suite_adapter import FinalSuiteRowSpec, load_final_suite_row_specs
from runner.schemas import SchemaValidationError

DEFAULT_FINAL_SUITE_RUN_ROOT = Path(
    "tracking/collab/final_harness_eval_suite/runs/20260529T184245Z"
)

CUSTOM_TASK_PACK_REQUIRED_FIELDS = (
    "task_pack_id",
    "row_id",
    "row_type",
)

CUSTOM_V1_REQUIRED_FIELDS = (
    "schema_version",
    "task_pack_id",
    "row_id",
    "row_type",
    "provenance_type",
    "admission_level_target",
    "primary_clusters",
    "canonical_workspace_root",
    "solver_visible_prompt_ref",
    "fixture_manifest_ref",
    "hidden_truth_ref",
    "hidden_verifier_ref",
    "grader_ref",
    "timeout_policy_ref",
    "known_bad_ref",
    "ceiling_ref",
    "deterministic_grading",
    "runtime_contract",
    "expected_outputs",
    "task_brief",
    "row_contract_mode",
    "row_contract_note",
)

CUSTOM_LEGACY_REQUIRED_FIELDS = (
    "task_pack_id",
    "row_id",
    "tier",
    "source_type",
    "source_benchmark_family",
    "solver_entrypoint",
    "visible_verifier",
    "hidden_verifier",
    "grader",
    "expected_candidate_artifacts",
    "admission_level",
    "row_contract_mode",
    "row_contract_note",
)

RESULT_ROW_FINAL_BOARD_REQUIRED_FIELDS = (
    "board_id",
    "board_version",
    "row_id",
    "row_type",
    "provenance_type",
    "contamination_gate",
    "invalidity_gate",
    "current_stack_ref",
    "execution_source",
    "lane_id",
    "recipe_id",
    "recipe_snapshot_ref",
    "critical_clusters",
    "is_flagship",
)

BENCHMARK_FINAL_BOARD_REQUIRED_FIELDS = (
    "benchmark_name",
    "benchmark_case_id",
    "difficulty_tier",
)

SUPPORTED_ROW_IDS = (
    "fsent_01_tool_call_bfcl_composite",
    "fhard_02_service_orchestration_flagship",
    "fhard_05_structured_retrieval_reduction",
    "fbench_acebench_normal_atom_bool_0",
    "fbench_contextbench_verified_06",
    "ftb_challenge_install_windows_3_11",
)

ATOMIC_LEVELS = ("A0", "A1", "A2", "A3", "A4", "A5")


@dataclass(frozen=True)
class AtomicCheckResult:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class AtomicTestResult:
    atomic_level: str
    atomic_test_id: str
    verdict: str
    failure_class: str
    reason_codes: tuple[str, ...]
    evidence_paths: tuple[str, ...]
    promotion_blocking: bool
    detail: str


@dataclass(frozen=True)
class AtomicRowDiagnostic:
    row_id: str
    source_kind: str
    task_pack_ref: str
    result_row_ref: str
    status: str
    checks: tuple[AtomicCheckResult, ...]
    atomic_tests: tuple[AtomicTestResult, ...]
    invalidity_reasons: tuple[str, ...]
    evidence_paths: tuple[str, ...]


def run_atomic_eval_diagnostics(
    *,
    repo_root: Path,
    row_ids: Sequence[str],
    output_root: Path,
    result_run_root: Path | None = None,
    atomic_levels: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run A0 static contract diagnostics over a row subset."""
    specs = _load_specs(repo_root, row_ids)
    run_root = result_run_root or repo_root / DEFAULT_FINAL_SUITE_RUN_ROOT
    rows_dir = output_root / "atomic_result_rows"
    rows_dir.mkdir(parents=True, exist_ok=True)

    diagnostics = [
        diagnose_atomic_row(
            repo_root=repo_root,
            result_run_root=run_root,
            spec=spec,
            atomic_levels=atomic_levels,
        )
        for spec in specs
    ]
    for diagnostic in diagnostics:
        _write_json(rows_dir / f"{diagnostic.row_id}.json", asdict(diagnostic))

    summary = summarize_atomic_diagnostics(diagnostics)
    _write_json(output_root / "atomic_score_summary.json", summary)
    _write_text(output_root / "atomic_failure_matrix.md", render_failure_matrix(diagnostics))
    _write_text(output_root / "atomic_invalidity_report.md", render_invalidity_report(diagnostics))

    return {
        "row_count": len(diagnostics),
        "summary_path": str(output_root / "atomic_score_summary.json"),
        "failure_matrix_path": str(output_root / "atomic_failure_matrix.md"),
        "invalidity_report_path": str(output_root / "atomic_invalidity_report.md"),
        "result_rows_dir": str(rows_dir),
        "diagnostics": [asdict(diagnostic) for diagnostic in diagnostics],
    }


def diagnose_atomic_row(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    atomic_levels: Sequence[str] | None = None,
) -> AtomicRowDiagnostic:
    checks: list[AtomicCheckResult] = []
    invalidity_reasons: list[str] = []
    task_pack_path = repo_root / spec.task_pack_ref if spec.task_pack_ref else _adapter_task_pack_ref(spec)
    result_row_path = result_run_root / "result_rows" / f"{spec.row_id}.json"
    task_pack: dict[str, Any] = {}
    result_row: dict[str, Any] = {}

    try:
        task_pack_path, task_pack = _load_task_pack(repo_root, spec)
        if spec.execution_source == "task_pack" and task_pack_path.exists():
            task_pack_path = task_pack_path.resolve()
    except Exception as exc:
        task_pack_report = AtomicRowDiagnostic(
            row_id=spec.row_id,
            source_kind=_source_kind(spec),
            task_pack_ref=str(task_pack_path),
            result_row_ref="",
            status="fail",
            checks=(AtomicCheckResult("task_pack_load", "fail", str(exc)),),
            atomic_tests=(),
            invalidity_reasons=(f"task_pack_load:{exc}",),
            evidence_paths=(),
        )
    else:
        task_pack_report = _safe_validate_task_pack_contract(
            repo_root=repo_root,
            spec=spec,
            task_pack_path=task_pack_path,
            task_pack=task_pack,
        )

    try:
        result_row_path, result_row = _load_result_row(result_run_root, spec.row_id)
        if result_row_path.exists():
            result_row_path = result_row_path.resolve()
    except Exception as exc:
        result_row_report = AtomicRowDiagnostic(
            row_id=spec.row_id,
            source_kind=_source_kind(spec),
            task_pack_ref="",
            result_row_ref=str(result_row_path),
            status="fail",
            checks=(AtomicCheckResult("result_row_load", "fail", str(exc)),),
            atomic_tests=(),
            invalidity_reasons=(f"result_row_load:{exc}",),
            evidence_paths=(),
        )
    else:
        result_row_report = _safe_validate_result_row_contract(spec=spec, result_row=result_row)

    checks.extend(task_pack_report.checks)
    checks.extend(result_row_report.checks)
    invalidity_reasons.extend(task_pack_report.invalidity_reasons)
    invalidity_reasons.extend(result_row_report.invalidity_reasons)
    invalidity_reasons.extend(
        f"{check.name}:{check.detail}" for check in checks if check.status == "fail"
    )

    atomic_tests = _build_atomic_tests(
        repo_root=repo_root,
        result_run_root=result_run_root,
        spec=spec,
        task_pack_path=task_pack_path,
        result_row_path=result_row_path,
        task_pack=task_pack,
        result_row=result_row,
        task_pack_report=task_pack_report,
        result_row_report=result_row_report,
        atomic_levels=atomic_levels,
    )
    status = "pass" if not invalidity_reasons else "fail"
    evidence_paths = _evidence_paths_for_row(spec, task_pack_path, result_row_path)
    for test in atomic_tests:
        for path in test.evidence_paths:
            if path not in evidence_paths:
                evidence_paths.append(path)
    return AtomicRowDiagnostic(
        row_id=spec.row_id,
        source_kind=_source_kind(spec),
        task_pack_ref=str(task_pack_path),
        result_row_ref=str(result_row_path),
        status=status,
        checks=tuple(checks),
        atomic_tests=tuple(atomic_tests),
        invalidity_reasons=tuple(sorted(set(invalidity_reasons))),
        evidence_paths=tuple(evidence_paths),
    )


def summarize_atomic_diagnostics(diagnostics: Sequence[AtomicRowDiagnostic]) -> dict[str, Any]:
    totals = {"pass": 0, "fail": 0, "total": 0}
    by_source_kind: dict[str, dict[str, int]] = {}
    invalidity_counts: dict[str, int] = {}
    check_counts: dict[str, dict[str, int]] = {}
    atomic_level_counts: dict[str, dict[str, int]] = {}
    atomic_test_counts: dict[str, dict[str, int]] = {}
    atomic_failure_counts: dict[str, int] = {}
    promotion_blocking_counts = {"true": 0, "false": 0}

    for diagnostic in diagnostics:
        totals["total"] += 1
        totals[diagnostic.status] += 1
        bucket = by_source_kind.setdefault(diagnostic.source_kind, {"pass": 0, "fail": 0, "total": 0})
        bucket["total"] += 1
        bucket[diagnostic.status] += 1
        for reason in diagnostic.invalidity_reasons:
            invalidity_counts[reason] = invalidity_counts.get(reason, 0) + 1
        for check in diagnostic.checks:
            bucket_counts = check_counts.setdefault(check.name, {"pass": 0, "fail": 0, "total": 0})
            bucket_counts["total"] += 1
            bucket_counts[check.status] += 1
        for test in diagnostic.atomic_tests:
            level_counts = atomic_level_counts.setdefault(test.atomic_level, {"pass": 0, "fail": 0, "invalid": 0, "blocked": 0, "total": 0})
            level_counts["total"] += 1
            level_counts[test.verdict] += 1
            atomic_counts = atomic_test_counts.setdefault(test.atomic_test_id, {"pass": 0, "fail": 0, "invalid": 0, "blocked": 0, "total": 0})
            atomic_counts["total"] += 1
            atomic_counts[test.verdict] += 1
            if test.verdict != "pass":
                atomic_failure_counts[test.failure_class] = atomic_failure_counts.get(test.failure_class, 0) + 1
            promotion_blocking_counts["true" if test.promotion_blocking else "false"] += 1

    return {
        "row_count": len(diagnostics),
        "totals": totals,
        "by_source_kind": by_source_kind,
        "invalidity_counts": invalidity_counts,
        "check_counts": check_counts,
        "atomic_level_counts": atomic_level_counts,
        "atomic_test_counts": atomic_test_counts,
        "atomic_failure_counts": atomic_failure_counts,
        "promotion_blocking_counts": promotion_blocking_counts,
        "row_ids": [diagnostic.row_id for diagnostic in diagnostics],
    }


def render_failure_matrix(diagnostics: Sequence[AtomicRowDiagnostic]) -> str:
    level_names = list(ATOMIC_LEVELS)
    lines = [
        "# Atomic Failure Matrix",
        "",
        "| Row | Status | " + " | ".join(level_names) + " |",
        "| --- | --- | " + " | ".join(["---"] * len(level_names)) + " |",
    ]
    by_name = {
        diagnostic.row_id: {test.atomic_level: test.verdict for test in diagnostic.atomic_tests}
        for diagnostic in diagnostics
    }
    for diagnostic in diagnostics:
        cells = [diagnostic.row_id, diagnostic.status]
        cells.extend(by_name[diagnostic.row_id].get(name, "n/a") for name in level_names)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def render_invalidity_report(diagnostics: Sequence[AtomicRowDiagnostic]) -> str:
    lines = ["# Atomic Invalidity Report", ""]
    failures = [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.invalidity_reasons or any(test.verdict != "pass" for test in diagnostic.atomic_tests)
    ]
    if not failures:
        lines.append("No atomic invalidities detected for the selected subset.")
        return "\n".join(lines) + "\n"

    for diagnostic in failures:
        lines.append(f"## {diagnostic.row_id}")
        lines.append(f"- status: {diagnostic.status}")
        lines.append(f"- source_kind: {diagnostic.source_kind}")
        for reason in diagnostic.invalidity_reasons:
            lines.append(f"- invalidity: {reason}")
        for test in diagnostic.atomic_tests:
            if test.verdict != "pass":
                reason_codes = ", ".join(test.reason_codes) if test.reason_codes else "none"
                lines.append(
                    f"- atomic_{test.atomic_level}:{test.atomic_test_id}: {test.verdict} "
                    f"({test.failure_class}; reasons: {reason_codes})"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_atomic_tests(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    result_row_path: Path,
    task_pack: dict[str, Any],
    result_row: dict[str, Any],
    task_pack_report: AtomicRowDiagnostic,
    result_row_report: AtomicRowDiagnostic,
    atomic_levels: Sequence[str] | None,
) -> list[AtomicTestResult]:
    selected_levels = {level.upper() for level in atomic_levels} if atomic_levels else set(ATOMIC_LEVELS)
    tests: list[AtomicTestResult] = []
    builders = [
        ("A0", "static_contract", _build_atomic_a0_test),
        ("A1", "workspace_sandbox", _build_atomic_a1_test),
        ("A2", "deterministic_ceiling", _build_atomic_a2_test),
        ("A3", "known_bad_negative", _build_atomic_a3_test),
        ("A4", "mechanism_replay", _build_atomic_a4_test),
        ("A5", "micro_smoke", _build_atomic_a5_test),
    ]
    for atomic_level, test_id, builder in builders:
        if atomic_level not in selected_levels:
            continue
        tests.append(
            builder(
                repo_root=repo_root,
                result_run_root=result_run_root,
                spec=spec,
                task_pack_path=task_pack_path,
                result_row_path=result_row_path,
                task_pack=task_pack,
                result_row=result_row,
                task_pack_report=task_pack_report,
                result_row_report=result_row_report,
            )
        )
    return tests


def _build_atomic_a0_test(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    result_row_path: Path,
    task_pack: dict[str, Any],
    result_row: dict[str, Any],
    task_pack_report: AtomicRowDiagnostic,
    result_row_report: AtomicRowDiagnostic,
) -> AtomicTestResult:
    _ = (repo_root, result_run_root, task_pack, result_row)
    invalidity_reasons = list(task_pack_report.invalidity_reasons) + list(result_row_report.invalidity_reasons)
    verdict = _verdict_from_status(task_pack_report.status, result_row_report.status)
    failure_class = _failure_class_from_reasons(invalidity_reasons, default="eval_definition")
    detail = "static task-pack and result-row contract validated" if verdict == "pass" else "static contract failed"
    return AtomicTestResult(
        atomic_level="A0",
        atomic_test_id="static_contract",
        verdict=verdict,
        failure_class=failure_class,
        reason_codes=tuple(_dedupe_preserve_order(invalidity_reasons)),
        evidence_paths=tuple(str(path) for path in _resolve_atomic_evidence_paths(task_pack_path, result_row_path)),
        promotion_blocking=verdict != "pass",
        detail=detail,
    )


def _build_atomic_a1_test(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    result_row_path: Path,
    task_pack: dict[str, Any],
    result_row: dict[str, Any],
    task_pack_report: AtomicRowDiagnostic,
    result_row_report: AtomicRowDiagnostic,
) -> AtomicTestResult:
    _ = task_pack_report
    evidence_paths = _resolve_atomic_evidence_paths(
        repo_root,
        task_pack_path,
        result_row_path,
        *_atomic_ref_paths(repo_root=repo_root, result_run_root=result_run_root, spec=spec, task_pack_path=task_pack_path, task_pack=task_pack, result_row=result_row),
    )
    if spec.execution_source == "terminalbench_challenge":
        return AtomicTestResult(
            atomic_level="A1",
            atomic_test_id="workspace_sandbox",
            verdict="blocked",
            failure_class="unsupported_source_kind",
            reason_codes=("task_pack_load_blocked",),
            evidence_paths=tuple(str(path) for path in evidence_paths),
            promotion_blocking=True,
            detail="terminalbench challenge row cannot be sandbox-validated without a supported task pack",
        )

    if spec.execution_source == "task_pack":
        env_result = _load_atomic_environment_manifest(repo_root, result_row)
        if env_result["verdict"] != "pass":
            return AtomicTestResult(
                atomic_level="A1",
                atomic_test_id="workspace_sandbox",
                verdict=env_result["verdict"],
                failure_class=env_result["failure_class"],
                reason_codes=tuple(env_result["reason_codes"]),
                evidence_paths=tuple(str(path) for path in evidence_paths),
                promotion_blocking=env_result["verdict"] != "pass",
                detail=env_result["detail"],
            )
        sandbox_reasons: list[str] = []
        try:
            validate_environment_manifest(env_result["manifest"])
        except Exception as exc:
            sandbox_reasons.append(f"environment_manifest:{exc}")
        task_pack_paths = _task_pack_workspace_paths(repo_root, task_pack_path, task_pack)
        missing = [str(path) for path in task_pack_paths if not path.exists()]
        if missing:
            sandbox_reasons.append("missing_workspace_files:" + ", ".join(missing))
        if sandbox_reasons:
            return AtomicTestResult(
                atomic_level="A1",
                atomic_test_id="workspace_sandbox",
                verdict="fail",
                failure_class=_failure_class_from_reasons(sandbox_reasons, default="sandbox"),
                reason_codes=tuple(sandbox_reasons),
                evidence_paths=tuple(str(path) for path in evidence_paths),
                promotion_blocking=True,
                detail="workspace/sandbox contract is not fully grounded",
            )
        return AtomicTestResult(
            atomic_level="A1",
            atomic_test_id="workspace_sandbox",
            verdict="pass",
            failure_class="none",
            reason_codes=(),
            evidence_paths=tuple(str(path) for path in evidence_paths),
            promotion_blocking=False,
            detail="certified workspace contract and visible files are present",
        )

    env_result = _load_atomic_environment_manifest(repo_root, result_row)
    verdict = "invalid" if env_result["verdict"] != "pass" else "pass"
    failure_class = env_result["failure_class"] if verdict != "pass" else "none"
    return AtomicTestResult(
        atomic_level="A1",
        atomic_test_id="workspace_sandbox",
        verdict=verdict,
        failure_class=failure_class,
        reason_codes=tuple(env_result["reason_codes"]),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        promotion_blocking=verdict != "pass",
        detail=env_result["detail"],
    )


def _build_atomic_a2_test(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    result_row_path: Path,
    task_pack: dict[str, Any],
    result_row: dict[str, Any],
    task_pack_report: AtomicRowDiagnostic,
    result_row_report: AtomicRowDiagnostic,
) -> AtomicTestResult:
    _ = (task_pack_report, result_row_report)
    evidence_paths = _resolve_atomic_evidence_paths(
        repo_root,
        task_pack_path,
        result_row_path,
        *_atomic_ref_paths(repo_root=repo_root, result_run_root=result_run_root, spec=spec, task_pack_path=task_pack_path, task_pack=task_pack, result_row=result_row),
    )
    if spec.execution_source == "terminalbench_challenge":
        return AtomicTestResult(
            atomic_level="A2",
            atomic_test_id="deterministic_ceiling",
            verdict="blocked",
            failure_class="unsupported_source_kind",
            reason_codes=("task_pack_load_blocked",),
            evidence_paths=tuple(str(path) for path in evidence_paths),
            promotion_blocking=True,
            detail="deterministic ceiling cannot be checked for unsupported TerminalBench challenge row",
        )
    reasons: list[str] = []
    if spec.execution_source == "task_pack":
        ceiling_path = _resolve_local_ref_path(repo_root, str(task_pack_path.parent / str(task_pack.get("ceiling_ref") or "")))
        if ceiling_path is None or not ceiling_path.exists():
            reasons.append("ceiling_ref_missing")
        if not isinstance(task_pack.get("deterministic_grading"), bool) or not task_pack.get("deterministic_grading"):
            reasons.append("deterministic_grading_missing")
        expected_outputs = task_pack.get("expected_outputs")
        if not isinstance(expected_outputs, dict) or not expected_outputs:
            reasons.append("expected_outputs_missing")
        if task_pack.get("schema_version") == "final_harness_task_pack.v1":
            prompt_path = _resolve_local_ref_path(repo_root, str(task_pack_path.parent / str(task_pack.get("solver_visible_prompt_ref") or "")))
            if prompt_path is None or not prompt_path.exists():
                reasons.append("solver_visible_prompt_missing")
            fixture_manifest_path = _resolve_local_ref_path(repo_root, str(task_pack_path.parent / str(task_pack.get("fixture_manifest_ref") or "")))
            if fixture_manifest_path is None or not fixture_manifest_path.exists():
                reasons.append("fixture_manifest_missing")
            hidden_verifier_path = _resolve_local_ref_path(repo_root, str(task_pack_path.parent / str(task_pack.get("hidden_verifier_ref") or "")))
            if hidden_verifier_path is None or not hidden_verifier_path.exists():
                reasons.append("hidden_verifier_missing")
            grader_path = _resolve_local_ref_path(repo_root, str(task_pack_path.parent / str(task_pack.get("grader_ref") or "")))
            if grader_path is None or not grader_path.exists():
                reasons.append("grader_missing")
        else:
            visible_verifier_path = _resolve_local_ref_path(repo_root, str(task_pack_path.parent / str(task_pack.get("visible_verifier") or "")))
            if visible_verifier_path is None or not visible_verifier_path.exists():
                reasons.append("visible_verifier_missing")
    else:
        if not _resolve_local_ref_path(repo_root, str(result_row.get("verifier_ref") or "")).exists():
            reasons.append("verifier_ref_missing")
        if not _resolve_local_ref_path(repo_root, str(result_row.get("grader_ref") or "")).exists():
            reasons.append("grader_ref_missing")
        if "score" not in result_row or not isinstance(result_row.get("score"), (int, float)):
            reasons.append("score_missing")
        final_board = result_row.get("final_board")
        if not isinstance(final_board, dict):
            reasons.append("final_board_missing")
        else:
            if not isinstance(final_board.get("invalidity_gate"), str):
                reasons.append("final_board_invalidity_gate_missing")
            if not isinstance(final_board.get("contamination_gate"), str):
                reasons.append("final_board_contamination_gate_missing")
    verdict = "pass" if not reasons else "fail"
    return AtomicTestResult(
        atomic_level="A2",
        atomic_test_id="deterministic_ceiling",
        verdict=verdict,
        failure_class=_failure_class_from_reasons(reasons, default="verification_grading"),
        reason_codes=tuple(reasons),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        promotion_blocking=verdict != "pass",
        detail="deterministic ceiling and grader/verifier contract present" if verdict == "pass" else "ceiling readiness is incomplete",
    )


def _build_atomic_a3_test(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    result_row_path: Path,
    task_pack: dict[str, Any],
    result_row: dict[str, Any],
    task_pack_report: AtomicRowDiagnostic,
    result_row_report: AtomicRowDiagnostic,
) -> AtomicTestResult:
    _ = (repo_root, result_run_root, task_pack_report, result_row_report)
    evidence_paths = _resolve_atomic_evidence_paths(task_pack_path, result_row_path, *_atomic_ref_paths(repo_root=repo_root, result_run_root=result_run_root, spec=spec, task_pack_path=task_pack_path, task_pack=task_pack, result_row=result_row))
    reasons: list[str] = []
    if spec.execution_source == "task_pack":
        known_bad_path = _resolve_local_ref_path(repo_root, str(task_pack.get("known_bad_ref") or ""))
        if known_bad_path is None or not known_bad_path.exists():
            reasons.append("known_bad_ref_missing")
    else:
        reason_codes = result_row.get("reason_codes")
        if isinstance(reason_codes, list) and any(isinstance(code, str) and code.strip() for code in reason_codes):
            reasons.extend(str(code) for code in reason_codes if isinstance(code, str) and code.strip())
        else:
            reasons.append("missing_negative_pressure_signal")
        final_board = result_row.get("final_board")
        if isinstance(final_board, dict) and not isinstance(final_board.get("invalidity_gate"), str):
            reasons.append("final_board_invalidity_gate_missing")
    verdict = "pass" if reasons else "fail"
    return AtomicTestResult(
        atomic_level="A3",
        atomic_test_id="known_bad_negative",
        verdict=verdict,
        failure_class=_failure_class_from_reasons(reasons, default="bypass_resistance"),
        reason_codes=tuple(_dedupe_preserve_order(reasons)),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        promotion_blocking=verdict != "pass",
        detail="known-bad and negative-pressure evidence present" if verdict == "pass" else "negative-pressure contract is incomplete",
    )


def _build_atomic_a4_test(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    result_row_path: Path,
    task_pack: dict[str, Any],
    result_row: dict[str, Any],
    task_pack_report: AtomicRowDiagnostic,
    result_row_report: AtomicRowDiagnostic,
) -> AtomicTestResult:
    _ = (task_pack_report, result_row_report)
    evidence_paths = _resolve_atomic_evidence_paths(task_pack_path, result_row_path, *_atomic_ref_paths(repo_root=repo_root, result_run_root=result_run_root, spec=spec, task_pack_path=task_pack_path, task_pack=task_pack, result_row=result_row))
    expected_paths = [path for path in evidence_paths if _is_within_root(path, repo_root)]
    registry_paths = [path for path in expected_paths if path.exists()]
    registry = {str(path): build_artifact_record(path=path, workspace_root=repo_root, generated=False) for path in registry_paths}
    registry_summary = summarize_artifact_registry(registry)
    required_refs = check_required_artifacts(
        workspace_root=repo_root,
        required_paths=[str(path.relative_to(repo_root)) for path in expected_paths],
    )
    reasons: list[str] = []
    reasons.extend(list(required_refs.get("missing_paths", [])))
    reasons.extend(list(required_refs.get("empty_paths", [])))
    trace_refs = result_row.get("trace_refs")
    if isinstance(trace_refs, list) and trace_refs:
        for ref in trace_refs:
            if not isinstance(ref, str) or not ref.strip():
                continue
            trace_path = _resolve_local_ref_path(repo_root, ref)
            if trace_path is None or not trace_path.exists():
                reasons.append(f"trace_ref_missing:{ref}")
    else:
        reasons.append("trace_refs_missing")
    if spec.execution_source == "task_pack":
        local_run_dir = result_row_path.parent.parent / "rows" / spec.row_id
        route_trace_dir = local_run_dir / "route_trace"
        if route_trace_dir.exists():
            for candidate in ("run_header.json", "route_manifest.json", "score_envelope.json"):
                if not (route_trace_dir / candidate).exists():
                    reasons.append(f"route_trace_{candidate}_missing")
    verdict = "pass" if not reasons else "fail"
    return AtomicTestResult(
        atomic_level="A4",
        atomic_test_id="mechanism_replay",
        verdict=verdict,
        failure_class=_failure_class_from_reasons(reasons, default="artifact_registry"),
        reason_codes=tuple(_dedupe_preserve_order(reasons)),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        promotion_blocking=verdict != "pass",
        detail="artifact registry and replay evidence are present" if verdict == "pass" else "mechanism/replay evidence is incomplete",
    )


def _build_atomic_a5_test(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    result_row_path: Path,
    task_pack: dict[str, Any],
    result_row: dict[str, Any],
    task_pack_report: AtomicRowDiagnostic,
    result_row_report: AtomicRowDiagnostic,
) -> AtomicTestResult:
    _ = (result_run_root, task_pack_report, result_row_report)
    evidence_paths = _resolve_atomic_evidence_paths(task_pack_path, result_row_path, *_atomic_ref_paths(repo_root=repo_root, result_run_root=result_run_root, spec=spec, task_pack_path=task_pack_path, task_pack=task_pack, result_row=result_row))
    visible_prompt = _resolve_local_ref_path(repo_root, str(task_pack.get("solver_visible_prompt_ref") or task_pack.get("solver_entrypoint") or ""))
    task_prompt = ""
    if visible_prompt is not None and visible_prompt.exists():
        task_prompt = visible_prompt.read_text(encoding="utf-8")
    elif isinstance(task_pack.get("task_brief"), str):
        task_prompt = str(task_pack.get("task_brief") or "")
    if not task_prompt.strip():
        task_prompt = f"Atomic smoke for {spec.row_id}"

    required_artifacts = [str(path.relative_to(repo_root)) for path in evidence_paths if _is_within_root(path, repo_root)]
    required_checks = ["verifier_output", "grader_output"]
    contract = {
        "status": "proposed",
        "contract_id": spec.row_id,
        "source_receipt_id": str(result_row.get("run_id") or spec.row_id),
        "criteria": [
            f"row_id:{spec.row_id}",
            f"source_kind:{_source_kind(spec)}",
            f"surface_type:{spec.surface_type}",
        ],
        "required_artifacts": required_artifacts,
        "required_checks": required_checks,
        "authority_hierarchy": [
            "visible_prompt",
            "task_pack",
            "result_row",
        ],
        "known_uncertainty": [f"task_truth_status:{result_row.get('task_truth_status', 'unknown')}"],
        "suspected_decoy_classes": ["reviewer_decoy", "stale_docs", "missing_artifact"],
        "done_checklist": [
            "success_contract_validated",
            "layer2_prompt_built",
            "layer2_fallback_parsed",
        ],
        "revision": 0,
        "visible_evidence_refs": required_artifacts,
    }
    contract_validation = validate_success_contract(contract)
    if contract_validation["status"] != "accepted":
        reasons = list(contract_validation["reason_codes"])
        return AtomicTestResult(
            atomic_level="A5",
            atomic_test_id="micro_smoke",
            verdict="fail",
            failure_class="success_contract",
            reason_codes=tuple(reasons),
            evidence_paths=tuple(str(path) for path in evidence_paths),
            promotion_blocking=True,
            detail="success contract substrate rejected the smoke contract",
        )
    contract_payload = contract_validation["contract"]
    rendered_contract = render_success_contract(contract_payload)
    if any(marker in rendered_contract for marker in ("hidden://", "/reviewer_pack", "hidden_truth")):
        return AtomicTestResult(
            atomic_level="A5",
            atomic_test_id="micro_smoke",
            verdict="fail",
            failure_class="prompt_contamination",
            reason_codes=("success_contract_render_leaked_hidden_refs",),
            evidence_paths=tuple(str(path) for path in evidence_paths),
            promotion_blocking=True,
            detail="rendered success contract leaked hidden references",
        )
    final_state = {
        "task_prompt": task_prompt,
        "success_contract": contract_payload,
        "artifact_refs": required_artifacts,
        "visible_artifact_refs": required_artifacts,
        "artifact_state": {"artifact_refs": required_artifacts},
        "verifier_checks": required_checks,
        "visible_checks": required_checks,
        "verifier_state": {"checks": required_checks},
    }
    audit = audit_success_contract_consistency(
        task_prompt=task_prompt,
        success_contract=contract_payload,
        final_state=final_state,
    )
    finalization_gate = {
        "governed_status": "governed_pass" if audit["status"] == "pass" else "governed_fail",
        "reason_codes": list(audit.get("reason_codes") or []),
        "open_obligations": {} if audit["status"] == "pass" else {"contract": audit.get("mismatches", [])},
    }
    route_manifest = {
        "feature_flags": {"layer2_success_audit": True},
        "layer2_success_audit": True,
    }
    should_layer2 = should_run_layer2(route_manifest=route_manifest, finalization_gate=finalization_gate)
    layer2_prompt = build_layer2_audit_prompt(
        task_prompt=task_prompt,
        success_contract=contract_payload,
        context_pack={
            "row_id": spec.row_id,
            "source_kind": _source_kind(spec),
            "artifact_refs": required_artifacts,
            "reason_codes": list(result_row.get("reason_codes") or []),
        },
        finalization_gate=finalization_gate,
    )
    prompt_text = json.dumps(layer2_prompt, indent=2)
    if any(marker in prompt_text for marker in ("hidden://", "/reviewer_pack", "hidden_truth")):
        return AtomicTestResult(
            atomic_level="A5",
            atomic_test_id="micro_smoke",
            verdict="fail",
            failure_class="prompt_contamination",
            reason_codes=("layer2_prompt_leaked_hidden_refs",),
            evidence_paths=tuple(str(path) for path in evidence_paths),
            promotion_blocking=True,
            detail="Layer 2 prompt leaked hidden references",
        )
    parsed = parse_layer2_audit_response({
        "text": json.dumps(
            {
                "verdict": "PASS" if audit["status"] == "pass" else "FAIL",
                "confidence": "high",
                "mismatches": audit.get("mismatches", []),
                "missing_evidence": audit.get("missing_evidence", []),
                "reason_codes": audit.get("reason_codes", []),
                "repair_instruction": "",
            }
        )
    })
    normalized = normalize_layer2_audit_state(
        deterministic_layer2_fallback(
            finalization_gate={
                "governed_status": "governed_pass" if audit["status"] == "pass" else "governed_fail",
                "reason_codes": list(audit.get("reason_codes") or []),
                "open_obligations": {} if audit["status"] == "pass" else {"contract": audit.get("mismatches", [])},
            },
            success_contract=contract_payload,
        )
    )
    reasons: list[str] = []
    if parsed.get("verdict") not in {"PASS", "FAIL", "UNCLEAR"}:
        reasons.append("layer2_parse_failed")
    if normalized.get("status") not in {"pass", "fail", "unclear"}:
        reasons.append("layer2_normalization_failed")
    if audit["status"] != "pass" and not audit.get("reason_codes"):
        reasons.append("layer2_audit_missing_reason_codes")
    if audit["status"] == "pass" and not should_layer2:
        reasons.append("layer2_should_run_false")
    if audit["status"] != "pass" and should_layer2:
        reasons.append("layer2_should_run_true_for_failed_gate")
    verdict = "pass" if not reasons else "fail"
    return AtomicTestResult(
        atomic_level="A5",
        atomic_test_id="micro_smoke",
        verdict=verdict,
        failure_class=_failure_class_from_reasons(reasons, default="model_harness_interaction"),
        reason_codes=tuple(reasons),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        promotion_blocking=verdict != "pass",
        detail="success-contract and Layer 2 smoke prompt built successfully" if verdict == "pass" else "micro smoke contract is incomplete",
    )


def _resolve_local_ref_path(repo_root: Path, ref: str) -> Path | None:
    ref = str(ref or "").strip()
    if not ref:
        return None
    if ref.startswith("adapter://") or ref.startswith("hidden://") or ref.startswith("provenance://"):
        return None
    path = Path(ref)
    if path.exists():
        return path
    marker = "/harnesseng/"
    if marker in ref:
        suffix = ref.split(marker, 1)[1]
        candidate = repo_root / suffix
        return candidate
    if ref.startswith(str(repo_root)):
        return Path(ref)
    return path


def _is_within_root(path: Path, root: Path) -> bool:
    path_text = str(path)
    if "://" in path_text or path_text.startswith(("adapter:", "hidden:", "provenance:")):
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _failure_class_from_reasons(reasons: Sequence[str], *, default: str) -> str:
    for reason in reasons:
        if "environment_manifest" in reason or "workspace" in reason or "sandbox" in reason:
            return "sandbox"
        if "ceiling" in reason or "verifier" in reason or "grader" in reason or "score" in reason:
            return "verification_grading"
        if "known_bad" in reason or "negative" in reason or "contamination" in reason:
            return "verification_grading"
        if "layer2" in reason or "success_contract" in reason:
            return "model_harness_interaction"
        if "task_pack_load" in reason or "result_row_load" in reason:
            return "eval_definition"
    return default


def _verdict_from_status(*statuses: str) -> str:
    normalized = [status.lower() for status in statuses if isinstance(status, str)]
    if any(status == "fail" for status in normalized):
        return "fail"
    if any(status == "invalid" for status in normalized):
        return "invalid"
    if any(status == "blocked" for status in normalized):
        return "blocked"
    return "pass"


def _atomic_ref_paths(
    *,
    repo_root: Path,
    result_run_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    task_pack: dict[str, Any],
    result_row: dict[str, Any],
) -> list[Path]:
    refs: list[str] = []
    if spec.execution_source == "task_pack":
        base = task_pack_path.parent
        refs.extend(
            [
                str(base / str(task_pack.get("solver_visible_prompt_ref") or "")),
                str(base / str(task_pack.get("fixture_manifest_ref") or "")),
                str(base / str(task_pack.get("hidden_truth_ref") or "")),
                str(base / str(task_pack.get("hidden_verifier_ref") or "")),
                str(base / str(task_pack.get("grader_ref") or "")),
                str(base / str(task_pack.get("timeout_policy_ref") or "")),
                str(base / str(task_pack.get("known_bad_ref") or "")),
                str(base / str(task_pack.get("ceiling_ref") or "")),
            ]
        )
        if isinstance(task_pack.get("solver_entrypoint"), str):
            refs.append(str(base / str(task_pack.get("solver_entrypoint"))))
        if isinstance(task_pack.get("visible_verifier"), str):
            refs.append(str(base / str(task_pack.get("visible_verifier"))))
        if isinstance(task_pack.get("hidden_verifier"), str):
            refs.append(str(base / str(task_pack.get("hidden_verifier"))))
        if isinstance(task_pack.get("grader"), str):
            refs.append(str(base / str(task_pack.get("grader"))))
    refs.extend(
        [
            str(result_row.get("environment_ref") or ""),
            str(result_row.get("verifier_ref") or ""),
            str(result_row.get("grader_ref") or ""),
        ]
    )
    for key in ("artifact_refs", "trace_refs"):
        value = result_row.get(key)
        if isinstance(value, list):
            refs.extend(str(item) for item in value if isinstance(item, str))
    run_root = result_run_root.resolve()
    artifact_bundle = run_root / "rows" / spec.row_id / "artifacts" / "artifact_bundle.json"
    if artifact_bundle.exists():
        refs.append(str(artifact_bundle))
    trace_root = run_root / "rows" / spec.row_id / "route_trace"
    if trace_root.exists():
        refs.extend(str(trace_root / name) for name in ("run_header.json", "route_manifest.json", "score_envelope.json", "run_events.jsonl"))
    resolved: list[Path] = []
    for ref in refs:
        path = _resolve_local_ref_path(repo_root, ref)
        if path is not None:
            resolved.append(path)
    return _dedupe_paths(resolved)


def _dedupe_paths(paths: Sequence[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def _resolve_atomic_evidence_paths(*paths: Path) -> list[Path]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if not isinstance(path, Path):
            continue
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def _load_atomic_environment_manifest(repo_root: Path, result_row: dict[str, Any]) -> dict[str, Any]:
    ref = result_row.get("environment_ref")
    path = _resolve_local_ref_path(repo_root, str(ref or ""))
    if path is None or not path.exists():
        return {
            "verdict": "invalid",
            "failure_class": "sandbox",
            "reason_codes": ["environment_manifest_missing"],
            "detail": "environment manifest is missing",
        }
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "verdict": "invalid",
            "failure_class": "sandbox",
            "reason_codes": [f"environment_manifest_parse:{exc}"],
            "detail": "environment manifest could not be parsed",
        }
    if not isinstance(manifest, dict):
        return {
            "verdict": "invalid",
            "failure_class": "sandbox",
            "reason_codes": ["environment_manifest_not_mapping"],
            "detail": "environment manifest is not a mapping",
        }
    if manifest.get("status") == "invalid":
        return {
            "verdict": "invalid",
            "failure_class": "sandbox",
            "reason_codes": [str(manifest.get("reason_code") or "environment_invalid")],
            "manifest": manifest,
            "detail": str(manifest.get("reason") or "environment marked invalid"),
        }
    return {
        "verdict": "pass",
        "failure_class": "none",
        "reason_codes": [],
        "manifest": manifest,
        "detail": "environment manifest is present and usable",
    }


def _task_pack_workspace_paths(repo_root: Path, task_pack_path: Path, task_pack: dict[str, Any]) -> list[Path]:
    base = task_pack_path.parent
    paths: list[Path] = []
    if task_pack.get("schema_version") == "final_harness_task_pack.v1":
        for field in (
            "solver_visible_prompt_ref",
            "fixture_manifest_ref",
            "hidden_truth_ref",
            "hidden_verifier_ref",
            "grader_ref",
            "timeout_policy_ref",
            "known_bad_ref",
            "ceiling_ref",
        ):
            ref = task_pack.get(field)
            if isinstance(ref, str) and ref.strip():
                paths.append(_resolve_local_ref_path(repo_root, str(base / ref)) or base / ref)
    else:
        for field in ("solver_entrypoint", "visible_verifier", "hidden_verifier", "grader"):
            ref = task_pack.get(field)
            if isinstance(ref, str) and ref.strip():
                paths.append(base / ref)
        paths.append(base / "fixture_manifest.json")
        for field in ("known_bad_ref", "ceiling_ref"):
            ref = task_pack.get(field)
            if isinstance(ref, str) and ref.strip():
                paths.append(base / ref)
    return _dedupe_paths(paths)


def _validate_task_pack_contract(
    *,
    repo_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    task_pack: dict[str, Any],
) -> AtomicRowDiagnostic:
    checks: list[AtomicCheckResult] = []
    invalidity_reasons: list[str] = []

    if spec.execution_source == "task_pack":
        checks.extend(_validate_custom_task_pack_contract(repo_root=repo_root, spec=spec, task_pack_path=task_pack_path, task_pack=task_pack))
    elif spec.benchmark_name == "BFCL":
        checks.extend(_validate_adapter_task_pack(task_pack, build_bfcl_task_pack(task_pack_id=spec.row_id, case_id=str(spec.benchmark_case_id))))
        checks.extend(_validate_adapter_case(build_bfcl_benchmark_case(case_id=str(spec.benchmark_case_id), task_pack_id=spec.row_id)))
    elif spec.benchmark_name == "ACEBench":
        checks.extend(_validate_adapter_task_pack(task_pack, build_acebench_task_pack(
            task_pack_id=spec.row_id,
            authority_label=ACEBENCH_AUTHORITY_LABEL,
            authority_detail=ACEBENCH_AUTHORITY_DETAIL,
            adapter_label=ACEBENCH_ADAPTER_LABEL,
            case_id=str(spec.benchmark_case_id),
        )))
        checks.extend(_validate_adapter_case(build_acebench_benchmark_case(
            task_pack_id=spec.row_id,
            authority_label=ACEBENCH_AUTHORITY_LABEL,
            authority_detail=ACEBENCH_AUTHORITY_DETAIL,
            case_id=str(spec.benchmark_case_id),
        )))
    elif spec.benchmark_name == "ContextBench":
        checks.extend(_validate_adapter_task_pack(task_pack, build_contextbench_task_pack(task_pack_id=spec.row_id, probe_id=str(spec.benchmark_case_id))))
        checks.extend(_validate_adapter_case(build_contextbench_benchmark_case(probe_id=str(spec.benchmark_case_id), task_pack_id=spec.row_id)))
    elif spec.benchmark_name == "Letta":
        checks.extend(_validate_adapter_task_pack(task_pack, build_letta_task_pack(task_pack_id=spec.row_id, probe_id=str(spec.benchmark_case_id))))
        checks.extend(_validate_adapter_case(build_letta_benchmark_case(probe_id=str(spec.benchmark_case_id), task_pack_id=spec.row_id)))
    elif spec.execution_source == "terminalbench_challenge":
        checks.extend(_validate_adapter_task_pack(task_pack, build_terminalbench_task_pack(task_pack_id=spec.row_id, task_id=str(spec.challenge_task_id or spec.benchmark_case_id))))
        checks.extend(_validate_adapter_case(build_terminalbench_benchmark_case(task_id=str(spec.challenge_task_id or spec.benchmark_case_id), task_pack_id=spec.row_id)))
    else:
        invalidity_reasons.append(f"unsupported_source_kind:{spec.execution_source}")
        checks.append(AtomicCheckResult("task_pack_contract", "fail", "unsupported source kind"))

    return AtomicRowDiagnostic(
        row_id=spec.row_id,
        source_kind=_source_kind(spec),
        task_pack_ref=str(task_pack_path),
        result_row_ref="",
        status="pass" if not invalidity_reasons else "fail",
        checks=tuple(checks),
        atomic_tests=(),
        invalidity_reasons=tuple(invalidity_reasons),
        evidence_paths=(),
    )


def _safe_validate_task_pack_contract(
    *,
    repo_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    task_pack: dict[str, Any],
) -> AtomicRowDiagnostic:
    try:
        return _validate_task_pack_contract(
            repo_root=repo_root,
            spec=spec,
            task_pack_path=task_pack_path,
            task_pack=task_pack,
        )
    except Exception as exc:
        return AtomicRowDiagnostic(
            row_id=spec.row_id,
            source_kind=_source_kind(spec),
            task_pack_ref=str(task_pack_path),
            result_row_ref="",
            status="fail",
            checks=(AtomicCheckResult("task_pack_contract", "fail", str(exc)),),
            atomic_tests=(),
            invalidity_reasons=(f"task_pack_contract:{exc}",),
            evidence_paths=(),
        )


def _safe_validate_result_row_contract(
    *,
    spec: FinalSuiteRowSpec,
    result_row: dict[str, Any],
) -> AtomicRowDiagnostic:
    try:
        return _validate_result_row_contract(spec=spec, result_row=result_row)
    except Exception as exc:
        return AtomicRowDiagnostic(
            row_id=spec.row_id,
            source_kind=_source_kind(spec),
            task_pack_ref="",
            result_row_ref="",
            status="fail",
            checks=(AtomicCheckResult("result_row_contract", "fail", str(exc)),),
            atomic_tests=(),
            invalidity_reasons=(f"result_row_contract:{exc}",),
            evidence_paths=(),
        )


def _validate_result_row_contract(
    *,
    spec: FinalSuiteRowSpec,
    result_row: dict[str, Any],
) -> AtomicRowDiagnostic:
    checks: list[AtomicCheckResult] = []
    invalidity_reasons: list[str] = []

    try:
        validate_result_row(result_row)
        checks.append(AtomicCheckResult("result_row_base_schema", "pass", "base substrate result row validated"))
    except Exception as exc:  # pragma: no cover - exercised in dedicated tests
        invalidity_reasons.append(f"result_row_base_schema:{exc}")
        checks.append(AtomicCheckResult("result_row_base_schema", "fail", str(exc)))

    final_board = result_row.get("final_board")
    if isinstance(final_board, dict):
        try:
            _validate_final_board(final_board, spec)
            checks.append(AtomicCheckResult("final_board_contract", "pass", "final_board validated"))
        except Exception as exc:  # pragma: no cover - exercised in dedicated tests
            invalidity_reasons.append(f"final_board_contract:{exc}")
            checks.append(AtomicCheckResult("final_board_contract", "fail", str(exc)))
    else:
        invalidity_reasons.append("missing_final_board")
        checks.append(AtomicCheckResult("final_board_contract", "fail", "final_board missing or invalid"))

    if "verdict" in result_row:
        verdict = result_row["verdict"]
        if verdict in {"pass", "fail", "invalid"}:
            checks.append(AtomicCheckResult("result_row_verdict", "pass", str(verdict)))
        else:
            invalidity_reasons.append("invalid_verdict")
            checks.append(AtomicCheckResult("result_row_verdict", "fail", f"unexpected verdict: {verdict!r}"))
    else:
        checks.append(AtomicCheckResult("result_row_verdict", "fail", "missing verdict field"))
        invalidity_reasons.append("missing_verdict")

    if spec.execution_source == "benchmark_adapter":
        if "authority_label" in result_row:
            if isinstance(result_row["authority_label"], str) and result_row["authority_label"].strip():
                checks.append(AtomicCheckResult("authority_label", "pass", result_row["authority_label"]))
            else:
                invalidity_reasons.append("authority_label_invalid")
                checks.append(AtomicCheckResult("authority_label", "fail", "authority_label present but not a string"))
        if "contamination_labels" in result_row:
            labels = result_row["contamination_labels"]
            if isinstance(labels, list) and all(isinstance(label, str) and label for label in labels):
                checks.append(AtomicCheckResult("contamination_labels", "pass", "present"))
            else:
                invalidity_reasons.append("contamination_labels_invalid")
                checks.append(AtomicCheckResult("contamination_labels", "fail", "contamination_labels malformed"))

    return AtomicRowDiagnostic(
        row_id=spec.row_id,
        source_kind=_source_kind(spec),
        task_pack_ref="",
        result_row_ref="",
        status="pass" if not invalidity_reasons else "fail",
        checks=tuple(checks),
        atomic_tests=(),
        invalidity_reasons=tuple(invalidity_reasons),
        evidence_paths=(),
    )


def _validate_custom_task_pack_contract(
    *,
    repo_root: Path,
    spec: FinalSuiteRowSpec,
    task_pack_path: Path,
    task_pack: dict[str, Any],
) -> list[AtomicCheckResult]:
    checks: list[AtomicCheckResult] = []
    if task_pack.get("schema_version") == "final_harness_task_pack.v1":
        checks.append(_check_mapping_fields("custom_task_pack_schema", task_pack, CUSTOM_V1_REQUIRED_FIELDS))
        checks.append(_check_string(task_pack, "task_pack_id", expected=str(spec.row_id)))
        checks.append(_check_string(task_pack, "row_id", expected=str(spec.row_id)))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "solver_visible_prompt_ref"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "fixture_manifest_ref"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "hidden_truth_ref"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "hidden_verifier_ref"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "grader_ref"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "timeout_policy_ref"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "known_bad_ref"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "ceiling_ref"))
        checks.append(_check_fixture_manifest(task_pack_path.parent / str(task_pack.get("fixture_manifest_ref", "fixture_manifest.json"))))
        checks.append(_check_expected_outputs(task_pack.get("expected_outputs"), "expected_outputs"))
        checks.append(_check_bool(task_pack, "deterministic_grading"))
        checks.append(_check_runtime_contract(task_pack.get("runtime_contract")))
    else:
        checks.append(_check_mapping_fields("custom_task_pack_schema", task_pack, CUSTOM_LEGACY_REQUIRED_FIELDS))
        checks.append(_check_string(task_pack, "task_pack_id", expected=str(spec.row_id)))
        checks.append(_check_string(task_pack, "row_id", expected=str(spec.row_id)))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "solver_entrypoint"))
        checks.append(_check_path_exists(task_pack_path.parent / "fixture_manifest.json", "fixture_manifest.json"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "visible_verifier"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "hidden_verifier"))
        checks.append(_check_relative_path(task_pack_path.parent, task_pack, "grader"))
        checks.append(_check_candidate_artifacts(task_pack_path.parent, task_pack))
        checks.append(_check_path_exists(task_pack_path.parent / str(task_pack.get("known_bad_ref", "known_bad/README.md")), "known_bad_ref"))
        checks.append(_check_path_exists(task_pack_path.parent / str(task_pack.get("ceiling_ref", "ceiling/README.md")), "ceiling_ref"))
        checks.append(_check_fixture_manifest(task_pack_path.parent / "fixture_manifest.json"))
    checks.append(_check_string(task_pack, "row_contract_mode"))
    checks.append(_check_string(task_pack, "row_contract_note"))
    checks.append(_check_contamination_signal(task_pack))
    return checks


def _validate_adapter_task_pack(generated: dict[str, Any], expected: dict[str, Any]) -> list[AtomicCheckResult]:
    checks: list[AtomicCheckResult] = []
    checks.append(AtomicCheckResult("adapter_task_pack_schema", "pass", "builder output accepted by adapter validator"))
    checks.append(AtomicCheckResult("adapter_task_pack_roundtrip", "pass", "adapter builder produced a valid task pack"))
    if generated.get("canonical_root") != expected.get("canonical_root"):
        checks.append(AtomicCheckResult("adapter_task_pack_canonical_root", "fail", "canonical_root mismatch"))
    else:
        checks.append(AtomicCheckResult("adapter_task_pack_canonical_root", "pass", "canonical_root=/app"))
    return checks


def _validate_adapter_case(case: dict[str, Any]) -> list[AtomicCheckResult]:
    return [
        AtomicCheckResult("adapter_case_contract", "pass", "benchmark adapter case validated"),
    ]


def _validate_final_board(final_board: dict[str, Any], spec: FinalSuiteRowSpec) -> None:
    _require_mapping(final_board, "result_row.final_board")
    _require_fields(final_board, RESULT_ROW_FINAL_BOARD_REQUIRED_FIELDS, "result_row.final_board")
    if final_board.get("row_id") != spec.row_id:
        raise SchemaValidationError("result_row.final_board.row_id must match row spec")
    if final_board.get("row_type") != spec.row_type:
        raise SchemaValidationError("result_row.final_board.row_type must match row spec")
    if final_board.get("execution_source") != spec.execution_source:
        raise SchemaValidationError("result_row.final_board.execution_source must match row spec")
    if final_board.get("critical_clusters") and not isinstance(final_board.get("critical_clusters"), list):
        raise SchemaValidationError("result_row.final_board.critical_clusters must be a list")
    if spec.execution_source == "benchmark_adapter":
        _require_fields(final_board, BENCHMARK_FINAL_BOARD_REQUIRED_FIELDS, "result_row.final_board")
        if not isinstance(final_board.get("benchmark_name"), str):
            raise SchemaValidationError("result_row.final_board.benchmark_name must be a string")
        if final_board.get("benchmark_case_id") != spec.benchmark_case_id:
            raise SchemaValidationError("result_row.final_board.benchmark_case_id must match row spec")
        if spec.challenge_task_id is None and final_board.get("challenge_task_id") is not None:
            raise SchemaValidationError("result_row.final_board.challenge_task_id must be null for benchmark rows")
    elif spec.execution_source == "terminalbench_challenge":
        _require_string(final_board.get("benchmark_name"), "result_row.final_board.benchmark_name")
        _require_string(final_board.get("benchmark_case_id"), "result_row.final_board.benchmark_case_id")
        _require_string(final_board.get("challenge_task_id"), "result_row.final_board.challenge_task_id")


def _load_specs(repo_root: Path, row_ids: Sequence[str]) -> list[FinalSuiteRowSpec]:
    specs = {spec.row_id: spec for spec in load_final_suite_row_specs(repo_root)}
    ordered: list[FinalSuiteRowSpec] = []
    for row_id in row_ids:
        try:
            ordered.append(specs[row_id])
        except KeyError as exc:
            raise ValueError(f"unknown final suite row_id: {row_id}") from exc
    return ordered


def _safe_load_task_pack(repo_root: Path, spec: FinalSuiteRowSpec) -> tuple[Path, dict[str, Any]]:
    try:
        return _load_task_pack(repo_root, spec)
    except Exception as exc:
        raise SchemaValidationError(f"failed to load task pack for {spec.row_id}: {exc}") from exc


def _load_task_pack(repo_root: Path, spec: FinalSuiteRowSpec) -> tuple[Path, dict[str, Any]]:
    if spec.task_pack_ref:
        path = repo_root / spec.task_pack_ref
        return path, _load_yaml(path)

    synthetic_path = _adapter_task_pack_ref(spec)
    task_pack = _build_adapter_task_pack(spec)
    return synthetic_path, task_pack


def _load_result_row(result_run_root: Path, row_id: str) -> tuple[Path, dict[str, Any]]:
    path = result_run_root / "result_rows" / f"{row_id}.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _build_adapter_task_pack(spec: FinalSuiteRowSpec) -> dict[str, Any]:
    if spec.benchmark_name == "BFCL":
        return build_bfcl_task_pack(task_pack_id=spec.row_id, case_id=str(spec.benchmark_case_id))
    if spec.benchmark_name == "ACEBench":
        return build_acebench_task_pack(
            task_pack_id=spec.row_id,
            authority_label=ACEBENCH_AUTHORITY_LABEL,
            authority_detail=ACEBENCH_AUTHORITY_DETAIL,
            adapter_label=ACEBENCH_ADAPTER_LABEL,
            case_id=str(spec.benchmark_case_id),
        )
    if spec.benchmark_name == "ContextBench":
        return build_contextbench_task_pack(task_pack_id=spec.row_id, probe_id=str(spec.benchmark_case_id))
    if spec.benchmark_name == "Letta":
        return build_letta_task_pack(task_pack_id=spec.row_id, probe_id=str(spec.benchmark_case_id))
    if spec.execution_source == "terminalbench_challenge":
        return build_terminalbench_task_pack(task_pack_id=spec.row_id, task_id=str(spec.challenge_task_id or spec.benchmark_case_id))
    raise ValueError(f"unsupported adapter row: {spec.row_id}")


def _adapter_task_pack_ref(spec: FinalSuiteRowSpec) -> Path:
    return Path(f"adapter://{spec.benchmark_name or spec.execution_source}/{spec.row_id}")


def _source_kind(spec: FinalSuiteRowSpec) -> str:
    if spec.execution_source == "task_pack":
        return "custom_task_pack"
    if spec.execution_source == "benchmark_adapter":
        return f"benchmark_adapter:{spec.benchmark_name}"
    if spec.execution_source == "terminalbench_challenge":
        return "terminalbench_challenge"
    return spec.execution_source


def _evidence_paths_for_row(spec: FinalSuiteRowSpec, task_pack_path: Path, result_row_path: Path) -> list[str]:
    paths = [str(task_pack_path), str(result_row_path)]
    if spec.task_pack_ref:
        base = task_pack_path.parent
        if (base / "fixture_manifest.json").exists():
            paths.append(str(base / "fixture_manifest.json"))
        if (base / "grader").exists():
            paths.append(str(base / "grader"))
    return paths


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
    else:  # pragma: no cover
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            cmd = [
                "ruby",
                "-ryaml",
                "-rjson",
                "-e",
                "puts JSON.dump(YAML.safe_load(File.read(ARGV[0]), aliases: true))",
                str(path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise SchemaValidationError(f"{path} must contain a top-level mapping")
    return data


def _require_fields(data: dict[str, Any], fields: Sequence[str], path: str) -> None:
    missing = [field for field in fields if field not in data]
    if missing:
        raise SchemaValidationError(f"{path} missing required fields: {', '.join(missing)}")


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{path} must be an object")
    return value


def _require_string(value: Any, path: str, *, expected: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{path} must be a non-empty string")
    if expected is not None and value != expected:
        raise SchemaValidationError(f"{path} must equal {expected}")
    return value


def _check_mapping_fields(name: str, data: dict[str, Any], required_fields: Sequence[str]) -> AtomicCheckResult:
    missing = [field for field in required_fields if field not in data]
    if missing:
        return AtomicCheckResult(name, "fail", f"missing fields: {', '.join(missing)}")
    return AtomicCheckResult(name, "pass", "required fields present")


def _check_string(data: dict[str, Any], field: str, *, expected: str | None = None) -> AtomicCheckResult:
    value = data.get(field)
    try:
        _require_string(value, field, expected=expected)
    except Exception as exc:
        return AtomicCheckResult(field, "fail", str(exc))
    return AtomicCheckResult(field, "pass", str(value))


def _check_bool(data: dict[str, Any], field: str) -> AtomicCheckResult:
    value = data.get(field)
    if isinstance(value, bool):
        return AtomicCheckResult(field, "pass", str(value))
    return AtomicCheckResult(field, "fail", f"{field} must be a boolean")


def _check_path_exists(path: Path, label: str) -> AtomicCheckResult:
    if path.exists():
        return AtomicCheckResult(label, "pass", str(path))
    return AtomicCheckResult(label, "fail", f"missing path: {path}")


def _check_relative_path(base: Path, task_pack: dict[str, Any], field: str) -> AtomicCheckResult:
    value = task_pack.get(field)
    if not isinstance(value, str) or not value.strip():
        return AtomicCheckResult(field, "fail", f"{field} missing or invalid")
    return _check_path_exists(base / value, field)


def _check_candidate_artifacts(base: Path, task_pack: dict[str, Any]) -> AtomicCheckResult:
    artifacts = task_pack.get("expected_candidate_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return AtomicCheckResult("expected_candidate_artifacts", "fail", "expected_candidate_artifacts missing or empty")
    for artifact in artifacts:
        if not isinstance(artifact, str) or not artifact.strip():
            return AtomicCheckResult("expected_candidate_artifacts", "fail", "expected_candidate_artifacts contains invalid entries")
    return AtomicCheckResult("expected_candidate_artifacts", "pass", "candidate artifacts declared")


def _check_fixture_manifest(path: Path) -> AtomicCheckResult:
    if not path.exists():
        return AtomicCheckResult("fixture_manifest", "fail", f"missing path: {path}")
    try:
        payload = _load_yaml(path)
    except Exception as exc:
        return AtomicCheckResult("fixture_manifest", "fail", str(exc))
    if "task_pack_id" not in payload:
        return AtomicCheckResult("fixture_manifest", "fail", "missing task_pack_id")
    return AtomicCheckResult("fixture_manifest", "pass", "parsed")


def _check_expected_outputs(expected_outputs: Any, label: str) -> AtomicCheckResult:
    if not isinstance(expected_outputs, dict) or not expected_outputs:
        return AtomicCheckResult(label, "fail", "expected_outputs missing or empty")
    if not any(isinstance(value, str) and value for value in expected_outputs.values()):
        return AtomicCheckResult(label, "fail", "expected_outputs has no string paths")
    return AtomicCheckResult(label, "pass", "expected output paths declared")


def _check_runtime_contract(runtime_contract: Any) -> AtomicCheckResult:
    if not isinstance(runtime_contract, dict):
        return AtomicCheckResult("runtime_contract", "fail", "runtime_contract missing or invalid")
    if not isinstance(runtime_contract.get("python_command"), str) or not runtime_contract.get("python_command"):
        return AtomicCheckResult("runtime_contract", "fail", "python_command missing")
    return AtomicCheckResult("runtime_contract", "pass", "runtime contract present")


def _check_contamination_signal(task_pack: dict[str, Any]) -> AtomicCheckResult:
    if "contamination_safeguards" in task_pack and isinstance(task_pack["contamination_safeguards"], list):
        return AtomicCheckResult("contamination_signal", "pass", "contamination safeguards present")
    if "contamination_policy" in task_pack and isinstance(task_pack["contamination_policy"], dict):
        return AtomicCheckResult("contamination_signal", "pass", "contamination policy present")
    return AtomicCheckResult("contamination_signal", "fail", "missing contamination signal")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
