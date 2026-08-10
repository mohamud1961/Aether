"""Deterministic preparation and authority scoring for Architect v3 canaries."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .architect_v3_contract import (
    ArchitectV3Contract,
    architect_v3_provider_schema,
    validate_architect_v3,
)
from .architect_v3_model import (
    ARCHITECT_V3_MAX_OUTPUT_TOKENS,
    ARCHITECT_V3_SYSTEM_PROMPT,
    architect_v3_source_catalog,
    architect_v3_source_contents,
    build_architect_v3_model_request,
)
from .runtime_ir import CapabilityDescriptor, EnvMap, FIXED_KERNEL_TOOL_SURFACE


@dataclass(frozen=True)
class ArchitectV3CanaryPolicy:
    max_system_prompt_chars: int = 9_000
    max_request_chars: int = 20_000
    max_schema_chars: int = 20_000
    max_raw_output_chars: int = 32_000
    max_output_tokens: int = ARCHITECT_V3_MAX_OUTPUT_TOKENS
    max_total_tokens: int = 20_000
    max_reasoning_tokens: int = 10_000
    deterministic_score_required: int = 12
    model_calls_required: int = 1


DEFAULT_CANARY_POLICY = ArchitectV3CanaryPolicy()


@dataclass(frozen=True)
class ArchitectV3DeterministicScore:
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


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def build_public_fixture_envmap(row: Mapping[str, Any]) -> EnvMap:
    """Build raw public material without feeding reference semantic labels."""

    raw_visible = row.get("visible_materials", ())
    if isinstance(raw_visible, str):
        raw_visible = (raw_visible,)
    if not isinstance(raw_visible, (list, tuple)):
        raise ValueError("visible_materials must be an array of raw source values")
    visible_values = [item for item in raw_visible if item not in (None, "")]
    reference_requires_visible = any(
        "visible_materials" in parameter.get("source_refs", ())
        for owner in (
            *row["contract"].get("outcomes", ()),
            *row["contract"].get("constraints", ()),
        )
        for parameter in owner.get("parameters", ())
    )
    if reference_requires_visible and not visible_values:
        raise ValueError(
            "reference uses visible_materials but fixture provides no raw visible material"
        )
    metadata: dict[str, Any] = {}
    if visible_values:
        metadata = {
            "visible_examples": [
                {"content": value}
                for value in visible_values
            ],
            "visible_material_summary": {
                "source": "public_zero_model_fixture",
                "visible_value_count": len(visible_values),
            },
        }
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
        task_metadata=metadata,
    )


def _source_types(
    parameter: Mapping[str, Any],
    catalog: Mapping[str, str],
) -> frozenset[str]:
    return frozenset(
        str(catalog.get(str(ref), f"unknown:{ref}"))
        for ref in parameter.get("source_refs", ())
    )


def _parameter_signature(
    parameter: Mapping[str, Any],
    catalog: Mapping[str, str],
) -> tuple[str, str, frozenset[str]]:
    return (
        _normalize_text(parameter.get("source_text")),
        _normalize_text(parameter.get("value")),
        _source_types(parameter, catalog),
    )


_ACCEPTANCE_CRITICAL_PHRASES = (
    "must not",
    "do not",
    "without",
    "not",
    "never",
    "before",
    "after",
    "followed by",
    "precedes",
    "then",
    "at most",
    "at least",
    "less than",
    "more than",
    "under",
    "over",
    "exactly",
)


def _acceptance_critical_signature(text: str) -> frozenset[str]:
    return frozenset(
        phrase
        for phrase in _ACCEPTANCE_CRITICAL_PHRASES
        if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text)
    )


def _parameter_signatures_compatible(
    candidate: tuple[str, str, frozenset[str]],
    required: tuple[str, str, frozenset[str]],
) -> bool:
    candidate_text, candidate_value, candidate_sources = candidate
    required_text, required_value, required_sources = required
    if not candidate_text or not required_text:
        return False
    if not candidate_sources.intersection(required_sources):
        return False
    spans_overlap = (
        candidate_text in required_text
        or required_text in candidate_text
    )
    if not spans_overlap:
        return False
    # Identical grounded spans may safely support a different decomposition of
    # the same declaration (for example, `int32 val = 2` versus numeric `2`).
    if candidate_text == required_text or candidate_value == required_value:
        return True
    # A coupled value may include harmless source wrappers such as `the
    # requested ...`. Accept containment only when the grounded spans preserve
    # the same negation, ordering, comparator, and threshold language.
    values_overlap = (
        candidate_value in required_value
        or required_value in candidate_value
    )
    return (
        values_overlap
        and _acceptance_critical_signature(candidate_text)
        == _acceptance_critical_signature(required_text)
    )


def _owner_parameter_signatures(
    row: Mapping[str, Any],
    catalog: Mapping[str, str],
) -> tuple[tuple[str, str, frozenset[str]], ...]:
    return tuple(
        _parameter_signature(parameter, catalog)
        for parameter in row.get("parameters", ())
    )


def _parameters_equivalent(
    candidate: Sequence[tuple[str, str, frozenset[str]]],
    required: Sequence[tuple[str, str, frozenset[str]]],
) -> bool:
    if not required:
        return not candidate
    if not candidate:
        return False
    required_covered = all(
        any(
            _parameter_signatures_compatible(candidate_item, required_item)
            for candidate_item in candidate
        )
        for required_item in required
    )
    candidate_covered = all(
        any(
            _parameter_signatures_compatible(candidate_item, required_item)
            for required_item in required
        )
        for candidate_item in candidate
    )
    return required_covered and candidate_covered


def _outcome_parameters_preserve_authority(
    candidate_row: Mapping[str, Any],
    reference_row: Mapping[str, Any],
    reference_constraints: Sequence[Mapping[str, Any]],
    catalog: Mapping[str, str],
) -> bool:
    """Allow grounded outcome detail without admitting method authority.

    Architect may make an outcome more explicit than a reviewed reference by
    recording additional exact, owner-local task facts.  A reference outcome's
    required anchors must still be covered.  Extra candidate anchors are safe
    only when they are not anchors that the reference assigns exclusively to a
    method constraint; that keeps cross-lane outcome/method promotion fail
    closed while allowing harmless semantic decomposition.
    """
    candidate_parameters = _owner_parameter_signatures(candidate_row, catalog)
    required_parameters = _owner_parameter_signatures(reference_row, catalog)
    if not all(
        any(
            _parameter_signatures_compatible(candidate_item, required_item)
            for candidate_item in candidate_parameters
        )
        for required_item in required_parameters
    ):
        return False

    required_outcome_signatures = tuple(required_parameters)
    constraint_only_signatures = tuple(
        parameter
        for constraint in reference_constraints
        for parameter in _owner_parameter_signatures(constraint, catalog)
        if not any(
            _parameter_signatures_compatible(parameter, outcome_parameter)
            for outcome_parameter in required_outcome_signatures
        )
    )
    return not any(
        any(
            _parameter_signatures_compatible(candidate_item, constraint_item)
            for constraint_item in constraint_only_signatures
        )
        for candidate_item in candidate_parameters
        if not any(
            _parameter_signatures_compatible(candidate_item, required_item)
            for required_item in required_outcome_signatures
        )
    )


def _owner_rows(
    contract: ArchitectV3Contract,
    owner_type: str,
) -> tuple[Mapping[str, Any], ...]:
    key = "outcomes" if owner_type == "outcome" else "constraints"
    return tuple(contract.payload[key])


def _owner_id(row: Mapping[str, Any], owner_type: str) -> str:
    return str(row["outcome_id" if owner_type == "outcome" else "constraint_id"])


def _match_outcomes(
    candidate: ArchitectV3Contract,
    reference: ArchitectV3Contract,
    catalog: Mapping[str, str],
) -> dict[str, str] | None:
    candidate_rows = _owner_rows(candidate, "outcome")
    reference_rows = _owner_rows(reference, "outcome")
    if len(candidate_rows) != len(reference_rows):
        return None
    candidates_by_reference: dict[str, list[str]] = {}
    candidate_by_id = {_owner_id(row, "outcome"): row for row in candidate_rows}
    for reference_row in reference_rows:
        reference_id = _owner_id(reference_row, "outcome")
        matches = [
            candidate_id
            for candidate_id, candidate_row in candidate_by_id.items()
            if _outcome_parameters_preserve_authority(
                candidate_row,
                reference_row,
                _owner_rows(reference, "constraint"),
                catalog,
            )
        ]
        if not matches:
            return None
        candidates_by_reference[reference_id] = matches

    ordered = sorted(candidates_by_reference, key=lambda item: len(candidates_by_reference[item]))

    def bind(index: int, used: set[str], result: dict[str, str]) -> dict[str, str] | None:
        if index >= len(ordered):
            return result
        reference_id = ordered[index]
        for candidate_id in candidates_by_reference[reference_id]:
            if candidate_id in used:
                continue
            found = bind(
                index + 1,
                used | {candidate_id},
                {**result, candidate_id: reference_id},
            )
            if found is not None:
                return found
        return None

    return bind(0, set(), {})


def _constraint_signature(
    row: Mapping[str, Any],
    catalog: Mapping[str, str],
    outcome_map: Mapping[str, str],
) -> tuple[Any, ...]:
    return (
        str(row["kind"]),
        tuple(sorted(outcome_map[str(item)] for item in row.get("applies_to", ()))),
        _owner_parameter_signatures(row, catalog),
    )


def _match_constraints(
    candidate: ArchitectV3Contract,
    reference: ArchitectV3Contract,
    catalog: Mapping[str, str],
    outcome_map: Mapping[str, str],
) -> dict[str, str] | None:
    candidate_rows = _owner_rows(candidate, "constraint")
    reference_rows = _owner_rows(reference, "constraint")
    if len(candidate_rows) != len(reference_rows):
        return None
    if not reference_rows:
        return {}
    reference_outcome_identity = {
        outcome_id: outcome_id for outcome_id in reference.outcome_ids
    }
    candidates_by_reference: dict[str, list[str]] = {}
    for reference_row in reference_rows:
        reference_id = _owner_id(reference_row, "constraint")
        reference_signature = _constraint_signature(
            reference_row,
            catalog,
            reference_outcome_identity,
        )
        matches: list[str] = []
        for candidate_row in candidate_rows:
            candidate_id = _owner_id(candidate_row, "constraint")
            candidate_signature = _constraint_signature(
                candidate_row,
                catalog,
                outcome_map,
            )
            same_header = candidate_signature[:2] == reference_signature[:2]
            same_parameters = _parameters_equivalent(
                candidate_signature[2], reference_signature[2]
            )
            if same_header and same_parameters:
                matches.append(candidate_id)
        if not matches:
            return None
        candidates_by_reference[reference_id] = matches

    ordered = sorted(candidates_by_reference, key=lambda item: len(candidates_by_reference[item]))

    def bind(index: int, used: set[str], result: dict[str, str]) -> dict[str, str] | None:
        if index >= len(ordered):
            return result
        reference_id = ordered[index]
        for candidate_id in candidates_by_reference[reference_id]:
            if candidate_id in used:
                continue
            found = bind(
                index + 1,
                used | {candidate_id},
                {**result, candidate_id: reference_id},
            )
            if found is not None:
                return found
        return None

    return bind(0, set(), {})


def _proof_relationships_preserved(
    candidate: ArchitectV3Contract,
    reference: ArchitectV3Contract,
    outcome_map: Mapping[str, str] | None,
    constraint_map: Mapping[str, str] | None,
) -> bool:
    if outcome_map is None or constraint_map is None:
        return False

    def rows(
        contract: ArchitectV3Contract,
        *,
        translate: bool,
    ) -> Counter[tuple[str, str, str]]:
        # Proof relationship identity is deliberately limited to the target
        # type, mapped target, and proof kind.  Pilot-only insufficient proxies
        # remain required and validated by validate_architect_v3, but cannot be
        # compared with legacy references that predate that field.
        result: list[tuple[str, str, str]] = []
        for row in contract.payload["proof_facets"]:
            target_type = str(row["target_type"])
            target_id = str(row["target_id"])
            if translate:
                target_id = (
                    outcome_map[target_id]
                    if target_type == "outcome"
                    else constraint_map[target_id]
                )
            result.append((
                target_type,
                target_id,
                str(row["proof_kind"]),
            ))
        return Counter(result)

    return rows(candidate, translate=True) == rows(reference, translate=False)


def _strategy_coverage(contract: ArchitectV3Contract) -> tuple[set[str], set[str], set[str]]:
    outcomes: set[str] = set()
    constraints: set[str] = set()
    proofs: set[str] = set()
    payload = contract.payload
    if "pilot_briefing" in payload:
        authority = {
            "outcome": set(contract.outcome_ids),
            "constraint": set(contract.constraint_ids),
            "proof": set(contract.proof_ids),
        }
        refs = tuple(payload["pilot_briefing"].get("priorities", ()))
        refs += tuple(
            item
            for row in payload["pilot_briefing"].get("adaptive_strategy", ())
            for item in row.get("serves", ())
        )
        for item in refs:
            value = str(item)
            if value in authority["outcome"]:
                outcomes.add(value)
            elif value in authority["constraint"]:
                constraints.add(value)
            elif value in authority["proof"]:
                proofs.add(value)
        return outcomes, constraints, proofs
    for row in payload["solver_strategy"]["approach"]:
        outcomes.update(str(item) for item in row.get("outcome_refs", ()))
        constraints.update(str(item) for item in row.get("constraint_refs", ()))
        proofs.update(str(item) for item in row.get("proof_refs", ()))
    return outcomes, constraints, proofs


def _strategy_is_cognitive(contract: ArchitectV3Contract) -> bool:
    uncertainty_pattern = re.compile(
        r"(?:\b(?:whether|which|what|how|unknown|uncertain|unclear|unresolved|"
        r"hypothesis|relationship|may|might|could|can|possibly|unspecified)\b|"
        r"\bnot\s+(?:yet\s+)?(?:known|established|determined|clear|specified)\b|"
        r"\bdoes\s+not\s+(?:specify|state|spell\s+out|provide|include|expose)\b|"
        r"\bmust\s+(?:be\s+)?(?:determine|determined|confirm|confirmed|resolve|resolved|"
        r"establish|established|identify|identified|infer|inferred)\b|"
        r"\bwithout\s+(?:exposing|providing|specifying|stating|including)\b|"
        r"\bto\s+be\s+(?:determined|confirmed|resolved|established|identified)\b)",
        re.IGNORECASE,
    )
    forbidden = tuple(item.casefold() for item in FIXED_KERNEL_TOOL_SURFACE)
    payload = contract.payload
    if "pilot_briefing" in payload:
        uncertainties = " ".join(
            str(item) for item in payload["pilot_briefing"].get("uncertainties", ())
        )
        if uncertainty_pattern.search(uncertainties) is None:
            return False
        rows = payload["pilot_briefing"].get("adaptive_strategy", ())
        for row in rows:
            rendered = (
                str(row.get("guidance", "")) + " "
                + str(row.get("pivot_when", ""))
            ).casefold()
            if any(token in rendered for token in forbidden):
                return False
    else:
        for row in payload["solver_strategy"]["approach"]:
            uncertainty = str(row.get("uncertainty", ""))
            rendered = (
                str(row.get("guidance", "")) + " " + uncertainty
            ).casefold()
            if uncertainty_pattern.search(uncertainty) is None:
                return False
            if any(token in rendered for token in forbidden):
                return False
    return True


def score_architect_v3_candidate(
    candidate: ArchitectV3Contract | Mapping[str, Any],
    *,
    reference: ArchitectV3Contract | Mapping[str, Any],
    source_catalog: Mapping[str, str],
    source_contents: Mapping[str, Any],
    raw_output: str = "",
    policy: ArchitectV3CanaryPolicy = DEFAULT_CANARY_POLICY,
) -> ArchitectV3DeterministicScore:
    candidate_contract = (
        candidate
        if isinstance(candidate, ArchitectV3Contract)
        else validate_architect_v3(
            candidate,
            source_catalog=source_catalog,
            source_contents=source_contents,
        )
    )
    reference_contract = (
        reference
        if isinstance(reference, ArchitectV3Contract)
        else validate_architect_v3(
            reference,
            source_catalog=source_catalog,
            source_contents=source_contents,
        )
    )

    outcome_map = _match_outcomes(
        candidate_contract,
        reference_contract,
        source_catalog,
    )
    candidate_has_constraints = bool(candidate_contract.constraint_ids)
    reference_has_constraints = bool(reference_contract.constraint_ids)
    if not candidate_has_constraints and not reference_has_constraints:
        constraint_map: dict[str, str] | None = {}
    elif outcome_map is None:
        constraint_map = None
    else:
        constraint_map = _match_constraints(
            candidate_contract,
            reference_contract,
            source_catalog,
            outcome_map,
        )
    strategy_outcomes, strategy_constraints, strategy_proofs = _strategy_coverage(
        candidate_contract
    )
    checks = {
        "schema_and_source_grounding_valid": True,
        "owner_local_parameter_authority_preserved": outcome_map is not None,
        "outcome_authority_partition_preserved": outcome_map is not None,
        "explicit_constraint_authority_preserved": constraint_map is not None,
        "proof_relationships_preserved": _proof_relationships_preserved(
            candidate_contract,
            reference_contract,
            outcome_map,
            constraint_map,
        ),
        "strategy_covers_all_outcomes": (
            strategy_outcomes == set(candidate_contract.outcome_ids)
        ),
        "strategy_covers_all_constraints": (
            strategy_constraints == set(candidate_contract.constraint_ids)
        ),
        "strategy_references_current_proofs": (
            bool(strategy_proofs)
            and strategy_proofs <= set(candidate_contract.proof_ids)
        ),
        "strategy_is_uncertainty_aware_and_non_executable": _strategy_is_cognitive(
            candidate_contract
        ),
        "parameters_are_owner_local_and_grounded": (
            "facts" not in candidate_contract.payload
            and all(
                set(parameter) == {
                    "parameter_id",
                    "value",
                    "source_text",
                    "source_refs",
                }
                for owner in (
                    *candidate_contract.payload["outcomes"],
                    *candidate_contract.payload["constraints"],
                )
                for parameter in owner.get("parameters", ())
            )
        ),
        "no_v2_semantic_buckets": not any(
            key in candidate_contract.payload
            for key in (
                "task_contract",
                "method_constraints",
                "solver_design",
                "verifier_design",
                "information_emphasis",
                "false_positive_risks",
            )
        ),
        "raw_output_within_ceiling": (
            not raw_output or len(raw_output) <= policy.max_raw_output_chars
        ),
    }
    findings = tuple(name for name, passed in checks.items() if not passed)
    return ArchitectV3DeterministicScore(
        score=sum(bool(value) for value in checks.values()),
        ceiling=len(checks),
        checks=checks,
        findings=findings,
    )


def evaluate_provider_telemetry(
    events: Sequence[Mapping[str, Any]],
    *,
    policy: ArchitectV3CanaryPolicy = DEFAULT_CANARY_POLICY,
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


def build_canary_plan(
    envmap: EnvMap,
    *,
    reference: Mapping[str, Any],
    fixture_name: str,
    effort: str,
    max_output_tokens: int,
    policy: ArchitectV3CanaryPolicy = DEFAULT_CANARY_POLICY,
) -> dict[str, Any]:
    if effort not in {"low", "medium"}:
        raise ValueError("Architect v3 canary effort must be low or medium")
    if int(max_output_tokens) > policy.max_output_tokens:
        raise ValueError("Architect v3 canary output ceiling exceeds policy")
    request = build_architect_v3_model_request(envmap)
    catalog = architect_v3_source_catalog(request)
    contents = architect_v3_source_contents(request)
    validate_architect_v3(
        reference,
        source_catalog=catalog,
        source_contents=contents,
    )
    schema = architect_v3_provider_schema()
    sizes = {
        "system_prompt_chars": len(ARCHITECT_V3_SYSTEM_PROMPT),
        "request_chars": len(_canonical(request)),
        "schema_chars": len(_canonical(schema)),
    }
    size_checks = {
        "system_prompt_within_ceiling": sizes["system_prompt_chars"] <= policy.max_system_prompt_chars,
        "request_within_ceiling": sizes["request_chars"] <= policy.max_request_chars,
        "schema_within_ceiling": sizes["schema_chars"] <= policy.max_schema_chars,
    }
    return {
        "schema_version": "architect_v3_canary_plan.v1",
        "fixture_name": fixture_name,
        "effort": effort,
        "max_output_tokens": int(max_output_tokens),
        "request": request,
        "source_catalog": catalog,
        "source_contents": contents,
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


def load_public_fixture(path: str | Path, fixture_name: str) -> Mapping[str, Any]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    matches = [row for row in rows if row.get("name") == fixture_name]
    if len(matches) != 1:
        raise ValueError(f"expected one fixture named {fixture_name!r}")
    return matches[0]
