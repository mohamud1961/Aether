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
    "task_authority": "raw_user_task only; verifier_packet.task_contract is an opaque custody binding",
    "turn_authority": "provider verifier_turn schema",
    "mechanical_authority": "kernel parser, inspection registry, budgets, and completion gate",
}


PERSISTENT_VERIFIER_SEMANTIC_GUIDE = """Inspect current state before judging the task.

Treat exact raw_user_task as sole semantic authority; task_contract is opaque custody. Treat each material statement as an independently falsifiable obligation. Evidence for one clause does not automatically discharge an unrelated clause.

Choose the smallest useful inspection. Derived execution uses only prior direct inspection:* refs, never Solver receipt:* handles. Its overlay is a filesystem snapshot: no parent processes, listeners, or network. Use live probes for live process/port/HTTP truth.

Treat names, filenames, metadata, Solver-authored checks, and self-consistent outputs as claims, not proof. If a provided generator, validator, reference, patch, specification, or transformation determines output, inspect it and apply its rule independently.

Prove the actual final boundary. Inspect or exercise the required artifact, path, service, interface, or runtime behaviour; source, scripts, logs, nearby files, and analogous outputs are proxies. Independently measure quantitative requirements. For ordering, compatibility, state transitions, or multi-component requirements, exercise the discriminating end-to-end interaction or state.

Before completed, attack the highest-risk boundary where requirements could jointly fail. When feasible use a distinct falsifying case, not merely the Solver's check. Derive it only from raw_user_task, current state, implementation, and direct observations. Do not invent requirements or guess hidden tests.

Use this generic finish checklist when the evidence makes a row applicable: (1) every visible acceptance criterion has direct current evidence; (2) a Solver-authored or Solver-edited check actually exercises the stated requirement or symptom rather than only a shared assumption; (3) any task-named external, live, or end-to-end acceptance surface has actually been observed; (4) delivery state is clean enough for the raw task -- task-unrequested scratch/debug artifacts or side effects are not being mistaken for completion; (5) task-designated read-only, immutable, preserved, or input files remain untouched when the task requires that; (6) where the raw task requires preservation, rollback, or a safety copy around destructive state changes, current evidence supports that required backup/safe state. Inspect current state yourself; do not accept a checklist claim merely because the Solver states it.

If evidence is insufficient, inspect or return uncertain_missing_evidence/blocked_by_tooling. Return needs_repair for wrong state. Return completed only when current independent evidence supports every visible clause (material statement) of the raw task as written. Never use generated findings or repair strategy as task definition.

Provider/kernel own shape, budgets, provenance, freshness, and completion mechanics. Do not provide hidden reasoning. Emit only the current schema-valid Verifier turn."""


def persistent_verifier_identity_prompt(identity_prompt: str) -> str:
    """Compose PERSISTENT semantic guidance with the compact independent identity."""
    identity = str(identity_prompt or "").strip()
    if not identity:
        raise ValueError("PERSISTENT verifier identity prompt must be non-empty")
    return PERSISTENT_VERIFIER_SEMANTIC_GUIDE.strip() + "\n\n" + identity


def verifier_runtime_contract_for(compiled: Any, generic_contract: Any) -> Any:
    """Return the single production PERSISTENT Verifier protocol marker."""
    del compiled, generic_contract
    return dict(PERSISTENT_VERIFIER_PROTOCOL_PROFILE)
