"""Research-only provenance graph for G-JUDGE-0.

The graph stores task-local requirements, Solver-owned hypotheses, observations,
semantic relation labels, and explicit provenance.  It has no action or
completion authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any


HEAD_CHOICES = {
    "ranking": frozenset({"relevant", "irrelevant", "uncertain"}),
    "assumption": frozenset({"supports", "contradicts", "irrelevant", "uncertain"}),
}
PROVENANCE_RELATIONS = frozenset({"cites", "derived_from"})


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    text: str
    task_sha256: str
    source_span: str = ""
    status: str = "current"


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    text: str
    created_step: int
    status: str = "active"


@dataclass(frozen=True)
class Observation:
    receipt_id: str
    task_id: str
    run_id: str
    task_state_generation: int | None
    origin_id: str
    kind: str
    summary: str
    step: int = 0
    process_generation: str = ""
    artifact_sha256: str = ""
    payload_sha256: str = ""


@dataclass(frozen=True)
class Relation:
    subject_id: str
    receipt_id: str
    relation: str
    source: str
    head: str = "assumption"
    question_sha256: str = ""
    model_id: str = ""
    schema_version: str = ""
    probabilities: dict[str, float] | None = None


@dataclass(frozen=True)
class ProvenanceEdge:
    subject_id: str
    receipt_id: str
    relation: str = "cites"
    source: str = "solver_explicit"


class EvidenceGraph:
    """Task-local advisory state; never an executor or completion gate."""

    authority = "advisory_only"
    snapshot_schema = "aether.evidence_graph_snapshot.v0"

    def __init__(
        self,
        *,
        task_id: str,
        run_id: str,
        task_sha256: str,
        generation: int = 0,
    ) -> None:
        if not task_id or not run_id or not task_sha256:
            raise ValueError("scope identity required")
        if type(generation) is not int or generation < 0:
            raise ValueError("generation invalid")
        self.task_id = task_id
        self.run_id = run_id
        self.task_sha256 = task_sha256
        self.generation = generation
        self.requirements: dict[str, Requirement] = {}
        self.hypotheses: dict[str, Hypothesis] = {}
        self.observations: dict[str, Observation] = {}
        self.relations: dict[tuple[str, str, str, str, str], Relation] = {}
        self.provenance_edges: dict[tuple[str, str, str], ProvenanceEdge] = {}
        self.invalidated_relations: set[tuple[str, str, str, str, str]] = set()
        self.invalidated_provenance: set[tuple[str, str, str]] = set()
        self.events: list[dict[str, Any]] = []

    @staticmethod
    def _canonical(value: Any) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        )

    def add_requirement(self, requirement: Requirement) -> None:
        if not requirement.requirement_id or not requirement.text:
            raise ValueError("requirement identity/text required")
        if requirement.status not in {"current", "superseded"}:
            raise ValueError("requirement status invalid")
        if requirement.task_sha256 != self.task_sha256:
            raise ValueError("requirement task hash mismatch")
        old = self.requirements.get(requirement.requirement_id)
        if old is not None and old != requirement:
            raise ValueError("requirement identity collision")
        self.requirements[requirement.requirement_id] = requirement

    def mark_requirement_superseded(self, requirement_id: str) -> None:
        if requirement_id not in self.requirements:
            raise ValueError("unknown old requirement")
        old = self.requirements[requirement_id]
        if old.status == "superseded":
            return
        self.requirements[requirement_id] = Requirement(
            old.requirement_id,
            old.text,
            old.task_sha256,
            old.source_span,
            "superseded",
        )
        for key, relation in self.relations.items():
            if relation.subject_id == requirement_id:
                self.invalidated_relations.add(key)
        for key, edge in self.provenance_edges.items():
            if edge.subject_id == requirement_id:
                self.invalidated_provenance.add(key)
        self.events.append({"kind": "requirement_superseded", "old": requirement_id})

    def supersede_requirement(self, old_id: str, new: Requirement) -> None:
        self.mark_requirement_superseded(old_id)
        self.add_requirement(new)
        self.events.append(
            {"kind": "requirement_successor", "old": old_id, "new": new.requirement_id}
        )

    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        if not hypothesis.hypothesis_id or not hypothesis.text:
            raise ValueError("hypothesis identity/text required")
        if type(hypothesis.created_step) is not int or hypothesis.created_step < 0:
            raise ValueError("hypothesis step invalid")
        if hypothesis.status not in {"active", "retired"}:
            raise ValueError("hypothesis status invalid")
        old = self.hypotheses.get(hypothesis.hypothesis_id)
        if old is not None and old != hypothesis:
            raise ValueError("hypothesis identity collision")
        self.hypotheses[hypothesis.hypothesis_id] = hypothesis

    def retire_hypothesis(self, hypothesis_id: str) -> None:
        current = self.hypotheses[hypothesis_id]
        self.hypotheses[hypothesis_id] = Hypothesis(
            current.hypothesis_id,
            current.text,
            current.created_step,
            "retired",
        )

    def add_observation(self, observation: Observation) -> None:
        if not observation.receipt_id or not observation.origin_id or not observation.kind:
            raise ValueError("observation identity/origin/kind required")
        if (observation.task_id, observation.run_id) != (self.task_id, self.run_id):
            raise ValueError("cross-scope observation")
        if type(observation.step) is not int or observation.step < 0:
            raise ValueError("observation step invalid")
        generation = observation.task_state_generation
        if generation is not None:
            if type(generation) is not int or generation < 0:
                raise ValueError("observation generation invalid")
            if generation > self.generation:
                raise ValueError("future observation generation")
        old = self.observations.get(observation.receipt_id)
        if old is not None and old != observation:
            raise ValueError("receipt identity collision")
        self.observations[observation.receipt_id] = observation

    def mutate(self, new_generation: int | None = None) -> None:
        target = self.generation + 1 if new_generation is None else int(new_generation)
        if target <= self.generation:
            raise ValueError("task generation must advance")
        self.generation = target
        self.events.append({"kind": "task_state_generation", "generation": target})

    def add_provenance_edge(self, edge: ProvenanceEdge) -> None:
        if edge.relation not in PROVENANCE_RELATIONS:
            raise ValueError("invalid provenance relation")
        if edge.subject_id not in self.requirements and edge.subject_id not in self.hypotheses:
            raise ValueError("unknown subject")
        if edge.receipt_id not in self.observations:
            raise ValueError("unknown receipt")
        key = (edge.subject_id, edge.receipt_id, edge.relation)
        old = self.provenance_edges.get(key)
        if old is not None and old != edge:
            raise ValueError("provenance edge identity collision")
        self.provenance_edges[key] = edge

    def add_relation(self, relation: Relation) -> None:
        if not relation.source:
            raise ValueError("relation source required")
        if relation.head not in HEAD_CHOICES:
            raise ValueError("invalid semantic head")
        if relation.relation not in HEAD_CHOICES[relation.head]:
            raise ValueError("invalid relation for semantic head")
        if relation.subject_id not in self.requirements and relation.subject_id not in self.hypotheses:
            raise ValueError("unknown subject")
        if relation.receipt_id not in self.observations:
            raise ValueError("unknown receipt")
        if relation.probabilities is not None:
            if set(relation.probabilities) != set(HEAD_CHOICES[relation.head]):
                raise ValueError("incomplete probability distribution")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 <= value <= 1
                for value in relation.probabilities.values()
            ):
                raise ValueError("invalid probabilities")
            if abs(sum(relation.probabilities.values()) - 1) > 0.02:
                raise ValueError("probability total invalid")
        key = (
            relation.subject_id,
            relation.receipt_id,
            relation.head,
            relation.source,
            relation.question_sha256,
        )
        old = self.relations.get(key)
        if old is not None and old != relation:
            raise ValueError("relation identity collision")
        self.relations[key] = relation

    def observation_freshness(self, receipt_id: str) -> str:
        generation = self.observations[receipt_id].task_state_generation
        if generation is None:
            return "unknown_generation"
        if generation == self.generation:
            return "current"
        if generation < self.generation:
            return "historical"
        return "future_invalid"

    def relation_rows(self, subject_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, relation in self.relations.items():
            if relation.subject_id != subject_id:
                continue
            observation = self.observations[relation.receipt_id]
            rows.append(
                {
                    **asdict(relation),
                    "freshness": self.observation_freshness(relation.receipt_id),
                    "origin_id": observation.origin_id,
                    "process_generation": observation.process_generation,
                    "invalidated": key in self.invalidated_relations,
                }
            )
        rows.sort(
            key=lambda item: (
                item["invalidated"],
                item["freshness"] != "current",
                item["receipt_id"],
            )
        )
        return rows

    def provenance_rows(self, subject_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, edge in self.provenance_edges.items():
            if edge.subject_id != subject_id:
                continue
            observation = self.observations[edge.receipt_id]
            rows.append(
                {
                    **asdict(edge),
                    "freshness": self.observation_freshness(edge.receipt_id),
                    "origin_id": observation.origin_id,
                    "invalidated": key in self.invalidated_provenance,
                }
            )
        rows.sort(
            key=lambda item: (
                item["invalidated"],
                item["freshness"] != "current",
                item["receipt_id"],
            )
        )
        return rows

    def current_relation_rows(self, subject_id: str) -> list[dict[str, Any]]:
        return [
            row
            for row in self.relation_rows(subject_id)
            if row["freshness"] == "current" and not row["invalidated"]
        ]

    def independent_origin_count(self, subject_id: str) -> int:
        return len({row["origin_id"] for row in self.current_relation_rows(subject_id)})

    def compact_summary(self, max_items: int = 8) -> dict[str, Any]:
        subjects: list[dict[str, Any]] = []
        for subject_id in [*self.requirements, *self.hypotheses]:
            relations = self.relation_rows(subject_id)
            provenance = self.provenance_rows(subject_id)
            if subject_id in self.requirements:
                subject = self.requirements[subject_id]
                subject_kind = "requirement"
                text = subject.text
                status = subject.status
            else:
                subject = self.hypotheses[subject_id]
                subject_kind = "hypothesis"
                text = subject.text
                status = subject.status
            subjects.append(
                {
                    "subject_id": subject_id,
                    "kind": subject_kind,
                    "text": text[:1000],
                    "status": status,
                    "relations": relations[:max_items],
                    "provenance": provenance[:max_items],
                }
            )

        # Keep current task state visible under the bounded projection. Retired
        # hypotheses and superseded requirements remain durable in the graph,
        # but cannot crowd active/current subjects out of the Solver-facing
        # compact summary merely because they were inserted earlier.
        subjects.sort(
            key=lambda item: item["status"] not in {"active", "current"}
        )

        observations = []
        for observation in self.observations.values():
            observations.append({
                "receipt_id": observation.receipt_id,
                "kind": observation.kind,
                "summary": observation.summary[:1000],
                "step": observation.step,
                "freshness": self.observation_freshness(observation.receipt_id),
                "origin_id": observation.origin_id,
                "process_generation": observation.process_generation,
                "artifact_sha256": observation.artifact_sha256,
                "payload_sha256": observation.payload_sha256,
            })
        observations.sort(key=lambda item: (
            item["freshness"] != "current",
            item["freshness"] == "unknown_generation",
            -int(item["step"]),
            item["receipt_id"],
        ))

        # Collapse only mechanically identical observations in the bounded
        # projection. Every receipt remains durable in self.observations and in
        # snapshot(). Same origin with changed bytes/payload is retained.
        compact_observations = []
        seen_observation_versions: set[tuple[str, str, str]] = set()
        duplicate_observation_count = 0
        for item in observations:
            exact_version = str(item.get("artifact_sha256") or item.get("payload_sha256") or "")
            key = (
                str(item.get("freshness") or ""),
                str(item.get("origin_id") or ""),
                exact_version,
            )
            if exact_version and key in seen_observation_versions:
                duplicate_observation_count += 1
                continue
            if exact_version:
                seen_observation_versions.add(key)
            compact_observations.append(item)

        rendered_observations = compact_observations[:max_items]
        return {
            "schema": "aether.evidence_graph_summary.v0",
            "authority": self.authority,
            "task_state_generation": self.generation,
            "subjects": subjects[:max_items],
            "observations": rendered_observations,
            "observation_rendering": {
                "durable_receipts": len(observations),
                "distinct_versions": len(compact_observations),
                "rendered": len(rendered_observations),
                "duplicate_receipts_collapsed": duplicate_observation_count,
                "distinct_versions_omitted": max(0, len(compact_observations) - len(rendered_observations)),
            },
        }

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": self.snapshot_schema,
            "authority": self.authority,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "task_sha256": self.task_sha256,
            "task_state_generation": self.generation,
            "requirements": [asdict(item) for item in self.requirements.values()],
            "hypotheses": [asdict(item) for item in self.hypotheses.values()],
            "observations": [asdict(item) for item in self.observations.values()],
            "relations": [asdict(item) for item in self.relations.values()],
            "provenance_edges": [asdict(item) for item in self.provenance_edges.values()],
            "invalidated_relation_keys": [
                list(item) for item in sorted(self.invalidated_relations)
            ],
            "invalidated_provenance_keys": [
                list(item) for item in sorted(self.invalidated_provenance)
            ],
            "events": list(self.events),
        }
        return {
            "body": body,
            "sha256": sha256(self._canonical(body).encode()).hexdigest(),
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "EvidenceGraph":
        if set(snapshot) != {"body", "sha256"}:
            raise ValueError("snapshot envelope invalid")
        body = snapshot["body"]
        if not isinstance(body, dict) or body.get("schema") != cls.snapshot_schema:
            raise ValueError("snapshot schema invalid")
        if body.get("authority") != "advisory_only":
            raise ValueError("snapshot authority invalid")
        actual = sha256(cls._canonical(body).encode()).hexdigest()
        if actual != snapshot.get("sha256"):
            raise ValueError("snapshot integrity mismatch")
        generation = int(body.get("task_state_generation", 0))
        if generation < 0:
            raise ValueError("snapshot generation invalid")

        graph = cls(
            task_id=str(body.get("task_id") or ""),
            run_id=str(body.get("run_id") or ""),
            task_sha256=str(body.get("task_sha256") or ""),
            generation=generation,
        )
        for row in body.get("requirements") or []:
            graph.add_requirement(Requirement(**row))
        for row in body.get("hypotheses") or []:
            graph.add_hypothesis(Hypothesis(**row))
        for row in body.get("observations") or []:
            graph.add_observation(Observation(**row))
        for row in body.get("provenance_edges") or []:
            graph.add_provenance_edge(ProvenanceEdge(**row))
        for row in body.get("relations") or []:
            graph.add_relation(Relation(**row))

        invalid_relations: set[tuple[str, str, str, str, str]] = set()
        for row in body.get("invalidated_relation_keys") or []:
            if not isinstance(row, list) or len(row) != 5:
                raise ValueError("invalid relation key")
            key = tuple(str(value) for value in row)
            if key not in graph.relations:
                raise ValueError("invalidated relation missing from graph")
            invalid_relations.add(key)
        graph.invalidated_relations = invalid_relations

        invalid_provenance: set[tuple[str, str, str]] = set()
        for row in body.get("invalidated_provenance_keys") or []:
            if not isinstance(row, list) or len(row) != 3:
                raise ValueError("invalid provenance key")
            key = tuple(str(value) for value in row)
            if key not in graph.provenance_edges:
                raise ValueError("invalidated provenance missing from graph")
            invalid_provenance.add(key)
        graph.invalidated_provenance = invalid_provenance

        events = body.get("events") or []
        if not isinstance(events, list) or any(not isinstance(item, dict) for item in events):
            raise ValueError("snapshot events invalid")
        graph.events = list(events)
        return graph
