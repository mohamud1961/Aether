"""Deterministic preparation and scoring for bounded Architect v2 canaries."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .architect_v2_adapter import adapt_architect_v2_to_runtime
from .architect_v2_contract import (
    ArchitectV2Contract,
    architect_v2_provider_schema,
    find_exact_normalized_duplicates,
    validate_architect_v2,
)
from .architect_v2_model import (
    ARCHITECT_V2_MAX_OUTPUT_TOKENS,
    ARCHITECT_V2_SYSTEM_PROMPT,
    build_architect_v2_model_request,
)
from .compiler import CapabilityRegistry, ConfigCompiler
from .runtime_ir import CapabilityDescriptor, CompletionPolicy, EnvMap, RuntimeConfigIR


@dataclass(frozen=True)
class ArchitectV2CanaryPolicy:
    max_system_prompt_chars: int = 6_000
    max_request_chars: int = 20_000
    max_schema_chars: int = 20_000
    max_raw_output_chars: int = 32_000
    max_output_tokens: int = ARCHITECT_V2_MAX_OUTPUT_TOKENS
    max_total_tokens: int = 20_000
    max_reasoning_tokens: int = 10_000
    deterministic_score_required: int = 14
    model_calls_required: int = 1


DEFAULT_CANARY_POLICY = ArchitectV2CanaryPolicy()


@dataclass(frozen=True)
class ArchitectV2DeterministicScore:
    score: int
    ceiling: int
    checks: Mapping[str, bool]
    findings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.score == self.ceiling and not self.findings


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )



def build_public_fixture_envmap(row: Mapping[str, Any]) -> EnvMap:
    """Build the isolated factual EnvMap used by public v2 canaries."""

    return EnvMap(
        task_prompt=str(row["task_prompt"]),
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem",
                "workspace file access",
                tool_names=("read_file", "write_file"),
            ),
            "shell": CapabilityDescriptor(
                "shell",
                "local command execution",
                tool_names=("run_command",),
            ),
            "managed_process": CapabilityDescriptor(
                "managed_process",
                "managed local services",
                tool_names=("launch_process", "stop_process"),
            ),
            "service_probe": CapabilityDescriptor(
                "service_probe",
                "local service probes",
                tool_names=("probe_service",),
            ),
            "artifact_inspection": CapabilityDescriptor(
                "artifact_inspection",
                "artifact inspection",
                tool_names=("inspect_artifact",),
            ),
        },
        task_metadata={
            "visible_examples": [
                {
                    "fact_id": fact["fact_id"],
                    "statement": fact["statement"],
                    "source": fact["source"],
                    "verbatim_anchors": list(fact.get("verbatim_anchors", ())),
                }
                for fact in row["facts"]
            ],
            "visible_material_summary": {
                "source": "public_zero_model_fixture",
                "fact_count": len(row["facts"]),
            },
        },
    )

def build_neutral_canary_baseline(envmap: EnvMap) -> RuntimeConfigIR:
    selected = tuple(
        item.capability_id
        for item in sorted(envmap.capabilities.values(), key=lambda row: row.capability_id)
        if item.available
    )
    return RuntimeConfigIR(
        architect_summary="",
        solver_identity_prompt="",
        selected_capabilities=selected,
        completion_policy=CompletionPolicy(
            require_authoritative_check=False,
            allow_evidence_fallback=True,
            require_all_obligations=True,
            require_recent_progress=False,
            require_clean_integrity=True,
        ),
    )


def _fact_rows(contract: ArchitectV2Contract) -> tuple[Mapping[str, Any], ...]:
    return tuple(contract.payload["task_contract"]["exact_facts"])


def _anchor_spans_overlap(left: str, right: str) -> bool:
    return bool(left and right and (left in right or right in left))


def _method_anchor_set(contract: ArchitectV2Contract) -> frozenset[str]:
    return frozenset(
        str(anchor)
        for row in _required_method_rows(contract)
        for anchor in row.get("verbatim_anchors", ())
    )


def _outcome_anchor_set(contract: ArchitectV2Contract) -> frozenset[str]:
    return frozenset(
        str(anchor)
        for row in _fact_rows(contract)
        for anchor in row.get("verbatim_anchors", ())
    )


def _anchor_ownership_map(
    contract: ArchitectV2Contract,
) -> dict[str, frozenset[str]]:
    ownership: dict[str, set[str]] = {}
    for row in _fact_rows(contract):
        for anchor in row.get("verbatim_anchors", ()):
            ownership.setdefault(str(anchor), set()).add("outcome")
    for row in _required_method_rows(contract):
        for anchor in row.get("verbatim_anchors", ()):
            ownership.setdefault(str(anchor), set()).add("method")
    return {anchor: frozenset(owners) for anchor, owners in ownership.items()}


def _reference_anchors_preserved(
    candidate: ArchitectV2Contract,
    reference: ArchitectV2Contract,
) -> bool:
    """Preserve outcome anchors exactly and method authority by grounded span.

    This general coverage slot must not re-freeze method anchor tokenisation
    after the dedicated authority checks have accepted a longer or shorter
    visible span. It remains strict for outcome anchors.
    """

    if not _outcome_anchor_set(reference) <= _outcome_anchor_set(candidate):
        return False
    candidate_methods = _method_anchor_set(candidate)
    return all(
        any(
            _anchor_spans_overlap(reference_anchor, candidate_anchor)
            for candidate_anchor in candidate_methods
        )
        for reference_anchor in _method_anchor_set(reference)
    )


def _reference_fact_authority_preserved(
    candidate: ArchitectV2Contract,
    reference: ArchitectV2Contract,
) -> bool:
    """Preserve lane ownership while permitting method-span refinement.

    Outcome anchors remain exact. Method anchors may use a longer or shorter
    grounded verbatim span only when one span contains the other. A method-only
    reference span may not be promoted into the candidate outcome lane.
    """

    candidate_outcomes = _outcome_anchor_set(candidate)
    candidate_methods = _method_anchor_set(candidate)
    reference_outcomes = _outcome_anchor_set(reference)
    reference_methods = _method_anchor_set(reference)

    if not reference_outcomes <= candidate_outcomes:
        return False
    for anchor in reference_methods:
        if not any(
            _anchor_spans_overlap(anchor, candidate_anchor)
            for candidate_anchor in candidate_methods
        ):
            return False
        # Cross-lane promotion is exact: short outcome literals such as `ok`
        # may legitimately occur inside a distinct method path such as
        # `/app/server_ok.py`. Span refinement applies only method-to-method.
        if anchor not in reference_outcomes and anchor in candidate_outcomes:
            return False
    return True


def _obligation_rows(contract: ArchitectV2Contract) -> tuple[Mapping[str, Any], ...]:
    return tuple(contract.payload["task_contract"]["obligations"])


def _proof_rows(contract: ArchitectV2Contract) -> tuple[Mapping[str, Any], ...]:
    return tuple(contract.payload["proof_intent"])


def _risk_rows(contract: ArchitectV2Contract) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        contract.payload["verifier_design"].get("false_positive_risks", ())
    )


def _required_method_rows(
    contract: ArchitectV2Contract,
) -> tuple[Mapping[str, Any], ...]:
    return tuple(contract.payload.get("method_constraints", ()))


def _anchor_set(contract: ArchitectV2Contract) -> set[str]:
    return {
        str(anchor)
        for row in (*_fact_rows(contract), *_required_method_rows(contract))
        for anchor in row.get("verbatim_anchors", ())
    }


def _obligation_anchor_groups(contract: ArchitectV2Contract) -> tuple[frozenset[str], ...]:
    facts = {str(row["fact_id"]): row for row in _fact_rows(contract)}
    groups = []
    for obligation in _obligation_rows(contract):
        anchors = {
            str(anchor)
            for fact_id in obligation.get("fact_refs", ())
            for anchor in facts[str(fact_id)].get("verbatim_anchors", ())
        }
        groups.append(frozenset(anchors))
    return tuple(groups)


def _obligation_anchor_map(
    contract: ArchitectV2Contract,
) -> dict[str, frozenset[str]]:
    return {
        str(row["obligation_id"]): group
        for row, group in zip(
            _obligation_rows(contract),
            _obligation_anchor_groups(contract),
        )
    }


def _fact_anchor_map(
    contract: ArchitectV2Contract,
) -> dict[str, frozenset[str]]:
    return {
        str(row["fact_id"]): frozenset(
            str(anchor) for anchor in row.get("verbatim_anchors", ())
        )
        for row in _fact_rows(contract)
    }


def _method_authority_map(
    contract: ArchitectV2Contract,
) -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    obligations = _obligation_anchor_map(contract)
    result: dict[str, tuple[frozenset[str], frozenset[str]]] = {}
    for row in _required_method_rows(contract):
        method_id = str(row["constraint_id"])
        fact_anchors = frozenset(
            str(anchor) for anchor in row.get("verbatim_anchors", ())
        )
        obligation_anchors = frozenset().union(
            *(
                obligations.get(str(ref), frozenset())
                for ref in row.get("obligation_refs", ())
            )
        )
        result[method_id] = (fact_anchors, obligation_anchors)
    return result


def _reference_required_methods_preserved(
    candidate: ArchitectV2Contract,
    reference: ArchitectV2Contract,
) -> bool:
    """Compare mandatory method authority without freezing wording or tool names.

    A candidate may rename, merge, or refine required-method rules. It must keep
    every defining visible fact anchor in the dedicated method_constraints lane
    and bind the method to overlapping final-outcome authority. Advisory prose,
    strategy text, or an equivalent fact outside the formal method lane cannot
    satisfy the reference requirement.
    """

    reference_methods = _method_authority_map(reference)
    candidate_methods = _method_authority_map(candidate)
    if not reference_methods:
        return not candidate_methods

    all_reference_anchors = frozenset().union(
        *(method_anchors for method_anchors, _ in reference_methods.values())
    )
    for candidate_anchors, candidate_obligations in candidate_methods.values():
        if not candidate_anchors:
            return False
        if any(
            not any(
                _anchor_spans_overlap(candidate_anchor, reference_anchor)
                for reference_anchor in all_reference_anchors
            )
            for candidate_anchor in candidate_anchors
        ):
            return False
        overlapping_references = tuple(
            (required_anchors, required_obligations)
            for required_anchors, required_obligations in reference_methods.values()
            if any(
                _anchor_spans_overlap(candidate_anchor, reference_anchor)
                for candidate_anchor in candidate_anchors
                for reference_anchor in required_anchors
            )
        )
        if not overlapping_references:
            return False
        if candidate_obligations and not any(
            not required_obligations
            or candidate_obligations.intersection(required_obligations)
            for _, required_obligations in overlapping_references
        ):
            return False

    for required_anchors, required_obligations in reference_methods.values():
        if not required_anchors:
            return False
        covering = tuple(
            (candidate_anchors, candidate_obligations)
            for candidate_anchors, candidate_obligations in candidate_methods.values()
            if any(
                _anchor_spans_overlap(candidate_anchor, reference_anchor)
                for candidate_anchor in candidate_anchors
                for reference_anchor in required_anchors
            )
            and (
                not required_obligations
                or candidate_obligations.intersection(required_obligations)
            )
        )
        if not covering:
            return False
        for required_anchor in required_anchors:
            if not any(
                _anchor_spans_overlap(required_anchor, candidate_anchor)
                for candidate_anchors, _ in covering
                for candidate_anchor in candidate_anchors
            ):
                return False
    return True


def _risk_anchor_map(
    contract: ArchitectV2Contract,
) -> dict[str, frozenset[str]]:
    obligation_anchors = _obligation_anchor_map(contract)
    all_anchors = frozenset().union(*obligation_anchors.values())
    result: dict[str, frozenset[str]] = {}
    for row in _risk_rows(contract):
        risk_id = str(row["risk_id"])
        refs = tuple(str(item) for item in row.get("obligation_refs", ()))
        result[risk_id] = (
            frozenset().union(
                *(obligation_anchors.get(ref, frozenset()) for ref in refs)
            )
            if refs
            else all_anchors
        )
    return result


def _proof_kinds_by_risk(
    contract: ArchitectV2Contract,
) -> dict[str, frozenset[str]]:
    result: dict[str, set[str]] = {
        str(row["risk_id"]): set()
        for row in _risk_rows(contract)
    }
    for proof in _proof_rows(contract):
        proof_kind = str(proof["proof_kind"])
        for risk_id in proof.get("risk_refs", ()):
            result.setdefault(str(risk_id), set()).add(proof_kind)
    return {
        risk_id: frozenset(kinds)
        for risk_id, kinds in result.items()
    }


def _proof_kinds_by_obligation(
    contract: ArchitectV2Contract,
) -> dict[str, frozenset[str]]:
    result: dict[str, set[str]] = {
        str(row["obligation_id"]): set()
        for row in _obligation_rows(contract)
    }
    for proof in _proof_rows(contract):
        proof_kind = str(proof["proof_kind"])
        for obligation_id in proof["obligation_refs"]:
            result[str(obligation_id)].add(proof_kind)
    return {
        obligation_id: frozenset(kinds)
        for obligation_id, kinds in result.items()
    }


def _proof_kind_requirement_satisfied(
    required_kind: str,
    available_kinds: frozenset[str],
) -> bool:
    """Return whether candidate evidence is at least as strong as Gold evidence.

    Gold proof kinds are normalized evidence expectations, not an immutable route
    ontology. Exact equality is accepted. In addition, independent_comparison may
    satisfy exact_state for the same authority anchors because it compares the
    current candidate against an independently derived authoritative expectation.
    The relation is intentionally one-way: exact_state cannot satisfy an
    independent_comparison requirement, and no kind substitutes for public
    behavior or direct perception.
    """

    return (
        required_kind in available_kinds
        or (
            required_kind == "exact_state"
            and "independent_comparison" in available_kinds
        )
    )


def _reference_risk_authority_preserved(
    candidate: ArchitectV2Contract,
    reference: ArchitectV2Contract,
) -> bool:
    """Compare material risk authority without freezing IDs or prose.

    A candidate may rename, merge, repartition, or refine risks. Gold risks may
    be attached to a coarse obligation even when the actual counterexample
    concerns only one independently judgeable part. For each Gold risk, at least
    one candidate risk must overlap its visible obligation authority and the
    overlapping candidate risks must provide proof kinds at least as strong as
    the Gold facets that formally close that risk. Exact risk prose, IDs, and the
    full coarse obligation anchor set are not frozen.
    """

    reference_anchors = _risk_anchor_map(reference)
    if not reference_anchors:
        return True
    candidate_anchors = _risk_anchor_map(candidate)
    reference_kinds = _proof_kinds_by_risk(reference)
    candidate_kinds = _proof_kinds_by_risk(candidate)
    for reference_id, required_anchors in reference_anchors.items():
        if not required_anchors:
            return False
        covering_ids = tuple(
            candidate_id
            for candidate_id, anchors in candidate_anchors.items()
            if anchors and anchors.intersection(required_anchors)
        )
        if not covering_ids:
            return False
        available_kinds = frozenset().union(
            *(candidate_kinds.get(candidate_id, frozenset()) for candidate_id in covering_ids)
        )
        if not all(
            _proof_kind_requirement_satisfied(required_kind, available_kinds)
            for required_kind in reference_kinds.get(reference_id, frozenset())
        ):
            return False
    return True


def _reference_refinement_checks(
    candidate: ArchitectV2Contract,
    reference: ArchitectV2Contract,
) -> tuple[bool, bool]:
    """Judge proof/authority preservation without freezing Gold ontology.

    Gold obligation partitions are evidence fixtures, not a universal semantic
    ontology. A candidate may partition or coarsen them. For each Gold obligation,
    candidate obligations that overlap its visible authority must collectively
    retain every Gold anchor and every required proof kind. This permits one
    model-authored end-to-end obligation to carry several conjunctive proof facets
    while still failing contracts that omit exact-state or behavioral evidence.
    """

    candidate_anchors = _obligation_anchor_map(candidate)
    reference_anchors = _obligation_anchor_map(reference)
    candidate_kinds = _proof_kinds_by_obligation(candidate)
    reference_kinds = _proof_kinds_by_obligation(reference)

    anchors_preserved = True
    proof_kinds_preserved = True
    for reference_id, required_anchors in reference_anchors.items():
        if not required_anchors:
            anchors_preserved = False
            proof_kinds_preserved = False
            continue
        covering_ids = tuple(
            candidate_id
            for candidate_id, anchors in candidate_anchors.items()
            if anchors and anchors.intersection(required_anchors)
        )
        covered_anchors = frozenset().union(
            *(
                candidate_anchors[candidate_id].intersection(required_anchors)
                for candidate_id in covering_ids
            )
        )
        if covered_anchors != required_anchors:
            anchors_preserved = False
        available_kinds = frozenset().union(
            *(candidate_kinds.get(candidate_id, frozenset()) for candidate_id in covering_ids)
        )
        required_kinds = reference_kinds.get(reference_id, frozenset())
        if not all(
            _proof_kind_requirement_satisfied(required_kind, available_kinds)
            for required_kind in required_kinds
        ):
            proof_kinds_preserved = False
    return anchors_preserved, proof_kinds_preserved


def score_architect_v2_candidate(
    candidate: ArchitectV2Contract | Mapping[str, Any],
    *,
    reference: ArchitectV2Contract | Mapping[str, Any],
    request: Mapping[str, Any],
    envmap: EnvMap,
    raw_output: str = "",
    policy: ArchitectV2CanaryPolicy = DEFAULT_CANARY_POLICY,
) -> ArchitectV2DeterministicScore:
    candidate_contract = (
        candidate if isinstance(candidate, ArchitectV2Contract)
        else validate_architect_v2(candidate)
    )
    reference_contract = (
        reference if isinstance(reference, ArchitectV2Contract)
        else validate_architect_v2(reference)
    )
    request_text = _canonical(request)
    candidate_anchors = _anchor_set(candidate_contract)
    reference_anchors_preserved = _reference_anchors_preserved(
        candidate_contract, reference_contract,
    )
    candidate_group_rows = _obligation_anchor_groups(candidate_contract)
    reference_group_rows = _obligation_anchor_groups(reference_contract)
    (
        reference_anchor_groups_preserved,
        reference_proof_kinds_preserved,
    ) = _reference_refinement_checks(candidate_contract, reference_contract)
    reference_risk_authority_preserved = _reference_risk_authority_preserved(
        candidate_contract,
        reference_contract,
    )
    reference_required_methods_preserved = _reference_required_methods_preserved(
        candidate_contract,
        reference_contract,
    )
    reference_fact_authority_preserved = _reference_fact_authority_preserved(
        candidate_contract,
        reference_contract,
    )
    duplicate_rows = find_exact_normalized_duplicates(candidate_contract.payload)

    compile_valid = False
    role_isolation = False
    v1_mirrors_absent = False
    try:
        baseline = build_neutral_canary_baseline(envmap)
        adapted = adapt_architect_v2_to_runtime(
            candidate_contract,
            baseline=baseline,
            envmap=envmap,
        )
        compiled = ConfigCompiler(CapabilityRegistry.from_envmap(envmap)).compile(
            adapted.runtime_ir,
            envmap,
        )
        sections = dict(compiled.stable_prefix_sections)
        compile_valid = True
        emphasis_rows = tuple(candidate_contract.payload.get("information_emphasis", ()))
        role_isolation = (
            compiled.verifier_identity_prompt not in "\n".join(sections.values())
            and "[Architect v2 information emphasis]" not in compiled.verifier_identity_prompt
            and all(
                not str(item.get("rationale", "")).strip()
                or str(item.get("rationale", "")).strip() not in compiled.verifier_identity_prompt
                for item in emphasis_rows
            )
        )
        v1_mirrors_absent = all(
            key not in sections
            for key in (
                "architect_visible_contract",
                "success_definition",
                "solver_clause_contract",
                "inspection_plan",
                "proof_plan",
            )
        )
    except Exception:
        compile_valid = False

    checks = {
        "schema_valid": True,
        "reference_anchors_preserved": reference_anchors_preserved,
        "candidate_anchors_grounded": all(anchor in request_text for anchor in candidate_anchors),
        "candidate_exact_facts_grounded": all(
            tuple(fact.get("verbatim_anchors", ()))
            and all(str(anchor) in request_text for anchor in fact.get("verbatim_anchors", ()))
            for fact in _fact_rows(candidate_contract)
        ),
        "reference_obligations_groundable": all(reference_group_rows),
        "reference_obligation_anchor_groups_preserved": reference_anchor_groups_preserved,
        "reference_proof_kinds_preserved": reference_proof_kinds_preserved,
        # Obligation proof coverage is already a validator invariant. Use this
        # score slot for the non-redundant Gold risk-authority refinement gate.
        "reference_risk_authority_preserved": reference_risk_authority_preserved,
        # Solver mission/strategy presence is already a schema invariant. Use
        # this score slot for non-redundant mandatory-method authority.
        "reference_required_methods_preserved": reference_required_methods_preserved,
        # Verifier role presence is already a schema invariant. This slot
        # now enforces the non-redundant model-authored fact ownership boundary.
        "reference_fact_authority_preserved": reference_fact_authority_preserved,
        "no_exact_normalized_duplicates": not duplicate_rows,
        "adapter_compile_valid": compile_valid,
        "role_isolation": role_isolation,
        "v1_semantic_mirrors_absent": v1_mirrors_absent,
    }
    findings = []
    for name, passed in checks.items():
        if not passed:
            findings.append(name)
    if raw_output and len(raw_output) > policy.max_raw_output_chars:
        findings.append("raw_output_char_ceiling_exceeded")
    return ArchitectV2DeterministicScore(
        score=sum(bool(value) for value in checks.values()),
        ceiling=len(checks),
        checks=checks,
        findings=tuple(findings),
    )


def evaluate_provider_telemetry(
    events: Sequence[Mapping[str, Any]],
    *,
    policy: ArchitectV2CanaryPolicy = DEFAULT_CANARY_POLICY,
) -> dict[str, Any]:
    event = dict(events[-1]) if events else {}
    total_tokens = event.get("total_tokens")
    reasoning_tokens = event.get("reasoning_tokens")
    output_tokens = event.get("output_tokens")
    status = str(event.get("usage_status", "unmeasured"))
    checks = {
        "exactly_one_provider_call": len(events) == policy.model_calls_required,
        "usage_reported": status == "reported",
        "output_tokens_within_ceiling": (
            isinstance(output_tokens, int) and output_tokens <= policy.max_output_tokens
        ),
        "total_tokens_within_ceiling": (
            isinstance(total_tokens, int) and total_tokens <= policy.max_total_tokens
        ),
        "reasoning_tokens_within_ceiling": (
            isinstance(reasoning_tokens, int) and reasoning_tokens <= policy.max_reasoning_tokens
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "event": event,
        "policy": asdict(policy),
    }


def canary_status_for_mechanical_gate(mechanical_gate_passed: bool) -> str:
    """Mechanical success remains pending until independent semantic review."""
    return "pending_manual_review" if mechanical_gate_passed else "failed"


def build_canary_plan(
    envmap: EnvMap,
    *,
    reference: Mapping[str, Any],
    fixture_name: str,
    effort: str,
    max_output_tokens: int,
    policy: ArchitectV2CanaryPolicy = DEFAULT_CANARY_POLICY,
) -> dict[str, Any]:
    if effort not in {"low", "medium"}:
        raise ValueError("Architect v2 canary effort must be low or medium")
    if int(max_output_tokens) > policy.max_output_tokens:
        raise ValueError("Architect v2 canary output ceiling exceeds policy")
    validate_architect_v2(reference)
    request = build_architect_v2_model_request(envmap)
    schema = architect_v2_provider_schema()
    sizes = {
        "system_prompt_chars": len(ARCHITECT_V2_SYSTEM_PROMPT),
        "request_chars": len(_canonical(request)),
        "schema_chars": len(_canonical(schema)),
    }
    size_checks = {
        "system_prompt_within_ceiling": sizes["system_prompt_chars"] <= policy.max_system_prompt_chars,
        "request_within_ceiling": sizes["request_chars"] <= policy.max_request_chars,
        "schema_within_ceiling": sizes["schema_chars"] <= policy.max_schema_chars,
    }
    return {
        "schema_version": "architect_v2_canary_plan.v1",
        "fixture_name": fixture_name,
        "effort": effort,
        "max_output_tokens": int(max_output_tokens),
        "request": request,
        "provider_schema": schema,
        "reference": reference,
        "sizes": sizes,
        "size_checks": size_checks,
        "policy": asdict(policy),
        "call_policy": {
            "provider_calls": 1,
            "automatic_retries": 0,
            "review_calls": 0,
            "finalizer_calls": 0,
            "correction_calls": 0,
            "solver_runs": 0,
            "verifier_runs": 0,
            "production_dispatch": "blocked",
        },
        "ready_for_model_call": all(size_checks.values()),
    }


def load_public_task_pack_fixture(path: str | Path, fixture_name: str) -> Mapping[str, Any]:
    rows = json.loads(Path(path).read_text())
    matches = [row for row in rows if row.get("name") == fixture_name]
    if len(matches) != 1:
        raise ValueError(f"expected one fixture named {fixture_name!r}")
    return matches[0]


def fixture_reference_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Project public/historical fixtures into the active self-contained lanes.

    Sealed historical rows may carry method facts and formal rules in older
    locations. This boundary folds that authority into self-contained method
    constraints without relaxing active provider validation.
    """

    solver_design = dict(row["solver_design"])
    source_facts = [dict(item) for item in row["facts"]]
    facts_by_id = {str(item["fact_id"]): item for item in source_facts}
    legacy_rules = tuple(solver_design.get("task_specific_rules", ()) or ())
    raw_methods = [dict(item) for item in row.get("method_constraints", ())]
    advisory_rules: list[dict[str, str]] = []
    for item in legacy_rules:
        rule = dict(item)
        if str(rule.get("authority") or "advisory") == "required_method":
            raw_methods.append({
                "constraint_id": str(rule["rule_id"]),
                "statement": str(rule["statement"]),
                "fact_refs": [str(ref) for ref in rule.get("fact_refs", ())],
                "obligation_refs": [
                    str(ref) for ref in rule.get("obligation_refs", ())
                ],
            })
        else:
            advisory_rules.append({
                "rule_id": str(rule["rule_id"]),
                "statement": str(rule["statement"]),
            })
    if advisory_rules:
        solver_design["task_specific_rules"] = advisory_rules
    else:
        solver_design.pop("task_specific_rules", None)

    method_fact_ids = {
        str(ref)
        for method in raw_methods
        for ref in method.get("fact_refs", ())
    }
    method_fact_ids.update(
        str(fact["fact_id"])
        for fact in source_facts
        if str(fact.get("authority_scope") or "") == "method"
    )

    methods: list[dict[str, Any]] = []
    for index, source in enumerate(raw_methods):
        method = dict(source)
        refs = [str(ref) for ref in method.pop("fact_refs", ())]
        method_facts = [facts_by_id[ref] for ref in refs if ref in facts_by_id]
        anchors = [
            str(anchor)
            for fact in method_facts
            for anchor in fact.get("verbatim_anchors", ())
        ]
        anchors.extend(str(anchor) for anchor in method.get("verbatim_anchors", ()))
        anchors = list(dict.fromkeys(anchor for anchor in anchors if anchor))
        statement = str(method.get("statement") or "Required execution method.")
        missing_statements = [
            str(fact.get("statement") or "")
            for fact in method_facts
            if any(
                str(anchor) not in statement
                for anchor in fact.get("verbatim_anchors", ())
            )
        ]
        if missing_statements:
            statement = statement.rstrip() + " " + " ".join(missing_statements)
        methods.append({
            "constraint_id": str(
                method.get("constraint_id") or f"historical_method_{index + 1}"
            ),
            "statement": statement,
            "verbatim_anchors": anchors,
            "obligation_refs": [
                str(ref) for ref in method.get("obligation_refs", ())
            ],
            "acceptance_observation": str(
                method.get("acceptance_observation")
                or (
                    "Immutable action history establishes method constraint "
                    + str(method.get("constraint_id") or f"historical_method_{index + 1}")
                    + "."
                )
            ),
            "falsification_observation": str(
                method.get("falsification_observation")
                or (
                    "Immutable action history does not establish method constraint "
                    + str(method.get("constraint_id") or f"historical_method_{index + 1}")
                    + "."
                )
            ),
        })

    outcome_facts = []
    for source in source_facts:
        fact_id = str(source["fact_id"])
        scope = str(source.get("authority_scope") or "")
        if fact_id in method_fact_ids or scope == "method":
            continue
        fact = dict(source)
        fact.pop("authority_scope", None)
        outcome_facts.append(fact)

    return {
        "schema_version": "aether_architect.v2",
        "task_contract": {
            "exact_facts": outcome_facts,
            "obligations": row["obligations"],
        },
        "method_constraints": methods,
        "proof_intent": row["proofs"],
        "solver_design": solver_design,
        "verifier_design": row["verifier_design"],
        "information_emphasis": row.get("information_emphasis", []),
    }
