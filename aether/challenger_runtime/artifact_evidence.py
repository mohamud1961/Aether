"""Artifact-evidence request builder shared by the live challenger_v5 review and the offline JUDGE bench.

The evidence is the current contents of the files the run wrote plus its recent test and
verification outputs, fitted under a byte budget by tightening per-view limits. The caller
supplies the wire assembly, so the production client and the bench build one request shape.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable, Mapping, Sequence

from .failure_question import failure_question
from .progress_question import compact

COMPLETENESS_CHOICES = ("direct_and_current", "indirect", "self_written_check_only", "none", "contradicted")
V6_TIERS = ((8000, 3000), (4000, 1500), (2000, 800), (1000, 400), (500, 200), (250, 120))
CRITERIA_STEPS = (12, 8, 6, 4, 2)
RECENT_TESTS_FIRST = 3
TEST_RE = re.compile(r"pytest|unittest|\bPASS(?:ED)?\b|\bFAIL(?:ED)?\b|\d+ passed|\d+ failed|Traceback|AssertionError", re.I)
TEST_CMD_RE = re.compile(r"pytest|unittest|\btest|make check|cargo test|go test|npm test|\bdiff\b|cmp ", re.I)

Wire = Callable[[dict[str, Any], Sequence[Mapping[str, str]], Mapping[str, str], Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ArtifactFile:
    path: str
    content: str | None  # None: edited, final content unknown
    content_source: str
    call_index: int
    extra_view: Callable[[int], str] | None = None  # shown instead of content when it is unknown
    provenance_step: int | None = None  # real ledger step when call_index is a synthetic ordering key
    provenance_label: str | None = None  # explicit bound wording for replay observations

    @property
    def ref(self) -> str:
        return f"w{self.call_index}"


@dataclass(frozen=True)
class ArtifactTest:
    ref: str
    view: Callable[[int], str]
    receipt_id: str = ""  # the ledger receipt behind a test output, so a cited copy is not shown twice


@dataclass(frozen=True)
class ArtifactRequest:
    request: dict[str, Any]
    criteria: list[dict[str, str]]
    criteria_dropped: int
    views: dict[str, str]
    trim: dict[str, Any]


def looks_like_test(command: str, output: str) -> bool:
    return bool(TEST_CMD_RE.search(command) or (command and TEST_RE.search(output[:4000])))


def file_view(f: ArtifactFile, limit: int) -> str:
    if f.content is None:
        return f"[file {f.path}] edited only; final content is not in the trace.\n" + (f.extra_view(limit) if f.extra_view else "")
    when = f.provenance_label or (f"t{f.provenance_step}" if f.provenance_step is not None else f"t{f.call_index}")
    return compact(f"[file {f.path}] final content as written at {when} ({f.content_source})\n{f.content}", limit)


def completeness_specs(criteria: Sequence[Mapping[str, str]], refs: list[str]) -> dict[str, Any]:
    return {f"completeness:{c['criterion_id']}": {
        "relation": f"Classify whether the cited evidence directly and currently establishes criterion {c['criterion_id']}.",
        "choices": list(COMPLETENESS_CHOICES), "criterion_id": c["criterion_id"], "evidence_refs": refs} for c in criteria}


def artifact_questions(criteria: Sequence[Mapping[str, str]], refs: list[str]) -> dict[str, Any]:
    return {**completeness_specs(criteria, refs), "failure_mode": failure_question(refs, None)}


def request_size(request: Mapping[str, Any]) -> int:
    return len(json.dumps(request, allow_nan=False, separators=(",", ":")).encode())


def build_artifact_request(
    *, wire: Wire, criteria_all: Sequence[Mapping[str, str]], base_card: Callable[[list[str]], dict[str, Any]],
    files: Sequence[ArtifactFile], tests: Sequence[ArtifactTest], budget: int, max_views: int | None = None,
    cited: Sequence[ArtifactTest] = (), question_factory: Callable[[Sequence[Mapping[str, str]], list[str]], dict[str, Any]] = artifact_questions,
    allow_empty: bool = False,
) -> ArtifactRequest:
    """Cited receipts, the three latest test outputs, then newest-written files, then older tests.

    ``cited`` are the receipts the completion card cites (the evidence the failure-mode request shows); they
    outrank everything else, so a tight budget drops file content first. Raises ValueError if nothing fits."""
    cited_ids = {c.ref for c in cited}
    tests = [t for t in tests if t.receipt_id not in cited_ids]
    file_refs = {f.ref for f in files}
    wrote = [f.path for f in files]
    files = sorted(files, key=lambda f: f.call_index, reverse=True)
    best: ArtifactRequest | None = None
    for n_crit in CRITERIA_STEPS:
        criteria = list(criteria_all[:n_crit])
        for file_lim, test_lim in V6_TIERS:
            items = [(c.ref, c.view(test_lim)) for c in cited]
            items += [(t.ref, t.view(test_lim)) for t in tests[:RECENT_TESTS_FIRST]]
            items += [(f.ref, file_view(f, file_lim)) for f in files]
            items += [(t.ref, t.view(test_lim)) for t in tests[RECENT_TESTS_FIRST:]]

            def build(views: Mapping[str, str], omitted: list[str]) -> dict[str, Any]:
                card = {**base_card(list(views)), "files_written": wrote,
                        "files_shown": [r for r in views if r in file_refs], "evidence_omitted_refs": omitted}
                return wire(card, criteria, views, question_factory(criteria, list(views)))
            views: dict[str, str] = {}
            omitted: list[str] = []
            for ref, text in items:
                trial = {**views, ref: text}
                if ref not in views and (max_views is None or len(trial) <= max_views) and request_size(build(trial, omitted)) <= budget:
                    views = trial
                elif ref not in views:
                    omitted.append(ref)
            if not views and not allow_empty:
                continue
            request = build(views, omitted)
            if request_size(request) > budget:
                continue
            cand = ArtifactRequest(request, criteria, len(criteria_all) - len(criteria), dict(views), {
                "omitted_refs": omitted, "files_total": len(files), "files_kept": sum(1 for r in views if r in file_refs),
                "cited_total": len(cited), "cited_kept": sum(1 for c in cited if c.ref in views),
                "tests_total": len(tests), "view_limits": {"file": file_lim, "test": test_lim},
                "bytes": request_size(request), "budget": budget})
            if not omitted:
                return cand
            if best is None or len(omitted) < len(best.trim["omitted_refs"]):
                best = cand
        if best is not None:
            return best
    raise ValueError(f"artifact request cannot fit the {budget}-byte budget (no file writes or tests, or criteria too large)")
