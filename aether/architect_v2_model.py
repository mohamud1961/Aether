"""Compact one-call model boundary for Architect v2 qualification.

This module is intentionally separate from production dispatch. It exposes a
factual request, one fixed system prompt, the canonical v2 schema, and a
strict no-retry parse path for bounded Architect-only canaries.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .architect_input import build_architect_factual_input
from .architect_v2_contract import ArchitectV2Contract, validate_architect_v2
from .model_hooks import ModelCallable
from .runtime_ir import EnvMap


ARCHITECT_V2_REQUEST_SCHEMA_VERSION = "architect_v2_request.v1"
ARCHITECT_V2_MAX_OUTPUT_TOKENS = 8_000
ARCHITECT_V2_MAX_FILE_TREE_CHARS = 6_000
ARCHITECT_V2_MAX_TOP_LEVEL_PATHS = 40
ARCHITECT_V2_MAX_VALIDATION_ROWS = 20
ARCHITECT_V2_MAX_ASSET_ROWS = 24
ARCHITECT_V2_MAX_EXAMPLE_ROWS = 24

ARCHITECT_V2_SYSTEM_PROMPT = """You are the task Architect for Aether.
Return exactly one JSON object matching the supplied aether_architect.v2 schema.

Your job is to make the smallest task-specific semantic decisions needed to
adapt the existing Solver and Verifier. The kernel already owns tools, action
protocols, receipts, freshness, context, memory, safety, providers, timeouts,
and completion mechanics. Do not configure or restate those mechanics.

Completion-language boundary: instructions to signal completion, call `task_done`, or submit,
and optional wait/poll/check instructions are workflow, not independently judgeable user outcomes. Never create an exact fact, obligation, proof, risk, or target for the completion signal itself; optional polling and pre-finish checks do not belong in task_contract. Preserve the underlying observable artifact, state, timing, or behavior. A service remaining available after the agent loop exits is different: persistence is a task result.

Author each decision once:
- task_contract.exact_facts: only precision-critical visible facts; [] is valid.
  Never add filler. This lane contains outcome facts only. Each fact needs a short visible anchor occurring byte-for-byte in its statement. Execution-method authority never belongs here.
- task_contract.obligations: independently judgeable final requirements from the
  user-visible task, not proof mechanics. Each must reference every outcome fact defining its authority. Keep one
  end-to-end obligation unless the user could independently accept or reject the
  parts. Do not repeat proof or workflow prose.
- verifier_design: global strategy and only material false-positive risks,
  authored before proof_intent and bound to affected obligations. A risk means an
  observation could pass while a required relationship remains false; it is not a
  reminder, route, tool, or workflow note.
- proof_intent: one or more canonical proof facets may reference an obligation;
  every linked facet is required for completion. Several obligations may share a
  facet only when the same observation genuinely proves them. Each row's risk_refs
  must contain the exact risk_ids that the facet closes, or [] when it closes no
  declared risk. Every declared risk_id must appear in at least one proof row;
  verifier or Solver prose cannot substitute for formal closure. The proof_kind is
  formal authority, not prose. A successful public operation does not prove
  separately required exact bytes, structure, metadata, configuration, identity,
  or pairing. Attach separate exact_state and public_behavior facets to the same
  obligation when both relationships are needed; do not duplicate a semantic
  obligation merely to fit proof types. Choose proof_kind by the relationship
  that establishes correctness, not by the surface being inspected. When acceptance
  requires deriving expected semantics from authoritative input and comparing the
  candidate against them, independent_comparison takes precedence. Do not replace
  that relationship with exact_state merely because final bytes can be inspected,
  or with public_behavior merely because the candidate transformation can run.
  Use multiple facets for genuinely distinct required relationships, such as static
  implementation identity plus live behavior, or operation lifecycle plus final
  artifact state. Before returning, ensure each declared false-positive risk is
  impossible if all of its referenced proof facets pass.
- method_constraints: the only formal method authority. Add one only when visible task language makes a method mandatory and a different method must count as failure even if the outcome is correct. Each row owns grounded verbatim_anchors, obligation_refs, and acceptance_observation/falsification_observation for immutable action history. Anchors need not repeat in the statement. Include every required method detail: implementation, delay, registration, monitoring, or finished state. Describe the task-level method, not a kernel route or tool. Method counterexamples belong in the method falsification field, never outcome risks or proof_intent. Exclude completion signalling, optional polling, and suggested workflow.
- solver_design: an adaptive mission and strategy, not a predicted sequence of actions. task_specific_rules are advisory-only and contain no authority or formal bindings.
- information_emphasis: optional Solver-only advisory topics that matter for
  future decisions.

Use only these proof kinds, choosing by the relationship that defines
correctness rather than the easiest observation surface:
- independent_comparison: a separately derived computation, interpretation,
  transformation, or expected result is compared with the candidate.
- direct_perception: correctness is established by direct visual or perceptual inspection.
- public_behavior: the task's success criterion is a fresh operation through the
  required public interface, without a separate source-derived comparison.
- exact_state: correctness is fully established by current exact bytes, structure,
  metadata, configuration, identity, or pairing, without a separate derivation
  or public operation.

Before returning, audit the formal fields: every fact has a visible consistent
anchor and is referenced; every obligation binds relevant facts and has proof;
distinct proof relationships are conjunctive; proof_kind matches the relationship;
and each mandatory method appears once as a self-contained method constraint, not hidden in strategy or duplicated in outcome authority. Method-only anchors never enter outcome facts, obligations, proofs, or risks; method acceptance and falsification live only in method_constraints. Narrative cannot substitute for formal fields.

Do not invent facts, hidden tests, grader requirements, tool availability, or
unsupported constraints. Do not duplicate the same semantic requirement in
multiple sections. Return JSON only, with no markdown or commentary."""


@dataclass(frozen=True)
class ArchitectV2ModelResult:
    contract: ArchitectV2Contract | None
    raw_output: str
    errors: tuple[str, ...]
    call_count: int

    @property
    def valid(self) -> bool:
        return self.contract is not None and not self.errors


def _bounded_text(value: Any, limit: int) -> tuple[str, bool, int]:
    text = str(value or "")
    if len(text) <= limit:
        return text, False, len(text)
    head = max(1, int(limit * 0.75))
    tail = max(1, limit - head)
    compact = text[:head] + "\n...[file tree middle omitted]...\n" + text[-tail:]
    return compact, True, len(text)


def _drop_uninformative(value: Any) -> Any:
    if isinstance(value, Mapping):
        compact = {
            str(key): _drop_uninformative(item)
            for key, item in value.items()
        }
        return {
            key: item
            for key, item in compact.items()
            if item not in (None, "", (), [], {})
        }
    if isinstance(value, list):
        compact = [_drop_uninformative(item) for item in value]
        return [item for item in compact if item not in (None, "", (), [], {})]
    if isinstance(value, tuple):
        compact = [_drop_uninformative(item) for item in value]
        return [item for item in compact if item not in (None, "", (), [], {})]
    if isinstance(value, str) and value.strip().lower() in {"unknown", "unmeasured"}:
        return None
    return value


def _compact_task(source_task: Mapping[str, Any]) -> dict[str, Any]:
    tree, tree_truncated, original_tree_chars = _bounded_text(
        source_task.get("file_tree", ""), ARCHITECT_V2_MAX_FILE_TREE_CHARS
    )
    path_facts = dict(source_task.get("path_facts", {}) or {})
    top_level = path_facts.get("top_level")
    if isinstance(top_level, list):
        path_facts["top_level"] = top_level[:ARCHITECT_V2_MAX_TOP_LEVEL_PATHS]
    materials = dict(source_task.get("visible_materials", {}) or {})
    materials["validation_candidates"] = list(
        materials.get("validation_candidates", ())
    )[:ARCHITECT_V2_MAX_VALIDATION_ROWS]
    materials["declared_assets"] = list(
        materials.get("declared_assets", ())
    )[:ARCHITECT_V2_MAX_ASSET_ROWS]
    materials["visible_examples"] = list(
        materials.get("visible_examples", ())
    )[:ARCHITECT_V2_MAX_EXAMPLE_ROWS]
    result = {
        "prompt": str(source_task.get("prompt", "")),
        "workspace_root": str(source_task.get("workspace_root", "")),
        "file_tree": tree,
        "path_facts": _drop_uninformative(path_facts),
        "visible_materials": _drop_uninformative(materials),
    }
    if tree_truncated:
        result["file_tree_compaction"] = {
            "truncated": True,
            "original_chars": original_tree_chars,
            "rendered_chars": len(tree),
        }
    return result


def build_architect_v2_model_request(envmap: EnvMap) -> dict[str, Any]:
    """Return bounded factual material without the V1 runtime manual."""
    source = build_architect_factual_input(envmap)
    source_environment = dict(source["environment"])
    availability = []
    for row in source_environment.get("capability_availability", ()):
        if not isinstance(row, Mapping):
            continue
        availability.append({
            "capability_id": str(row.get("capability_id", "")),
            "available": bool(row.get("available", False)),
        })
    environment = _drop_uninformative({
        "network_scope": source_environment.get("network_scope"),
        "enforced_network_policy": source_environment.get("enforced_network_policy"),
        "resource_limits": source_environment.get("resource_limits"),
        "permissions": source_environment.get("permissions"),
        "services": source_environment.get("services"),
        "interactive_features": source_environment.get("interactive_features"),
        "capability_availability": availability,
        "observed_support": source_environment.get("observed_support"),
        "probe_facts": source_environment.get("probe_facts"),
    })
    return {
        "schema_version": ARCHITECT_V2_REQUEST_SCHEMA_VERSION,
        "request_identity": dict(source["request_identity"]),
        "task": _compact_task(source["task"]),
        "environment": environment,
    }


def _drop_provider_null_optionals(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _drop_provider_null_optionals(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_drop_provider_null_optionals(item) for item in value]
    return value


def architect_v2_messages(request: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": ARCHITECT_V2_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                request,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                default=str,
            ),
        },
    ]


class ArchitectV2Model:
    """One provider call, no repair, review, finalizer, or automatic retry."""

    def __init__(
        self,
        model: ModelCallable,
        *,
        max_output_tokens: int = ARCHITECT_V2_MAX_OUTPUT_TOKENS,
    ) -> None:
        parsed = int(max_output_tokens)
        if parsed < 1_000 or parsed > ARCHITECT_V2_MAX_OUTPUT_TOKENS:
            raise ValueError(
                f"Architect v2 max_output_tokens must be 1000..{ARCHITECT_V2_MAX_OUTPUT_TOKENS}"
            )
        self._model = model
        self.max_output_tokens = parsed
        self.call_count = 0
        self.last_messages: tuple[dict[str, str], ...] = ()
        self.last_raw_output = ""
        self.last_errors: tuple[str, ...] = ()

    def configure(self, request: Mapping[str, Any]) -> ArchitectV2ModelResult:
        messages = architect_v2_messages(request)
        self.last_messages = tuple(dict(item) for item in messages)
        self.call_count += 1
        try:
            raw_value = self._model(
                messages,
                max_output_tokens=self.max_output_tokens,
            )
            if isinstance(raw_value, Mapping):
                raw = json.dumps(
                    dict(raw_value), sort_keys=True, separators=(",", ":")
                )
                payload: Any = dict(raw_value)
            else:
                raw = str(raw_value)
                payload = json.loads(raw)
            if not isinstance(payload, Mapping):
                raise ValueError("Architect v2 output must be one JSON object")
            contract = validate_architect_v2(_drop_provider_null_optionals(payload))
            self.last_raw_output = raw
            self.last_errors = ()
            return ArchitectV2ModelResult(contract, raw, (), self.call_count)
        except Exception as exc:
            self.last_raw_output = locals().get("raw", "")
            self.last_errors = (str(exc),)
            return ArchitectV2ModelResult(
                None,
                self.last_raw_output,
                self.last_errors,
                self.call_count,
            )
