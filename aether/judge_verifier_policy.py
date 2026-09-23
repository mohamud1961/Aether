"""Experimental Judge-only typed Verifier policy.

This module is intentionally inert: production Harbor does not import it.
It is a ModelCallable-compatible experiment adapter that emits Aether's existing
Verifier protocol.  The production verify_with_inspector loop remains authority
for inspection execution, proof/currentness, phase budgets, active findings and
final admission.

Judge (or a provider-free fake) answers only bounded typed questions.  Code owns
candidate construction and protocol rendering.  No generative helper is hidden
inside the V3 arm.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .persistent_task_contract import compile_persistent_task_contract


V3_POLICY_VERSION = "v3.typed-relation.provider-free.20260923.2"
V3_QUESTION_POLICY_VERSION = "v3.pair-referent.20260923.1"
V3_QUESTION_SCHEMA_VERSION = "aether.judge.choice-criteria.v1"
V3_PROVIDER_STATE_PROJECTION_VERSION = "aether.judge.provider-semantic-state.v1"
V3_PROVIDER_REQUEST_HARD_LIMIT_BYTES = 16000
V3_RELATION_PROVIDER_PROJECTION_VERSION = "aether.judge.relation-pair-catalog.v1"
DEFAULT_MIN_SEMANTIC_CONFIDENCE = 0.80
DEFAULT_MAX_CANDIDATES = 12
MAX_EVALUATOR_ROUNDS_PER_VERIFIER_CALL = 3
SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
CANDIDATE_PRIORITY = {
    "task_http": 4,
    "task_port": 5,
    "current_service_port": 6,
    "current_job": 7,
    "primary_image_perception": 7,
    "file_next_page": 8,
    "authorized_check": 9,
    "visible_image_perception": 10,
    "primary_file_read": 12,
    "primary_exact_receipt": 13,
    "primary_output": 14,
    "generic_action_history": 18,
    "scoped_action_history": 18,
    "visible_output": 20,
    "primary_artifact_metadata": 22,
    "primary_initial_compare": 28,
    "visible_file_read": 30,
    "visible_artifact_metadata": 40,
    "visible_initial_compare": 45,
}


NON_COMPLETION_VERDICTS = (
    "needs_repair",
    "uncertain_missing_evidence",
    "blocked_by_tooling",
    "blocked_by_harness_config",
    "incomplete_state_wrong",
    "incomplete_missing_required_artifact",
    "incomplete_semantic_mismatch",
    "insufficient_inspectable_evidence",
    "reviewer_tool_execution_failed",
    "reviewer_capability_missing",
    "probe_inconclusive",
    "environment_blocked",
    "timeout_or_budget_blocked",
)
SOLVER_REPAIR_VERDICTS = {
    "needs_repair",
    "incomplete_state_wrong",
    "incomplete_missing_required_artifact",
    "incomplete_semantic_mismatch",
}


class TypedQuestionEvaluator(Protocol):
    def __call__(
        self,
        state: Mapping[str, Any],
        questions: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Mapping[str, Any]]: ...


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    text: str
    clause_ids: tuple[str, ...] = ()
    exact_atoms: tuple[str, ...] = ()


@dataclass(frozen=True)
class InspectionCandidate:
    candidate_id: str
    description: str
    request: Mapping[str, Any]
    priority: int


def _json_user_payloads(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for message in messages:
        if str(message.get("role") or "") != "user":
            continue
        try:
            value = json.loads(str(message.get("content") or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            payloads.append(value)
    return payloads


def _initial_payload(payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    for payload in payloads:
        if isinstance(payload.get("verifier_packet"), Mapping):
            return dict(payload)
    return {}


def _all_inspection_results(payloads: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        value = payload.get("verifier_inspection_results")
        if not isinstance(value, list):
            continue
        rows.extend(dict(row) for row in value if isinstance(row, Mapping))
    return rows


def _requirements(packet: Mapping[str, Any], raw_task: str) -> tuple[Requirement, ...]:
    """Return source-faithful semantic work units without changing task authority.

    PERSISTENT deliberately exposes one opaque persistent_v11_raw task-contract clause.
    For Judge experiment navigation only, mechanically factor the exact raw task
    with the existing source-faithful splitter. Those internal units never
    become new kernel authority: every unit remains bound to the compiler-owned
    clause id(s) that actually exist in the production packet.
    """
    task_contract = packet.get("task_contract")
    clauses = task_contract.get("clauses", ()) if isinstance(task_contract, Mapping) else ()
    schema_version = (
        str(task_contract.get("schema_version") or "").strip()
        if isinstance(task_contract, Mapping)
        else ""
    )
    rows = [row for row in clauses if isinstance(row, Mapping)] if isinstance(clauses, (list, tuple)) else []
    contract_ids = tuple(
        str(row.get("clause_id") or "").strip()
        for row in rows
        if str(row.get("clause_id") or "").strip()
    )

    if rows and schema_version != "persistent_v11_raw":
        out: list[Requirement] = []
        for index, row in enumerate(rows):
            requirement_id = str(row.get("clause_id") or "").strip() or f"task:{index + 1}"
            requirement_text = str(row.get("text") or "").strip()
            atoms_raw = row.get("exact_atoms", ())
            atoms = tuple(
                str(item).strip()
                for item in atoms_raw
                if str(item).strip()
            ) if isinstance(atoms_raw, (list, tuple)) else ()
            if not requirement_text and atoms:
                requirement_text = "Exact task atoms: " + ", ".join(atoms)
            if requirement_text:
                out.append(Requirement(
                    requirement_id=requirement_id,
                    text=requirement_text,
                    clause_ids=(requirement_id,),
                    exact_atoms=atoms,
                ))
        if out:
            return tuple(out)

    source = str(raw_task or "").strip()
    if not source and rows:
        source = str(rows[0].get("text") or "").strip()
    if not source:
        return ()
    factored = compile_persistent_task_contract(source)
    return tuple(
        Requirement(
            requirement_id=f"judge:{clause.clause_id}",
            text=str(clause.text),
            clause_ids=contract_ids,
            exact_atoms=tuple(str(item) for item in clause.exact_atoms),
        )
        for clause in factored.clauses
        if str(clause.text).strip()
    )

def _available_routes(packet: Mapping[str, Any]) -> set[str]:
    caps = packet.get("verifier_runtime_capabilities")
    if not isinstance(caps, Mapping):
        return set()
    raw = caps.get("available_direct_observation_kinds")
    if not isinstance(raw, (list, tuple)):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def _result_locator(row: Mapping[str, Any]) -> str:
    kind = str(row.get("kind") or "").strip()
    if kind == "read_file":
        return str(row.get("requested_path") or row.get("path") or "").strip()
    if kind == "read_output":
        return str(row.get("handle") or "").strip()
    if kind == "rerun_check":
        return str(row.get("check_id") or "").strip()
    if kind == "probe_http":
        return str(row.get("url") or row.get("target") or "").strip()
    if kind == "probe_port":
        target = str(row.get("target") or "").strip()
        if target:
            return target
        port = str(row.get("port") or "").strip()
        host = str(row.get("host") or "").strip()
        return f"{host}:{port}" if host and host != "127.0.0.1" else port
    if kind == "probe_process":
        return str(row.get("pattern") or row.get("target") or "").strip()
    if kind == "probe_job":
        return str(row.get("target") or row.get("job_id") or "").strip()
    if kind in {"inspect_artifact", "perceive_artifact", "compare_initial_path"}:
        return str(row.get("requested_path") or row.get("path") or "").strip()
    if kind in {"inspect_action_receipts", "inspect_recent_receipts"}:
        return str(row.get("receipt_kind") or "*").strip()
    return str(
        row.get("path") or row.get("handle") or row.get("check_id") or row.get("target") or ""
    ).strip()


def _performed_locators(
    results: Sequence[Mapping[str, Any]],
) -> set[tuple[str, str, int]]:
    done: set[tuple[str, str, int]] = set()
    for row in results:
        kind = str(row.get("kind") or "").strip()
        locator = _result_locator(row)
        offset = int(row.get("offset", 0) or 0) if kind == "read_file" else 0
        if kind and locator:
            done.add((kind, locator, offset))
    return done

def build_inspection_candidates(
    packet: Mapping[str, Any],
    prior_results: Sequence[Mapping[str, Any]],
    *,
    raw_task: str = "",
    requirements: Sequence[Requirement] = (),
    limit: int = DEFAULT_MAX_CANDIDATES,
) -> tuple[InspectionCandidate, ...]:
    """Build a finite visible-only candidate set; never invent private paths."""
    routes = _available_routes(packet)
    done = _performed_locators(prior_results)
    drafts: dict[
        tuple[str, str, int],
        tuple[int, int, str, dict[str, Any]],
    ] = {}
    ordinal = 0

    def add(
        kind: str,
        locator_key: str,
        locator: str,
        description: str,
        *,
        priority: int = 50,
        requires_direct_route: bool = True,
        **extra: Any,
    ) -> None:
        nonlocal ordinal
        locator = str(locator or "").strip()
        offset_key = int(extra.get("offset", 0) or 0) if kind == "read_file" else 0
        key = (kind, locator, offset_key)
        if not locator or key in done:
            return
        if requires_direct_route and routes and kind not in routes:
            return
        request: dict[str, Any] = {
            "kind": kind,
            locator_key: locator,
        }
        request.update({k: v for k, v in extra.items() if v not in (None, "", [], ())})
        existing = drafts.get(key)
        if existing is not None and int(existing[0]) <= int(priority):
            return
        if existing is None:
            ordinal += 1
            item_ordinal = ordinal
        else:
            item_ordinal = existing[1]
        drafts[key] = (int(priority), item_ordinal, description, request)

    def add_unscoped(
        kind: str,
        dedupe_locator: str,
        description: str,
        *,
        priority: int = 50,
        **fields: Any,
    ) -> None:
        nonlocal ordinal
        locator = str(dedupe_locator or "").strip()
        key = (kind, locator, 0)
        if not locator or key in done:
            return
        if routes and kind not in routes:
            return
        request: dict[str, Any] = {"kind": kind}
        request.update({k: v for k, v in fields.items() if v not in (None, "", [], ())})
        existing = drafts.get(key)
        if existing is not None and int(existing[0]) <= int(priority):
            return
        if existing is None:
            ordinal += 1
            item_ordinal = ordinal
        else:
            item_ordinal = existing[1]
        drafts[key] = (int(priority), item_ordinal, description, request)

    # Continue a bounded file read when the previous current observation
    # proved that decisive content remains beyond the inspected span.
    for row in prior_results:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("kind") or "").strip() != "read_file":
            continue
        if row.get("error") not in (None, "") or row.get("observation_valid") is not True:
            continue
        path_value = str(row.get("requested_path") or row.get("path") or "").strip()
        try:
            offset = max(0, int(row.get("offset", 0) or 0))
            span = max(1, int(row.get("span", 4000) or 4000))
            content_chars = max(0, int(row.get("content_chars", 0) or 0))
        except (TypeError, ValueError):
            continue
        next_offset = offset + span
        if path_value and next_offset < content_chars:
            add(
                "read_file", "path", path_value,
                f"Read the next bounded page of current Solver-visible file {path_value!r}.",
                priority=CANDIDATE_PRIORITY["file_next_page"],
                offset=next_offset, span=min(4000, content_chars - next_offset),
            )

    handles = packet.get("state_inspection_handles")
    if isinstance(handles, (list, tuple)):
        for row in handles:
            if not isinstance(row, Mapping):
                continue
            kind = str(row.get("kind") or "").strip()
            if kind == "file":
                path = str(row.get("path") or "").strip()
                add(
                    "read_file", "path", path,
                    f"Read the current Solver-visible file {path!r}.",
                    priority=CANDIDATE_PRIORITY["visible_file_read"],
                    offset=0, span=4000,
                )
                add(
                    "inspect_artifact", "path", path,
                    f"Inspect current metadata/type for Solver-visible artifact {path!r}.",
                    priority=CANDIDATE_PRIORITY["visible_artifact_metadata"],
                )
                add(
                    "compare_initial_path", "path", path,
                    f"Compare the current Solver-visible file {path!r} with its immutable initial state.",
                    priority=CANDIDATE_PRIORITY["visible_initial_compare"],
                )
                add(
                    "inspect_artifact_history", "path", path,
                    f"Inspect immutable history for Solver-visible artifact {path!r}.",
                    priority=36,
                    limit=5,
                )
                if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    add(
                        "perceive_artifact", "path", path,
                        f"Independently perceive the current Solver-visible image {path!r}.",
                        priority=CANDIDATE_PRIORITY["visible_image_perception"],
                    )
            elif kind == "output":
                handle = str(row.get("handle") or "").strip()
                add(
                    "read_output", "handle", handle,
                    f"Read the immutable Solver-visible output handle {handle!r}.",
                    priority=CANDIDATE_PRIORITY["visible_output"],
                )

    submission = packet.get("primary_submission")
    cited = (
        submission.get("cited_evidence_index", ())
        if isinstance(submission, Mapping)
        else ()
    )
    if isinstance(cited, (list, tuple)):
        for row in cited:
            if not isinstance(row, Mapping):
                continue
            projection = row.get("current_payload_projection")
            if isinstance(projection, Mapping):
                path_value = str(projection.get("path") or "").strip()
                if path_value:
                    add(
                        "read_file", "path", path_value,
                        f"Re-observe Primary-cited current file {path_value!r}.",
                        priority=CANDIDATE_PRIORITY["primary_file_read"],
                        offset=0, span=4000,
                    )
                    add(
                        "inspect_artifact", "path", path_value,
                        f"Inspect Primary-cited current artifact {path_value!r}.",
                        priority=CANDIDATE_PRIORITY["primary_artifact_metadata"],
                    )
                    add(
                        "compare_initial_path", "path", path_value,
                        f"Compare Primary-cited current path {path_value!r} with initial state.",
                        priority=CANDIDATE_PRIORITY["primary_initial_compare"],
                    )
                    add(
                        "inspect_artifact_history", "path", path_value,
                        f"Inspect immutable history for Primary-cited artifact {path_value!r}.",
                        priority=26,
                        limit=5,
                    )
                    if path_value.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS):
                        add(
                            "perceive_artifact", "path", path_value,
                            f"Independently perceive Primary-cited image {path_value!r}.",
                            priority=CANDIDATE_PRIORITY["primary_image_perception"],
                        )
                for field in ("stdout_handle", "stderr_handle"):
                    output_handle = str(projection.get(field) or "").strip()
                    if output_handle:
                        add(
                            "read_output", "handle", output_handle,
                            f"Read Primary-cited immutable output handle {output_handle!r}.",
                            priority=CANDIDATE_PRIORITY["primary_output"],
                        )
            exact_handle = str(row.get("exact_receipt_handle") or "").strip()
            if exact_handle:
                add(
                    "read_output", "handle", exact_handle,
                    f"Read the exact Primary-cited receipt handle {exact_handle!r}.",
                    priority=CANDIDATE_PRIORITY["primary_exact_receipt"],
                )

    dynamic_state = packet.get("dynamic_state")
    if isinstance(dynamic_state, Mapping):
        services = dynamic_state.get("services")
        if isinstance(services, Mapping):
            for service_name, row in services.items():
                if not isinstance(row, Mapping):
                    continue
                port_value = row.get("port")
                try:
                    port = int(port_value)
                except (TypeError, ValueError):
                    port = 0
                if 0 < port <= 65535:
                    add(
                        "probe_port", "target", str(port),
                        (
                            "Probe the current runtime service port "
                            f"{port} for {str(service_name)!r}."
                        ),
                        priority=CANDIDATE_PRIORITY["current_service_port"],
                    )
        jobs = dynamic_state.get("jobs")
        if isinstance(jobs, Mapping):
            for job_name, row in jobs.items():
                if not isinstance(row, Mapping):
                    continue
                target = str(row.get("job_id") or job_name or "").strip()
                if target:
                    add(
                        "probe_job", "target", target,
                        f"Probe current runtime job {target!r}.",
                        priority=CANDIDATE_PRIORITY["current_job"],
                    )

    task_contract = packet.get("task_contract")
    method_clause_ids: list[str] = []
    if isinstance(task_contract, Mapping):
        raw_methods = task_contract.get("method_constraints", ())
        if isinstance(raw_methods, (list, tuple)):
            method_clause_ids = [
                str(row.get("constraint_id") or "").strip()
                for row in raw_methods
                if isinstance(row, Mapping)
                and str(row.get("constraint_id") or "").strip()
            ]
    add_unscoped(
        "inspect_action_receipts",
        "*",
        "Inspect the newest immutable governed action receipts for method/provenance facts.",
        priority=CANDIDATE_PRIORITY["generic_action_history"],
        limit=8,
        clause_ids=method_clause_ids,
    )
    add_unscoped(
        "inspect_recent_receipts",
        "*",
        "Inspect bounded recent receipt metadata for unresolved runtime or failure facts.",
        priority=38,
        limit=8,
    )

    # Public behavior named explicitly in the raw task is a legitimate
    # Verifier target even when it is not a workspace path. Parse only exact
    # URL/port literals; never invent a host, private path, or benchmark route.
    task_text = str(raw_task or "")
    if not task_text and requirements:
        task_text = "\n".join(item.text for item in requirements)

    if not routes or "probe_http" in routes:
        seen_urls: set[str] = set()
        for match in re.finditer(r"https?://[^\s<>\"']+", task_text):
            url = match.group(0).rstrip(".,;:!?)]}")
            if url and url not in seen_urls:
                seen_urls.add(url)
                add(
                    "probe_http", "target", url,
                    f"Probe the exact task-declared HTTP endpoint {url!r}.",
                    priority=CANDIDATE_PRIORITY["task_http"],
                )

    if not routes or "probe_port" in routes:
        seen_ports: set[str] = set()
        port_patterns = (
            r"\bport\s+([0-9]{2,5})\b",
            r"\b(?:localhost|127\.0\.0\.1):([0-9]{2,5})\b",
        )
        for pattern in port_patterns:
            for match in re.finditer(pattern, task_text, flags=re.IGNORECASE):
                port = match.group(1)
                try:
                    valid = 0 < int(port) <= 65535
                except ValueError:
                    valid = False
                if valid and port not in seen_ports:
                    seen_ports.add(port)
                    add(
                        "probe_port", "target", port,
                        f"Probe the exact task-declared local TCP port {port}.",
                        priority=CANDIDATE_PRIORITY["task_port"],
                    )

    checks = packet.get("authoritative_check_ids")
    if isinstance(checks, (list, tuple)):
        for check_id in checks:
            cid = str(check_id or "").strip()
            add(
                "rerun_check", "check_id", cid,
                f"Rerun the task-authorized check {cid!r}.",
                priority=CANDIDATE_PRIORITY["authorized_check"],
                requires_direct_route=False,
            )

    if isinstance(cited, (list, tuple)) and (
        not routes or "inspect_action_receipts" in routes
    ):
        kinds: list[str] = []
        for row in cited:
            if not isinstance(row, Mapping):
                continue
            receipt_kind = str(row.get("kind") or "").strip()
            if receipt_kind and receipt_kind not in kinds:
                kinds.append(receipt_kind)
        for receipt_kind in kinds:
            add(
                "inspect_action_receipts",
                "receipt_kind",
                receipt_kind,
                f"Inspect current governed action receipts of kind {receipt_kind!r}.",
                priority=CANDIDATE_PRIORITY["scoped_action_history"],
                limit=5,
            )
    selected = sorted(
        drafts.values(),
        key=lambda item: (item[0], item[1], item[2]),
    )[: max(0, int(limit))]
    candidates: list[InspectionCandidate] = []
    for index, (_priority, _ordinal, description, raw_request) in enumerate(
        selected, start=1
    ):
        request = dict(raw_request)
        request["request_id"] = f"judge-typed-{index}"
        candidates.append(InspectionCandidate(
            candidate_id=f"probe_{index}",
            description=description,
            request=request,
            priority=int(_priority),
        ))
    return tuple(candidates)


def _choice(instructions: str, choices: Mapping[str, str]) -> dict[str, Any]:
    return {
        "type": "choice",
        "instructions": instructions,
        "criteria": dict(choices),
    }


def _answer_choice(
    raw: Mapping[str, Mapping[str, Any]],
    question_id: str,
    allowed: set[str],
    default: str,
) -> tuple[str, dict[str, float]]:
    row = raw.get(question_id)
    if not isinstance(row, Mapping):
        return default, {}
    choice = str(row.get("choice") or "").strip()
    if choice not in allowed:
        choice = default
    probs = row.get("probabilities")
    if not isinstance(probs, Mapping):
        return choice, {}
    clean = {
        str(key): float(value)
        for key, value in probs.items()
        if isinstance(value, (int, float))
    }
    return choice, clean


def _bounded_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    head = max(1, (limit * 2) // 3)
    tail = max(1, limit - head - len(" ...[truncated]... "))
    return text[:head] + " ...[truncated]... " + text[-tail:]


def _result_excerpt(row: Mapping[str, Any]) -> str:
    """Render the exact current observation into a bounded semantic referent.

    Direct textual observations keep their native text. Structured verifier
    observations must not collapse to a generic placeholder: Judge's relation
    head needs the actual model-visible facts (for example mode=600 or the
    command/proto text in immutable action history). This is presentation only;
    it does not infer a semantic summary or add authority.
    """
    for key in ("excerpt", "stdout", "stderr", "summary", "content"):
        text = str(row.get(key) or "").strip()
        if text:
            return _bounded_text(text, limit=2400)

    kind = str(row.get("kind") or "").strip()
    projection: dict[str, Any] = {"kind": kind} if kind else {}

    if kind == "inspect_artifact":
        for key in (
            "requested_path", "path", "exists", "file_type", "size_bytes",
            "mode", "owner", "mtime_epoch", "sha256", "semantic_content_status",
            "media_metadata",
        ):
            if key in row and row.get(key) not in (None, "", [], {}):
                projection[key] = row.get(key)
    elif kind in {
        "inspect_action_receipts",
        "inspect_recent_receipts",
        "inspect_artifact_history",
    }:
        for key in (
            "path", "receipt_kind", "matching_count", "returned_count",
            "successful_count", "failed_count", "older_available_count",
            "metadata_view", "structured_view", "method_evidence_only",
        ):
            if key in row and row.get(key) not in (None, "", [], {}):
                projection[key] = row.get(key)
        rows = row.get("rows")
        if isinstance(rows, (list, tuple)):
            compact_rows: list[Any] = []
            for item in list(rows)[-4:]:
                if not isinstance(item, Mapping):
                    compact_rows.append(_bounded_text(item, limit=500))
                    continue
                compact: dict[str, Any] = {}
                for key in (
                    "receipt_id", "step", "kind", "success", "failure_class",
                    "state_change", "status", "summary", "path",
                ):
                    if key in item and item.get(key) not in (None, "", [], {}):
                        compact[key] = item.get(key)
                payload = item.get("payload")
                if isinstance(payload, Mapping):
                    safe_payload: dict[str, Any] = {}
                    for key in (
                        "path", "command", "exit_code", "modified_paths",
                        "artifact_paths", "removed_paths", "target", "live",
                        "job_status", "completed", "job_succeeded",
                        "job_exit_code", "contract_guarantees",
                    ):
                        if key not in payload or payload.get(key) in (None, "", [], {}):
                            continue
                        value = payload.get(key)
                        if key == "command":
                            value = _bounded_text(value, limit=900)
                        safe_payload[key] = value
                    if safe_payload:
                        compact["payload"] = safe_payload
                compact_rows.append(compact)
            if compact_rows:
                projection["rows"] = compact_rows
    else:
        # Probe/typed inspection results are already model-visible, bounded
        # runtime facts. Keep a conservative field allowlist rather than
        # serialising provider/control metadata.
        for key in (
            "requested_path", "path", "target", "found", "exists", "status",
            "success", "completed", "job_succeeded", "job_exit_code", "pid",
            "process_id", "job_id", "live", "detail", "outcome_detail",
            "file_type", "size_bytes", "mode", "owner", "sha256",
        ):
            if key in row and row.get(key) not in (None, "", [], {}):
                projection[key] = row.get(key)

    if projection and projection != {"kind": kind}:
        rendered = json.dumps(
            projection, sort_keys=True, ensure_ascii=False, default=str,
            separators=(",", ":"),
        )
        return _bounded_text(rendered, limit=3600)
    return "registered current verifier observation"


def _evidence_options(
    results: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, Mapping[str, Any]]]:
    criteria: dict[str, str] = {
        "none": "No current registered inspection establishes this requirement."
    }
    by_key: dict[str, Mapping[str, Any]] = {}
    index = 0
    for row in results:
        if row.get("error") not in (None, "") or row.get("observation_valid") is not True:
            continue
        inspection_id = str(row.get("inspection_id") or "").strip()
        if not inspection_id:
            continue
        index += 1
        key = f"e{index}"
        criteria[key] = f"Registered inspection {inspection_id!r}: {_result_excerpt(row)}"
        by_key[key] = row
    return criteria, by_key


def _semantic_questions(
    requirements: Sequence[Requirement],
    evidence_criteria: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    """Select evidence only; pair-specific semantics are judged in the next round."""
    questions: dict[str, dict[str, Any]] = {}
    for index, requirement in enumerate(requirements):
        questions[f"evidence_{index}"] = _choice(
            (
                "Which one current registered inspection is most materially relevant "
                f"to this exact raw-task obligation: {requirement.text!r}? Choose none "
                "when no current inspection materially bears on it."
            ),
            evidence_criteria,
        )
    return questions


def _pair_referent(requirement: Requirement, row: Mapping[str, Any]) -> str:
    inspection_id = str(row.get("inspection_id") or "").strip()
    kind = str(row.get("kind") or "").strip()
    return (
        f"obligation={requirement.text!r}; "
        f"inspection_id={inspection_id!r}; kind={kind!r}; "
        f"evidence={_result_excerpt(row)!r}"
    )


def _relation_questions(
    requirements: Sequence[Requirement],
    selected_evidence: Sequence[Mapping[str, Any] | None],
) -> dict[str, dict[str, Any]]:
    """Judge each exact requirement/evidence pair independently.

    The question text repeats the concrete obligation and inspection identity so
    Judge never has to infer which evidence a semantic guard refers to.
    """
    questions: dict[str, dict[str, Any]] = {}
    for index, (requirement, row) in enumerate(zip(requirements, selected_evidence)):
        if row is None:
            continue
        referent = _pair_referent(requirement, row)
        questions[f"relation_{index}"] = _choice(
            (
                "What is the semantic relation of this exact current evidence to "
                f"this exact raw-task obligation? {referent}. Judge only this pair."
            ),
            {
                "supports": "The evidence materially supports/establishes the obligation.",
                "contradicts": "The evidence materially contradicts or undermines the obligation.",
                "irrelevant": "The evidence does not materially bear on the obligation.",
                "uncertain": "The relation cannot be established from this evidence.",
            },
        )
        questions[f"dependence_{index}"] = _choice(
            (
                "For this exact obligation/evidence pair, is the evidence materially "
                "independent of the production hypothesis or method when independence "
                f"is required? {referent}. Judge only this pair."
            ),
            {
                "independent": "Materially independent of the production hypothesis or method.",
                "correlated": "Shares the decisive production assumption or method.",
                "insufficient": "The visible pair does not establish independence.",
                "not_required": "Independence is not materially required for this direct observation.",
            },
        )
        questions[f"determinant_{index}"] = _choice(
            (
                "For this exact obligation/evidence pair, does the evidence test the "
                "actual semantic determinant rather than metadata, labels, shape, "
                f"presence, or a self-confirming proxy? {referent}. Judge only this pair."
            ),
            {"yes": "yes", "no": "no", "uncertain": "uncertain"},
        )
    return questions


def _routing_questions(
    candidates: Sequence[InspectionCandidate],
    unresolved_gaps: Sequence[str],
) -> dict[str, dict[str, Any]]:
    choices: dict[str, str] = {
        "verdict_now": "Return a fail-closed final Verifier verdict from current evidence."
    }
    for candidate in candidates:
        choices[candidate.candidate_id] = candidate.description
    gap_text = "; ".join(str(item) for item in unresolved_gaps if str(item).strip())
    return {
        "next_move": _choice(
            (
                "Choose the single bounded next Verifier step that best resolves one "
                "current evidence gap. Do not invent a path, command, capability, or "
                f"grader fact outside the listed candidates. Current gaps: {gap_text or 'none'}"
            ),
            choices,
        )
    }


class TypedJudgeVerifierCallable:
    """ModelCallable-compatible V3 policy with complete per-call audit traces."""

    judge_verifier_experiment_arm = "V3"

    def __init__(
        self,
        evaluator: TypedQuestionEvaluator,
        *,
        min_semantic_confidence: float = DEFAULT_MIN_SEMANTIC_CONFIDENCE,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
    ) -> None:
        confidence = float(min_semantic_confidence)
        if not 0.0 < confidence <= 1.0:
            raise ValueError("min_semantic_confidence must be in (0, 1]")
        if isinstance(max_candidates, bool):
            raise ValueError("max_candidates must be an integer")
        candidate_limit = int(max_candidates)
        if candidate_limit < 1 or candidate_limit > 64:
            raise ValueError("max_candidates must be in [1, 64]")
        self._evaluator = evaluator
        self._min_confidence = confidence
        self._max_candidates = candidate_limit
        self._trace: list[dict[str, Any]] = []
        self._telemetry_scope: dict[str, str | None] | None = None

    def drain_trace(self) -> list[dict[str, Any]]:
        rows = list(self._trace)
        self._trace.clear()
        return rows

    def bind_run_cancellation(self, event: Any) -> None:
        """Forward task cancellation to the nested Judge transport when supported."""
        bind = getattr(self._evaluator, "bind_run_cancellation", None)
        if callable(bind):
            bind(event)

    def drain_telemetry(self) -> tuple[dict[str, Any], ...]:
        """Expose policy decisions and nested judge usage through ModelHooks."""
        rows: list[dict[str, Any]] = list(self._trace)
        self._trace.clear()
        drain = getattr(self._evaluator, "drain_telemetry", None)
        if callable(drain):
            for row in drain() or ():
                if isinstance(row, Mapping):
                    rows.append(dict(row))
        return tuple(rows)

    def call_with_telemetry_scope(
        self,
        messages: list[dict[str, str]],
        *,
        run_id: str,
        task_id: str | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        """Bind one ordinary ModelHooks run/task scope to V3 and its transport."""
        prior_scope = self._telemetry_scope
        scope = {"run_id": str(run_id), "task_id": task_id}
        self._telemetry_scope = scope
        set_scope = getattr(self._evaluator, "set_telemetry_scope", None)
        if callable(set_scope):
            set_scope(run_id=str(run_id), task_id=task_id)
        try:
            return self.__call__(
                messages,
                max_output_tokens=max_output_tokens,
            )
        finally:
            self._telemetry_scope = prior_scope
            if callable(set_scope):
                if prior_scope is None:
                    set_scope(run_id="", task_id=None)
                else:
                    set_scope(
                        run_id=str(prior_scope.get("run_id") or ""),
                        task_id=prior_scope.get("task_id"),
                    )

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int | None = None,
    ) -> str:
        del max_output_tokens
        payloads = _json_user_payloads(messages)
        initial = _initial_payload(payloads)
        packet_value = initial.get("verifier_packet")
        packet = dict(packet_value) if isinstance(packet_value, Mapping) else {}
        raw_task = str(initial.get("authoritative_task_prompt") or "")
        requirements = _requirements(packet, raw_task)
        results = _all_inspection_results(payloads)
        candidates = build_inspection_candidates(
            packet, results, raw_task=raw_task, requirements=requirements,
            limit=self._max_candidates,
        )
        # Build an uncapped-enough provider-free inventory solely for audit.
        # This never changes the model's candidate set. It distinguishes
        # "host never offered the route" from "Judge saw it and chose another".
        eligible_candidates = build_inspection_candidates(
            packet, results, raw_task=raw_task, requirements=requirements,
            limit=max(512, self._max_candidates),
        )
        selected_route_kinds = sorted({
            str(item.request.get("kind") or "").strip()
            for item in candidates
            if str(item.request.get("kind") or "").strip()
        })
        eligible_route_kinds = sorted({
            str(item.request.get("kind") or "").strip()
            for item in eligible_candidates
            if str(item.request.get("kind") or "").strip()
        })
        available_direct_routes = sorted(_available_routes(packet))
        uninstantiated_reasons = {
            "read_file": "no current Solver-visible file locator",
            "read_output": "no current immutable output/receipt handle",
            "compare_initial_path": "no current Solver-visible file locator",
            "inspect_artifact_history": "no current Solver-visible artifact path",
            "inspect_recent_receipts": "no bounded metadata candidate was constructed",
            "inspect_action_receipts": "no bounded action-history candidate was constructed",
            "probe_port": "no exact task-declared or current-service port",
            "probe_http": "no exact task-declared HTTP(S) URL",
            "probe_process": (
                "no exact current process pattern is available without inventing "
                "generative text; open-ended process-pattern generation is not V3 host authority"
            ),
            "probe_job": "no current managed-job identifier",
            "inspect_artifact": "no current Solver-visible artifact path",
            "perceive_artifact": "no current Solver-visible image path",
        }
        candidate_coverage = {
            "candidate_limit": self._max_candidates,
            "eligible_candidate_count": len(eligible_candidates),
            "selected_candidate_count": len(candidates),
            "available_direct_routes": available_direct_routes,
            "eligible_route_kinds": eligible_route_kinds,
            "selected_route_kinds": selected_route_kinds,
            "truncated_route_kinds": sorted(
                set(eligible_route_kinds) - set(selected_route_kinds)
            ),
            "uninstantiated_available_direct_routes": {
                kind: uninstantiated_reasons.get(
                    kind, "no finite visible-only locator was constructed"
                )
                for kind in available_direct_routes
                if kind not in eligible_route_kinds
            },
            "finite_derived_routes": {
                "rerun_check": (
                    "offered"
                    if "rerun_check" in eligible_route_kinds
                    else "no authoritative_check_ids in current model-visible packet"
                ),
            },
            "reserved_for_v4": [
                "overlay_run_command",
                "overlay_write_fixture",
            ],
        }

        constraint = "inspect_or_verdict"
        for payload in reversed(payloads):
            value = str(payload.get("verifier_turn_constraint") or "").strip()
            if value:
                constraint = value
                break

        state = {
            "raw_task": raw_task,
            "requirements": [
                {
                    "requirement_id": item.requirement_id,
                    "text": item.text,
                    "clause_ids": list(item.clause_ids),
                    "exact_atoms": list(item.exact_atoms),
                }
                for item in requirements
            ],
            "verifier_packet": packet,
            "registered_inspection_results": results,
            "candidate_inspections": [
                {
                    "candidate_key": item.candidate_id,
                    "priority": item.priority,
                    "description": item.description,
                    "request": dict(item.request),
                }
                for item in candidates
            ],
            "candidate_coverage": candidate_coverage,
            "turn_constraint": constraint,
        }

        evidence_criteria, evidence_rows = _evidence_options(results)
        evaluation_rounds: list[dict[str, Any]] = []

        def evaluate(
            label: str,
            eval_state: Mapping[str, Any],
            eval_questions: Mapping[str, Mapping[str, Any]],
        ) -> Mapping[str, Mapping[str, Any]]:
            if not eval_questions:
                return {}
            if len(evaluation_rounds) >= MAX_EVALUATOR_ROUNDS_PER_VERIFIER_CALL:
                raise RuntimeError(
                    "typed Judge evaluator-round budget exhausted inside one Verifier call"
                )
            raw = self._evaluator(eval_state, eval_questions)
            clean = raw if isinstance(raw, Mapping) else {}
            evaluation_rounds.append({
                "label": label,
                "state": dict(eval_state),
                "questions": {str(key): dict(value) for key, value in eval_questions.items()},
                "answers": dict(clean),
            })
            return clean

        statuses: list[tuple[str, dict[str, float]]] = [
            ("insufficient", {}) for _ in requirements
        ]
        selected_evidence: list[Mapping[str, Any] | None] = [
            None for _ in requirements
        ]
        pair_dependence: list[str] = [
            "insufficient" for _ in requirements
        ]
        pair_determinant: list[str] = [
            "uncertain" for _ in requirements
        ]

        if requirements and results:
            semantic_questions = _semantic_questions(requirements, evidence_criteria)
            semantic_state = dict(state)
            semantic_state["semantic_phase"] = "evidence_selection"
            semantic_answers = evaluate(
                "evidence_selection",
                semantic_state,
                semantic_questions,
            )

            for index, _requirement in enumerate(requirements):
                evidence_choice, evidence_probabilities = _answer_choice(
                    semantic_answers,
                    f"evidence_{index}",
                    set(evidence_criteria),
                    "none",
                )
                selected_probability = float(
                    evidence_probabilities.get(evidence_choice, 0.0)
                )
                selected_evidence[index] = (
                    evidence_rows.get(evidence_choice)
                    if (
                        evidence_choice != "none"
                        and selected_probability >= self._min_confidence
                    )
                    else None
                )

            relation_questions = _relation_questions(
                requirements, selected_evidence,
            )
            relation_state = dict(state)
            relation_state["semantic_phase"] = "requirement_evidence_relation"
            relation_state["selected_evidence"] = [
                {
                    "inspection_id": str(row.get("inspection_id") or ""),
                    "kind": str(row.get("kind") or ""),
                    "evidence": _result_excerpt(row),
                }
                if row is not None else None
                for row in selected_evidence
            ]
            relation_answers = evaluate(
                "requirement_evidence_relation",
                relation_state,
                relation_questions,
            )

            for index, row in enumerate(selected_evidence):
                if row is None:
                    continue
                relation, probabilities = _answer_choice(
                    relation_answers,
                    f"relation_{index}",
                    {"supports", "contradicts", "irrelevant", "uncertain"},
                    "uncertain",
                )
                if float(probabilities.get(relation, 0.0)) < self._min_confidence:
                    relation = "uncertain"
                if relation == "supports":
                    statuses[index] = ("established", probabilities)
                elif relation == "contradicts":
                    statuses[index] = ("contradicted", probabilities)
                else:
                    statuses[index] = ("insufficient", probabilities)

                dependence, dependence_probabilities = _answer_choice(
                    relation_answers,
                    f"dependence_{index}",
                    {"independent", "correlated", "insufficient", "not_required"},
                    "insufficient",
                )
                if float(
                    dependence_probabilities.get(dependence, 0.0)
                ) < self._min_confidence:
                    dependence = "insufficient"
                pair_dependence[index] = dependence

                determinant, determinant_probabilities = _answer_choice(
                    relation_answers,
                    f"determinant_{index}",
                    {"yes", "no", "uncertain"},
                    "uncertain",
                )
                if float(
                    determinant_probabilities.get(determinant, 0.0)
                ) < self._min_confidence:
                    determinant = "uncertain"
                pair_determinant[index] = determinant

        all_established = bool(requirements) and all(
            status[0] == "established" for status in statuses
        )
        semantic_safe = bool(requirements) and all(
            dependence in {"independent", "not_required"}
            and determinant == "yes"
            for dependence, determinant in zip(
                pair_dependence, pair_determinant
            )
        )

        if all_established and semantic_safe:
            entries: list[dict[str, Any]] = []
            for requirement, row in zip(requirements, selected_evidence):
                assert row is not None
                inspection_id = str(row.get("inspection_id") or "").strip()
                entries.append({
                    "requirement": requirement.text,
                    "observed": _result_excerpt(row),
                    "falsification_check": (
                        "A current registered inspection showing the opposite "
                        "semantic relation would falsify this obligation."
                    ),
                    "inspection_refs": [inspection_id],
                    "clause_ids": list(requirement.clause_ids),
                    "evidence_class": str(
                        row.get("actual_evidence_class") or ""
                    ).strip(),
                    "risk_refs": [],
                    "requirement_status": "satisfied",
                })
            emitted = {
                "verdict": "completed",
                "confidence": "medium",
                "summary": (
                    "High-confidence typed Judge requirement/evidence relations "
                    "support every mechanically factored raw-task obligation."
                ),
                "findings": [],
                "missing_evidence_requests": [],
                "completion_evidence": entries,
            }
            self._record_trace(
                state, {}, {}, emitted, decision="typed_completed",
                extra={"evaluation_rounds": evaluation_rounds},
            )
            return json.dumps(emitted, sort_keys=True)

        contradicted = [
            (requirement, row)
            for requirement, status, row in zip(
                requirements, statuses, selected_evidence
            )
            if status[0] == "contradicted"
        ]
        if contradicted:
            findings: list[dict[str, Any]] = []
            for index, (requirement, row) in enumerate(contradicted, start=1):
                if row is None:
                    continue
                inspection_id = str(row.get("inspection_id") or "").strip()
                if not inspection_id:
                    continue
                findings.append({
                    "finding_id": f"judge-typed:{requirement.requirement_id}:{index}",
                    "created_step": int(packet.get("step") or 0),
                    "verdict": "needs_repair",
                    "priority": "blocking",
                    "summary": (
                        "Current admissible evidence contradicts raw-task obligation: "
                        + requirement.text
                    ),
                    "evidence": [_result_excerpt(row)],
                    "repair_instruction": (
                        "Repair the task state so this obligation is established: "
                        + requirement.text
                    ),
                    "applies_to": [],
                    "supporting_inspection_ids": [inspection_id],
                    "required_evidence_route": "",
                })
            if findings:
                emitted = {
                    "verdict": "needs_repair",
                    "confidence": "medium",
                    "summary": (
                        "A high-confidence typed Judge relation found a current "
                        "evidence-backed task contradiction."
                    ),
                    "findings": findings,
                    "missing_evidence_requests": [],
                    "completion_evidence": [],
                }
                self._record_trace(
                    state, {}, {}, emitted, decision="typed_contradiction",
                    extra={"evaluation_rounds": evaluation_rounds},
                )
                return json.dumps(emitted, sort_keys=True)

        unresolved_gaps = [
            (
                "No high-confidence current evidence establishes obligation: "
                + requirement.text
            )
            for requirement, status in zip(requirements, statuses)
            if status[0] != "established"
        ]
        for requirement, dependence, determinant in zip(
            requirements, pair_dependence, pair_determinant
        ):
            if dependence in {"correlated", "insufficient"}:
                unresolved_gaps.append(
                    "Evidence for obligation is correlated with production or does "
                    "not establish independence: " + requirement.text
                )
            if determinant != "yes":
                unresolved_gaps.append(
                    "Evidence does not establish the semantic determinant for obligation: "
                    + requirement.text
                )

        if constraint != "verdict_only" and candidates:
            routing_state = dict(state)
            routing_state["semantic_phase"] = "inspection_routing"
            # The routing question already carries every unresolved gap verbatim
            # in its instruction. Do not duplicate the same potentially-large
            # semantic text in provider state: judge receives both state and
            # questions in one request, and the credential-free broker has a
            # fixed 16 KB safety bound.
            routing_questions = _routing_questions(candidates, unresolved_gaps)
            routing_answers = evaluate(
                "inspection_routing",
                routing_state,
                routing_questions,
            )
            allowed_moves = {"verdict_now"} | {
                item.candidate_id for item in candidates
            }
            next_move, next_probabilities = _answer_choice(
                routing_answers,
                "next_move",
                allowed_moves,
                "verdict_now",
            )
            if next_move != "verdict_now":
                selected = next(
                    (
                        item for item in candidates
                        if item.candidate_id == next_move
                    ),
                    None,
                )
                if selected is not None:
                    emitted = {
                        "kind": "inspect",
                        "requests": [dict(selected.request)],
                    }
                    self._record_trace(
                        state, {}, {}, emitted,
                        decision="typed_probe_selected",
                        extra={
                            "evaluation_rounds": evaluation_rounds,
                            "next_move_probabilities": next_probabilities,
                        },
                    )
                    return json.dumps(emitted, sort_keys=True)

        missing = list(unresolved_gaps)
        if not missing:
            missing = ["Additional current admissible verifier evidence is required."]
        emitted = {
            "verdict": "uncertain_missing_evidence",
            "confidence": "medium",
            "summary": (
                "Typed Judge cannot certify completion from current registered evidence."
            ),
            "findings": [],
            "missing_evidence_requests": missing,
            "completion_evidence": [],
        }
        self._record_trace(
            state, {}, {}, emitted, decision="typed_noncompletion",
            extra={"evaluation_rounds": evaluation_rounds},
        )
        return json.dumps(emitted, sort_keys=True)

    def _record_trace(
        self,
        state: Mapping[str, Any],
        questions: Mapping[str, Any],
        answers: Mapping[str, Any],
        emitted: Mapping[str, Any],
        *,
        decision: str,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        canonical_state = json.dumps(
            state, sort_keys=True, default=str, separators=(",", ":"),
        )
        row: dict[str, Any] = {
            "schema": "aether.judge_typed_verifier_trace.v3",
            "policy": {
                "version": V3_POLICY_VERSION,
                "question_policy_version": V3_QUESTION_POLICY_VERSION,
                "question_schema_version": V3_QUESTION_SCHEMA_VERSION,
                "min_semantic_confidence": self._min_confidence,
                "max_candidates": self._max_candidates,
                "max_evaluator_rounds_per_verifier_call": MAX_EVALUATOR_ROUNDS_PER_VERIFIER_CALL,
            },
            "call_index": len(self._trace) + 1,
            "state_sha256": sha256(
                canonical_state.encode("utf-8")
            ).hexdigest(),
            "state": state,
            "questions": questions,
            "answers": answers,
            "emitted_turn": emitted,
            "decision": decision,
        }
        if self._telemetry_scope is not None:
            row["run_id"] = str(self._telemetry_scope.get("run_id") or "")
            row["task_id"] = self._telemetry_scope.get("task_id")
        if extra:
            extra_row = dict(extra)
            rounds = extra_row.pop("evaluation_rounds", None)
            if isinstance(rounds, list):
                row["evaluation_rounds"] = rounds
            if extra_row:
                row["extra"] = extra_row
        self._trace.append(row)


def _provider_semantic_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Project local typed-Verifier state to the semantic facts Judge needs.

    The full unprojected state remains in local V3 audit traces. The provider
    receives exact typed questions plus this bounded semantic context instead
    of a duplicate full verifier packet.
    """
    source = dict(state)
    source_canonical = json.dumps(
        source, sort_keys=True, default=str, separators=(",", ":"), ensure_ascii=False,
    )
    requirements: list[dict[str, Any]] = []
    raw_requirements = source.get("requirements")
    if isinstance(raw_requirements, (list, tuple)):
        for item in list(raw_requirements)[:32]:
            if not isinstance(item, Mapping):
                continue
            requirements.append({
                "requirement_id": str(item.get("requirement_id") or ""),
                "text": _bounded_text(item.get("text"), limit=1200),
                "clause_ids": list(item.get("clause_ids") or ())[:16],
                "exact_atoms": [
                    _bounded_text(value, limit=300)
                    for value in list(item.get("exact_atoms") or ())[:16]
                ],
            })

    coverage: dict[str, Any] = {}
    raw_coverage = source.get("candidate_coverage")
    if isinstance(raw_coverage, Mapping):
        for key in (
            "candidate_limit",
            "eligible_candidate_count",
            "selected_candidate_count",
            "available_direct_routes",
            "eligible_route_kinds",
            "selected_route_kinds",
            "truncated_route_kinds",
            "finite_derived_routes",
        ):
            value = raw_coverage.get(key)
            if value not in (None, "", [], {}):
                coverage[key] = value

    selected: list[dict[str, Any]] = []
    raw_selected = source.get("selected_evidence")
    if isinstance(raw_selected, (list, tuple)):
        for item in list(raw_selected)[:32]:
            if not isinstance(item, Mapping):
                selected.append({})
                continue
            selected.append({
                "inspection_id": str(item.get("inspection_id") or ""),
                "kind": str(item.get("kind") or ""),
                "evidence": _bounded_text(item.get("evidence"), limit=1600),
            })

    results = source.get("registered_inspection_results")
    candidates = source.get("candidate_inspections")
    unresolved = source.get("unresolved_gaps")
    projected: dict[str, Any] = {
        "schema": V3_PROVIDER_STATE_PROJECTION_VERSION,
        "source_state_sha256": sha256(source_canonical.encode("utf-8")).hexdigest(),
        "source_state_bytes": len(source_canonical.encode("utf-8")),
        "semantic_phase": str(source.get("semantic_phase") or ""),
        "turn_constraint": str(source.get("turn_constraint") or ""),
        "raw_task": _bounded_text(source.get("raw_task"), limit=4000),
        "requirements": requirements,
        "registered_inspection_count": len(results) if isinstance(results, (list, tuple)) else 0,
        "candidate_count": len(candidates) if isinstance(candidates, (list, tuple)) else 0,
        "candidate_coverage": coverage,
        "unresolved_gap_count": len(unresolved) if isinstance(unresolved, (list, tuple)) else 0,
    }
    if selected:
        projected["selected_evidence"] = selected
    return projected


def _catalog_criteria(
    question_rows: Mapping[str, Mapping[str, Any]],
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, str],
]:
    """Deduplicate exact choice-description maps without changing choice keys."""
    catalogs: dict[str, dict[str, str]] = {}
    canonical_to_key: dict[str, str] = {}
    question_to_key: dict[str, str] = {}
    for question_id, raw_question in question_rows.items():
        raw_criteria = raw_question.get("criteria")
        criteria = (
            {str(key): str(value) for key, value in raw_criteria.items()}
            if isinstance(raw_criteria, Mapping)
            else {}
        )
        canonical = json.dumps(
            criteria, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        catalog_key = canonical_to_key.get(canonical)
        if catalog_key is None:
            catalog_key = f"c{len(canonical_to_key) + 1}"
            canonical_to_key[canonical] = catalog_key
            catalogs[catalog_key] = criteria
        question_to_key[str(question_id)] = catalog_key
    return catalogs, question_to_key


def _provider_question_projection(
    source_state: Mapping[str, Any],
    provider_state: Mapping[str, Any],
    questions: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    """Deduplicate repeated semantic referents while preserving typed choices.

    Full local state/questions stay in typed-Verifier traces. Provider-visible
    catalogs retain each exact semantic description once; projected questions
    keep their stable IDs and exact choice keys and point back to those catalogs.
    """
    phase = str(source_state.get("semantic_phase") or "")
    projected_questions = {
        str(key): dict(value) for key, value in questions.items()
    }
    if phase not in {"evidence_selection", "requirement_evidence_relation"}:
        return (
            dict(provider_state),
            projected_questions,
            V3_PROVIDER_STATE_PROJECTION_VERSION,
        )

    raw_requirements = source_state.get("requirements")
    requirements: dict[str, dict[str, Any]] = {}
    if isinstance(raw_requirements, (list, tuple)):
        for index, raw_requirement in enumerate(raw_requirements):
            if not isinstance(raw_requirement, Mapping):
                continue
            requirements[f"r{index}"] = {
                "requirement_id": str(raw_requirement.get("requirement_id") or ""),
                "text": str(raw_requirement.get("text") or ""),
                "clause_ids": list(raw_requirement.get("clause_ids") or ()),
                "exact_atoms": list(raw_requirement.get("exact_atoms") or ()),
            }

    criteria_catalog, question_criteria = _catalog_criteria(projected_questions)

    if phase == "evidence_selection":
        compact_questions: dict[str, dict[str, Any]] = {}
        question_bindings: dict[str, dict[str, str]] = {}
        for question_id, raw_question in projected_questions.items():
            question = dict(raw_question)
            requirement_key = ""
            try:
                prefix, suffix = question_id.rsplit("_", 1)
                if prefix == "evidence":
                    requirement_key = f"r{int(suffix)}"
            except (TypeError, ValueError):
                requirement_key = ""
            criteria_key = question_criteria.get(question_id, "")
            if requirement_key in requirements and criteria_key in criteria_catalog:
                question_bindings[question_id] = {
                    "requirement_key": requirement_key,
                    "criteria_key": criteria_key,
                }
                question["instructions"] = (
                    f"Using provider state requirements[{requirement_key!r}] and "
                    f"criteria_catalog[{criteria_key!r}], choose the one current "
                    "registered inspection most materially relevant to this exact "
                    "raw-task obligation. Choose 'none' when no current inspection "
                    "materially bears on it."
                )
                question["criteria"] = {
                    choice: (
                        f"See provider state criteria_catalog[{criteria_key!r}]"
                        f"[{choice!r}]."
                    )
                    for choice in criteria_catalog[criteria_key]
                }
            compact_questions[question_id] = question

        evidence_state = {
            "schema": "aether.judge.evidence-selection-catalog.v1",
            "source_state_sha256": str(provider_state.get("source_state_sha256") or ""),
            "source_state_bytes": provider_state.get("source_state_bytes"),
            "semantic_phase": phase,
            "turn_constraint": str(source_state.get("turn_constraint") or ""),
            "raw_task": str(provider_state.get("raw_task") or ""),
            "requirements": requirements,
            "criteria_catalog": criteria_catalog,
            "question_bindings": question_bindings,
        }
        return (
            evidence_state,
            compact_questions,
            "aether.judge.evidence-selection-catalog.v1",
        )

    raw_selected = source_state.get("selected_evidence")
    if not isinstance(raw_selected, (list, tuple)):
        return (
            dict(provider_state),
            projected_questions,
            V3_PROVIDER_STATE_PROJECTION_VERSION,
        )

    evidence_catalog: dict[str, dict[str, Any]] = {}
    relation_pairs: dict[str, dict[str, str]] = {}
    evidence_keys: dict[tuple[str, str, str], str] = {}
    for index, raw_evidence in enumerate(raw_selected):
        requirement_key = f"r{index}"
        if requirement_key not in requirements or not isinstance(raw_evidence, Mapping):
            continue
        identity = (
            str(raw_evidence.get("inspection_id") or ""),
            str(raw_evidence.get("kind") or ""),
            str(raw_evidence.get("evidence") or ""),
        )
        evidence_key = evidence_keys.get(identity)
        if evidence_key is None:
            evidence_key = f"e{len(evidence_keys) + 1}"
            evidence_keys[identity] = evidence_key
            evidence_catalog[evidence_key] = {
                "inspection_id": identity[0],
                "kind": identity[1],
                "evidence": identity[2],
            }
        relation_pairs[f"p{index}"] = {
            "requirement_key": requirement_key,
            "evidence_key": evidence_key,
        }

    compact_questions = {}
    question_bindings: dict[str, dict[str, str]] = {}
    for question_id, raw_question in projected_questions.items():
        question = dict(raw_question)
        pair_key = ""
        try:
            head, suffix = question_id.rsplit("_", 1)
            if head in {"relation", "dependence", "determinant"}:
                pair_key = f"p{int(suffix)}"
        except (TypeError, ValueError):
            pair_key = ""
        criteria_key = question_criteria.get(question_id, "")
        if pair_key in relation_pairs and criteria_key in criteria_catalog:
            question_bindings[question_id] = {
                "pair_key": pair_key,
                "criteria_key": criteria_key,
            }
            question_bindings[question_id]["head"] = question_id.rsplit("_", 1)[0]
            question["instructions"] = (
                f"Use provider state question_bindings[{question_id!r}] and its "
                "referenced pair/criteria catalogs to answer this semantic head. "
                "Judge only that pair."
            )
            question["criteria"] = {
                choice: choice
                for choice in criteria_catalog[criteria_key]
            }
        compact_questions[question_id] = question

    relation_state = {
        "schema": V3_RELATION_PROVIDER_PROJECTION_VERSION,
        "source_state_sha256": str(provider_state.get("source_state_sha256") or ""),
        "source_state_bytes": provider_state.get("source_state_bytes"),
        "semantic_phase": phase,
        "turn_constraint": str(source_state.get("turn_constraint") or ""),
        "requirements": requirements,
        "evidence": evidence_catalog,
        "relation_pairs": relation_pairs,
        "criteria_catalog": criteria_catalog,
        "question_bindings": question_bindings,
    }
    return (
        relation_state,
        compact_questions,
        V3_RELATION_PROVIDER_PROJECTION_VERSION,
    )


class JudgeQuestionAdapter:
    """Adapt a judge transport and retain explicit Judge usage telemetry."""

    def __init__(self, transport: Any, *, model: str = "judge-1.13.0") -> None:
        model_name = str(model or "").strip()
        if not model_name:
            raise ValueError("judge model name must be non-empty")
        self._transport = transport
        self._model = model_name
        self._telemetry: list[dict[str, Any]] = []
        self._telemetry_scope: dict[str, str | None] | None = None

    def bind_run_cancellation(self, event: Any) -> None:
        bind = getattr(self._transport, "bind_run_cancellation", None)
        if callable(bind):
            bind(event)

    def set_telemetry_scope(
        self, *, run_id: str, task_id: str | None = None,
    ) -> None:
        clean_run = str(run_id or "").strip()
        self._telemetry_scope = (
            {"run_id": clean_run, "task_id": task_id}
            if clean_run else None
        )

    def drain_telemetry(self) -> list[dict[str, Any]]:
        rows = list(self._telemetry)
        self._telemetry.clear()
        return rows

    def __call__(
        self,
        state: Mapping[str, Any],
        questions: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Mapping[str, Any]]:
        source_state = dict(state)
        base_provider_state = _provider_semantic_state(source_state)
        provider_state = dict(base_provider_state)
        provider_questions = {
            str(key): dict(value) for key, value in questions.items()
        }
        provider_projection = V3_PROVIDER_STATE_PROJECTION_VERSION

        def build_request() -> tuple[dict[str, Any], int]:
            row = {
                "model": self._model,
                "state": provider_state,
                "questions": provider_questions,
            }
            canonical = json.dumps(
                row,
                sort_keys=True,
                default=str,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            return row, len(canonical.encode("utf-8"))

        request, request_bytes = build_request()
        if request_bytes > V3_PROVIDER_REQUEST_HARD_LIMIT_BYTES:
            provider_state, provider_questions, provider_projection = (
                _provider_question_projection(
                    source_state,
                    base_provider_state,
                    questions,
                )
            )
            request, request_bytes = build_request()
        if request_bytes > V3_PROVIDER_REQUEST_HARD_LIMIT_BYTES:
            raise ValueError(
                "typed JUDGE provider request exceeds declared bound after semantic projection: "
                f"{request_bytes} > {V3_PROVIDER_REQUEST_HARD_LIMIT_BYTES}"
            )
        response = self._transport(request)
        if not isinstance(response, Mapping):
            raise ValueError("judge response is not a mapping")

        result = response.get("result")
        answers: Mapping[str, Any] | None = None
        usage: Mapping[str, Any] | None = None
        reported_model = self._model
        provider = str(response.get("provider") or "").strip()
        if isinstance(result, Mapping):
            if isinstance(result.get("answers"), Mapping):
                answers = result["answers"]
            if isinstance(result.get("usage"), Mapping):
                usage = result["usage"]
            if str(result.get("model") or "").strip():
                reported_model = str(result.get("model")).strip()
        if answers is None and isinstance(response.get("answers"), Mapping):
            answers = response["answers"]
        if usage is None and isinstance(response.get("usage"), Mapping):
            usage = response["usage"]

        usage_row: dict[str, int | float] = {}
        if isinstance(usage, Mapping):
            for key, value in usage.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                usage_row[str(key)] = value

        canonical_state = json.dumps(
            source_state, sort_keys=True, default=str, separators=(",", ":"), ensure_ascii=False,
        )
        canonical_provider_state = json.dumps(
            provider_state, sort_keys=True, default=str, separators=(",", ":"), ensure_ascii=False,
        )
        telemetry_row = {
            "schema": "aether.judge_adapter_telemetry.v2",
            "call_index": len(self._telemetry) + 1,
            "requested_model": self._model,
            "reported_model": reported_model,
            "provider": provider,
            "state_sha256": sha256(canonical_state.encode("utf-8")).hexdigest(),
            "provider_state_projection": provider_projection,
            "provider_state_sha256": sha256(
                canonical_provider_state.encode("utf-8")
            ).hexdigest(),
            "provider_state_bytes": len(canonical_provider_state.encode("utf-8")),
            "provider_request_bytes": request_bytes,
            "question_ids": sorted(str(key) for key in provider_questions),
            "question_policy_version": V3_QUESTION_POLICY_VERSION,
            "question_schema_version": V3_QUESTION_SCHEMA_VERSION,
            "usage": usage_row,
        }
        if self._telemetry_scope is not None:
            telemetry_row["run_id"] = str(
                self._telemetry_scope.get("run_id") or ""
            )
            telemetry_row["task_id"] = self._telemetry_scope.get("task_id")
        self._telemetry.append(telemetry_row)
        if answers is None:
            raise ValueError("judge response does not contain answers")
        return answers
