"""Minimal semantic-and-cognitive authority for Architect v3.

Architect v3 exposes four model-owned concepts:

* outcomes: independently judgeable completion conditions with grounded parameters;
* constraints: explicit task-imposed execution restrictions attached to outcomes;
* proof facets: evidence relationships attached to outcomes or constraints;
* solver strategy: structured task-specific cognitive design for the Solver.

Exact values are owner-local data. They cannot exist independently of the
outcome or explicit constraint that gives them meaning. The compiler may
validate references and mechanically project the contract, but it must not
invent task meaning. The same validated contract is used by qualification and the certified production projection.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from .model_hooks import ModelOutputError
from .proof_contract import (
    PROOF_KINDS,
    CompiledProofRequirement,
    compile_proof_requirements,
    proof_requirements_identity,
)


V3_SCHEMA_VERSION = "aether_architect.v3"
V3_CONSTRAINT_KINDS = (
    "required_method",
    "prohibited_method",
    "resource_limit",
    "timing",
    "ordering",
)
V3_SOURCE_TYPES = (
    "task_prompt",
    "visible_material",
    "visible_environment",
)
V3_PROOF_TARGET_TYPES = ("outcome", "constraint")
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_GENERIC_PARAMETER_ID = re.compile(
    r"^(?:f|fact|p|param|parameter|item|value|v)[._-]?\d+$",
    re.IGNORECASE,
)
_TASK_TEXT_AS_COMPLIANCE_PATTERN = re.compile(
    r"\b(?:task prompt|task (?:says|states|requires)|"
    r"instructions? (?:say|says|state|states|require|requires))\b",
    re.IGNORECASE,
)
_AUTHORITATIVE_CONSTRAINT_SOURCE_TYPES = frozenset({
    "task_prompt",
    "visible_material",
})
_V3_PROXY_FIELD_ALIASES = ("insufficient_proxies", "insufficient_proxy_evidence")
_PILOT_FORBIDDEN_TOKENS = (
    "run_command",
    "launch_process",
    "probe_service",
    "probe_port",
    "provider",
    "context policy",
    "memory policy",
    "verifier identity",
)
_PILOT_ACTION_VERB = (
    r"(?:run|execute|invoke|call|launch|start|stop|restart|sleep|edit|write|"
    r"read|open|delete)"
)
_PILOT_ACTION_TARGET = r"(?:`[^`]+`|[a-z0-9_./:-]+)"
_PILOT_ACTION_PATTERNS = (
    # Direct imperative at the start of a sentence or independent clause.
    re.compile(
        rf"(?:^|(?<=[.!?;:])\s+)(?:(?:please|never)\s+|do\s+not\s+)?"
        rf"{_PILOT_ACTION_VERB}\s+{_PILOT_ACTION_TARGET}",
        re.IGNORECASE,
    ),
    # A condition followed by an executable instruction.
    re.compile(
        rf"\b(?:if|when|unless|once)\b[^.!?;]{{0,240}},\s*"
        rf"(?:then\s+)?(?:(?:never)\s+|do\s+not\s+)?"
        rf"{_PILOT_ACTION_VERB}\s+{_PILOT_ACTION_TARGET}",
        re.IGNORECASE,
    ),
    # Explicitly tell the Solver or operator to perform a concrete action.
    re.compile(
        rf"\b(?:you|solver|agent|operator)\s+"
        rf"(?:must|should|shall|need(?:s)?\s+to|has\s+to|have\s+to)\s+"
        rf"{_PILOT_ACTION_VERB}\s+{_PILOT_ACTION_TARGET}",
        re.IGNORECASE,
    ),
    # Encode a concrete method through a gerund construction.
    re.compile(
        r"\b(?:by|through)\s+(?:running|executing|invoking|calling|launching|"
        r"starting|stopping|restarting|sleeping|editing|writing|reading|opening|"
        r"deleting)\b",
        re.IGNORECASE,
    ),
    # Sequenced commands remain prescriptions even without a sentence boundary.
    re.compile(
        rf"\b(?:then|next)\s+(?:(?:never)\s+|do\s+not\s+)?"
        rf"{_PILOT_ACTION_VERB}\s+{_PILOT_ACTION_TARGET}",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class ArchitectV3Contract:
    """Immutable validated minimal semantic-and-cognitive authority."""

    _canonical_payload: str
    contract_identity: str
    outcome_ids: tuple[str, ...]
    constraint_ids: tuple[str, ...]
    proof_ids: tuple[str, ...]
    parameter_ids: tuple[str, ...]

    @property
    def payload(self) -> Mapping[str, Any]:
        return json.loads(self._canonical_payload)

    @property
    def canonical_payload(self) -> str:
        return self._canonical_payload


@dataclass(frozen=True)
class ArchitectV3RuntimeProjection:
    """Lossless production projection into existing proof machinery."""

    contract: ArchitectV3Contract
    task_material: str
    solver_prompt: str
    verifier_prompt: str
    requirements: tuple[CompiledProofRequirement, ...]
    requirements_identity: str
    proof_targets: tuple[tuple[str, str, str], ...]
    status: str = "runtime_eligible"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "contract_identity": self.contract.contract_identity,
            "task_material": self.task_material,
            "solver_prompt": self.solver_prompt,
            "verifier_prompt": self.verifier_prompt,
            "proof_requirements": [item.as_dict() for item in self.requirements],
            "proof_requirements_identity": self.requirements_identity,
            "proof_targets": [
                {
                    "proof_id": proof_id,
                    "target_type": target_type,
                    "target_id": target_id,
                }
                for proof_id, target_type, target_id in self.proof_targets
            ],
            "activation": "certified_runtime_projection",
        }


@dataclass(frozen=True)
class ArchitectV3ShadowProjection:
    """Lossless, non-dispatching projection into existing proof machinery."""

    contract: ArchitectV3Contract
    task_material: str
    solver_prompt: str
    verifier_prompt: str
    requirements: tuple[CompiledProofRequirement, ...]
    requirements_identity: str
    proof_targets: tuple[tuple[str, str, str], ...]
    status: str = "shadow_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "contract_identity": self.contract.contract_identity,
            "task_material": self.task_material,
            "solver_prompt": self.solver_prompt,
            "verifier_prompt": self.verifier_prompt,
            "proof_requirements": [item.as_dict() for item in self.requirements],
            "proof_requirements_identity": self.requirements_identity,
            "proof_targets": [
                {
                    "proof_id": proof_id,
                    "target_type": target_type,
                    "target_id": target_id,
                }
                for proof_id, target_type, target_id in self.proof_targets
            ],
            "activation": "not_runtime_eligible",
        }


def _mapping(value: Any, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelOutputError(f"{location} must be an object")
    return value


def _list(
    value: Any,
    location: str,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> list[Any]:
    if not isinstance(value, list):
        raise ModelOutputError(f"{location} must be an array")
    if len(value) < minimum:
        raise ModelOutputError(f"{location} must contain at least {minimum} item(s)")
    if maximum is not None and len(value) > maximum:
        raise ModelOutputError(f"{location} must contain at most {maximum} item(s)")
    return value


def _text(value: Any, location: str, *, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelOutputError(f"{location} must be a non-empty string")
    text = value.strip()
    if len(text) > maximum:
        raise ModelOutputError(f"{location} exceeds {maximum} characters")
    return text


def _identifier(value: Any, location: str) -> str:
    text = _text(value, location, maximum=64)
    if not _ID_PATTERN.fullmatch(text):
        raise ModelOutputError(f"{location} is not a valid v3 identifier")
    return text


def _descriptive_parameter_id(value: Any, location: str) -> str:
    text = _identifier(value, location)
    if _GENERIC_PARAMETER_ID.fullmatch(text):
        raise ModelOutputError(
            f"{location} must describe what the value means; generic numbered IDs are forbidden"
        )
    return text


def _assert_keys(
    value: Mapping[str, Any],
    allowed: set[str],
    required: set[str],
    location: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ModelOutputError(f"{location} has unsupported fields: {', '.join(unknown)}")
    missing = sorted(required - set(value))
    if missing:
        raise ModelOutputError(f"{location} is missing required fields: {', '.join(missing)}")


def _rows(
    value: Any,
    location: str,
    *,
    minimum: int = 0,
    maximum: int,
) -> list[Mapping[str, Any]]:
    return [
        _mapping(item, f"{location}[{index}]")
        for index, item in enumerate(
            _list(value, location, minimum=minimum, maximum=maximum)
        )
    ]


def _unique_ids(
    rows: Sequence[Mapping[str, Any]],
    key: str,
    location: str,
) -> tuple[str, ...]:
    values = tuple(
        _identifier(row.get(key), f"{location}[{index}].{key}")
        for index, row in enumerate(rows)
    )
    if len(set(values)) != len(values):
        raise ModelOutputError(f"{location}.{key} values must be unique")
    return values


def _refs(
    value: Any,
    location: str,
    known: set[str],
    *,
    minimum: int = 0,
) -> tuple[str, ...]:
    raw = _list(value, location, minimum=minimum)
    rendered: list[str] = []
    for index, item in enumerate(raw):
        try:
            rendered.append(_identifier(item, f"{location}[{index}]"))
        except ModelOutputError as exc:
            raise ModelOutputError(
                f"{location} must contain v3 authority IDs, not natural-language "
                f"prose ({exc})"
            ) from exc
    result = tuple(rendered)
    if len(set(result)) != len(result):
        raise ModelOutputError(f"{location} values must be unique")
    unknown = sorted(set(result) - known)
    if unknown:
        raise ModelOutputError(
            f"{location} contains unknown references: {', '.join(unknown)}"
        )
    return result


def _literal(value: Any, location: str) -> str | int | float:
    if value is None or isinstance(value, (list, tuple, Mapping, bool)):
        raise ModelOutputError(
            f"{location} must be an exact source string or number; booleans and containers are forbidden"
        )
    if isinstance(value, str):
        return _text(value, location, maximum=2000)
    if isinstance(value, (int, float)):
        return value
    raise ModelOutputError(
        f"{location} must be an exact source string or number; booleans and containers are forbidden"
    )


def _source_catalog(
    source_catalog: Mapping[str, str] | None,
) -> dict[str, str]:
    if source_catalog is None:
        return {}
    result: dict[str, str] = {}
    for raw_id, raw_type in source_catalog.items():
        source_id = _identifier(raw_id, "source_catalog.source_id")
        source_type = str(raw_type or "").strip()
        if source_type not in V3_SOURCE_TYPES:
            raise ModelOutputError(
                f"source_catalog[{source_id!r}] has unsupported source type"
            )
        result[source_id] = source_type
    return result


def _source_contents(
    source_contents: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if source_contents is None:
        return {}
    return {
        _identifier(raw_id, "source_contents.source_id"): value
        for raw_id, value in source_contents.items()
    }


def _flatten_source_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return "\n".join(
            f"{key}\n{_flatten_source_text(child)}"
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return "\n".join(_flatten_source_text(item) for item in value)
    return str(value)


def _source_refs(
    value: Any,
    location: str,
    catalog: Mapping[str, str],
) -> tuple[str, ...]:
    raw = _list(value, location, minimum=1, maximum=8)
    refs = tuple(
        _identifier(item, f"{location}[{index}]")
        for index, item in enumerate(raw)
    )
    if len(set(refs)) != len(refs):
        raise ModelOutputError(f"{location} values must be unique")
    if catalog:
        unknown = sorted(set(refs) - set(catalog))
        if unknown:
            raise ModelOutputError(
                f"{location} contains unknown source references: {', '.join(unknown)}"
            )
    return refs


_INLINE_CODE_SPAN = re.compile(r"(?<!`)`([^`\r\n]+)`(?!`)")


def _source_text_without_inline_code_delimiters(source_text: str) -> str:
    """Remove only paired single-backtick presentation delimiters.

    Architect values deliberately exclude presentation-only Markdown while
    source_text remains a verbatim cited span. This helper does not normalize
    whitespace, punctuation, quotes, emphasis, fences, or prose.
    """
    return _INLINE_CODE_SPAN.sub(r"\1", source_text)


def _literal_occurs_in_source_text(value: Any, source_text: str) -> bool:
    literal = str(value)
    return (
        literal in source_text
        or literal in _source_text_without_inline_code_delimiters(source_text)
    )


def _canonical_source_text(
    literal: Any,
    source_text: str,
    known_contents: Sequence[str],
) -> str:
    """Canonicalize presentation noise without inventing semantic binding.

    Exact source spans remain authoritative. Two mechanical fallbacks are
    permitted only when the literal itself is visible: one paired Markdown
    backtick wrapper, or an invented surrounding phrase around a distinctive
    path/name/token. Small ambiguous scalars still require their exact coupled
    source span, preventing request/response field values from being swapped.
    """
    if any(source_text in source for source in known_contents):
        return source_text
    literal_text = str(literal)
    literal_visible = any(literal_text in source for source in known_contents)
    if (
        len(source_text) >= 3
        and source_text.startswith("`")
        and source_text.endswith("`")
        and not source_text.startswith("```")
        and not source_text.endswith("```")
    ):
        inner = source_text[1:-1]
        if inner == literal_text and literal_visible:
            return inner
    distinctive = (
        len(literal_text) >= 5
        or (
            len(literal_text) >= 3
            and any(marker in literal_text for marker in ("/", ".", "_", ":", "-"))
        )
    )
    if distinctive and literal_visible and literal_text in source_text:
        return literal_text
    return source_text


def _validate_parameters(
    value: Any,
    location: str,
    *,
    catalog: Mapping[str, str],
    contents: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows = tuple(_rows(value, location, maximum=16))
    parameter_ids: list[str] = []
    validated_rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(rows):
        row_location = f"{location}[{index}]"
        validated_row: Mapping[str, Any] = row
        _assert_keys(
            row,
            {"parameter_id", "value", "source_text", "source_refs"},
            {"parameter_id", "value", "source_text", "source_refs"},
            row_location,
        )
        parameter_id = _descriptive_parameter_id(
            row.get("parameter_id"), f"{row_location}.parameter_id"
        )
        parameter_ids.append(parameter_id)
        literal = _literal(row.get("value"), f"{row_location}.value")
        source_text = _text(
            row.get("source_text"),
            f"{row_location}.source_text",
            maximum=400,
        )
        if "\n" in source_text or "\r" in source_text:
            raise ModelOutputError(
                f"{row_location}.source_text must be one exact source span"
            )
        if not _literal_occurs_in_source_text(literal, source_text):
            raise ModelOutputError(
                f"{row_location}.value must occur in source_text"
            )
        refs = _source_refs(
            row.get("source_refs"),
            f"{row_location}.source_refs",
            catalog,
        )
        if contents:
            known_contents = [
                _flatten_source_text(contents[ref])
                for ref in refs
                if ref in contents
            ]
            if not known_contents:
                raise ModelOutputError(
                    f"{row_location}.source_refs have no model-visible source content"
                )
            canonical_source_text = _canonical_source_text(
                literal, source_text, known_contents,
            )
            if not any(canonical_source_text in source for source in known_contents):
                raise ModelOutputError(
                    f"{row_location}.source_text is not present in cited model-visible sources"
                )
            if canonical_source_text != source_text:
                validated_row = {
                    **row,
                    "source_text": canonical_source_text,
                }
                source_text = canonical_source_text
        validated_rows.append(validated_row)
    if len(set(parameter_ids)) != len(parameter_ids):
        raise ModelOutputError(f"{location}.parameter_id values must be unique")
    return tuple(validated_rows)


def _validate_insufficient_proxies(
    row: Mapping[str, Any],
    location: str,
    *,
    required: bool,
) -> tuple[str, ...]:
    """Validate weak observations without turning them into route instructions.

    The new pilot contract requires every proof facet to name at least one
    attractive but insufficient proxy.  Older frozen V3 fixtures predate this
    field and remain readable as compatibility inputs, but they are never
    emitted by the canonical provider schema.
    """
    present = [name for name in _V3_PROXY_FIELD_ALIASES if name in row]
    if len(present) > 1:
        raise ModelOutputError(
            f"{location} must use only one insufficient-proxy field"
        )
    if not present:
        if required:
            raise ModelOutputError(
                f"{location} must include insufficient_proxies"
            )
        return ()
    field = present[0]
    values = _list(
        row[field],
        f"{location}.{field}",
        minimum=1 if required else 0,
        maximum=8,
    )
    rendered: list[str] = []
    for index, value in enumerate(values):
        text = _text(
            value,
            f"{location}.{field}[{index}]",
            maximum=320,
        )
        if "\n" in text or "\r" in text:
            raise ModelOutputError(
                f"{location}.{field}[{index}] must be one short line"
            )
        rendered.append(text)
    if len(set(rendered)) != len(rendered):
        raise ModelOutputError(f"{location}.{field} values must be unique")
    return tuple(rendered)


def _insufficient_proxy_values(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Read canonical or compatibility proxy spelling without rewriting input."""
    raw = row.get("insufficient_proxies")
    if raw is None:
        raw = row.get("insufficient_proxy_evidence", ())
    return tuple(str(item) for item in (raw or ()))


def _briefing_authority_ids(
    outcome_ids: set[str],
    constraint_ids: set[str],
    proof_ids: set[str],
) -> set[str]:
    return outcome_ids | constraint_ids | proof_ids


def _pilot_text(value: Any, location: str, *, maximum: int) -> str:
    text = _text(value, location, maximum=maximum)
    if "\n" in text or "\r" in text:
        raise ModelOutputError(f"{location} must be one short line")
    rendered = text.casefold()
    if any(token in rendered for token in _PILOT_FORBIDDEN_TOKENS):
        raise ModelOutputError(
            f"{location} contains Architect-owned runtime mechanics"
        )
    if any(pattern.search(text) for pattern in _PILOT_ACTION_PATTERNS):
        raise ModelOutputError(f"{location} prescribes an exact action")
    return text


def _validate_pilot_briefing(
    value: Any,
    *,
    outcome_set: set[str],
    constraint_set: set[str],
    proof_ids: tuple[str, ...],
) -> None:
    briefing = _mapping(value, "v3.pilot_briefing")
    _assert_keys(
        briefing,
        {"mission", "priorities", "uncertainties", "adaptive_strategy"},
        {"mission", "priorities", "uncertainties", "adaptive_strategy"},
        "v3.pilot_briefing",
    )
    _pilot_text(briefing.get("mission"), "v3.pilot_briefing.mission", maximum=600)
    authority_ids = _briefing_authority_ids(
        outcome_set,
        constraint_set,
        set(proof_ids),
    )
    _refs(
        briefing.get("priorities"),
        "v3.pilot_briefing.priorities",
        authority_ids,
        minimum=1,
    )
    uncertainties = _list(
        briefing.get("uncertainties"),
        "v3.pilot_briefing.uncertainties",
        minimum=1,
        maximum=4,
    )
    for index, value in enumerate(uncertainties):
        _pilot_text(
            value,
            f"v3.pilot_briefing.uncertainties[{index}]",
            maximum=320,
        )
    strategy_rows = _rows(
        briefing.get("adaptive_strategy"),
        "v3.pilot_briefing.adaptive_strategy",
        minimum=1,
        maximum=4,
    )
    for index, row in enumerate(strategy_rows):
        location = f"v3.pilot_briefing.adaptive_strategy[{index}]"
        _assert_keys(
            row,
            {"guidance", "serves", "pivot_when"},
            {"guidance", "serves", "pivot_when"},
            location,
        )
        _pilot_text(row.get("guidance"), f"{location}.guidance", maximum=320)
        _pilot_text(row.get("pivot_when"), f"{location}.pivot_when", maximum=320)
        _refs(
            row.get("serves"),
            f"{location}.serves",
            authority_ids,
            minimum=1,
        )


def validate_architect_v3(
    payload: Mapping[str, Any],
    *,
    source_catalog: Mapping[str, str] | None = None,
    source_contents: Mapping[str, Any] | None = None,
) -> ArchitectV3Contract:
    """Validate V3 ownership, grounding, reference, and proof coverage.

    The validator confirms only model-authored structure and direct provenance.
    It does not infer task semantics or create missing meaning.
    """

    root = deepcopy(_mapping(payload, "v3"))
    required = {
        "schema_version",
        "outcomes",
        "constraints",
        "proof_facets",
    }
    _assert_keys(
        root,
        required | {"solver_strategy", "pilot_briefing"},
        required,
        "v3",
    )
    briefing_fields = [
        field for field in ("solver_strategy", "pilot_briefing") if field in root
    ]
    if len(briefing_fields) != 1:
        raise ModelOutputError(
            "v3 must contain exactly one of solver_strategy or pilot_briefing"
        )
    pilot_mode = briefing_fields[0] == "pilot_briefing"
    if root.get("schema_version") != V3_SCHEMA_VERSION:
        raise ModelOutputError(
            f"v3.schema_version must be {V3_SCHEMA_VERSION}"
        )
    catalog = _source_catalog(source_catalog)
    contents = _source_contents(source_contents)
    if contents and catalog:
        unknown_content = sorted(set(contents) - set(catalog))
        if unknown_content:
            raise ModelOutputError(
                "source_contents contains unknown source IDs: "
                + ", ".join(unknown_content)
            )

    outcome_rows = _rows(
        root["outcomes"], "v3.outcomes", minimum=1, maximum=32
    )
    canonical_outcomes: list[Mapping[str, Any]] = []
    qualified_parameter_ids: list[str] = []
    for index, row in enumerate(outcome_rows):
        location = f"v3.outcomes[{index}]"
        _assert_keys(
            row,
            {"outcome_id", "description", "parameters", "source_refs"},
            {"outcome_id", "description", "parameters", "source_refs"},
            location,
        )
        outcome_id = _identifier(row.get("outcome_id"), f"{location}.outcome_id")
        _text(row.get("description"), f"{location}.description")
        parameters = _validate_parameters(
            row.get("parameters"),
            f"{location}.parameters",
            catalog=catalog,
            contents=contents,
        )
        qualified_parameter_ids.extend(
            f"outcome:{outcome_id}:{parameter['parameter_id']}"
            for parameter in parameters
        )
        canonical_outcomes.append({
            **row,
            "parameters": [dict(parameter) for parameter in parameters],
        })
        _source_refs(
            row.get("source_refs"),
            f"{location}.source_refs",
            catalog,
        )
    outcome_ids = _unique_ids(outcome_rows, "outcome_id", "v3.outcomes")
    outcome_set = set(outcome_ids)

    constraint_rows = _rows(
        root["constraints"], "v3.constraints", maximum=16
    )
    canonical_constraints: list[Mapping[str, Any]] = []
    for index, row in enumerate(constraint_rows):
        location = f"v3.constraints[{index}]"
        _assert_keys(
            row,
            {
                "constraint_id",
                "kind",
                "description",
                "applies_to",
                "parameters",
                "source_refs",
            },
            {
                "constraint_id",
                "kind",
                "description",
                "applies_to",
                "parameters",
                "source_refs",
            },
            location,
        )
        constraint_id = _identifier(
            row.get("constraint_id"), f"{location}.constraint_id"
        )
        kind = str(row.get("kind", "")).strip()
        if kind not in V3_CONSTRAINT_KINDS:
            raise ModelOutputError(
                f"{location}.kind must be one of: "
                + ", ".join(V3_CONSTRAINT_KINDS)
            )
        _text(row.get("description"), f"{location}.description")
        _refs(
            row.get("applies_to"),
            f"{location}.applies_to",
            outcome_set,
            minimum=1,
        )
        parameters = _validate_parameters(
            row.get("parameters"),
            f"{location}.parameters",
            catalog=catalog,
            contents=contents,
        )
        qualified_parameter_ids.extend(
            f"constraint:{constraint_id}:{parameter['parameter_id']}"
            for parameter in parameters
        )
        canonical_constraints.append({
            **row,
            "parameters": [dict(parameter) for parameter in parameters],
        })
        refs = _source_refs(
            row.get("source_refs"),
            f"{location}.source_refs",
            catalog,
        )
        if catalog and not any(
            catalog[ref] in _AUTHORITATIVE_CONSTRAINT_SOURCE_TYPES
            for ref in refs
        ):
            raise ModelOutputError(
                f"{location} must cite an explicit task or visible-material source"
            )
    constraint_ids = _unique_ids(
        constraint_rows, "constraint_id", "v3.constraints"
    )
    constraint_set = set(constraint_ids)

    proof_rows = _rows(
        root["proof_facets"], "v3.proof_facets", minimum=1, maximum=64
    )
    outcome_coverage: set[str] = set()
    constraint_coverage: set[str] = set()
    for index, row in enumerate(proof_rows):
        location = f"v3.proof_facets[{index}]"
        _assert_keys(
            row,
            {
                "proof_id",
                "target_type",
                "target_id",
                "proof_kind",
                "acceptance_observation",
                "falsification_observation",
                *_V3_PROXY_FIELD_ALIASES,
            },
            {
                "proof_id",
                "target_type",
                "target_id",
                "proof_kind",
                "acceptance_observation",
                "falsification_observation",
            },
            location,
        )
        target_type = str(row.get("target_type", "")).strip()
        if target_type not in V3_PROOF_TARGET_TYPES:
            raise ModelOutputError(
                f"{location}.target_type must be outcome or constraint"
            )
        target_id = _identifier(
            row.get("target_id"), f"{location}.target_id"
        )
        known_targets = outcome_set if target_type == "outcome" else constraint_set
        if target_id not in known_targets:
            raise ModelOutputError(
                f"{location}.target_id is not a known {target_type}"
            )
        if target_type == "outcome":
            outcome_coverage.add(target_id)
        else:
            constraint_coverage.add(target_id)
        proof_kind = str(row.get("proof_kind", "")).strip()
        if proof_kind not in PROOF_KINDS:
            raise ModelOutputError(
                f"{location}.proof_kind must be one of: "
                + ", ".join(PROOF_KINDS)
            )
        acceptance_observation = _text(
            row.get("acceptance_observation"),
            f"{location}.acceptance_observation",
        )
        _text(
            row.get("falsification_observation"),
            f"{location}.falsification_observation",
        )
        _validate_insufficient_proxies(
            row,
            location,
            required=pilot_mode,
        )
        if (
            target_type == "constraint"
            and _TASK_TEXT_AS_COMPLIANCE_PATTERN.search(acceptance_observation)
        ):
            raise ModelOutputError(
                f"{location}.acceptance_observation uses task wording as "
                "constraint-compliance evidence"
            )
    proof_ids = _unique_ids(proof_rows, "proof_id", "v3.proof_facets")

    missing_outcomes = sorted(outcome_set - outcome_coverage)
    if missing_outcomes:
        raise ModelOutputError(
            "v3 proof_facets do not cover outcomes: "
            + ", ".join(missing_outcomes)
        )
    missing_constraints = sorted(constraint_set - constraint_coverage)
    if missing_constraints:
        raise ModelOutputError(
            "v3 proof_facets do not cover constraints: "
            + ", ".join(missing_constraints)
        )

    if pilot_mode:
        _validate_pilot_briefing(
            root["pilot_briefing"],
            outcome_set=outcome_set,
            constraint_set=constraint_set,
            proof_ids=proof_ids,
        )
    else:
        strategy = _mapping(root["solver_strategy"], "v3.solver_strategy")
        _assert_keys(
            strategy,
            {"approach"},
            {"approach"},
            "v3.solver_strategy",
        )
        approach_rows = _rows(
            strategy["approach"],
            "v3.solver_strategy.approach",
            minimum=1,
            maximum=4,
        )
        for index, row in enumerate(approach_rows):
            location = f"v3.solver_strategy.approach[{index}]"
            _assert_keys(
                row,
                {
                    "strategy_id",
                    "guidance",
                    "uncertainty",
                    "outcome_refs",
                    "constraint_refs",
                    "proof_refs",
                },
                {
                    "strategy_id",
                    "guidance",
                    "uncertainty",
                    "outcome_refs",
                    "constraint_refs",
                    "proof_refs",
                },
                location,
            )
            guidance = _text(row.get("guidance"), f"{location}.guidance", maximum=320)
            uncertainty = _text(
                row.get("uncertainty"),
                f"{location}.uncertainty",
                maximum=320,
            )
            if "\n" in guidance or "\r" in guidance:
                raise ModelOutputError(f"{location}.guidance must be one short line")
            if "\n" in uncertainty or "\r" in uncertainty:
                raise ModelOutputError(f"{location}.uncertainty must be one short line")
            outcome_refs = _refs(
                row.get("outcome_refs"),
                f"{location}.outcome_refs",
                outcome_set,
            )
            constraint_refs = _refs(
                row.get("constraint_refs"),
                f"{location}.constraint_refs",
                constraint_set,
            )
            proof_refs = _refs(
                row.get("proof_refs"),
                f"{location}.proof_refs",
                set(proof_ids),
            )
            if not (outcome_refs or constraint_refs or proof_refs):
                raise ModelOutputError(
                    f"{location} must reference at least one outcome, constraint, or proof"
                )
        _unique_ids(
            approach_rows,
            "strategy_id",
            "v3.solver_strategy.approach",
        )

    canonical_root = {
        **root,
        "outcomes": canonical_outcomes,
        "constraints": canonical_constraints,
    }
    canonical_payload = json.dumps(
        canonical_root,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ArchitectV3Contract(
        _canonical_payload=canonical_payload,
        contract_identity=sha256(
            canonical_payload.encode("utf-8")
        ).hexdigest(),
        outcome_ids=outcome_ids,
        constraint_ids=constraint_ids,
        proof_ids=proof_ids,
        parameter_ids=tuple(qualified_parameter_ids),
    )


def _render_parameters(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    return ", ".join(
        f"{row['parameter_id']}={row['value']!r}"
        for row in rows
    )


def _render_solver_prompt(payload: Mapping[str, Any]) -> str:
    lines = ["[Architect v3 outcomes]"]
    for row in payload["outcomes"]:
        rendered = _render_parameters(row.get("parameters", ()))
        suffix = f" [parameters: {rendered}]" if rendered else ""
        lines.append(f"- {row['outcome_id']}: {row['description']}{suffix}")
    constraints = tuple(payload.get("constraints", ()))
    if constraints:
        lines.append("[Architect v3 explicit constraints]")
        for row in constraints:
            applies = ",".join(str(item) for item in row["applies_to"])
            rendered = _render_parameters(row.get("parameters", ()))
            suffix = f" [parameters: {rendered}]" if rendered else ""
            lines.append(
                f"- {row['constraint_id']} ({row['kind']} -> {applies}): "
                f"{row['description']}{suffix}"
            )
    if "pilot_briefing" in payload:
        briefing = payload["pilot_briefing"]
        lines.append("[Architect v3 Solver pilot briefing]")
        lines.append(f"Mission: {briefing['mission']}")
        lines.append(
            "Priorities (ordered authority IDs; preserve this order): "
            + ", ".join(str(item) for item in briefing["priorities"])
        )
        lines.append("Uncertainties to resolve before relying on assumptions:")
        lines.extend(f"- {item}" for item in briefing["uncertainties"])
        lines.append("Adaptive strategy:")
        for index, row in enumerate(briefing["adaptive_strategy"], start=1):
            serves = ",".join(str(item) for item in row["serves"])
            lines.append(
                f"{index}. {row['guidance']} Pivot when: {row['pivot_when']} "
                f"[serves={serves}]"
            )
    else:
        lines.append("[Architect v3 solver strategy]")
        for index, row in enumerate(payload["solver_strategy"]["approach"], start=1):
            refs: list[str] = []
            if row.get("outcome_refs"):
                refs.append("outcomes=" + ",".join(str(item) for item in row["outcome_refs"]))
            if row.get("constraint_refs"):
                refs.append("constraints=" + ",".join(str(item) for item in row["constraint_refs"]))
            if row.get("proof_refs"):
                refs.append("proofs=" + ",".join(str(item) for item in row["proof_refs"]))
            suffix = f" [{'; '.join(refs)}]" if refs else ""
            lines.append(
                f"{index}. {row['strategy_id']}: {row['guidance']} "
                f"Uncertainty to resolve before relying on it: {row['uncertainty']}{suffix}"
            )
    return "\n".join(lines)


def _render_verifier_prompt(payload: Mapping[str, Any]) -> str:
    lines = [
        "[Architect v3 proof facets]",
        "The Verifier remains neutral and chooses its own read-only inspection route.",
    ]
    for row in payload["proof_facets"]:
        lines.append(
            f"- {row['proof_id']} -> {row['target_type']}:{row['target_id']} "
            f"[{row['proof_kind']}]; accept when: {row['acceptance_observation']}; "
            f"falsify when: {row['falsification_observation']}"
        )
        proxies = _insufficient_proxy_values(row)
        if proxies:
            lines.append(
                "  Insufficient proxies: " + "; ".join(str(item) for item in proxies)
            )
    return "\n".join(lines)


def project_architect_v3_runtime(
    payload_or_contract: Mapping[str, Any] | ArchitectV3Contract,
    *,
    source_catalog: Mapping[str, str] | None = None,
    source_contents: Mapping[str, Any] | None = None,
) -> ArchitectV3RuntimeProjection:
    """Mechanically project V3 without selecting tools or inventing semantics."""

    contract = (
        payload_or_contract
        if isinstance(payload_or_contract, ArchitectV3Contract)
        else validate_architect_v3(
            payload_or_contract,
            source_catalog=source_catalog,
            source_contents=source_contents,
        )
    )
    payload = contract.payload
    constraints = {
        str(row["constraint_id"]): tuple(str(item) for item in row["applies_to"])
        for row in payload["constraints"]
    }
    proof_rows: list[dict[str, Any]] = []
    proof_targets: list[tuple[str, str, str]] = []
    for row in payload["proof_facets"]:
        target_type = str(row["target_type"])
        target_id = str(row["target_id"])
        obligation_refs = (
            (target_id,)
            if target_type == "outcome"
            else constraints[target_id]
        )
        proof_rows.append({
            "proof_id": row["proof_id"],
            "obligation_refs": list(obligation_refs),
            "risk_refs": [],
            "proof_kind": row["proof_kind"],
            "target_type": target_type,
            "target_id": target_id,
            "acceptance_observation": row["acceptance_observation"],
            "falsification_observation": row["falsification_observation"],
            "insufficient_proxies": list(_insufficient_proxy_values(row)),
        })
        proof_targets.append((str(row["proof_id"]), target_type, target_id))
    requirements = compile_proof_requirements(tuple(proof_rows))
    task_material = json.dumps(
        {
            "outcomes": payload["outcomes"],
            "constraints": payload["constraints"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ArchitectV3RuntimeProjection(
        contract=contract,
        task_material=task_material,
        solver_prompt=_render_solver_prompt(payload),
        verifier_prompt=_render_verifier_prompt(payload),
        requirements=requirements,
        requirements_identity=proof_requirements_identity(requirements),
        proof_targets=tuple(proof_targets),
    )


def project_architect_v3_shadow(
    payload_or_contract: Mapping[str, Any] | ArchitectV3Contract,
    *,
    source_catalog: Mapping[str, str] | None = None,
    source_contents: Mapping[str, Any] | None = None,
) -> ArchitectV3ShadowProjection:
    """Compatibility shadow view of the same lossless projection."""
    runtime = project_architect_v3_runtime(
        payload_or_contract,
        source_catalog=source_catalog,
        source_contents=source_contents,
    )
    return ArchitectV3ShadowProjection(
        contract=runtime.contract,
        task_material=runtime.task_material,
        solver_prompt=runtime.solver_prompt,
        verifier_prompt=runtime.verifier_prompt,
        requirements=runtime.requirements,
        requirements_identity=runtime.requirements_identity,
        proof_targets=runtime.proof_targets,
    )


def architect_v3_json_schema() -> dict[str, Any]:
    """Return the canonical sparse parser schema for Architect v3."""

    text = {
        "type": "string",
        "minLength": 1,
        "maxLength": 4000,
        "pattern": r".*\S.*",
    }
    short_text = {
        "type": "string",
        "minLength": 1,
        "maxLength": 320,
        "pattern": r"[^\r\n]*\S[^\r\n]*",
    }
    source_text = {
        "type": "string",
        "minLength": 1,
        "maxLength": 400,
        "pattern": r"[^\r\n]*\S[^\r\n]*",
    }
    identifier = {
        "type": "string",
        "pattern": _ID_PATTERN.pattern,
        "maxLength": 64,
    }
    descriptive_parameter_id = {
        "type": "string",
        "pattern": _ID_PATTERN.pattern,
        "maxLength": 64,
        "description": (
            "Descriptive key naming what the value means, such as grpc_port or "
            "request_field_declaration. Generic IDs such as f1 are invalid."
        ),
    }
    refs = {
        "type": "array",
        "uniqueItems": True,
        "items": identifier,
    }
    source_refs = {**refs, "minItems": 1, "maxItems": 8}
    literal = {
        "description": (
            "Exact source value only. Use a string or number that appears in source_text. "
            "Do not encode relational meaning as a boolean or paraphrased clause; keep "
            "that meaning in the owning outcome or constraint description."
        ),
        "anyOf": [
            {"type": "string", "minLength": 1, "maxLength": 2000},
            {"type": "number"},
        ]
    }
    parameter = {
        "type": "object",
        "additionalProperties": False,
        "required": ["parameter_id", "value", "source_text", "source_refs"],
        "properties": {
            "parameter_id": descriptive_parameter_id,
            "value": literal,
            "source_text": source_text,
            "source_refs": source_refs,
        },
    }
    parameters = {
        "description": (
            "Owner-local exact source data. Values are strings or numbers only and "
            "exclude presentation-only Markdown. Copy source_text verbatim; preserve "
            "Markdown delimiters only when they actually occur in the chosen span, and "
            "never add delimiters. Use the shortest exact span that preserves the value's "
            "binding. Keep "
            "relational meaning in the owner description and keep coupled declarations "
            "together when splitting would lose which value belongs to which entity."
        ),
        "type": "array",
        "maxItems": 16,
        "items": parameter,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://aether.invalid/schemas/aether_architect.v3.canonical.json",
        "title": "Aether Architect v3 minimal semantic and cognitive authority",
        "description": "Certified semantic and cognitive authority for Architect V3.",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "outcomes",
            "constraints",
            "proof_facets",
            "pilot_briefing",
        ],
        "properties": {
            "schema_version": {"const": V3_SCHEMA_VERSION},
            "outcomes": {
                "description": (
                    "Independently judgeable completion conditions. Do not split a "
                    "process-start or liveness means into a separate outcome when the "
                    "required public behavior subsumes it. Preserve acceptance-changing "
                    "modifiers such as fresh, current, exact, ordering, and thresholds "
                    "inside owner-local parameters."
                ),
                "type": "array",
                "minItems": 1,
                "maxItems": 32,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "outcome_id",
                        "description",
                        "parameters",
                        "source_refs",
                    ],
                    "properties": {
                        "outcome_id": identifier,
                        "description": text,
                        "parameters": parameters,
                        "source_refs": source_refs,
                    },
                },
            },
            "constraints": {
                "description": (
                    "Only explicit task-imposed execution restrictions. Named ports, "
                    "paths, endpoints, protocols, and services are normally outcome "
                    "parameters; they become constraint parameters only when task language "
                    "explicitly makes using that route, path, launcher, ordering, resource "
                    "limit, or method mandatory independently of the final outcome."
                ),
                "type": "array",
                "maxItems": 16,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "constraint_id",
                        "kind",
                        "description",
                        "applies_to",
                        "parameters",
                        "source_refs",
                    ],
                    "properties": {
                        "constraint_id": identifier,
                        "kind": {
                            "type": "string",
                            "enum": list(V3_CONSTRAINT_KINDS),
                            "description": (
                                "Use required_method for a positively mandatory route such "
                                "as 'must use X'. Use prohibited_method for an explicit "
                                "exclusion such as 'without X', 'do not use X', or 'must "
                                "not use X'."
                            ),
                        },
                        "description": text,
                        "applies_to": {**refs, "minItems": 1},
                        "parameters": parameters,
                        "source_refs": source_refs,
                    },
                },
            },
            "proof_facets": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "proof_id",
                        "target_type",
                        "target_id",
                        "proof_kind",
                        "acceptance_observation",
                        "falsification_observation",
                        "insufficient_proxies",
                    ],
                    "properties": {
                        "proof_id": identifier,
                        "target_type": {
                            "type": "string",
                            "enum": list(V3_PROOF_TARGET_TYPES),
                        },
                        "target_id": identifier,
                        "proof_kind": {
                            "type": "string",
                            "enum": list(PROOF_KINDS),
                            "description": (
                                "Choose by the relationship establishing correctness. "
                                "Execution receipts, action history, process metadata, "
                                "launcher identity, and socket ownership are exact_state. "
                                "direct_perception is visual, audio, or other "
                                "perceptual artifact content. When the decisive "
                                "acceptance observation requires recognising content "
                                "in frames, images, or audio, use direct_perception "
                                "even if the content is stored in a file; do not choose "
                                "exact_state merely because the artifact has a path."
                            ),
                        },
                        "acceptance_observation": {
                            **text,
                            "description": (
                                "Observation of completed state, behavior, telemetry, or "
                                "immutable action history that establishes the target. Task "
                                "wording itself is never compliance evidence."
                            ),
                        },
                        "falsification_observation": text,
                        "insufficient_proxies": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 8,
                            "uniqueItems": True,
                            "items": short_text,
                            "description": (
                                "Attractive observations that do not establish this "
                                "target on their own, such as liveness or metadata "
                                "when the required relationship is semantic behavior."
                            ),
                        },
                    },
                },
            },
            "pilot_briefing": {
                "description": (
                    "Concise task-specific Solver pilot briefing. It may prioritize "
                    "formal authority and name uncertainty, but may not prescribe tools, "
                    "commands, exact actions, routes, retries, or a fixed workflow. "
                    "Its priorities and adaptive strategy references must use existing "
                    "outcome, constraint, or proof authority IDs; they are not prose."
                ),
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "mission",
                    "priorities",
                    "uncertainties",
                    "adaptive_strategy",
                ],
                "properties": {
                    "mission": {
                        **text,
                        "maxLength": 600,
                    },
                    "priorities": {
                        **refs,
                        "minItems": 1,
                        "description": (
                            "Ordered references to existing v3 authority IDs: each item "
                            "must exactly match an outcome_id, constraint_id, or proof_id. "
                            "Do not put natural-language priority descriptions here."
                        ),
                    },
                    "uncertainties": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": short_text,
                    },
                    "adaptive_strategy": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "guidance",
                                "serves",
                                "pivot_when",
                            ],
                            "properties": {
                                "guidance": short_text,
                                "serves": {**refs, "minItems": 1},
                                "pivot_when": short_text,
                            },
                        },
                    },
                },
            },
        },
    }


def _provider_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and any(
        isinstance(item, Mapping) and item.get("type") == "null"
        for item in any_of
    ):
        return schema
    return {"anyOf": [schema, {"type": "null"}]}


def _provider_strict_node(value: Any) -> Any:
    if isinstance(value, list):
        return [_provider_strict_node(item) for item in value]
    if not isinstance(value, Mapping):
        return deepcopy(value)

    is_object = value.get("type") == "object"
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"$schema", "$id", "uniqueItems"}:
            continue
        if is_object and key == "properties":
            continue
        result[str(key)] = _provider_strict_node(item)

    if "const" in result:
        constant = result.pop("const")
        result["enum"] = [constant]
        if "type" not in result:
            result["type"] = "string"

    if is_object:
        properties = value.get("properties", {})
        if not isinstance(properties, Mapping):
            raise ValueError("object schema properties must be a mapping")
        original_required = set(value.get("required", ()))
        strict_properties: dict[str, Any] = {}
        for name, child in properties.items():
            rendered = _provider_strict_node(child)
            if str(name) not in original_required:
                rendered = _provider_nullable(rendered)
            strict_properties[str(name)] = rendered
        result["properties"] = strict_properties
        result["required"] = list(strict_properties)
        result["additionalProperties"] = False
    return result


def architect_v3_provider_schema() -> dict[str, Any]:
    """Return the strict Azure/OpenAI provider schema for V3 output."""

    rendered = _provider_strict_node(architect_v3_json_schema())
    if not isinstance(rendered, dict):
        raise TypeError("Architect v3 provider schema must be an object")
    return rendered
