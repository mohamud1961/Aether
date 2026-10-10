"""Optional evidence advice for the lean Solver; never changes task authority.

Inputs are existing model-authored completion conditions and exact execution
receipts. No summaries, benchmark labels, future observations or private graders
are used to manufacture semantic questions. Mandatory context is untouched.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import math
from typing import Any, Callable, Mapping

from .completion_record import latest_completion_record
from .ledger import ExecutionLedger
from .persistent_context import evidence_alias
from .run_cancellation import RunCancellationRequested
from .run_deadline import KernelRunTimeout


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def incomplete(value: Any) -> bool:
    if isinstance(value, Mapping):
        if any(value.get(k) is True for k in ("truncated", "is_truncated", "output_truncated")):
            return True
        if any(value.get(k) is False for k in ("complete", "content_complete", "representation_complete")):
            return True
        return any(incomplete(v) for v in value.values())
    return isinstance(value, (list, tuple)) and any(incomplete(v) for v in value)


class SemanticAssistance:
    """A run-local, bounded Judge relation client with an injected transport.

    The callable transport receives the exact request and must own paid-call
    authorization, timeouts and budget enforcement. Tests can inject a labelled
    fake transport; that only qualifies the interface, never Judge efficacy.
    """

    HEADS = {
        "ranking": ("relevant", "irrelevant", "uncertain"),
        "assumption": ("supports", "contradicts", "irrelevant", "uncertain"),
    }
    OBSERVATIONS = frozenset({"read_file", "read_file_page", "command_result", "run_command", "artifact_inspection"})

    def __init__(self, evaluate: Callable[[dict], dict], *, model: str,
                 heads: tuple[str, ...] = ("ranking",), max_calls: int = 24,
                 calls_per_turn: int = 4, max_request_bytes: int = 16000):
        if not heads or any(h not in self.HEADS for h in heads):
            raise ValueError("unknown or empty assistance heads")
        if min(max_calls, calls_per_turn, max_request_bytes) <= 0 or not model:
            raise ValueError("positive limits and exact model identity required")
        self.evaluate = evaluate
        self.model = model
        self.heads = tuple(dict.fromkeys(heads))
        self.max_calls = max_calls
        self.calls_per_turn = calls_per_turn
        self.max_request_bytes = max_request_bytes
        self.calls = 0
        self.events: list[dict] = []
        self._cache: dict[str, dict] = {}
        self._failed_requests: set[str] = set()
        self._scope: tuple[str, str] | None = None

    def bind_run_cancellation(self, event):
        bind = getattr(self.evaluate, "bind_run_cancellation", None)
        if callable(bind):
            bind(event)

    def __call__(self, *, task_text: str, ledger: ExecutionLedger, step: int,
                 runtime_identity: Mapping[str, Any]) -> dict:
        task_hash = sha256(task_text.encode()).hexdigest()
        scope = (str(runtime_identity.get("run_id", "")), task_hash)
        if not scope[0]:
            raise ValueError("semantic assistance requires a run identity")
        if self._scope is not None and self._scope != scope:
            raise ValueError("semantic assistance instance cannot cross runs")
        self._scope = scope
        record = latest_completion_record(ledger)
        result: dict = {"schema": "aether.semantic_advice.v1", "authority": "advisory_only",
                       "context_pruned": False,
                       "projection": "relation_only_provenance_v1",
                       "items": [], "calls_total": self.calls}
        if not record:
            result["status"] = "no_solver_conditions"
            return result
        generation = ledger.task_state_generation()
        observations = [r for r in ledger.all_receipts()
                        if r.kind in self.OBSERVATIONS and r.success and not r.state_change
                        and ledger.receipt_payload_is_intact(r)
                        and ledger.receipt_task_state_generation(r.receipt_id) == generation]
        # Bound work to recent eligible receipts; older evidence remains available
        # through ordinary history tools and is never deleted by this module.
        observations = observations[-4:]
        conditions = [c for c in record["conditions"] if c["assessment"] != "retired"][:4]
        turn_calls = 0
        for condition in conditions:
            for receipt in reversed(observations):
                observed = asdict(receipt)
                if incomplete(observed):
                    continue
                for head in self.heads:
                    if head == "assumption" and condition["kind"] != "derived":
                        continue
                    choices = self.HEADS[head]
                    evidence_ref = evidence_alias(receipt.receipt_id)
                    condition_id = str(condition["id"])
                    if head == "ranking":
                        question = (
                            f"Condition {condition_id!r} asks proof_needed={str(condition.get('proof_needed') or '')!r}. "
                            f"Evidence receipt {receipt.receipt_id!r} (evidence_ref={evidence_ref!r}, "
                            f"kind={receipt.kind!r}, generation={generation}) is the only evidence referent for this question. "
                            "Does that exact observed evidence materially answer the named proof_needed question? "
                            "Rank relevance, not task completion. Use uncertain when the relation is not established."
                        )
                    else:
                        question = (
                            f"Condition {condition_id!r} asserts outcome={str(condition.get('outcome') or '')!r}. "
                            f"Evidence receipt {receipt.receipt_id!r} (evidence_ref={evidence_ref!r}, "
                            f"kind={receipt.kind!r}, generation={generation}) is the only evidence referent for this question. "
                            "Does that exact observation support or contradict the named Solver-authored outcome assertion? "
                            "A desired outcome is not a fact. Use uncertain when the relation is not established."
                        )
                    request = {"model": self.model, "state": {
                        "run_id": scope[0], "task_hash": task_hash,
                        "generation": generation, "record_revision": record["revision"],
                        "question_policy_version": "gjudge0-explicit-referent-v1",
                        "response_schema_version": "gjudge0-relation-v1",
                        "condition_id": condition_id,
                        "evidence_ref": evidence_ref,
                        "condition": condition, "observation": observed,
                    }, "questions": {head: {"type": "choice", "instructions": question,
                                             "criteria": {c: c for c in choices}}}}
                    encoded = canonical(request).encode()
                    if len(encoded) > self.max_request_bytes:
                        continue  # Do not cut an excerpt and silently call it complete.
                    digest = sha256(encoded).hexdigest()
                    if digest in self._failed_requests:
                        continue  # Unchanged failed input is not authority for a paid retry.
                    answer = self._cache.get(digest)
                    cache_hit = answer is not None
                    if answer is None:
                        if self.calls >= self.max_calls or turn_calls >= self.calls_per_turn:
                            continue
                        self.calls += 1
                        turn_calls += 1
                        event = {"step": step, "request_sha256": digest, "request": request}
                        try:
                            raw = self.evaluate(request)
                            event["response"] = raw
                            answer = self._answer(raw, head, choices)
                            # Cache only a fully validated result. Error receipts
                            # can never turn into cached successful judgements.
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
                    item = {"head": head, "condition_id": condition["id"],
                            "record_revision": record["revision"], "generation": generation,
                            "receipt_id": receipt.receipt_id,
                            "evidence_ref": evidence_alias(receipt.receipt_id),
                            "observation_ref": {
                                "receipt_id": receipt.receipt_id,
                                "evidence_ref": evidence_alias(receipt.receipt_id),
                                "step": receipt.step,
                                "kind": receipt.kind,
                                "success": bool(receipt.success),
                                "state_change": bool(receipt.state_change),
                            },
                            "source_sha256": sha256(canonical(observed).encode()).hexdigest(),
                            "request_sha256": digest,
                            "cache_hit": cache_hit, **answer}
                    result["items"].append(item)
        result["items"].sort(key=lambda x: -(x["probabilities"].get("contradicts", 0)
                                               + x["probabilities"].get("relevant", 0)))
        # Advice is an additive bounded view, never a replacement for source
        # context. Prefer strongest relations; retain raw evidence in the ledger.
        bounded = []
        for item in result["items"]:
            if len(bounded) == 4:
                break
            if len(canonical(bounded + [item]).encode()) <= 4096:
                bounded.append(item)
        result["items"] = bounded
        result["calls_total"] = self.calls
        result["status"] = "advice" if result["items"] else "abstained_or_no_eligible_evidence"
        return result

    @staticmethod
    def _answer(raw: dict, head: str, choices: tuple[str, ...]) -> dict:
        row = raw["answers"][head]
        if row["choice"] not in choices:
            raise ValueError("unexpected choice")
        probabilities = row["probabilities"]
        if set(probabilities) != set(choices):
            raise ValueError("incomplete probability distribution")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities.values()):
            raise ValueError("invalid probability")
        if abs(sum(probabilities.values()) - 1) > .02:
            raise ValueError("invalid probability total")
        return {"choice": row["choice"], "probabilities": dict(probabilities)}
