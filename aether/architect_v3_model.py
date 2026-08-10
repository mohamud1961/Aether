"""One-call model boundary for Architect v3 qualification.

The request contains raw source-tagged task and environment material.  It does
not pre-classify facts, outcomes, constraints, or proof candidates.  The model
owns that semantic classification and returns the minimal v3 contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .architect_input import build_architect_factual_input
from .architect_v3_contract import (
    ArchitectV3Contract,
    validate_architect_v3,
)
from .model_hooks import ModelCallable
from .runtime_ir import EnvMap


ARCHITECT_V3_REQUEST_SCHEMA_VERSION = "architect_v3_request.v2"
ARCHITECT_V3_MAX_OUTPUT_TOKENS = 5_000
ARCHITECT_V3_MAX_FILE_TREE_CHARS = 6_000
ARCHITECT_V3_MAX_TOP_LEVEL_PATHS = 40
ARCHITECT_V3_MAX_VISIBLE_ROWS = 24

ARCHITECT_V3_SYSTEM_PROMPT = """You are the task Architect for Aether.
Return JSON matching the aether_architect.v3 schema.

You are the semantic authority. The kernel owns tools, action protocols,
receipts, context, memory, provider mechanics, safety, and runtime execution.
The Solver owns concrete execution. Do not choose tools, commands, exact actions,
command order, routes, retries, or a fixed workflow. Architect designs a
task-specific pilot briefing.

Classify the raw source-tagged material in this order:

1. Outcomes and owner-local parameters
Identify the smallest set of independently judgeable conditions that must be
true when the task is finished. Outcomes are final state or externally
observable success conditions. Apply runtime_protocol completion ownership: a
bare harness finish instruction is submit_outcome protocol, not a task outcome;
preserve only a separately required named external signal effect. Do not create
 outcomes for literals, workflow instructions, optional checks, or implementation
 steps. Apply outcome subsumption: when task language is
`run/start/launch X so Y` or `... to Y`, X is normally the means and Y is the
independently judgeable outcome. Do not create a separate process-running or
service-started outcome when the required public behavior already proves the
relevant service is operational. Create separate process-state authority only
when the user independently requires persistence, process identity, liveness
beyond the public operation, or another relationship not subsumed by Y. A weak
liveness proxy never replaces or duplicates stronger public behavior.

Place every precision-critical literal directly inside the outcome that owns it
as a parameter. Parameter values must be exact source strings or numbers only.
Never encode a relationship as a boolean such as true/false, and never paraphrase
a clause into the value. Put relational meaning in the owning description and
use parameters only for exact source literals. For example, describe that a
service must persist after exit, then ground the exact phrase `after the agent
loop exits`; describe that a file must exist, then ground the exact filename.
Each parameter_id must describe what the value means, such as grpc_port,
request_field_declaration, or result_path; generic IDs such as f1 are invalid.
source_text must be copied verbatim from a cited source. Preserve Markdown only
when present; never add formatting delimiters. The value is the underlying task
value without presentation-only Markdown. Do not normalize or reconstruct
source_text. Inline `ok`: value `ok`, source_text `` `ok` ``. Fenced status: ready:
source_text `status: ready`, not an invented inline-code wrapper. Use the shortest
exact span preserving binding. Keep coupled declarations together when splitting would
lose which value belongs to which entity. Preserve acceptance-changing modifiers
such as `fresh`, `current`, `exact`, ordering, thresholds, and comparators as
owner-local parameters rather than leaving them only in prose.
For example, preserve `SetValRequest contains int32 val = 2` rather than
extracting an unlabeled `2`, and preserve `fresh request` when freshness is part
of the required public observation.

2. Explicit task-imposed constraints
Add a constraint only when authoritative task language explicitly requires or
prohibits an execution method, resource use, timing relationship, ordering, or
and violating it must count as failure even if the outcome is otherwise
correct. Attach every constraint to the outcome(s) it governs. Put exact
constraint values inside that constraint as owner-local parameters. Ports, paths,
filenames, endpoints, protocols, service names, configuration locations, and
desired runtime availability are normally outcome parameters and are not
constraints merely because they are named. They become constraint parameters
when authoritative task language explicitly makes using that route, path,
launcher, ordering, resource limit, or method mandatory independently of the
final outcome. For example, `listen on port 5328` makes 5328 an outcome parameter;
`run using server_ok.py` makes server_ok.py a required-method constraint; and
`configure the route using /etc/nginx/conf.d/default.conf` makes that path a
required-method constraint. Visible repository contents and Solver-chosen methods
are not constraints. Classify constraint polarity exactly: `must use X`, `using
X`, or another positive mandatory route is `required_method`; `without X`, `do
not use X`, `must not use X`, or another explicit exclusion is
`prohibited_method`. Do not encode an excluded method as a required method. Use
this counterfactual test: if a different method that
produced every required outcome would still satisfy the task, there is no method
constraint. Imperative verbs such as `write`, `create`, `run`, `serve`, or
`generate` normally state desired outcomes, not methods. `Write config.yaml` is
a file outcome and `run the service so /ready reports ready` is a live-behavior
outcome; neither requires a method constraint. An empty constraints array is
normal for most tasks.

3. Proof facets
Attach each proof facet to exactly one outcome or explicit constraint. Describe
what observation would establish or falsify the target. Do not prescribe a
command, tool, route, or sequence. Every outcome and constraint needs direct
proof coverage. Multiple
facets are allowed only for genuinely distinct relationships such as exact state
plus public behavior.
For every proof facet, include one to eight `insufficient_proxies`: weak
observations that do not establish the target alone. Name the observation, not
a command or route. Examples: an open port for protocol behavior, a process for
persistence or identity, matching artifact metadata, or a solver-authored check
without independent derivation.

Choose proof_kind by the relationship that establishes correctness:
- exact_state: exact bytes, structure, metadata, configuration, identity, field
  binding, numbering, pairing, immutable action history, execution receipts,
  launcher identity or socket ownership
  establish correctness.
- public_behavior: a fresh operation through the required public interface
  establishes correctness without separately proving exact internal structure.
- independent_comparison: an independently derived expected result is compared
  with the candidate.
- direct_perception: visual, audio, or other perceptual artifact content must be
  judged perceptually. Use direct_perception whenever the decisive acceptance
  observation requires recognising content in frames, images, audio, or another
  perceptual medium, even when file existence or artifact path are also exact
  state. Do not choose exact_state merely because perceptual content is stored in
  a file. Logs, receipts, process tables, metadata, configuration, and
  action history are exact state, not direct perception.
A successful public operation does not prove separately required exact schema,
field numbering, generated bindings, configuration, identity, or pairing. A
constraint proof must establish completed execution compliance from current state,
telemetry, or immutable action history. The fact that the task prompt or
instructions contain a requirement never proves that execution complied with it.

4. Solver pilot briefing
Return `pilot_briefing`: mission; ordered `priorities` are authority IDs (each exactly one existing `outcome_id`, `constraint_id`, or `proof_id`). Do not write natural-language priority descriptions. Include 1–4 uncertainties and 1–4 adaptive strategy rows. Each gives adaptive cognitive guidance, served IDs, and pivot_when. Phrase unobserved state as a hypothesis, not known fact. Do not prescribe
concrete actions, commands, tools, read/retry sequences, or fixed workflow. The Solver must be able to change all concrete actions while still following the strategy in the briefing. `pivot_when` must state only an observed state or
contradiction that triggers replanning: describe evidence, never the method
afterward. Keep commands, tools, routes, reads, writes, checks, and alternate
methods out of `pivot_when`, even conditionally.
Omit generic plan/inspect/test/verify advice. Legacy `solver_strategy` is
compatibility-only; emit `pilot_briefing`.

Parameters are exact owner-local data, not independent semantic owners. Never copy
the whole task prompt, workspace root, file tree, or environment inventory into a
parameter. Do not add one merely because a value is visible. Its value must occur
in exact source_text, and source_text in a cited model-visible source. Do not invent
hidden tests, grader requirements, unavailable facts, or user constraints.


Author each semantic decision once. Outcomes own success meaning and exact
parameters; constraints narrow execution and own exact parameters; proof facets
define evidence relationships. The Solver pilot briefing can prioritise/orient
those authorities but cannot redefine or add to them.
Return JSON only, with no markdown or commentary."""


@dataclass(frozen=True)
class ArchitectV3ModelResult:
    contract: ArchitectV3Contract | None
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
    compact = text[:head] + "\n...[middle omitted]...\n" + text[-tail:]
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
    if isinstance(value, (list, tuple)):
        compact = [_drop_uninformative(item) for item in value]
        return [
            item for item in compact
            if item not in (None, "", (), [], {})
        ]
    if isinstance(value, str) and value.strip().lower() in {
        "unknown",
        "unmeasured",
    }:
        return None
    return value


def _bounded_rows(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    return list(value[:limit])


def build_architect_v3_model_request(envmap: EnvMap) -> dict[str, Any]:
    """Return bounded raw source-tagged material without semantic candidates."""

    source = build_architect_factual_input(envmap)
    task = dict(source["task"])
    environment = dict(source["environment"])
    tree, tree_truncated, original_tree_chars = _bounded_text(
        task.get("file_tree", ""), ARCHITECT_V3_MAX_FILE_TREE_CHARS
    )
    path_facts = dict(task.get("path_facts", {}) or {})
    top_level = path_facts.get("top_level")
    if isinstance(top_level, list):
        path_facts["top_level"] = top_level[:ARCHITECT_V3_MAX_TOP_LEVEL_PATHS]

    materials = dict(task.get("visible_materials", {}) or {})
    for key in ("validation_candidates", "declared_assets", "visible_examples"):
        materials[key] = _bounded_rows(
            materials.get(key, ()), ARCHITECT_V3_MAX_VISIBLE_ROWS
        )

    sources: list[dict[str, Any]] = [
        {
            "source_id": "user_task",
            "source_type": "task_prompt",
            "content": str(task.get("prompt", "")),
        },
    ]
    compact_workspace = _drop_uninformative({
        "file_tree": tree,
        "path_facts": path_facts,
        "file_tree_compaction": (
            {
                "truncated": True,
                "original_chars": original_tree_chars,
                "rendered_chars": len(tree),
            }
            if tree_truncated else {}
        ),
    })
    if compact_workspace:
        sources.append({
            "source_id": "workspace",
            "source_type": "visible_environment",
            "content": compact_workspace,
        })
    compact_materials = _drop_uninformative(materials)
    if compact_materials:
        sources.append({
            "source_id": "visible_materials",
            "source_type": "visible_material",
            "content": compact_materials,
        })
    compact_environment = _drop_uninformative({
        "network_scope": environment.get("network_scope"),
        "enforced_network_policy": environment.get("enforced_network_policy"),
        "resource_limits": environment.get("resource_limits"),
        "permissions": environment.get("permissions"),
        "services": environment.get("services"),
        "interactive_features": environment.get("interactive_features"),
        "observed_support": environment.get("observed_support"),
        "probe_facts": environment.get("probe_facts"),
    })
    if compact_environment:
        sources.append({
            "source_id": "environment",
            "source_type": "visible_environment",
            "content": compact_environment,
        })
    return {
        "schema_version": ARCHITECT_V3_REQUEST_SCHEMA_VERSION,
        "request_identity": dict(source["request_identity"]),
        "runtime_protocol": {
            "completion_signal_owner": "solver submit_outcome protocol",
            "completion_language_rule": (
                "Bare instructions to signal completion, call task_done, finish, or "
                "equivalent are harness protocol and are not task outcomes or proofs. "
                "Preserve a completion signal only when the task separately requires a "
                "named external artifact, message, callback, API effect, receipt, or "
                "process event."
            ),
        },
        "sources": sources,
    }


def architect_v3_source_catalog(
    request: Mapping[str, Any],
) -> dict[str, str]:
    """Return the exact source IDs and source types visible to the model."""

    catalog: dict[str, str] = {}
    raw_sources = request.get("sources", ())
    if not isinstance(raw_sources, list):
        return catalog
    for row in raw_sources:
        if not isinstance(row, Mapping):
            continue
        source_id = str(row.get("source_id", "")).strip()
        source_type = str(row.get("source_type", "")).strip()
        if source_id and source_type:
            catalog[source_id] = source_type
    return catalog


def architect_v3_source_contents(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact source contents visible to the model."""

    contents: dict[str, Any] = {}
    raw_sources = request.get("sources", ())
    if not isinstance(raw_sources, list):
        return contents
    for row in raw_sources:
        if not isinstance(row, Mapping):
            continue
        source_id = str(row.get("source_id", "")).strip()
        if source_id and "content" in row:
            contents[source_id] = row["content"]
    return contents


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


def architect_v3_messages(request: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": ARCHITECT_V3_SYSTEM_PROMPT},
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


class ArchitectV3Model:
    """One provider call, strict parse, no correction or semantic retry."""

    def __init__(
        self,
        model: ModelCallable,
        *,
        max_output_tokens: int = ARCHITECT_V3_MAX_OUTPUT_TOKENS,
    ) -> None:
        parsed = int(max_output_tokens)
        if parsed < 1_000 or parsed > ARCHITECT_V3_MAX_OUTPUT_TOKENS:
            raise ValueError(
                "Architect v3 max_output_tokens must be "
                f"1000..{ARCHITECT_V3_MAX_OUTPUT_TOKENS}"
            )
        self._model = model
        self.max_output_tokens = parsed
        self.call_count = 0
        self.last_messages: tuple[dict[str, str], ...] = ()
        self.last_raw_output = ""
        self.last_errors: tuple[str, ...] = ()

    def configure(self, request: Mapping[str, Any]) -> ArchitectV3ModelResult:
        messages = architect_v3_messages(request)
        self.last_messages = tuple(dict(item) for item in messages)
        self.last_raw_output = ""
        self.last_errors = ()
        self.call_count += 1
        raw = ""
        try:
            raw_value = self._model(
                messages,
                max_output_tokens=self.max_output_tokens,
            )
            if isinstance(raw_value, Mapping):
                payload: Any = dict(raw_value)
                raw = json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            else:
                raw = str(raw_value)
                payload = json.loads(raw)
            if not isinstance(payload, Mapping):
                raise ValueError("Architect v3 output must be one JSON object")
            contract = validate_architect_v3(
                _drop_provider_null_optionals(payload),
                source_catalog=architect_v3_source_catalog(request),
                source_contents=architect_v3_source_contents(request),
            )
            self.last_raw_output = raw
            return ArchitectV3ModelResult(
                contract,
                raw,
                (),
                self.call_count,
            )
        except Exception as exc:
            self.last_raw_output = raw
            self.last_errors = (str(exc),)
            return ArchitectV3ModelResult(
                None,
                raw,
                self.last_errors,
                self.call_count,
            )
