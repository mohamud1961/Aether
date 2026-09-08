"""Immutable task truth for the canonical Aether-Next runtime.

The Architect may propose strategy, but these facts and clauses are the
immutable task authority consumed by downstream state and verifier code. The
module deliberately contains no benchmark- or task-specific knowledge.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class TaskFact:
    fact_id: str
    statement: str
    source: str
    verbatim_anchors: tuple[str, ...] = ()
    authority_scope: str = "outcome"

    def __post_init__(self) -> None:
        if not isinstance(self.fact_id, str) or not self.fact_id.strip():
            raise ValueError("fact_id must be non-empty")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ValueError("fact statement must be non-empty")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("fact source must be non-empty")
        anchors = tuple(self.verbatim_anchors)
        if any(not isinstance(item, str) or not item.strip() for item in anchors):
            raise ValueError("verbatim anchors must be non-empty strings")
        if len(anchors) != len(set(anchors)):
            raise ValueError("verbatim anchors must be unique within a fact")
        if any(item not in self.statement for item in anchors):
            raise ValueError("every verbatim anchor must occur byte-for-byte in its fact")
        scope = str(self.authority_scope or "outcome").strip()
        if scope not in {"outcome", "method"}:
            raise ValueError("fact authority_scope must be outcome or method")
        object.__setattr__(self, "verbatim_anchors", anchors)
        object.__setattr__(self, "authority_scope", scope)

    def as_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "fact_id": self.fact_id,
            "statement": self.statement,
            "source": self.source,
        }
        if self.verbatim_anchors:
            payload["verbatim_anchors"] = list(self.verbatim_anchors)
        if self.authority_scope != "outcome":
            payload["authority_scope"] = self.authority_scope
        return payload


@dataclass(frozen=True)
class TaskClause:
    clause_id: str
    text: str
    exact_atoms: tuple[str, ...] = ()
    fact_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.clause_id, str) or not self.clause_id.strip():
            raise ValueError("clause_id must be non-empty")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("clause text must be non-empty")
        atoms = tuple(self.exact_atoms)
        refs = tuple(self.fact_refs)
        if any(not isinstance(atom, str) or not atom.strip() for atom in atoms):
            raise ValueError("exact task atoms must be non-empty strings")
        if len(atoms) != len(set(atoms)):
            raise ValueError("exact task atoms must be unique within a clause")
        if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("fact references must be non-empty strings")
        if len(refs) != len(set(refs)):
            raise ValueError("fact references must be unique within a clause")
        object.__setattr__(self, "exact_atoms", atoms)
        object.__setattr__(self, "fact_refs", refs)

    def as_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "clause_id": self.clause_id,
            "text": self.text,
            "exact_atoms": list(self.exact_atoms),
        }
        if self.fact_refs:
            payload["fact_refs"] = list(self.fact_refs)
        return payload


@dataclass(frozen=True)
class MethodConstraint:
    """A task-mandated execution method, separate from final outcome proof.

    The Architect authors the statement and bindings. The kernel does not
    interpret the prose or choose a tool; it only preserves immutable identity
    and later requires evidence for the exact constraint ID.
    """

    constraint_id: str
    statement: str
    obligation_refs: tuple[str, ...]
    fact_refs: tuple[str, ...] = ()
    verbatim_anchors: tuple[str, ...] = ()
    acceptance_observation: str = ""
    falsification_observation: str = ""
    constraint_kind: str = "required_method"

    def __post_init__(self) -> None:
        if not isinstance(self.constraint_id, str) or not self.constraint_id.strip():
            raise ValueError("method constraint_id must be non-empty")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ValueError("method constraint statement must be non-empty")
        obligations = tuple(self.obligation_refs)
        kind = str(self.constraint_kind or "required_method").strip()
        facts = tuple(self.fact_refs)
        anchors = tuple(self.verbatim_anchors)
        acceptance = str(self.acceptance_observation or "").strip()
        falsification = str(self.falsification_observation or "").strip()
        if kind not in {
            "required_method", "prohibited_method", "resource_limit", "timing", "ordering"
        }:
            raise ValueError("unsupported method constraint_kind")
        if not obligations:
            raise ValueError("method constraints must bind at least one obligation")
        if any(not isinstance(ref, str) or not ref.strip() for ref in obligations):
            raise ValueError("method obligation references must be non-empty strings")
        if len(obligations) != len(set(obligations)):
            raise ValueError("method obligation references must be unique")
        if any(not isinstance(ref, str) or not ref.strip() for ref in facts):
            raise ValueError("method fact references must be non-empty strings")
        if len(facts) != len(set(facts)):
            raise ValueError("method fact references must be unique")
        if any(not isinstance(anchor, str) or not anchor.strip() for anchor in anchors):
            raise ValueError("method verbatim anchors must be non-empty strings")
        if len(anchors) != len(set(anchors)):
            raise ValueError("method verbatim anchors must be unique")
        object.__setattr__(self, "obligation_refs", obligations)
        object.__setattr__(self, "constraint_kind", kind)
        object.__setattr__(self, "fact_refs", facts)
        object.__setattr__(self, "verbatim_anchors", anchors)
        object.__setattr__(self, "acceptance_observation", acceptance)
        object.__setattr__(self, "falsification_observation", falsification)

    def as_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "constraint_id": self.constraint_id,
            "statement": self.statement,
            "obligation_refs": list(self.obligation_refs),
        }
        if self.constraint_kind != "required_method":
            payload["constraint_kind"] = self.constraint_kind
        if self.fact_refs:
            payload["fact_refs"] = list(self.fact_refs)
        if self.verbatim_anchors:
            payload["verbatim_anchors"] = list(self.verbatim_anchors)
        if self.acceptance_observation:
            payload["acceptance_observation"] = self.acceptance_observation
        if self.falsification_observation:
            payload["falsification_observation"] = self.falsification_observation
        return payload


@dataclass(frozen=True)
class TaskContract:
    raw_task_prompt: str
    clauses: tuple[TaskClause, ...]
    facts: tuple[TaskFact, ...] = ()
    method_constraints: tuple[MethodConstraint, ...] = ()
    schema_version: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.raw_task_prompt, str) or not self.raw_task_prompt.strip():
            raise ValueError("raw_task_prompt must be non-empty")
        clauses = tuple(self.clauses)
        facts = tuple(self.facts)
        method_constraints = tuple(self.method_constraints)
        if self.schema_version and (
            not isinstance(self.schema_version, str) or not self.schema_version.strip()
        ):
            raise ValueError("task contract schema_version must be a non-empty string")
        if not clauses:
            raise ValueError("at least one task clause is required")
        if any(not isinstance(clause, TaskClause) for clause in clauses):
            raise TypeError("clauses must contain TaskClause values")
        if any(not isinstance(fact, TaskFact) for fact in facts):
            raise TypeError("facts must contain TaskFact values")
        if any(not isinstance(item, MethodConstraint) for item in method_constraints):
            raise TypeError("method_constraints must contain MethodConstraint values")
        clause_ids = [clause.clause_id for clause in clauses]
        fact_ids = [fact.fact_id for fact in facts]
        method_ids = [item.constraint_id for item in method_constraints]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError("task clause IDs must be unique")
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("task fact IDs must be unique")
        if len(method_ids) != len(set(method_ids)):
            raise ValueError("method constraint IDs must be unique")
        unknown = sorted({ref for clause in clauses for ref in clause.fact_refs} - set(fact_ids))
        if unknown:
            raise ValueError("task clauses contain unknown fact references: " + ", ".join(unknown))
        fact_scope = {fact.fact_id: fact.authority_scope for fact in facts}
        method_only_in_clauses = sorted({
            ref for clause in clauses for ref in clause.fact_refs
            if fact_scope.get(ref) == "method"
        })
        if method_only_in_clauses:
            raise ValueError(
                "task clauses cannot reference method-only facts: "
                + ", ".join(method_only_in_clauses)
            )
        unknown_method_facts = sorted(
            {ref for item in method_constraints for ref in item.fact_refs} - set(fact_ids)
        )
        if unknown_method_facts:
            raise ValueError(
                "method constraints contain unknown fact references: "
                + ", ".join(unknown_method_facts)
            )
        outcome_only_in_methods = sorted({
            ref for item in method_constraints for ref in item.fact_refs
            if fact_scope.get(ref) == "outcome"
        })
        if outcome_only_in_methods:
            raise ValueError(
                "method constraints cannot reference outcome-only facts: "
                + ", ".join(outcome_only_in_methods)
            )
        method_fact_refs = {ref for item in method_constraints for ref in item.fact_refs}
        unbound_method_facts = sorted(
            fact.fact_id for fact in facts
            if fact.authority_scope == "method"
            and fact.fact_id not in method_fact_refs
        )
        if unbound_method_facts:
            raise ValueError(
                "method facts must be referenced by a method constraint: "
                + ", ".join(unbound_method_facts)
            )
        unknown_method_obligations = sorted(
            {ref for item in method_constraints for ref in item.obligation_refs} - set(clause_ids)
        )
        if unknown_method_obligations:
            raise ValueError(
                "method constraints contain unknown obligation references: "
                + ", ".join(unknown_method_obligations)
            )
        object.__setattr__(self, "clauses", clauses)
        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "method_constraints", method_constraints)

    @property
    def clause_ids(self) -> frozenset[str]:
        return frozenset(clause.clause_id for clause in self.clauses)

    @property
    def fact_ids(self) -> frozenset[str]:
        return frozenset(fact.fact_id for fact in self.facts)

    @property
    def enriched(self) -> bool:
        return bool(
            self.schema_version
            or self.facts
            or self.method_constraints
            or any(clause.fact_refs for clause in self.clauses)
        )

    @property
    def contract_identity(self) -> str:
        return sha256(_canonical(self._identity_payload()).encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        raw_task_prompt: str,
        clauses: Iterable[TaskClause],
        *,
        facts: Iterable[TaskFact] = (),
        method_constraints: Iterable[MethodConstraint] = (),
        schema_version: str = "",
    ) -> "TaskContract":
        return cls(
            raw_task_prompt=raw_task_prompt,
            clauses=tuple(clauses),
            facts=tuple(facts),
            method_constraints=tuple(method_constraints),
            schema_version=schema_version,
        )

    def _identity_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "raw_task_prompt": self.raw_task_prompt,
            "clauses": [clause.as_payload() for clause in self.clauses],
        }
        if self.schema_version:
            payload["schema_version"] = self.schema_version
        if self.facts:
            payload["facts"] = [fact.as_payload() for fact in self.facts]
        if self.method_constraints:
            payload["method_constraints"] = [
                item.as_payload() for item in self.method_constraints
            ]
        return payload

    def as_payload(self) -> dict[str, object]:
        payload = self._identity_payload()
        if self.enriched:
            payload["contract_identity"] = self.contract_identity
        return payload
