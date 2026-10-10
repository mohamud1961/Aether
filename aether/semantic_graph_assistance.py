"""G-JUDGE-0 persistent provenance-graph assistance.

Research-only advisory representation. It consumes the same Solver-authored
completion conditions and execution receipts as SemanticAssistance. It never
executes actions, rewrites conditions, or gates completion.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Any, Callable, Mapping

from .completion_record import latest_completion_record, latest_completion_record_receipt
from .evidence_graph import EvidenceGraph, Hypothesis, Observation, ProvenanceEdge, Relation, Requirement
from .ledger import ExecutionLedger, Receipt
from .persistent_context import evidence_alias
from .run_cancellation import RunCancellationRequested
from .run_deadline import KernelRunTimeout
from .semantic_assistance import SemanticAssistance, canonical, incomplete


class GraphSemanticAssistance:
    """Persistent graph view with optional bounded JUDGE relation labeling."""

    # Graph representation may retain factual non-mutating receipts that are
    # already part of Aether's ordinary evidence surface. JUDGE scheduling stays
    # on the incumbent SemanticAssistance set so D-vs-C does not silently gain
    # a broader semantic-call policy.
    GRAPH_OBSERVATIONS = frozenset({
        "read_file", "read_file_page", "command_result", "run_command",
        "artifact_inspection", "inspection_record", "check_result",
        "schema_validation", "job_probe", "service_probe", "read_output",
        "grep_output", "inspect_artifact",
    })
    SEMANTIC_OBSERVATIONS = SemanticAssistance.OBSERVATIONS

    def __init__(
        self,
        evaluate: Callable[[dict], dict] | None = None,
        *,
        model: str = "",
        heads: tuple[str, ...] = ("ranking",),
        max_calls: int = 24,
        calls_per_turn: int = 4,
        max_request_bytes: int = 16000,
        max_render_bytes: int = 8192,
    ) -> None:
        if evaluate is not None:
            if not model:
                raise ValueError("JUDGE graph assistance requires exact model identity")
            if not heads or any(head not in SemanticAssistance.HEADS for head in heads):
                raise ValueError("unknown or empty assistance heads")
        if min(max_calls, calls_per_turn, max_request_bytes, max_render_bytes) <= 0:
            raise ValueError("positive limits required")
        self.evaluate = evaluate
        self.model = model
        self.heads = tuple(dict.fromkeys(heads)) if evaluate is not None else ()
        self.max_calls = int(max_calls)
        self.calls_per_turn = int(calls_per_turn)
        self.max_request_bytes = int(max_request_bytes)
        self.max_render_bytes = int(max_render_bytes)
        self.calls = 0
        self.events: list[dict[str, Any]] = []
        self._cache: dict[str, dict[str, Any]] = {}
        self._failed_requests: set[str] = set()
        self._scope: tuple[str, str, str] | None = None
        self._graph: EvidenceGraph | None = None

    @property
    def graph(self) -> EvidenceGraph | None:
        return self._graph

    def bind_run_cancellation(self, event: Any) -> None:
        if self.evaluate is None:
            return
        bind = getattr(self.evaluate, "bind_run_cancellation", None)
        if callable(bind):
            bind(event)

    @staticmethod
    def _origin_id(receipt: Receipt) -> str:
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        for key in (
            "origin_id",
            "process_generation",
            "job_id",
            "process_id",
            "check_id",
            "action_id",
        ):
            value = str(payload.get(key) or "").strip()
            if value:
                return f"{key}:{value}"
        path = str(payload.get("path") or payload.get("resolved_path") or "").strip()
        if path:
            # Executor receipts already expose the canonical task-visible path.
            # Keep rereads of the same file correlated without conflating
            # different files merely because they share the read_file kind.
            while path.startswith("/app/"):
                path = path[5:]
            while path.startswith("./"):
                path = path[2:]
            return "path:" + path
        file_handle = str(payload.get("file_handle") or "").strip()
        if file_handle:
            return "file_handle:" + file_handle
        command = str(payload.get("command") or "").strip()
        if command:
            return "command:" + sha256(command.encode()).hexdigest()[:20]
        return f"unknown:{receipt.kind}"

    @staticmethod
    def _payload_sha256(receipt: Receipt) -> str:
        return sha256(canonical(dict(receipt.payload or {})).encode()).hexdigest()

    def _ensure_graph(
        self,
        *,
        task_text: str,
        ledger: ExecutionLedger,
        runtime_identity: Mapping[str, Any],
    ) -> EvidenceGraph:
        task_hash = sha256(task_text.encode()).hexdigest()
        task_id = str(runtime_identity.get("task_id") or "").strip()
        run_id = str(runtime_identity.get("run_id") or "").strip()
        if not task_id or not run_id:
            raise ValueError("graph semantic assistance requires task/run identity")
        scope = (task_id, run_id, task_hash)
        if self._scope is not None and self._scope != scope:
            raise ValueError("graph semantic assistance instance cannot cross runs")
        self._scope = scope
        generation = int(ledger.task_state_generation())
        if self._graph is None:
            self._graph = EvidenceGraph(
                task_id=task_id,
                run_id=run_id,
                task_sha256=task_hash,
                generation=generation,
            )
            self._graph.add_requirement(
                Requirement(
                    requirement_id="task:raw",
                    text="Authoritative raw task contract",
                    task_sha256=task_hash,
                    source_span=f"0:{len(task_text.encode())}",
                )
            )
        elif generation < self._graph.generation:
            raise ValueError("ledger task generation moved backwards")
        elif generation > self._graph.generation:
            self._graph.mutate(generation)
        return self._graph

    def _sync_observations(self, graph: EvidenceGraph, ledger: ExecutionLedger) -> None:
        for receipt in ledger.all_receipts():
            if (
                receipt.kind not in self.GRAPH_OBSERVATIONS
                or not receipt.success
                or receipt.state_change
            ):
                continue
            if not ledger.receipt_payload_is_intact(receipt):
                continue
            generation = ledger.receipt_task_state_generation(receipt.receipt_id)
            observation = Observation(
                receipt_id=receipt.receipt_id,
                task_id=graph.task_id,
                run_id=graph.run_id,
                task_state_generation=generation,
                origin_id=self._origin_id(receipt),
                kind=receipt.kind,
                summary=str(receipt.summary or "")[:1000],
                step=int(receipt.step),
                process_generation=str((receipt.payload or {}).get("process_generation") or ""),
                artifact_sha256=str((receipt.payload or {}).get("content_sha256") or ""),
                payload_sha256=self._payload_sha256(receipt),
            )
            graph.add_observation(observation)

    @staticmethod
    def _condition_id(revision: int, condition: Mapping[str, Any]) -> str:
        return f"condition:{revision}:{str(condition.get('id') or '').strip()}"

    def _sync_hypotheses_and_provenance(
        self,
        graph: EvidenceGraph,
        ledger: ExecutionLedger,
        record: Mapping[str, Any] | None,
    ) -> list[tuple[str, Mapping[str, Any]]]:
        if not record:
            return []
        revision = int(record.get("revision") or 0)
        active: list[tuple[str, Mapping[str, Any]]] = []
        active_ids: set[str] = set()
        alias_to_receipt = {
            evidence_alias(receipt.receipt_id): receipt.receipt_id
            for receipt in ledger.all_receipts()
        }
        record_receipt = latest_completion_record_receipt(ledger)
        record_step = int(record_receipt.step) if record_receipt is not None else 0
        for condition in record.get("conditions") or []:
            if not isinstance(condition, Mapping) or condition.get("assessment") == "retired":
                continue
            cid = self._condition_id(revision, condition)
            text = str(condition.get("outcome") or condition.get("proof_needed") or "").strip()
            if not text:
                continue
            graph.add_hypothesis(
                Hypothesis(
                    hypothesis_id=cid,
                    text=text,
                    created_step=max(0, record_step),
                )
            )
            active.append((cid, condition))
            active_ids.add(cid)
            for ref in condition.get("evidence_refs") or []:
                rid = alias_to_receipt.get(str(ref))
                if rid and rid in graph.observations:
                    graph.add_provenance_edge(
                        ProvenanceEdge(
                            subject_id=cid,
                            receipt_id=rid,
                            relation="cites",
                            source="solver_completion_record",
                        )
                    )
        for hid, hypothesis in list(graph.hypotheses.items()):
            if hypothesis.status == "active" and hid not in active_ids:
                graph.retire_hypothesis(hid)
        return active

    def _request(
        self,
        *,
        graph: EvidenceGraph,
        condition_id: str,
        condition: Mapping[str, Any],
        receipt: Receipt,
        head: str,
        record_revision: int,
    ) -> dict[str, Any]:
        choices = SemanticAssistance.HEADS[head]
        evidence_ref = evidence_alias(receipt.receipt_id)
        solver_condition_id = str(condition.get("id") or condition_id)
        if head == "ranking":
            question = (
                f"Condition {solver_condition_id!r} asks proof_needed={str(condition.get('proof_needed') or '')!r}. "
                f"Evidence receipt {receipt.receipt_id!r} (evidence_ref={evidence_ref!r}, "
                f"kind={receipt.kind!r}, generation={graph.generation}) is the only evidence referent for this question. "
                "Does that exact observed evidence materially answer the named proof_needed question? "
                "Rank relevance, not task completion. Use uncertain when the relation is not established."
            )
        else:
            question = (
                f"Condition {solver_condition_id!r} asserts outcome={str(condition.get('outcome') or '')!r}. "
                f"Evidence receipt {receipt.receipt_id!r} (evidence_ref={evidence_ref!r}, "
                f"kind={receipt.kind!r}, generation={graph.generation}) is the only evidence referent for this question. "
                "Does that exact observation support or contradict the named Solver-authored outcome assertion? "
                "A desired outcome is not a fact. Use uncertain when the relation is not established."
            )
        return {
            "model": self.model,
            "state": {
                "run_id": graph.run_id,
                "task_hash": graph.task_sha256,
                "generation": graph.generation,
                "record_revision": record_revision,
                "question_policy_version": "gjudge0-explicit-referent-v1",
                "response_schema_version": "gjudge0-relation-v1",
                "condition_id": condition_id,
                "solver_condition_id": solver_condition_id,
                "evidence_ref": evidence_ref,
                "condition": dict(condition),
                "observation": asdict(receipt),
            },
            "questions": {
                head: {
                    "type": "choice",
                    "instructions": question,
                    "criteria": {choice: choice for choice in choices},
                }
            },
        }

    def _add_semantic_relations(
        self,
        *,
        graph: EvidenceGraph,
        ledger: ExecutionLedger,
        active: list[tuple[str, Mapping[str, Any]]],
        record_revision: int,
        step: int,
    ) -> None:
        if self.evaluate is None:
            return
        receipts = {receipt.receipt_id: receipt for receipt in ledger.all_receipts()}
        # G-JUDGE-0 holds semantic-call eligibility constant with the incumbent
        # flat assistance arm. The graph may retain more history mechanically,
        # but Judge must see the same first four active conditions and last four
        # current eligible receipts so D-vs-C measures representation, not a
        # broader semantic-call policy.
        eligible_receipts = [
            receipt
            for receipt in ledger.all_receipts()
            if receipt.kind in self.SEMANTIC_OBSERVATIONS
            and receipt.success
            and not receipt.state_change
            and ledger.receipt_payload_is_intact(receipt)
            and ledger.receipt_task_state_generation(receipt.receipt_id) == graph.generation
            and receipt.receipt_id in graph.observations
        ][-4:]
        current = [graph.observations[receipt.receipt_id] for receipt in reversed(eligible_receipts)]
        turn_calls = 0
        for condition_id, condition in active[:4]:
            for observation in current:
                receipt = receipts[observation.receipt_id]
                observed = asdict(receipt)
                if incomplete(observed):
                    continue
                for head in self.heads:
                    if head == "assumption" and condition.get("kind") != "derived":
                        continue
                    request = self._request(
                        graph=graph,
                        condition_id=condition_id,
                        condition=condition,
                        receipt=receipt,
                        head=head,
                        record_revision=record_revision,
                    )
                    encoded = canonical(request).encode()
                    if len(encoded) > self.max_request_bytes:
                        continue
                    digest = sha256(encoded).hexdigest()
                    if digest in self._failed_requests:
                        continue
                    answer = self._cache.get(digest)
                    cache_hit = answer is not None
                    if answer is None:
                        if self.calls >= self.max_calls or turn_calls >= self.calls_per_turn:
                            continue
                        self.calls += 1
                        turn_calls += 1
                        event = {
                            "step": step,
                            "request_sha256": digest,
                            "condition_id": condition_id,
                            "receipt_id": receipt.receipt_id,
                            "head": head,
                        }
                        try:
                            raw = self.evaluate(request)
                            answer = SemanticAssistance._answer(
                                raw,
                                head,
                                SemanticAssistance.HEADS[head],
                            )
                            self._cache[digest] = answer
                            event["status"] = "ok"
                        except (RunCancellationRequested, KernelRunTimeout):
                            raise
                        except Exception as exc:
                            self._failed_requests.add(digest)
                            event["status"] = "abstained"
                            event["error_type"] = type(exc).__name__
                            self.events.append(event)
                            continue
                        self.events.append(event)
                    graph.add_relation(
                        Relation(
                            subject_id=condition_id,
                            receipt_id=receipt.receipt_id,
                            relation=str(answer["choice"]),
                            # Cache status is execution telemetry, not relation identity.
                            source="judge",
                            head=head,
                            question_sha256=digest,
                            model_id=self.model,
                            schema_version="aether.semantic_graph_relation.v0",
                            probabilities=dict(answer["probabilities"]),
                        )
                    )

    @staticmethod
    def _relation_item(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "head": row["head"],
            "condition_id": row["subject_id"],
            "receipt_id": row["receipt_id"],
            "evidence_ref": evidence_alias(str(row["receipt_id"])),
            "freshness": row.get("freshness"),
            "relation": row["relation"],
            "probabilities": row.get("probabilities") or {},
            "source": row["source"],
            "question_sha256": row.get("question_sha256") or "",
        }

    def _render(
        self,
        graph: EvidenceGraph,
        active: list[tuple[str, Mapping[str, Any]]],
    ) -> dict[str, Any]:
        relation_rows: list[dict[str, Any]] = []
        for condition_id, _ in active:
            relation_rows.extend(graph.relation_rows(condition_id))
        relation_rows.sort(
            key=lambda row: (
                row.get("invalidated") is True,
                row.get("freshness") != "current",
                -(row.get("probabilities") or {}).get("contradicts", 0),
                -(row.get("probabilities") or {}).get("relevant", 0),
                row.get("receipt_id", ""),
            )
        )
        items = [self._relation_item(row) for row in relation_rows if not row.get("invalidated")][:8]
        observations = list(graph.observations.values())
        result: dict[str, Any] = {
            "schema": "aether.semantic_graph_advice.v0",
            "authority": "advisory_only",
            "projection": "persistent_provenance_graph_v0",
            "task_state_generation": graph.generation,
            "calls_total": self.calls,
            "graph_snapshot_sha256": graph.snapshot()["sha256"],
            "counts": {
                "requirements": len(graph.requirements),
                "hypotheses": len(graph.hypotheses),
                "observations": len(observations),
                "current_observations": sum(
                    graph.observation_freshness(item.receipt_id) == "current"
                    for item in observations
                ),
                "historical_observations": sum(
                    graph.observation_freshness(item.receipt_id) == "historical"
                    for item in observations
                ),
                "unknown_generation_observations": sum(
                    graph.observation_freshness(item.receipt_id) == "unknown_generation"
                    for item in observations
                ),
                "relations": len(graph.relations),
            },
            "graph": graph.compact_summary(max_items=8),
            "items": items,
        }
        if len(canonical(result).encode()) > self.max_render_bytes:
            result["graph"] = {
                "schema": "aether.evidence_graph_summary.v0",
                "authority": "advisory_only",
                "task_state_generation": graph.generation,
                "items": [],
                "truncated": True,
            }
            result["items"] = items[:4]
            if len(canonical(result).encode()) > self.max_render_bytes:
                result["items"] = []
        return result

    def __call__(
        self,
        *,
        task_text: str,
        ledger: ExecutionLedger,
        step: int,
        runtime_identity: Mapping[str, Any],
    ) -> dict[str, Any]:
        graph = self._ensure_graph(
            task_text=task_text,
            ledger=ledger,
            runtime_identity=runtime_identity,
        )
        self._sync_observations(graph, ledger)
        record = latest_completion_record(ledger)
        active = self._sync_hypotheses_and_provenance(graph, ledger, record)
        revision = int(record.get("revision") or 0) if record else 0
        self._add_semantic_relations(
            graph=graph,
            ledger=ledger,
            active=active,
            record_revision=revision,
            step=step,
        )
        result = self._render(graph, active)
        if not record:
            result["status"] = "no_solver_conditions"
        elif self.evaluate is None:
            result["status"] = "graph_only"
        elif result["items"]:
            result["status"] = "graph_advice"
        else:
            result["status"] = "abstained_or_no_eligible_relation"
        return result
