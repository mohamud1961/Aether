"""Workspace delta snapshots and durable evidence ledger helpers for HarnessEng Aether-2."""

from __future__ import annotations

from dataclasses import dataclass, field, replace as dataclass_replace
from pathlib import Path
from typing import Any, Iterable, Mapping
import hashlib
import json
import os
import re
import time

from harness.aether2.traces.kernel_artifacts import _sha256_file, build_artifact_record


_IGNORED_DIR_NAMES = {
    ".git",
    ".aether2",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}

_REGISTRY_FILENAMES = {
    "service_registry": ("service_registry.json",),
    "process_registry": ("process_registry.json",),
    "job_registry": ("job_registry.json", "jobs.json"),
    "session_registry": ("session_registry.json", "sessions.json"),
}

_EVIDENCE_LEDGER_VERSION = 1
_VALID_REQUIREMENT_STATUSES = {"unproven", "partial", "proven", "contradicted"}
_VALID_EVIDENCE_STRENGTHS = {"none", "weak", "moderate", "strong"}
_VALID_BLOCKER_STATUSES = {"active", "candidate_resolved", "resolved", "obsolete", "exhausted"}
_REQUIREMENT_LIST_LIMITS = {
    "evidence_refs": 6,
    "evidence_provenance": 6,
    "failed_checks": 4,
    "disproven_assumptions": 4,
    "open_risks": 4,
    "verifier_blockers": 4,
    "next_required_evidence": 4,
}
_MAX_REQUIREMENTS = 24
_MAX_FAILURE_FAMILIES = 8
_MAX_BLOCKERS = 48
_MAX_TERMINAL_CLAIMS = 24
_BLOCKER_LIST_LIMITS = {
    "reason_codes": 6,
    "rejected_evidence_refs": 6,
    "rejected_evidence_provenance": 6,
    "required_next_evidence": 4,
}
_TERMINAL_CLAIM_LIST_LIMITS = {
    "requirements": 8,
    "evidence_refs": 6,
    "evidence_provenance": 6,
    "known_limitations": 6,
    "attempts": 6,
    "missing_external_state": 6,
    "recommended_next_evidence": 6,
}
_VERIFIER_INTEGRITY_REQUIREMENT = "verifier report integrity"
_TOKEN_RE = re.compile(r"[a-z0-9_./:-]+")
_RELEVANCE_STOPWORDS = {
    "a",
    "after",
    "already",
    "an",
    "and",
    "artifact",
    "artifacts",
    "be",
    "check",
    "confirmed",
    "direct",
    "evidence",
    "for",
    "fresh",
    "from",
    "in",
    "is",
    "it",
    "log",
    "of",
    "or",
    "proof",
    "ref",
    "repair",
    "requirement",
    "rerun",
    "step",
    "the",
    "to",
    "verifier",
    "visible",
    "with",
    "would",
}


def build_evidence_ledger(requirements: Iterable[str] | None = None) -> dict[str, Any]:
    entries = [_new_requirement_entry(requirement) for requirement in requirements or ()]
    return compact_evidence_ledger(
        {
            "version": _EVIDENCE_LEDGER_VERSION,
            "requirements": entries,
            "blockers": [],
            "terminal_claims": [],
            "repeated_failure_families": [],
        }
    )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass(frozen=True)
class FileDelta:
    path: str
    hash_before: str | None
    hash_after: str | None
    change_type: str


@dataclass(frozen=True)
class StateSnapshot:
    workspace_root: str
    captured_at: float
    files: dict[str, str]
    artifact_registry: dict[str, dict[str, Any]]
    service_registry: dict[str, dict[str, Any]]
    process_registry: dict[str, dict[str, Any]]
    job_registry: dict[str, dict[str, Any]]
    session_registry: dict[str, dict[str, Any]]
    # Cumulative, run-level facts that are NOT derivable from a single filesystem
    # snapshot: package-manager command successes and nonzero-exit commands seen
    # so far. Populated externally (loop.py / ExecutionContext) via
    # dataclasses.replace(); defaulted to empty here so plain snapshot()/diff()
    # callers are unaffected.
    installed_packages: tuple[str, ...] = ()
    nonzero_exits: tuple[dict[str, Any], ...] = ()
    evidence_ledger: dict[str, Any] = field(
        default_factory=lambda: {
            "version": _EVIDENCE_LEDGER_VERSION,
            "requirements": [],
            "blockers": [],
            "terminal_claims": [],
            "repeated_failure_families": [],
        }
    )


@dataclass(frozen=True)
class DeltaReport:
    workspace_root: str
    captured_at: float
    files_changed: list[FileDelta]
    artifact_registry_changed: bool
    service_registry_changed: bool
    process_registry_changed: bool
    job_registry_changed: bool
    session_registry_changed: bool
    added_paths: tuple[str, ...]
    modified_paths: tuple[str, ...]
    deleted_paths: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.files_changed and not any(
            (
                self.artifact_registry_changed,
                self.service_registry_changed,
                self.process_registry_changed,
                self.job_registry_changed,
                self.session_registry_changed,
            )
        )


def snapshot(workspace_root: Path) -> StateSnapshot:
    """Capture a conservative workspace snapshot from visible files and local registries."""

    root = workspace_root.resolve(strict=False)
    files: dict[str, str] = {}
    artifact_registry: dict[str, dict[str, Any]] = {}

    for path in _iter_visible_files(root):
        relative = path.relative_to(root).as_posix()
        files[relative] = _sha256_file(path)
        artifact_registry[relative] = build_artifact_record(
            path=relative,
            workspace_root=root,
            generated=None,
        )

    return StateSnapshot(
        workspace_root=root.as_posix(),
        captured_at=time.time(),
        files=files,
        artifact_registry=artifact_registry,
        service_registry=_load_registry(root, "service_registry"),
        process_registry=_load_registry(root, "process_registry"),
        job_registry=_load_job_registry(root),
        session_registry=_load_session_registry(root),
    )


def ensure_stated_requirements(
    ledger: Mapping[str, Any] | None,
    requirements: Iterable[str] | None,
) -> dict[str, Any]:
    normalized = compact_evidence_ledger(ledger)
    requirement_map = _requirement_map(normalized)
    for requirement in requirements or ():
        text = _clean_text(requirement)
        if not text or text in requirement_map:
            continue
        requirement_map[text] = _new_requirement_entry(text)
    normalized["requirements"] = list(requirement_map.values())
    return compact_evidence_ledger(normalized)


def record_observation_evidence(
    ledger: Mapping[str, Any] | None,
    *,
    requirement: str,
    tool_name: str,
    step: int | None = None,
    exit_code: int | None = None,
    raw_log_path: str | None = None,
    artifact_paths: Iterable[str] | None = None,
    note: str | None = None,
    disproved_assumption: str | None = None,
    open_risk: str | None = None,
    verifier_blocker: str | None = None,
    next_required_evidence: str | None = None,
    failure_family: str | None = None,
) -> dict[str, Any]:
    normalized = compact_evidence_ledger(ledger)
    entry = _ensure_requirement_entry(normalized, requirement)
    artifacts = [_clean_text(path) for path in artifact_paths or () if _clean_text(path)]
    evidence_ref = _build_observation_ref(
        tool_name=tool_name,
        step=step,
        exit_code=exit_code,
        raw_log_path=raw_log_path,
        artifact_paths=artifacts,
        note=note,
    )

    if exit_code == 0 and (artifacts or _clean_text(note)):
        entry["evidence_refs"] = _append_capped(
            entry["evidence_refs"],
            evidence_ref,
            limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"],
        )
        if entry["status"] == "unproven":
            entry["status"] = "partial"
        if entry["evidence_strength"] == "none":
            entry["evidence_strength"] = "weak"
        entry["next_required_evidence"] = _append_capped(
            entry["next_required_evidence"],
            _clean_text(next_required_evidence)
            or f"direct visible proof for requirement: {entry['requirement']}",
            limit=_REQUIREMENT_LIST_LIMITS["next_required_evidence"],
        )

    if _clean_text(disproved_assumption):
        entry["disproven_assumptions"] = _append_capped(
            entry["disproven_assumptions"],
            _clean_text(disproved_assumption),
            limit=_REQUIREMENT_LIST_LIMITS["disproven_assumptions"],
        )
    if _clean_text(open_risk):
        entry["open_risks"] = _append_capped(
            entry["open_risks"],
            _clean_text(open_risk),
            limit=_REQUIREMENT_LIST_LIMITS["open_risks"],
        )
    if _clean_text(verifier_blocker):
        entry["verifier_blockers"] = _append_capped(
            entry["verifier_blockers"],
            _clean_text(verifier_blocker),
            limit=_REQUIREMENT_LIST_LIMITS["verifier_blockers"],
        )
    if _clean_text(next_required_evidence):
        entry["next_required_evidence"] = _append_capped(
            entry["next_required_evidence"],
            _clean_text(next_required_evidence),
            limit=_REQUIREMENT_LIST_LIMITS["next_required_evidence"],
        )
    if exit_code not in (None, 0):
        family = _clean_text(failure_family) or "tool_observation_nonzero_exit"
        _record_failure_family(normalized, family=family, evidence_ref=evidence_ref)

    return compact_evidence_ledger(normalized)


def record_check_results(
    ledger: Mapping[str, Any] | None,
    *,
    requirement: str,
    check_results: Iterable[Any],
    step: int | None = None,
    raw_log_path: str | None = None,
) -> dict[str, Any]:
    normalized = compact_evidence_ledger(ledger)
    entry = _ensure_requirement_entry(normalized, requirement)
    for result in check_results:
        command = _clean_text(_read_attr(result, "command"))
        exit_code = _coerce_int(_read_attr(result, "exit_code"))
        timed_out = bool(_read_attr(result, "timed_out", False))
        reason_code = _clean_text(_read_attr(result, "error_reason_code"))
        error_kind = _clean_text(_read_attr(result, "error_kind"))
        evidence_ref = _build_check_ref(
            command=command,
            step=step,
            exit_code=exit_code,
            raw_log_path=raw_log_path,
            reason_code=reason_code,
            error_kind=error_kind,
            timed_out=timed_out,
        )

        if exit_code == 0 and not timed_out:
            entry["evidence_refs"] = _append_capped(
                entry["evidence_refs"],
                evidence_ref,
                limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"],
            )
            if entry["status"] == "unproven":
                entry["status"] = "partial"
            if entry["evidence_strength"] == "none":
                entry["evidence_strength"] = "weak"
            entry["next_required_evidence"] = _append_capped(
                entry["next_required_evidence"],
                f"fresh requirement-level verification for: {entry['requirement']}",
                limit=_REQUIREMENT_LIST_LIMITS["next_required_evidence"],
            )
            continue

        summary = (
            f"cmd={command or '<unknown>'} exit={exit_code if exit_code is not None else 'none'}"
            + (" timed_out=true" if timed_out else "")
            + (f" reason={reason_code}" if reason_code else "")
            + (f" kind={error_kind}" if error_kind else "")
        )
        entry["failed_checks"] = _append_capped(
            entry["failed_checks"],
            summary,
            limit=_REQUIREMENT_LIST_LIMITS["failed_checks"],
        )
        entry["evidence_refs"] = _append_capped(
            entry["evidence_refs"],
            evidence_ref,
            limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"],
        )
        entry["disproven_assumptions"] = _append_capped(
            entry["disproven_assumptions"],
            f"declared check would verify requirement: {command or '<unknown>'}",
            limit=_REQUIREMENT_LIST_LIMITS["disproven_assumptions"],
        )
        entry["open_risks"] = _append_capped(
            entry["open_risks"],
            f"declared check failed for requirement: {entry['requirement']}",
            limit=_REQUIREMENT_LIST_LIMITS["open_risks"],
        )
        entry["next_required_evidence"] = _append_capped(
            entry["next_required_evidence"],
            f"repair and rerun a visible check for: {entry['requirement']}",
            limit=_REQUIREMENT_LIST_LIMITS["next_required_evidence"],
        )
        entry["status"] = "contradicted"
        entry["evidence_strength"] = "strong"
        _record_failure_family(
            normalized,
            family=_failure_family_from_check(reason_code=reason_code, timed_out=timed_out, exit_code=exit_code),
            evidence_ref=evidence_ref,
        )
    return compact_evidence_ledger(normalized)


def record_verifier_report(
    ledger: Mapping[str, Any] | None,
    *,
    report: Any,
    verifier_ref: str | None = None,
    step: int | None = None,
    exhaustion_round_limit: int = 2,
) -> dict[str, Any]:
    return register_verifier_blockers(
        ledger,
        report=report,
        verifier_ref=verifier_ref,
        step=step,
        exhaustion_round_limit=exhaustion_round_limit,
    )


def record_terminal_claim(
    ledger: Mapping[str, Any] | None,
    *,
    claim: Mapping[str, Any],
    outcome: str,
    step: int | None = None,
    raw_log_path: str | None = None,
) -> dict[str, Any]:
    """Persist a generic terminal claim for later verifier/loop handoff.

    The loop should call this from its terminal claim tools once the claim is
    parsed into a structured mapping. The helper is intentionally claim-shape
    only: it records the claim, but it does not promote the claim to proof.
    """

    normalized = compact_evidence_ledger(ledger)
    claims = list(normalized.get("terminal_claims", []) or [])
    claims.append(
        _normalize_terminal_claim(
            claim,
            outcome=outcome,
            step=step,
            raw_log_path=raw_log_path,
        )
    )
    normalized["terminal_claims"] = _normalize_terminal_claims(claims, limit=_MAX_TERMINAL_CLAIMS)
    return compact_evidence_ledger(normalized)


def _infer_evidence_provenance(
    *,
    requirement: str,
    verdict: str,
    evidence: str,
    report_reason_codes: Iterable[str] | None = None,
    source_requirement: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    """Best-effort, conservative provenance fallback when a verifier finding omits it.

    Stays generic and observable: prefers `unknown` over a confident guess and
    never infers independence from command-text differences alone.
    """

    corpus = " ".join(
        part for part in [_clean_text(requirement), _clean_text(evidence)] if part
    ).lower()
    reason_codes = {str(code).strip().lower() for code in (report_reason_codes or ())}
    labels: list[str] = []

    if any(
        token in corpus
        for token in ("read back", "readback", "cat ", "head ", "tail ", "ls ", "exists", "present")
    ):
        labels.append("readback")
    if any(
        token in corpus
        for token in ("same method", "same heuristic", "self-check", "self check", "circular", "replayed", "same client")
    ):
        labels.append("same_method_check")
    if any(token in corpus for token in ("--help", "--version", "command -v", "which ", "import ")):
        labels.append("model_authored_check")
    if "verifier_parse_failure" in reason_codes or "verifier_schema_failure" in reason_codes:
        labels.append("model_authored_check")

    if not labels:
        labels.append("unknown")

    return tuple(_normalize_string_list(labels, limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"]))


_EVIDENCE_CLASS_VOCABULARY = (
    "external_client_or_protocol",
    "fresh_process_execution",
    "filesystem_or_path_state",
    "service_survival_or_response",
    "provided_check_execution",
    "value_or_invariant_comparison",
    "generic_observation",
)


def _normalize_terminal_evidence_class(
    value: Any,
    *,
    requirement: str,
    evidence: str,
    evidence_provenance: Iterable[str] | None = None,
    report_reason_codes: Iterable[str] | None = None,
) -> str:
    """Return a small, generic required-evidence-class label.

    Prefers an explicitly supplied class (if it is in the known vocabulary),
    otherwise infers conservatively from observable text. Defaults to
    `generic_observation` rather than guessing a specific class.
    """

    explicit = _clean_text(value).lower().replace(" ", "_")
    if explicit in _EVIDENCE_CLASS_VOCABULARY:
        return explicit

    corpus = " ".join(
        part for part in [_clean_text(requirement), _clean_text(evidence)] if part
    ).lower()
    provenance = {str(item).strip().lower() for item in (evidence_provenance or ())}
    reason_codes = {str(code).strip().lower() for code in (report_reason_codes or ())}

    if any(token in corpus for token in ("curl", "http", "client", "request", "response", "external")):
        return "external_client_or_protocol"
    if any(token in corpus for token in ("service", "survive", "survival", "listening", "port", "process")):
        return "service_survival_or_response"
    if any(token in corpus for token in ("fresh process", "new process", "reimport", "restart")):
        return "fresh_process_execution"
    if any(token in corpus for token in ("path", "install", "directory", "filesystem", "artifact")):
        return "filesystem_or_path_state"
    if any(token in corpus for token in ("pytest", "cargo test", "go test", "npm test", "make test", "provided check", "official test")):
        return "provided_check_execution"
    if any(token in corpus for token in ("expected", "actual", "checksum", "hash", "diff", "invariant")):
        return "value_or_invariant_comparison"
    if "proxy" in provenance or "verifier_parse_failure" in reason_codes or "verifier_schema_failure" in reason_codes:
        return "generic_observation"
    return "generic_observation"


def _infer_evidence_classes(
    *,
    evidence_refs: Iterable[str] | None = None,
    failed_checks: Iterable[str] | None = None,
    artifact_paths: Iterable[str] | None = None,
    verifier_refs: Iterable[str] | None = None,
) -> list[str]:
    """Conservatively infer generic evidence classes present in current evidence.

    Used to decide whether new evidence is relevant to a blocker's required
    evidence class. Defaults to an empty list (unknown) rather than guessing.
    """

    corpus = " ".join(
        _clean_text(item)
        for item in [
            *(evidence_refs or ()),
            *(failed_checks or ()),
            *(artifact_paths or ()),
            *(verifier_refs or ()),
        ]
        if _clean_text(item)
    ).lower()
    classes: list[str] = []
    if any(token in corpus for token in ("curl", "http", "client", "request", "response")):
        classes.append("external_client_or_protocol")
    if any(token in corpus for token in ("service", "survive", "survival", "listening", "port", "process")):
        classes.append("service_survival_or_response")
    if any(token in corpus for token in ("fresh process", "new process", "reimport", "restart")):
        classes.append("fresh_process_execution")
    if any(token in corpus for token in ("path", "install", "directory", "filesystem", "artifact")):
        classes.append("filesystem_or_path_state")
    if any(token in corpus for token in ("pytest", "cargo test", "go test", "npm test", "make test", "provided check")):
        classes.append("provided_check_execution")
    if any(token in corpus for token in ("expected", "actual", "checksum", "hash", "diff", "invariant")):
        classes.append("value_or_invariant_comparison")
    return _normalize_string_list(classes, limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"])


def register_verifier_blockers(
    ledger: Mapping[str, Any] | None,
    *,
    report: Any,
    verifier_ref: str | None = None,
    step: int | None = None,
    exhaustion_round_limit: int = 2,
) -> dict[str, Any]:
    normalized = compact_evidence_ledger(ledger)
    summary = _clean_text(_read_attr(report, "summary"))
    step_value = _coerce_step(step, report=report, verifier_ref=verifier_ref)
    report_reason_codes = _normalize_string_list(
        _read_attr(report, "reason_codes", ()) or (),
        limit=_BLOCKER_LIST_LIMITS["reason_codes"],
    )
    seen_blockers_by_requirement: dict[str, set[str]] = {}
    touched_requirements: set[str] = {_VERIFIER_INTEGRITY_REQUIREMENT}

    for item in _read_attr(report, "requirements", ()) or ():
        requirement = _clean_text(_read_attr(item, "requirement"))
        if not requirement:
            continue
        touched_requirements.add(requirement)
        verdict = _normalize_requirement_status(_read_attr(item, "verdict"), default="unproven")
        evidence = _clean_text(_read_attr(item, "evidence"))
        provenance = _normalize_string_list(
            _read_attr(item, "evidence_provenance", ()) or _infer_evidence_provenance(
                requirement=requirement,
                verdict=verdict,
                evidence=evidence,
                report_reason_codes=report_reason_codes,
                source_requirement=_ensure_requirement_entry(normalized, requirement),
            ),
            limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"],
        )
        entry = _ensure_requirement_entry(normalized, requirement)
        if provenance:
            entry["evidence_provenance"] = _normalize_string_list(
                [*entry.get("evidence_provenance", ()), *provenance],
                limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"],
            )
        evidence_ref = _build_verifier_ref(
            requirement=requirement,
            verdict=verdict,
            evidence=evidence or summary,
            verifier_ref=verifier_ref,
        )
        entry["evidence_refs"] = _append_capped(
            entry["evidence_refs"],
            evidence_ref,
            limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"],
        )

        if verdict == "proven":
            entry["status"] = "proven"
            entry["evidence_strength"] = "strong"
            entry["verifier_blockers"] = []
            entry["next_required_evidence"] = []
            _resolve_requirement_blockers(
                normalized,
                requirement=requirement,
                step=step_value,
                resolution_evidence=evidence or summary or f"verifier confirmed requirement: {requirement}",
                verifier_confirmation=evidence_ref,
            )
            continue

        if verdict == "contradicted":
            entry["status"] = "contradicted"
            entry["evidence_strength"] = "strong"
            if evidence:
                entry["open_risks"] = _append_capped(
                    entry["open_risks"],
                    evidence,
                    limit=_REQUIREMENT_LIST_LIMITS["open_risks"],
                )
            entry["disproven_assumptions"] = _append_capped(
                entry["disproven_assumptions"],
                f"requirement already satisfied: {requirement}",
                limit=_REQUIREMENT_LIST_LIMITS["disproven_assumptions"],
            )
            entry["next_required_evidence"] = _append_capped(
                entry["next_required_evidence"],
                f"fresh visible proof after repair for: {requirement}",
                limit=_REQUIREMENT_LIST_LIMITS["next_required_evidence"],
            )
            _record_failure_family(normalized, family="verifier_unsatisfied", evidence_ref=evidence_ref)
        else:
            if entry["status"] == "proven":
                entry["status"] = "partial" if entry["evidence_refs"] else "unproven"
            if evidence:
                entry["open_risks"] = _append_capped(
                    entry["open_risks"],
                    evidence,
                    limit=_REQUIREMENT_LIST_LIMITS["open_risks"],
                )
            _record_failure_family(normalized, family="verifier_unverifiable", evidence_ref=evidence_ref)

        blocker = _build_blocker_from_requirement_finding(
            normalized,
            requirement=requirement,
            verdict=verdict,
            verifier_ref=evidence_ref,
            finding=item,
            report_summary=summary,
            report_reason_codes=report_reason_codes,
            rejected_evidence_provenance=provenance,
        )
        blocker_id = blocker["blocker_id"]
        seen_blockers_by_requirement.setdefault(requirement, set()).add(blocker_id)
        _upsert_blocker(
            normalized,
            blocker,
            step=step_value,
            exhaustion_round_limit=exhaustion_round_limit,
        )

    structure_findings = list(_iter_verifier_structure_findings(report))
    if structure_findings:
        touched_requirements.add(_VERIFIER_INTEGRITY_REQUIREMENT)
    for finding in structure_findings:
        requirement = _VERIFIER_INTEGRITY_REQUIREMENT
        entry = _ensure_requirement_entry(normalized, requirement)
        entry["status"] = "contradicted"
        entry["evidence_strength"] = "strong"
        detail = _clean_text(_read_attr(finding, "detail")) or summary or "verifier report could not be interpreted"
        entry["open_risks"] = _append_capped(
            entry["open_risks"],
            detail,
            limit=_REQUIREMENT_LIST_LIMITS["open_risks"],
        )
        blocker = _build_blocker_from_structure_finding(
            finding=finding,
            verifier_ref=verifier_ref,
            step=step_value,
            report_summary=summary,
        )
        blocker_id = blocker["blocker_id"]
        seen_blockers_by_requirement.setdefault(requirement, set()).add(blocker_id)
        _upsert_blocker(
            normalized,
            blocker,
            step=step_value,
            exhaustion_round_limit=exhaustion_round_limit,
        )
        _record_failure_family(
            normalized,
            family=_clean_text(_read_attr(finding, "failure_family")) or "verifier_structure_failure",
            evidence_ref=verifier_ref,
        )

    _obsolete_unseen_blockers(
        normalized,
        touched_requirements=touched_requirements,
        seen_blockers_by_requirement=seen_blockers_by_requirement,
        step=step_value,
    )

    for code in report_reason_codes:
        _record_failure_family(normalized, family=f"verifier_reason:{code}", evidence_ref=verifier_ref)

    return compact_evidence_ledger(normalized)


def mark_blockers_candidate_resolved(
    ledger: Mapping[str, Any] | None,
    *,
    step: int | None = None,
    requirement: str | None = None,
    blocker_ids: Iterable[str] | None = None,
    relevant_evidence_refs: Iterable[str] | None = None,
    relevant_failed_checks: Iterable[str] | None = None,
    relevant_artifact_paths: Iterable[str] | None = None,
    relevant_verifier_refs: Iterable[str] | None = None,
    relevant_evidence_classes: Iterable[str] | None = None,
) -> dict[str, Any]:
    normalized = compact_evidence_ledger(ledger)
    blocker_id_filter = set(_normalize_string_list(blocker_ids or (), limit=_MAX_BLOCKERS))
    blockers = _blocker_map(normalized)
    for blocker in _iter_target_blockers(
        blockers,
        requirement=requirement,
        blocker_id_filter=blocker_id_filter,
        statuses={"active", "exhausted"},
    ):
        if not _has_relevant_new_evidence(
            normalized,
            blocker=blocker,
            relevant_evidence_refs=relevant_evidence_refs,
            relevant_failed_checks=relevant_failed_checks,
            relevant_artifact_paths=relevant_artifact_paths,
            relevant_verifier_refs=relevant_verifier_refs,
            relevant_evidence_classes=relevant_evidence_classes,
        ):
            continue
        blocker["status"] = "candidate_resolved"
        blocker["last_updated_step"] = _choose_step(step, blocker.get("last_updated_step"))
        blocker["age_steps"] = _compute_age_steps(blocker.get("created_step"), blocker.get("last_updated_step"))
        blocker["evidence_version_last_evaluated"] = _current_blocker_evidence_version(
            normalized,
            blocker=blocker,
            relevant_evidence_refs=relevant_evidence_refs,
            relevant_failed_checks=relevant_failed_checks,
            relevant_artifact_paths=relevant_artifact_paths,
            relevant_verifier_refs=relevant_verifier_refs,
            relevant_evidence_classes=relevant_evidence_classes,
        )
    normalized["blockers"] = list(blockers.values())
    return compact_evidence_ledger(normalized)


def mark_blockers_exhausted(
    ledger: Mapping[str, Any] | None,
    *,
    step: int | None = None,
    requirement: str | None = None,
    blocker_ids: Iterable[str] | None = None,
    exhaustion_round_limit: int = 2,
    force: bool = False,
) -> dict[str, Any]:
    normalized = compact_evidence_ledger(ledger)
    blocker_id_filter = set(_normalize_string_list(blocker_ids or (), limit=_MAX_BLOCKERS))
    limit = max(1, exhaustion_round_limit)
    blockers = _blocker_map(normalized)
    for blocker in _iter_target_blockers(
        blockers,
        requirement=requirement,
        blocker_id_filter=blocker_id_filter,
        statuses={"active", "candidate_resolved"},
    ):
        if not force and int(blocker.get("candidate_resolution_attempts") or 0) < limit:
            continue
        blocker["status"] = "exhausted"
        blocker["last_updated_step"] = _choose_step(step, blocker.get("last_updated_step"))
        blocker["age_steps"] = _compute_age_steps(blocker.get("created_step"), blocker.get("last_updated_step"))
    normalized["blockers"] = list(blockers.values())
    return compact_evidence_ledger(normalized)


def should_suppress_verifier_call(
    ledger: Mapping[str, Any] | None,
    *,
    requirement: str | None = None,
    blocker_ids: Iterable[str] | None = None,
    relevant_evidence_refs: Iterable[str] | None = None,
    relevant_failed_checks: Iterable[str] | None = None,
    relevant_artifact_paths: Iterable[str] | None = None,
    relevant_verifier_refs: Iterable[str] | None = None,
    relevant_evidence_classes: Iterable[str] | None = None,
) -> bool:
    normalized = compact_evidence_ledger(ledger)
    blocker_id_filter = set(_normalize_string_list(blocker_ids or (), limit=_MAX_BLOCKERS))
    blockers = _blocker_map(normalized)
    active_blockers = list(
        _iter_target_blockers(
            blockers,
            requirement=requirement,
            blocker_id_filter=blocker_id_filter,
            statuses={"active"},
        )
    )
    if not active_blockers:
        return False
    for blocker in active_blockers:
        if _has_relevant_new_evidence(
            normalized,
            blocker=blocker,
            relevant_evidence_refs=relevant_evidence_refs,
            relevant_failed_checks=relevant_failed_checks,
            relevant_artifact_paths=relevant_artifact_paths,
            relevant_verifier_refs=relevant_verifier_refs,
            relevant_evidence_classes=relevant_evidence_classes,
        ):
            return False
    return True


def compute_relevant_evidence_version(
    *,
    requirement: str,
    evidence_refs: Iterable[str] | None = None,
    failed_checks: Iterable[str] | None = None,
    artifact_paths: Iterable[str] | None = None,
    verifier_refs: Iterable[str] | None = None,
    reason_codes: Iterable[str] | None = None,
    evidence_classes: Iterable[str] | None = None,
) -> str:
    payload = {
        "requirement": _clean_text(requirement),
        "artifact_paths": _normalize_string_list(artifact_paths or (), limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"]),
        "evidence_refs": _normalize_string_list(evidence_refs or (), limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"]),
        "failed_checks": _normalize_string_list(failed_checks or (), limit=_REQUIREMENT_LIST_LIMITS["failed_checks"]),
        "evidence_classes": _normalize_string_list(evidence_classes or (), limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"]),
        "reason_codes": _normalize_string_list(reason_codes or (), limit=_BLOCKER_LIST_LIMITS["reason_codes"]),
        "verifier_refs": _normalize_string_list(verifier_refs or (), limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"]),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def serialize_evidence_ledger(ledger: Mapping[str, Any] | None) -> str:
    return json.dumps(
        compact_evidence_ledger(ledger),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def with_evidence_ledger(snapshot: StateSnapshot, ledger: Mapping[str, Any] | None) -> StateSnapshot:
    return dataclass_replace(snapshot, evidence_ledger=compact_evidence_ledger(ledger))


def diff(prev: StateSnapshot, curr: StateSnapshot) -> DeltaReport:
    """Compare two snapshots and return the file and registry deltas."""

    prev_files = dict(prev.files)
    curr_files = dict(curr.files)
    file_paths = sorted(set(prev_files) | set(curr_files))
    file_deltas: list[FileDelta] = []
    added_paths: list[str] = []
    modified_paths: list[str] = []
    deleted_paths: list[str] = []

    for path in file_paths:
        before = prev_files.get(path)
        after = curr_files.get(path)
        if before == after:
            continue
        if before is None:
            file_deltas.append(FileDelta(path=path, hash_before=None, hash_after=after, change_type="added"))
            added_paths.append(path)
        elif after is None:
            file_deltas.append(FileDelta(path=path, hash_before=before, hash_after=None, change_type="deleted"))
            deleted_paths.append(path)
        else:
            file_deltas.append(FileDelta(path=path, hash_before=before, hash_after=after, change_type="modified"))
            modified_paths.append(path)

    return DeltaReport(
        workspace_root=curr.workspace_root,
        captured_at=curr.captured_at,
        files_changed=file_deltas,
        artifact_registry_changed=prev.artifact_registry != curr.artifact_registry,
        service_registry_changed=prev.service_registry != curr.service_registry,
        process_registry_changed=prev.process_registry != curr.process_registry,
        job_registry_changed=prev.job_registry != curr.job_registry,
        session_registry_changed=prev.session_registry != curr.session_registry,
        added_paths=tuple(added_paths),
        modified_paths=tuple(modified_paths),
        deleted_paths=tuple(deleted_paths),
    )


def _iter_visible_files(workspace_root: Path):
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _IGNORED_DIR_NAMES for part in path.parts):
            continue
        yield path


def _load_registry(workspace_root: Path, registry_name: str) -> dict[str, dict[str, Any]]:
    candidates = [workspace_root / f"{filename}" for filename in _REGISTRY_FILENAMES[registry_name]]
    candidates.extend(
        workspace_root / ".aether2" / "state" / f"{filename}"
        for filename in _REGISTRY_FILENAMES[registry_name]
    )
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            return {
                str(key): dict(value) if isinstance(value, dict) else {}
                for key, value in data.items()
                if isinstance(key, str) and key
            }
    return {}


def _load_job_registry(workspace_root: Path) -> dict[str, dict[str, Any]]:
    jobs_dir = workspace_root / ".aether2" / "state" / "jobs"
    if not jobs_dir.exists():
        return _load_registry(workspace_root, "job_registry")
    jobs: dict[str, dict[str, Any]] = {}
    for meta_path in sorted(jobs_dir.glob("*/meta.json")):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        job_id = str(data.get("job_id") or meta_path.parent.name).strip()
        if not job_id:
            continue
        log_path = Path(str(data.get("log_path") or meta_path.parent / "job.log"))
        exit_code_path = Path(str(data.get("exit_code_path") or meta_path.parent / "exit_code"))
        pid = int(data.get("pid") or 0)
        exit_code = None
        if exit_code_path.exists():
            try:
                exit_code = int(exit_code_path.read_text(encoding="utf-8").strip())
            except ValueError:
                exit_code = None
        jobs[job_id] = {
            "pid": pid,
            "cwd": str(data.get("cwd") or ""),
            "alive": _pid_alive(pid) if pid > 0 and exit_code is None else False,
            "exit_code": exit_code,
            "log_path": str(log_path),
            "log_size": log_path.stat().st_size if log_path.exists() else 0,
            "registry_path": str(meta_path),
        }
    if jobs:
        return jobs
    return _load_registry(workspace_root, "job_registry")


def _load_session_registry(workspace_root: Path) -> dict[str, dict[str, Any]]:
    sessions_dir = workspace_root / ".aether2" / "state" / "sessions"
    if not sessions_dir.exists():
        return _load_registry(workspace_root, "session_registry")
    sessions: dict[str, dict[str, Any]] = {}
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        session_id = str(data.get("session_id") or path.stem).strip()
        if not session_id:
            continue
        sessions[session_id] = {
            "command": str(data.get("command") or ""),
            "registry_path": str(path),
        }
    if sessions:
        return sessions
    return _load_registry(workspace_root, "session_registry")


def compact_evidence_ledger(ledger: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized_requirements: list[dict[str, Any]] = []
    requirement_map = _requirement_map(ledger)
    blocker_map = _blocker_map(ledger)
    terminal_claims = _normalize_terminal_claims(
        (ledger or {}).get("terminal_claims", ()) if isinstance(ledger, Mapping) else (),
        limit=_MAX_TERMINAL_CLAIMS,
    )
    blocker_summaries = _blocker_requirement_summaries(blocker_map.values())
    for requirement in sorted(requirement_map):
        entry = requirement_map[requirement]
        blocker_summary = blocker_summaries.get(requirement, {})
        normalized_requirements.append(
            {
                "requirement_id": entry["requirement_id"],
                "requirement": requirement,
                "status": _normalize_requirement_status(entry.get("status"), default="unproven"),
                "evidence_strength": _normalize_evidence_strength(entry.get("evidence_strength"), default="none"),
                "evidence_refs": _normalize_string_list(
                    entry.get("evidence_refs", ()),
                    limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"],
                ),
                "evidence_provenance": _normalize_string_list(
                    entry.get("evidence_provenance", ()),
                    limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"],
                ),
                "failed_checks": _normalize_string_list(
                    entry.get("failed_checks", ()),
                    limit=_REQUIREMENT_LIST_LIMITS["failed_checks"],
                ),
                "disproven_assumptions": _normalize_string_list(
                    entry.get("disproven_assumptions", ()),
                    limit=_REQUIREMENT_LIST_LIMITS["disproven_assumptions"],
                ),
                "open_risks": _normalize_string_list(
                    entry.get("open_risks", ()),
                    limit=_REQUIREMENT_LIST_LIMITS["open_risks"],
                ),
                "verifier_blockers": _normalize_string_list(
                    [
                        *list(entry.get("verifier_blockers", ()) or ()),
                        *list(blocker_summary.get("verifier_blockers", ()) or ()),
                    ],
                    limit=_REQUIREMENT_LIST_LIMITS["verifier_blockers"],
                ),
                "next_required_evidence": _normalize_string_list(
                    [
                        *list(entry.get("next_required_evidence", ()) or ()),
                        *list(blocker_summary.get("next_required_evidence", ()) or ()),
                    ],
                    limit=_REQUIREMENT_LIST_LIMITS["next_required_evidence"],
                ),
            }
        )

    normalized_blockers = _normalize_blockers(
        (ledger or {}).get("blockers", ()) if isinstance(ledger, Mapping) else (),
        limit=_MAX_BLOCKERS,
    )
    normalized_families = _normalize_failure_families(
        (ledger or {}).get("repeated_failure_families", ()) if isinstance(ledger, Mapping) else (),
        limit=_MAX_FAILURE_FAMILIES,
    )

    return {
        "version": _EVIDENCE_LEDGER_VERSION,
        "requirements": normalized_requirements[:_MAX_REQUIREMENTS],
        "blockers": normalized_blockers,
        "terminal_claims": terminal_claims,
        "repeated_failure_families": normalized_families,
    }


def _new_requirement_entry(requirement: str) -> dict[str, Any]:
    cleaned = _clean_text(requirement)
    return {
        "requirement_id": _requirement_id(cleaned),
        "requirement": cleaned,
        "status": "unproven",
        "evidence_strength": "none",
        "evidence_refs": [],
        "evidence_provenance": [],
        "failed_checks": [],
        "disproven_assumptions": [],
        "open_risks": [],
        "verifier_blockers": [],
        "next_required_evidence": [],
    }


def _ensure_requirement_entry(ledger: dict[str, Any], requirement: str) -> dict[str, Any]:
    requirement_map = _requirement_map(ledger)
    text = _clean_text(requirement)
    if not text:
        raise ValueError("requirement must be non-empty")
    if text not in requirement_map:
        requirement_map[text] = _new_requirement_entry(text)
    ledger["requirements"] = list(requirement_map.values())
    return requirement_map[text]


def _requirement_map(ledger: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    requirement_map: dict[str, dict[str, Any]] = {}
    if not isinstance(ledger, Mapping):
        return requirement_map
    for item in ledger.get("requirements", ()) or ():
        if not isinstance(item, Mapping):
            continue
        requirement = _clean_text(item.get("requirement"))
        if not requirement:
            continue
        requirement_map[requirement] = {
            "requirement_id": _clean_text(item.get("requirement_id")) or _requirement_id(requirement),
            "requirement": requirement,
            "status": _normalize_requirement_status(item.get("status"), default="unproven"),
            "evidence_strength": _normalize_evidence_strength(item.get("evidence_strength"), default="none"),
            "evidence_refs": _normalize_string_list(item.get("evidence_refs", ()), limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"]),
            "evidence_provenance": _normalize_string_list(
                item.get("evidence_provenance", ()),
                limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"],
            ),
            "failed_checks": _normalize_string_list(item.get("failed_checks", ()), limit=_REQUIREMENT_LIST_LIMITS["failed_checks"]),
            "disproven_assumptions": _normalize_string_list(
                item.get("disproven_assumptions", ()),
                limit=_REQUIREMENT_LIST_LIMITS["disproven_assumptions"],
            ),
            "open_risks": _normalize_string_list(item.get("open_risks", ()), limit=_REQUIREMENT_LIST_LIMITS["open_risks"]),
            "verifier_blockers": _normalize_string_list(
                item.get("verifier_blockers", ()),
                limit=_REQUIREMENT_LIST_LIMITS["verifier_blockers"],
            ),
            "next_required_evidence": _normalize_string_list(
                item.get("next_required_evidence", ()),
                limit=_REQUIREMENT_LIST_LIMITS["next_required_evidence"],
            ),
        }
    return requirement_map


def _requirement_id(requirement: str) -> str:
    cleaned = _clean_text(requirement)
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12] if cleaned else "unknown"
    return f"req_{digest}"


def _blocker_map(ledger: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    blocker_map: dict[str, dict[str, Any]] = {}
    if not isinstance(ledger, Mapping):
        return blocker_map
    for item in ledger.get("blockers", ()) or ():
        if not isinstance(item, Mapping):
            continue
        blocker = _normalize_blocker(item)
        blocker_map[blocker["blocker_id"]] = blocker
    return blocker_map


def _normalize_blockers(values: Iterable[Any], *, limit: int) -> list[dict[str, Any]]:
    normalized = [_normalize_blocker(value) for value in values or () if isinstance(value, Mapping)]
    normalized.sort(key=_blocker_sort_key)
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit]


def _normalize_blocker(value: Mapping[str, Any]) -> dict[str, Any]:
    requirement = _clean_text(value.get("requirement"))
    requirement_id = _clean_text(value.get("requirement_id")) or _requirement_id(requirement)
    verdict = _normalize_requirement_status(value.get("verdict"), default="unproven")
    reason_codes = _normalize_string_list(value.get("reason_codes", ()), limit=_BLOCKER_LIST_LIMITS["reason_codes"])
    rejected_refs = _normalize_string_list(
        value.get("rejected_evidence_refs", ()),
        limit=_BLOCKER_LIST_LIMITS["rejected_evidence_refs"],
    )
    next_evidence = _normalize_string_list(
        value.get("required_next_evidence", ()),
        limit=_BLOCKER_LIST_LIMITS["required_next_evidence"],
    )
    insufficiency_reason = _clean_text(value.get("insufficiency_reason"))
    blocker_id = _clean_text(value.get("blocker_id")) or _build_blocker_id(
        requirement_id=requirement_id,
        verdict=verdict,
        reason_codes=reason_codes,
        insufficiency_reason=insufficiency_reason,
        required_next_evidence=next_evidence,
    )
    created_step = _coerce_int(value.get("created_step"))
    last_updated_step = _coerce_int(value.get("last_updated_step"))
    status = _normalize_blocker_status(value.get("status"), default="active")
    resolution_evidence = _clean_text(value.get("resolution_evidence"))
    verifier_confirmation = _clean_text(value.get("verifier_confirmation"))
    return {
        "blocker_id": blocker_id,
        "requirement_id": requirement_id,
        "requirement": requirement,
        "verdict": verdict,
        "reason_codes": reason_codes,
        "created_step": created_step,
        "last_updated_step": last_updated_step,
        "age_steps": _coerce_int(value.get("age_steps"))
        if _coerce_int(value.get("age_steps")) is not None
        else _compute_age_steps(created_step, last_updated_step),
        "rejected_evidence_refs": rejected_refs,
        "insufficiency_reason": insufficiency_reason,
        "required_next_evidence": next_evidence,
        "evidence_version_last_evaluated": _clean_text(value.get("evidence_version_last_evaluated")),
        "status": status,
        "resolution_evidence": resolution_evidence,
        "verifier_confirmation": verifier_confirmation,
        "evaluation_rounds": max(1, _coerce_int(value.get("evaluation_rounds")) or 1),
        "candidate_resolution_attempts": max(0, _coerce_int(value.get("candidate_resolution_attempts")) or 0),
    }


def _build_blocker_id(
    *,
    requirement_id: str,
    verdict: str,
    reason_codes: Iterable[str],
    insufficiency_reason: str,
    required_next_evidence: Iterable[str],
    required_evidence_class: str = "",
) -> str:
    payload = {
        "requirement_id": _clean_text(requirement_id),
        "verdict": _normalize_requirement_status(verdict, default="unproven"),
        "reason_codes": _normalize_string_list(reason_codes, limit=_BLOCKER_LIST_LIMITS["reason_codes"]),
        "insufficiency_reason": _clean_text(insufficiency_reason),
        "required_next_evidence": _normalize_string_list(
            required_next_evidence,
            limit=_BLOCKER_LIST_LIMITS["required_next_evidence"],
        ),
        "required_evidence_class": _clean_text(required_evidence_class),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"blk_{digest}"


def _blocker_sort_key(blocker: Mapping[str, Any]) -> tuple[str, int, str]:
    status_rank = {
        "active": 0,
        "candidate_resolved": 1,
        "exhausted": 2,
        "resolved": 3,
        "obsolete": 4,
    }.get(str(blocker.get("status", "active")), 5)
    return (
        _clean_text(blocker.get("requirement")),
        status_rank,
        _clean_text(blocker.get("blocker_id")),
    )


def _blocker_requirement_summaries(blockers: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, list[str]]]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for blocker in blockers:
        status = _normalize_blocker_status(blocker.get("status"), default="active")
        if status in {"resolved", "obsolete"}:
            continue
        requirement = _clean_text(blocker.get("requirement"))
        if not requirement:
            continue
        group = grouped.setdefault(requirement, {"verifier_blockers": [], "next_required_evidence": []})
        label = _clean_text(blocker.get("insufficiency_reason"))
        if label:
            group["verifier_blockers"] = _append_capped(
                group["verifier_blockers"],
                label,
                limit=_REQUIREMENT_LIST_LIMITS["verifier_blockers"],
            )
        for item in blocker.get("required_next_evidence", ()) or ():
            group["next_required_evidence"] = _append_capped(
                group["next_required_evidence"],
                _clean_text(item),
                limit=_REQUIREMENT_LIST_LIMITS["next_required_evidence"],
            )
    return grouped


def _build_blocker_from_requirement_finding(
    ledger: Mapping[str, Any],
    *,
    requirement: str,
    verdict: str,
    verifier_ref: str,
    finding: Any,
    report_summary: str,
    report_reason_codes: list[str],
    rejected_evidence_provenance: Iterable[str] | None = None,
) -> dict[str, Any]:
    requirement_map = _requirement_map(ledger)
    entry = requirement_map.get(requirement) or _new_requirement_entry(requirement)
    reason_codes = _normalize_string_list(
        _read_attr(finding, "reason_codes", ()) or report_reason_codes,
        limit=_BLOCKER_LIST_LIMITS["reason_codes"],
    )
    provenance = _normalize_string_list(
        _read_attr(finding, "evidence_provenance", ()) or rejected_evidence_provenance or (),
        limit=_BLOCKER_LIST_LIMITS["rejected_evidence_provenance"],
    )
    insufficiency_reason = (
        _clean_text(_read_attr(finding, "insufficiency_reason"))
        or _clean_text(_read_attr(finding, "evidence"))
        or report_summary
        or f"verifier lacked decisive visible evidence for: {requirement}"
    )
    rejected_evidence_refs = _normalize_string_list(
        _read_attr(finding, "rejected_evidence_refs", ())
        or _read_attr(finding, "insufficient_evidence_refs", ())
        or entry.get("evidence_refs", ()),
        limit=_BLOCKER_LIST_LIMITS["rejected_evidence_refs"],
    )
    required_next_evidence = _normalize_string_list(
        _read_attr(finding, "required_next_evidence", ())
        or [_default_next_evidence(requirement=requirement, verdict=verdict)],
        limit=_BLOCKER_LIST_LIMITS["required_next_evidence"],
    )
    required_evidence_class = _normalize_terminal_evidence_class(
        _read_attr(finding, "required_evidence_class"),
        requirement=requirement,
        evidence=_clean_text(_read_attr(finding, "evidence")) or report_summary,
        evidence_provenance=provenance,
        report_reason_codes=reason_codes,
    )
    evidence_version = compute_relevant_evidence_version(
        requirement=requirement,
        evidence_refs=entry.get("evidence_refs", ()),
        failed_checks=entry.get("failed_checks", ()),
        verifier_refs=[verifier_ref],
        reason_codes=reason_codes,
        evidence_classes=[required_evidence_class, *provenance],
    )
    requirement_id = entry["requirement_id"]
    return {
        "blocker_id": _build_blocker_id(
            requirement_id=requirement_id,
            verdict=verdict,
            reason_codes=reason_codes,
            insufficiency_reason=insufficiency_reason,
            required_next_evidence=required_next_evidence,
            required_evidence_class=required_evidence_class,
        ),
        "requirement_id": requirement_id,
        "requirement": requirement,
        "verdict": verdict,
        "reason_codes": reason_codes,
        "required_evidence_class": required_evidence_class,
        "created_step": None,
        "last_updated_step": None,
        "age_steps": 0,
        "rejected_evidence_refs": rejected_evidence_refs,
        "rejected_evidence_provenance": provenance,
        "insufficiency_reason": insufficiency_reason,
        "required_next_evidence": required_next_evidence,
        "evidence_version_last_evaluated": evidence_version,
        "status": "active",
        "resolution_evidence": "",
        "verifier_confirmation": "",
        "evaluation_rounds": 1,
        "candidate_resolution_attempts": 0,
    }


def _build_blocker_from_structure_finding(
    *,
    finding: Any,
    verifier_ref: str | None,
    step: int | None,
    report_summary: str,
) -> dict[str, Any]:
    requirement = _VERIFIER_INTEGRITY_REQUIREMENT
    requirement_id = _requirement_id(requirement)
    verdict = "contradicted"
    detail = (
        _clean_text(_read_attr(finding, "detail"))
        or _clean_text(_read_attr(finding, "evidence"))
        or report_summary
        or "verifier report could not be interpreted"
    )
    reason_codes = _normalize_string_list(
        _read_attr(finding, "reason_codes", ()) or [_clean_text(_read_attr(finding, "kind"))],
        limit=_BLOCKER_LIST_LIMITS["reason_codes"],
    )
    next_evidence = _normalize_string_list(
        _read_attr(finding, "required_next_evidence", ())
        or ["repair verifier output shape and rerun verification"],
        limit=_BLOCKER_LIST_LIMITS["required_next_evidence"],
    )
    required_evidence_class = _normalize_terminal_evidence_class(
        _read_attr(finding, "required_evidence_class"),
        requirement=requirement,
        evidence=detail,
        evidence_provenance=("proxy",),
        report_reason_codes=reason_codes,
    )
    evidence_version = compute_relevant_evidence_version(
        requirement=requirement,
        evidence_refs=[detail],
        verifier_refs=[_clean_text(verifier_ref)],
        reason_codes=reason_codes,
        evidence_classes=[required_evidence_class],
    )
    return {
        "blocker_id": _build_blocker_id(
            requirement_id=requirement_id,
            verdict=verdict,
            reason_codes=reason_codes,
            insufficiency_reason=detail,
            required_next_evidence=next_evidence,
            required_evidence_class=required_evidence_class,
        ),
        "requirement_id": requirement_id,
        "requirement": requirement,
        "verdict": verdict,
        "reason_codes": reason_codes,
        "required_evidence_class": required_evidence_class,
        "created_step": step,
        "last_updated_step": step,
        "age_steps": 0,
        "rejected_evidence_refs": _normalize_string_list(
            _read_attr(finding, "rejected_evidence_refs", ()) or (),
            limit=_BLOCKER_LIST_LIMITS["rejected_evidence_refs"],
        ),
        "rejected_evidence_provenance": ["proxy"],
        "insufficiency_reason": detail,
        "required_next_evidence": next_evidence,
        "evidence_version_last_evaluated": evidence_version,
        "status": "active",
        "resolution_evidence": "",
        "verifier_confirmation": "",
        "evaluation_rounds": 1,
        "candidate_resolution_attempts": 0,
    }


def _iter_verifier_structure_findings(report: Any) -> Iterable[dict[str, Any]]:
    parse_items = []
    parse_value = _read_attr(report, "parse_error")
    if parse_value:
        parse_items.append(parse_value)
    parse_items.extend(list(_read_attr(report, "parse_failures", ()) or ()))
    for item in parse_items:
        detail = _clean_text(_read_attr(item, "detail")) or _clean_text(item)
        if not detail:
            continue
        yield {
            "kind": "verifier_parse_failure",
            "detail": detail,
            "reason_codes": _read_attr(item, "reason_codes", ()) or ("verifier_parse_failure",),
            "required_next_evidence": _read_attr(item, "required_next_evidence", ())
            or ("repair verifier output format before retry",),
            "rejected_evidence_refs": _read_attr(item, "rejected_evidence_refs", ()) or (),
            "failure_family": "verifier_parse_failure",
        }

    schema_items = list(_read_attr(report, "schema_errors", ()) or ())
    schema_items.extend(list(_read_attr(report, "schema_failures", ()) or ()))
    for item in schema_items:
        detail = _clean_text(_read_attr(item, "detail")) or _clean_text(item)
        if not detail:
            continue
        yield {
            "kind": "verifier_schema_failure",
            "detail": detail,
            "reason_codes": _read_attr(item, "reason_codes", ()) or ("verifier_schema_failure",),
            "required_next_evidence": _read_attr(item, "required_next_evidence", ())
            or ("repair verifier schema and rerun verification",),
            "rejected_evidence_refs": _read_attr(item, "rejected_evidence_refs", ()) or (),
            "failure_family": "verifier_schema_failure",
        }


def _resolve_requirement_blockers(
    ledger: dict[str, Any],
    *,
    requirement: str,
    step: int | None,
    resolution_evidence: str,
    verifier_confirmation: str,
) -> None:
    blockers = _blocker_map(ledger)
    for blocker in blockers.values():
        if blocker["requirement"] != requirement:
            continue
        if blocker["status"] in {"resolved", "obsolete"}:
            continue
        blocker["status"] = "resolved"
        blocker["resolution_evidence"] = _clean_text(resolution_evidence)
        blocker["verifier_confirmation"] = _clean_text(verifier_confirmation)
        blocker["last_updated_step"] = _choose_step(step, blocker.get("last_updated_step"))
        blocker["age_steps"] = _compute_age_steps(blocker.get("created_step"), blocker.get("last_updated_step"))
    ledger["blockers"] = list(blockers.values())


def _upsert_blocker(
    ledger: dict[str, Any],
    blocker: Mapping[str, Any],
    *,
    step: int | None,
    exhaustion_round_limit: int,
) -> None:
    blockers = _blocker_map(ledger)
    incoming = _normalize_blocker(blocker)
    current = blockers.get(incoming["blocker_id"])
    if current is None:
        incoming["created_step"] = _choose_step(step, incoming.get("created_step"))
        incoming["last_updated_step"] = _choose_step(step, incoming.get("last_updated_step"))
        incoming["age_steps"] = _compute_age_steps(incoming.get("created_step"), incoming.get("last_updated_step"))
        blockers[incoming["blocker_id"]] = incoming
        ledger["blockers"] = list(blockers.values())
        return

    previous_status = current["status"]
    previous_created_step = current.get("created_step")
    previous_last_updated_step = current.get("last_updated_step")
    previous_evaluation_rounds = int(current.get("evaluation_rounds") or 1)
    previous_candidate_attempts = int(current.get("candidate_resolution_attempts") or 0)
    current.update(incoming)
    current["created_step"] = _choose_step(previous_created_step, incoming.get("created_step"))
    current["last_updated_step"] = _choose_step(step, previous_last_updated_step)
    current["age_steps"] = _compute_age_steps(current.get("created_step"), current.get("last_updated_step"))
    current["evaluation_rounds"] = previous_evaluation_rounds + 1
    current["resolution_evidence"] = ""
    current["verifier_confirmation"] = ""
    if previous_status == "candidate_resolved":
        attempts = previous_candidate_attempts + 1
        current["candidate_resolution_attempts"] = attempts
        current["status"] = "exhausted" if attempts >= max(1, exhaustion_round_limit) else "active"
    elif previous_status == "resolved":
        current["status"] = "active"
        current["candidate_resolution_attempts"] = 0
    else:
        current["candidate_resolution_attempts"] = previous_candidate_attempts
        current["status"] = "active"
    blockers[current["blocker_id"]] = current
    ledger["blockers"] = list(blockers.values())


def _obsolete_unseen_blockers(
    ledger: dict[str, Any],
    *,
    touched_requirements: set[str],
    seen_blockers_by_requirement: dict[str, set[str]],
    step: int | None,
) -> None:
    blockers = _blocker_map(ledger)
    for blocker in blockers.values():
        requirement = blocker["requirement"]
        if requirement not in touched_requirements:
            continue
        if blocker["status"] in {"resolved", "obsolete"}:
            continue
        seen_ids = seen_blockers_by_requirement.get(requirement, set())
        if blocker["blocker_id"] in seen_ids:
            continue
        if blocker["status"] == "candidate_resolved":
            continue
        blocker["status"] = "obsolete"
        blocker["last_updated_step"] = _choose_step(step, blocker.get("last_updated_step"))
        blocker["age_steps"] = _compute_age_steps(blocker.get("created_step"), blocker.get("last_updated_step"))
    ledger["blockers"] = list(blockers.values())


def _iter_target_blockers(
    blockers: Mapping[str, dict[str, Any]],
    *,
    requirement: str | None,
    blocker_id_filter: set[str],
    statuses: set[str],
) -> Iterable[dict[str, Any]]:
    requirement_text = _clean_text(requirement)
    for blocker in blockers.values():
        if blocker_id_filter and blocker["blocker_id"] not in blocker_id_filter:
            continue
        if requirement_text and blocker["requirement"] != requirement_text:
            continue
        if blocker["status"] not in statuses:
            continue
        yield blocker


def _current_blocker_evidence_version(
    ledger: Mapping[str, Any],
    *,
    blocker: Mapping[str, Any],
    relevant_evidence_refs: Iterable[str] | None,
    relevant_failed_checks: Iterable[str] | None,
    relevant_artifact_paths: Iterable[str] | None,
    relevant_verifier_refs: Iterable[str] | None,
    relevant_evidence_classes: Iterable[str] | None,
) -> str:
    entry = _requirement_map(ledger).get(_clean_text(blocker.get("requirement"))) or {}
    evidence_refs = list(entry.get("evidence_refs", []) or [])
    failed_checks = list(entry.get("failed_checks", []) or [])
    evidence_refs.extend(_normalize_string_list(relevant_evidence_refs or (), limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"]))
    failed_checks.extend(_normalize_string_list(relevant_failed_checks or (), limit=_REQUIREMENT_LIST_LIMITS["failed_checks"]))
    evidence_classes = _normalize_string_list(
        relevant_evidence_classes or (),
        limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"],
    )
    if not evidence_classes:
        evidence_classes = _infer_evidence_classes(
            evidence_refs=evidence_refs,
            failed_checks=failed_checks,
            artifact_paths=relevant_artifact_paths,
            verifier_refs=relevant_verifier_refs,
        )
    return compute_relevant_evidence_version(
        requirement=_clean_text(blocker.get("requirement")),
        evidence_refs=evidence_refs,
        failed_checks=failed_checks,
        artifact_paths=relevant_artifact_paths,
        verifier_refs=relevant_verifier_refs,
        reason_codes=blocker.get("reason_codes", ()),
        evidence_classes=evidence_classes,
    )


def _has_relevant_new_evidence(
    ledger: Mapping[str, Any],
    *,
    blocker: Mapping[str, Any],
    relevant_evidence_refs: Iterable[str] | None,
    relevant_failed_checks: Iterable[str] | None,
    relevant_artifact_paths: Iterable[str] | None,
    relevant_verifier_refs: Iterable[str] | None,
    relevant_evidence_classes: Iterable[str] | None,
) -> bool:
    new_version = _current_blocker_evidence_version(
        ledger,
        blocker=blocker,
        relevant_evidence_refs=relevant_evidence_refs,
        relevant_failed_checks=relevant_failed_checks,
        relevant_artifact_paths=relevant_artifact_paths,
        relevant_verifier_refs=relevant_verifier_refs,
        relevant_evidence_classes=relevant_evidence_classes,
    )
    if new_version == _clean_text(blocker.get("evidence_version_last_evaluated")):
        return False
    required_class = _clean_text(blocker.get("required_evidence_class"))
    if required_class:
        evidence_classes = _normalize_string_list(
            relevant_evidence_classes or (),
            limit=_REQUIREMENT_LIST_LIMITS["evidence_provenance"],
        )
        if not evidence_classes:
            evidence_classes = _infer_evidence_classes(
                evidence_refs=relevant_evidence_refs,
                failed_checks=relevant_failed_checks,
                artifact_paths=relevant_artifact_paths,
                verifier_refs=relevant_verifier_refs,
            )
        if required_class not in evidence_classes:
            return False
    direct_relevant_checks = _normalize_string_list(
        relevant_failed_checks or (),
        limit=_REQUIREMENT_LIST_LIMITS["failed_checks"],
    )
    direct_relevant_verifier_refs = _normalize_string_list(
        relevant_verifier_refs or (),
        limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"],
    )
    if direct_relevant_checks or direct_relevant_verifier_refs:
        return True
    evidence_texts = [
        *_normalize_string_list(relevant_evidence_refs or (), limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"]),
        *direct_relevant_checks,
        *_normalize_string_list(relevant_artifact_paths or (), limit=_REQUIREMENT_LIST_LIMITS["evidence_refs"]),
    ]
    if not evidence_texts:
        entry = _requirement_map(ledger).get(_clean_text(blocker.get("requirement"))) or {}
        seen = set(
            _normalize_string_list(
                blocker.get("rejected_evidence_refs", ()),
                limit=_BLOCKER_LIST_LIMITS["rejected_evidence_refs"],
            )
        )
        evidence_texts = [
            *[item for item in list(entry.get("evidence_refs", []) or []) if item not in seen],
            *[item for item in list(entry.get("failed_checks", []) or []) if item not in seen],
        ]
    if not evidence_texts:
        return False
    return _evidence_overlaps_blocker(blocker, evidence_texts)


def _evidence_overlaps_blocker(blocker: Mapping[str, Any], evidence_texts: Iterable[str]) -> bool:
    anchor_tokens = _token_set(
        [
            blocker.get("requirement"),
            blocker.get("insufficiency_reason"),
            *list(blocker.get("required_next_evidence", []) or []),
            *list(blocker.get("rejected_evidence_refs", []) or []),
        ]
    )
    if not anchor_tokens:
        return False
    for text in evidence_texts:
        evidence_tokens = _token_set([text])
        if evidence_tokens & anchor_tokens:
            return True
    return False


def _token_set(values: Iterable[Any]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in _TOKEN_RE.findall(_clean_text(value).lower()):
            if len(token) <= 2 or token in _RELEVANCE_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _default_next_evidence(*, requirement: str, verdict: str) -> str:
    if verdict == "contradicted":
        return f"fresh visible proof after repair for: {requirement}"
    if requirement == _VERIFIER_INTEGRITY_REQUIREMENT:
        return "repair verifier output shape and rerun verification"
    return f"direct visible evidence for: {requirement}"


def _normalize_blocker_status(value: Any, *, default: str) -> str:
    text = _clean_text(value).lower()
    if text in _VALID_BLOCKER_STATUSES:
        return text
    return default


def _compute_age_steps(created_step: Any, last_updated_step: Any) -> int:
    created = _coerce_int(created_step)
    updated = _coerce_int(last_updated_step)
    if created is None or updated is None:
        return 0
    return max(0, updated - created)


def _choose_step(preferred: Any, fallback: Any) -> int | None:
    preferred_int = _coerce_int(preferred)
    if preferred_int is not None:
        return preferred_int
    return _coerce_int(fallback)


def _coerce_step(step: Any, *, report: Any, verifier_ref: str | None) -> int | None:
    explicit = _coerce_int(step)
    if explicit is not None:
        return explicit
    report_step = _coerce_int(_read_attr(report, "step"))
    if report_step is not None:
        return report_step
    return _extract_step_from_text(verifier_ref)


def _extract_step_from_text(value: str | None) -> int | None:
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"step=(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def _record_failure_family(ledger: dict[str, Any], *, family: str, evidence_ref: str | None) -> None:
    text = _clean_text(family)
    if not text:
        return
    current = list(ledger.get("repeated_failure_families", []) or [])
    current.append(
        {
            "family": text,
            "count": 1,
            "last_evidence_ref": _clean_text(evidence_ref),
        }
    )
    ledger["repeated_failure_families"] = _normalize_failure_families(current, limit=_MAX_FAILURE_FAMILIES)


def _normalize_failure_families(values: Iterable[Any], *, limit: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for value in values or ():
        if isinstance(value, Mapping):
            family = _clean_text(value.get("family"))
            count = _coerce_int(value.get("count")) or 1
            last_ref = _clean_text(value.get("last_evidence_ref"))
        else:
            family = _clean_text(value)
            count = 1
            last_ref = ""
        if not family:
            continue
        if family not in merged:
            merged[family] = {"family": family, "count": 0, "last_evidence_ref": ""}
        merged[family]["count"] += max(1, count)
        if last_ref:
            merged[family]["last_evidence_ref"] = last_ref
    ranked = sorted(merged.values(), key=lambda item: (-item["count"], item["family"]))
    return ranked[:limit]


def _normalize_terminal_claims(values: Iterable[Any], *, limit: int) -> list[dict[str, Any]]:
    normalized = [_normalize_terminal_claim(value) for value in values or () if isinstance(value, Mapping)]
    normalized.sort(key=_terminal_claim_sort_key)
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit]


def _normalize_terminal_claim(
    value: Mapping[str, Any],
    *,
    outcome: str | None = None,
    step: int | None = None,
    raw_log_path: str | None = None,
) -> dict[str, Any]:
    claim_kind = _normalize_terminal_claim_kind(outcome or value.get("outcome") or value.get("claim_kind"))
    summary = _clean_text(value.get("summary")) or _clean_text(value.get("blocker")) or _clean_text(value.get("claim"))
    checks = _normalize_string_list(value.get("checks", ()), limit=_TERMINAL_CLAIM_LIST_LIMITS["evidence_refs"])
    evidence_refs = _normalize_string_list(
        [
            *checks,
            *(_normalize_string_list(value.get("evidence", ()), limit=_TERMINAL_CLAIM_LIST_LIMITS["evidence_refs"])),
        ],
        limit=_TERMINAL_CLAIM_LIST_LIMITS["evidence_refs"],
    )
    requirements = _normalize_terminal_requirement_claims(value.get("requirements", ()))
    known_limitations = _normalize_string_list(
        value.get("known_limitations", ()),
        limit=_TERMINAL_CLAIM_LIST_LIMITS["known_limitations"],
    )
    attempts = _normalize_string_list(value.get("attempts", ()), limit=_TERMINAL_CLAIM_LIST_LIMITS["attempts"])
    missing_external_state = _normalize_string_list(
        value.get("missing_external_state", ()),
        limit=_TERMINAL_CLAIM_LIST_LIMITS["missing_external_state"],
    )
    recommended_next_evidence = _normalize_string_list(
        value.get("recommended_next_evidence", ()),
        limit=_TERMINAL_CLAIM_LIST_LIMITS["recommended_next_evidence"],
    )
    evidence_provenance = _normalize_string_list(
        value.get("evidence_provenance", ()),
        limit=_TERMINAL_CLAIM_LIST_LIMITS["evidence_provenance"],
    )
    mapping_status = "structured" if requirements and all(item["claim_quality"] == "structured" for item in requirements) else "weak"
    if claim_kind == "blocked" and summary and attempts and missing_external_state and recommended_next_evidence and evidence_refs:
        mapping_status = "structured"
    blocker = _clean_text(value.get("blocker"))
    claimed_boundary = _clean_text(value.get("claimed_boundary"))
    claim_payload = {
        "claim_kind": claim_kind,
        "summary": summary,
        "requirements": requirements,
        "checks": checks,
        "evidence_refs": evidence_refs,
        "known_limitations": known_limitations,
        "attempts": attempts,
        "missing_external_state": missing_external_state,
        "recommended_next_evidence": recommended_next_evidence,
        "evidence_provenance": evidence_provenance,
        "blocker": blocker,
        "claimed_boundary": claimed_boundary,
        "mapping_status": mapping_status,
        "raw_log_path": _clean_text(raw_log_path) or _clean_text(value.get("raw_log_path")),
        "step": _choose_step(step, value.get("step")),
    }
    claim_payload["claim_id"] = _build_terminal_claim_id(claim_payload)
    return claim_payload


def _normalize_terminal_requirement_claims(values: Iterable[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for value in values or ():
        if not isinstance(value, Mapping):
            continue
        requirement = _clean_text(_read_attr(value, "requirement"))
        if not requirement:
            continue
        requirement_id = _clean_text(_read_attr(value, "requirement_id")) or _requirement_id(requirement)
        check = _clean_text(_read_attr(value, "check"))
        observation_ref = _clean_text(_read_attr(value, "observation_ref"))
        claimed_boundary = _clean_text(_read_attr(value, "claimed_boundary"))
        known_limitations = _normalize_string_list(
            _read_attr(value, "known_limitations", ()) or (),
            limit=_TERMINAL_CLAIM_LIST_LIMITS["known_limitations"],
        )
        claim_quality = "structured" if check or observation_ref or claimed_boundary or known_limitations else "weak"
        normalized.append(
            {
                "requirement": requirement,
                "requirement_id": requirement_id,
                "check": check,
                "observation_ref": observation_ref,
                "claimed_boundary": claimed_boundary,
                "known_limitations": known_limitations,
                "claim_quality": claim_quality,
            }
        )
    normalized.sort(key=lambda item: (item["requirement"], item["requirement_id"]))
    return normalized[: _TERMINAL_CLAIM_LIST_LIMITS["requirements"]]


def _normalize_terminal_claim_kind(value: Any) -> str:
    text = _clean_text(value).lower()
    if text in {"task_done", "done", "completion", "completed", "task_completion"}:
        return "completion"
    if text in {"task_blocked", "blocked", "unresolved", "report_unresolved"}:
        return "blocked"
    if "block" in text:
        return "blocked"
    return "completion"


def _build_terminal_claim_id(claim: Mapping[str, Any]) -> str:
    payload = {
        "claim_kind": _clean_text(claim.get("claim_kind")),
        "summary": _clean_text(claim.get("summary")),
        "requirements": claim.get("requirements", ()),
        "checks": claim.get("checks", ()),
        "evidence_refs": claim.get("evidence_refs", ()),
        "known_limitations": claim.get("known_limitations", ()),
        "attempts": claim.get("attempts", ()),
        "missing_external_state": claim.get("missing_external_state", ()),
        "recommended_next_evidence": claim.get("recommended_next_evidence", ()),
        "blocker": _clean_text(claim.get("blocker")),
        "claimed_boundary": _clean_text(claim.get("claimed_boundary")),
        "step": _coerce_int(claim.get("step")),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"claim_{digest}"


def _terminal_claim_sort_key(claim: Mapping[str, Any]) -> tuple[int, str, str]:
    kind_rank = {"blocked": 0, "completion": 1}.get(str(claim.get("claim_kind", "completion")), 2)
    return (
        kind_rank,
        _coerce_int(claim.get("step")) if _coerce_int(claim.get("step")) is not None else 10**9,
        _clean_text(claim.get("claim_id")),
    )


def _append_capped(values: list[str], item: str | None, *, limit: int) -> list[str]:
    text = _clean_text(item)
    if not text:
        return list(values)
    combined = [*values, text]
    return _normalize_string_list(combined, limit=limit)


def _normalize_string_list(values: Iterable[Any], *, limit: int) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        text = _clean_text(value)
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


def _normalize_requirement_status(value: Any, *, default: str) -> str:
    text = _clean_text(value).lower()
    if text == "satisfied":
        text = "proven"
    elif text == "unsatisfied":
        text = "contradicted"
    elif text == "unverifiable":
        text = "unproven"
    if text in _VALID_REQUIREMENT_STATUSES:
        return text
    return default


def _normalize_evidence_strength(value: Any, *, default: str) -> str:
    text = _clean_text(value).lower()
    if text in _VALID_EVIDENCE_STRENGTHS:
        return text
    return default


def _build_observation_ref(
    *,
    tool_name: str,
    step: int | None,
    exit_code: int | None,
    raw_log_path: str | None,
    artifact_paths: list[str],
    note: str | None,
) -> str:
    parts = [f"tool={_clean_text(tool_name) or 'unknown'}"]
    if step is not None:
        parts.append(f"step={step}")
    if exit_code is not None:
        parts.append(f"exit={exit_code}")
    if _clean_text(raw_log_path):
        parts.append(f"log={_clean_text(raw_log_path)}")
    if artifact_paths:
        parts.append(f"artifacts={','.join(artifact_paths)}")
    if _clean_text(note):
        parts.append(f"note={_clean_text(note)}")
    return " ".join(parts)


def _build_check_ref(
    *,
    command: str,
    step: int | None,
    exit_code: int | None,
    raw_log_path: str | None,
    reason_code: str | None,
    error_kind: str | None,
    timed_out: bool,
) -> str:
    parts = [f"check={command or '<unknown>'}"]
    if step is not None:
        parts.append(f"step={step}")
    if exit_code is not None:
        parts.append(f"exit={exit_code}")
    if timed_out:
        parts.append("timed_out=true")
    if reason_code:
        parts.append(f"reason={reason_code}")
    if error_kind:
        parts.append(f"kind={error_kind}")
    if _clean_text(raw_log_path):
        parts.append(f"log={_clean_text(raw_log_path)}")
    return " ".join(parts)


def _build_verifier_ref(
    *,
    requirement: str,
    verdict: str,
    evidence: str,
    verifier_ref: str | None,
) -> str:
    parts = [f"verifier requirement={requirement}", f"verdict={verdict}"]
    if evidence:
        parts.append(f"evidence={evidence}")
    if _clean_text(verifier_ref):
        parts.append(f"ref={_clean_text(verifier_ref)}")
    return " ".join(parts)


def _failure_family_from_check(*, reason_code: str | None, timed_out: bool, exit_code: int | None) -> str:
    if timed_out:
        return "check_timeout"
    if reason_code:
        return f"check_reason:{reason_code}"
    if exit_code not in (None, 0):
        return "check_exit_nonzero"
    return "check_failure"


def _clean_text(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        return ""
    return " ".join(text.split())


def _read_attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
