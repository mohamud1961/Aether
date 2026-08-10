"""Minimal model-facing Verifier protocol for PERSISTENT V0.

PERSISTENT keeps task strategy and falsification method with the independent model.
Provider schemas and deterministic kernel gates own serialization, budgets,
provenance, freshness, and completion admission, so those mechanics do not
need to be re-taught as a large prompt manual on every Verifier call.
"""
from __future__ import annotations

from typing import Any


PERSISTENT_VERIFIER_PROTOCOL_PROFILE = {
    "profile": "persistent_v0_thin_verifier_v1",
    "task_authority": "authoritative_task_prompt + verifier_packet.task_contract",
    "turn_authority": "provider verifier_turn schema",
    "mechanical_authority": "kernel parser, inspection registry, budgets, and completion gate",
}


PERSISTENT_VERIFIER_SEMANTIC_GUIDE = """You can inspect current state before judging the task.

Treat every visible task_contract clause as an independently falsifiable obligation. Before returning completed, seek current evidence that could have disproved each clause. Evidence for one clause does not automatically discharge an unrelated clause.

Choose the smallest useful inspection yourself. Before fresh independent execution, directly inspect every authoritative input it consumes, then execute in the disposable verifier environment using only those inspection:* refs. Never use Solver submission receipt:* handles as derived basis/input refs.

Treat Solver-authored checks, summaries, metadata, labels, and agreement among Solver-produced outputs as claims to audit, not semantic proof. If a task-provided generator, reference implementation, validator, or transformation defines a claimed output, inspect that authority and independently apply its rule; compare the expected result with current state. Do not substitute a Solver recomputation or self-consistent proxy.

verifier_phase_budget is a hard activation budget. Count prior derived-execution batches; never request another after max_derived_execution_batches is exhausted. Then decide from existing evidence or return uncertain_missing_evidence/blocked_by_tooling.

Do not infer unobserved cases. If current evidence is insufficient, inspect or return uncertain_missing_evidence. If current state is wrong, return needs_repair. Return completed only when current independent evidence supports every visible clause.

The provider and kernel enforce turn shape, inspection budgets, provenance, freshness, and completion-record structure. Do not provide hidden reasoning. Emit only the current schema-valid Verifier turn."""


def persistent_verifier_identity_prompt(identity_prompt: str) -> str:
    """Compose PERSISTENT semantic guidance with the compact independent identity."""
    identity = str(identity_prompt or "").strip()
    if not identity:
        raise ValueError("PERSISTENT verifier identity prompt must be non-empty")
    return PERSISTENT_VERIFIER_SEMANTIC_GUIDE.strip() + "\n\n" + identity


def verifier_runtime_contract_for(compiled: Any, generic_contract: Any) -> Any:
    """Return a thin PERSISTENT marker while leaving non-PERSISTENT runtime contracts intact."""
    if str(getattr(compiled, "solver_turn_protocol", "") or "") == "persistent_v0":
        return dict(PERSISTENT_VERIFIER_PROTOCOL_PROFILE)
    return generic_contract
