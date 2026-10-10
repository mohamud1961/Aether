"""challenger_v5: live artifact evidence for the completion-time JUDGE request.

Collects, from the run's own execution ledger and executor, the files the run wrote (current
content, else the latest write receipt) and its test/verification command outputs, and builds
the request with the builder shared with the offline bench (``artifact_evidence``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..challenger_claim_types import (
    MAX_EVIDENCE_VIEWS, QUESTIONNAIRE_SCHEMA, Criterion, QuestionDimension, QuestionSpec,
)
from ..ledger import ExecutionLedger
from ..run_cancellation import RunCancellationRequested
from ..run_deadline import KernelRunTimeout
from ..runtime_ir import normalize_relpath
from .artifact_evidence import (
    ArtifactFile, ArtifactTest, artifact_questions, build_artifact_request, looks_like_test,
)
from .config import ARTIFACT_MAX_FILES_READ, ARTIFACT_MAX_REQUEST_BYTES
from .evidence import is_scratch_path
from .failure_question import FAILURE_QUESTION_ID
from .judge_client import _wire_question
from .progress_question import compact
from .shell_writes import command_write_targets

_PROPAGATE = (RunCancellationRequested, KernelRunTimeout)


@dataclass(frozen=True)
class ArtifactReview:
    request: dict[str, Any]
    criteria: tuple[Criterion, ...]
    views: dict[str, str]
    questions: tuple[QuestionSpec, ...]
    trim: dict[str, Any]
    candidates: int


def _last_writes(ledger: ExecutionLedger, workspace_root: str) -> dict[str, tuple[int, str | None]]:
    """Path -> (step, content of that write when it carried it); the last write of each path wins."""
    last: dict[str, tuple[int, str | None]] = {}
    for r in ledger.all_receipts():
        payload = r.payload if isinstance(r.payload, Mapping) else {}
        if r.kind == "write_file" and r.success and payload.get("path"):
            found = {str(payload["path"]): (r.step, str(payload["content"]) if "content" in payload else None)}
        elif r.kind == "run_command":
            paths = list(payload.get("modified_paths") or ()) + list(command_write_targets(str(payload.get("command", ""))))
            found = {str(p): (r.step, None) for p in paths}
        else:
            continue
        for path, value in found.items():
            try:
                path = normalize_relpath(path, workspace_root)
            except ValueError:  # outside the workspace (e.g. /tmp logs): not a deliverable artifact
                continue
            if path and path != "." and not is_scratch_path(path, workspace_root):
                last.pop(path, None)
                last[path] = value
    return last


def collect_files(ledger: ExecutionLedger, executor: Any, workspace_root: str) -> tuple[list[ArtifactFile], int]:
    """Current content of the newest written non-scratch files; returns (files, candidate count)."""
    last = _last_writes(ledger, workspace_root)
    newest = sorted(last.items(), key=lambda kv: kv[1][0], reverse=True)[:ARTIFACT_MAX_FILES_READ]
    files: list[ArtifactFile] = []
    used: set[int] = set()
    for path, (step, receipt_content) in newest:
        try:
            content, source = executor.read_file(path), "current"
        except _PROPAGATE:
            raise
        except Exception:
            content, source = receipt_content, "write_receipt"
        if content is None:
            continue
        index = step
        while index in used:
            index += 1
        used.add(index)
        files.append(ArtifactFile(path, str(content), source, index))
    return sorted(files, key=lambda f: f.call_index), len(last)


def collect_tests(ledger: ExecutionLedger) -> list[ArtifactTest]:
    """Test and verification command outputs, newest first."""
    tests: list[ArtifactTest] = []
    for r in reversed(ledger.all_receipts()):
        if r.kind != "run_command":
            continue
        p = r.payload if isinstance(r.payload, Mapping) else {}
        command = str(p.get("command", ""))
        output = f"exit_code={p.get('exit_code')}\n{p.get('stdout') or ''}" + (f"\nstderr: {p['stderr']}" if p.get("stderr") else "")
        if looks_like_test(command, output):
            text = f"[run_command] {command}\n-> {output}"
            tests.append(ArtifactTest(f"a{r.step}", lambda lim, text=text: compact(text, lim), r.receipt_id))
    return tests


def _specs(questions: Mapping[str, Mapping[str, Any]]) -> tuple[QuestionSpec, ...]:
    return tuple(QuestionSpec(
        qid, QuestionDimension.FAILURE_MODE if qid == FAILURE_QUESTION_ID else QuestionDimension.COMPLETENESS,
        spec["relation"], tuple(spec["choices"]), criterion_id=spec.get("criterion_id", ""),
        evidence_refs=tuple(spec["evidence_refs"]), choice_details=dict(spec.get("choice_details") or {}))
        for qid, spec in questions.items())


def build_artifact_review(
    *, ledger: ExecutionLedger, executor: Any, workspace_root: str, model: str, raw_task: str,
    criteria: Sequence[Criterion], card_id: str, card_claims: Sequence[Mapping[str, Any]], final_claim: str,
    budget: int = ARTIFACT_MAX_REQUEST_BYTES, cited_views: Mapping[str, str] | None = None,
) -> ArtifactReview | None:
    """None when the run wrote no non-scratch file with readable content (the caller keeps the v1 request)."""
    files, candidates = collect_files(ledger, executor, workspace_root)
    if not files:
        return None
    all_criteria = [{"criterion_id": c.criterion_id, "text": c.text} for c in criteria]

    def wire(card: dict[str, Any], crit: Sequence[Mapping[str, str]], views: Mapping[str, str],
             questions: Mapping[str, Any]) -> dict[str, Any]:
        text = {str(c["criterion_id"]): str(c["text"]) for c in crit}
        return {"model": model,
                "state": {"schema": QUESTIONNAIRE_SCHEMA, "raw_task": raw_task, "criteria": list(crit),
                          "claim_card": card, "visible_evidence": dict(views)},
                "questions": {str(q): _wire_question(spec, text) for q, spec in questions.items()}}

    built = build_artifact_request(
        wire=wire, criteria_all=all_criteria, max_views=MAX_EVIDENCE_VIEWS, files=files, tests=collect_tests(ledger),
        cited=[ArtifactTest(ref, lambda lim, text=text: compact(text, lim)) for ref, text in (cited_views or {}).items()],
        budget=budget, base_card=lambda refs: {
            "card_id": card_id, "final_claim": compact(final_claim, 1200), "challenger_card": list(card_claims), "cited_refs": refs})
    kept = {c["criterion_id"] for c in built.criteria}
    questions = _specs(artifact_questions(built.criteria, list(built.views)))
    return ArtifactReview(built.request, tuple(c for c in criteria if c.criterion_id in kept), built.views,
                          questions, built.trim, candidates)
