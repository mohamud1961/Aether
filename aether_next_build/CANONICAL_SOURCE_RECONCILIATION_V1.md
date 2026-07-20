# Canonical Source Reconciliation v1

Date: 2026-07-20
Status: integration base selected; final canonical promotion pending invariant closure

## Decision

Use `0cbefbb47fc185baebfca7ceb41101b033554a2b` as the certification
**integration base**, not as an already-certified canonical release.

Reason:

- it is a clean, reachable commit on the latest proof-contract runtime line;
- it contains the current state-only Verifier/proof-contract replay work;
- its non-V5-ported deterministic suite is reproducible locally;
- its major defects are visible and can be closed without importing a second
  runtime.

The strict Architect/Gold line ending at
`2d4a1219ff931a31d265069c62c9487b07168288` is not an ancestor of the
integration base. It is a migration source for generic invariants, not a branch
to merge wholesale. It also contains board- and source-layout-specific material
that must not silently replace the proof-contract line.

The owner checkout and VM owner root are not source authority:

- local canonical checkout was dirty when the isolated worktree was created;
- VM owner root is older at `b392f2643b80125745e01c0f7259f7f42e0435c2`.

Only exact commits and clean isolated worktrees may supply certification source.

## Reconciled development lines

| Change/invariant | Origin | Present in 0cbefbb4 | Decision | Reason/replacement |
|---|---|---:|---|---|
| State-only Verifier and proof-contract substrate | `ca34376f` through `0cbefbb4` | yes | retain/rework | Strongest current basis; repair completion, freshness, and binding defects in place. |
| Route preflight and runtime proof wiring | `54135ee7`, `fdcd477b` | yes | retain/rework | Keep generic route readiness; deepen exact target/runtime checks later. |
| Known-bad container/receipt replay | `919f51ca`, `1c935f5d`, `0cbefbb4` | yes | retain as test substrate | Must never become alternate production runtime. |
| Exact Architect Gold source import | `0064636f` | no by ancestry | migration source only | Do not replace proof-contract integration base wholesale. |
| Solver commitment fields and exactly-one-action invariant | `3666960b`, `92439d61` | partial/no | port concept, revise | Adopt one state-changing frontier or one certified read-only observation batch. |
| Unique Solver turn identities | `47ef863d` | uncertain/partial | inspect and port if absent | Generic causal/provenance invariant. |
| Solver expectation contradiction signal | `591fe2f1`, `d4236a7d` | partial | rework | Keep objective contradiction receipts; no task-semantic controller. |
| Compiled Verifier routes | `5d545cfd`, `f6e7a6c8` | yes via newer proof line | retain current implementation | Avoid duplicate route system. |
| Cross-target finding rejection | `ee5290f5` | uncertain | port generic invariant | Finding must bind exact clause/target/generation. |
| Verifier retry within one submission | `1326922e` | partially present | reconcile with bounded owner routing | Retry only protocol/tool-owned failures, never hide Solver-state findings. |
| Falsification requirement | `69c83e95` | yes | retain/strengthen | Bind to registered inspection rather than model-restated route. |
| Startup failures and recovery budget | `4a06c394` | partial | retain generic ownership, rework | No benchmark/task-specific recovery logic. |
| Explicit named service requirements | `c0c5f067` | partial | rework | Architect-authored obligation plus generation-bound process/endpoint proof. |
| Service obligations from managed probes | `2d4a1219` | partial | rework | Must bind real process generation, not only name/port. |
| Provider raw-item canonicalisation | strict branch provider implementation | no | port and harden | Incomplete status must execute zero actions; strict branch still returned partial text and is not sufficient unchanged. |
| Provider cancellation/late generation | strict branch provider implementation | partial/no | port and harden | Late provider/Verifier work must be quarantined from active ledger/state. |
| Architect task-clause completeness machinery | strict branch | no/partial | do not copy deterministic semantic extraction | Preserve model-led clause ownership; compiler validates anchors and mechanics only. |
| Observation batch primitive | strict branch `observe_batch` | no | redesign and port | Batch only certified read-only inspections against one frozen generation. |
| Model-facing task capability classifier | current proof line `task_capability.py` | yes | remove from model-facing production path | Violates semantic-ownership constitution. Environment should expose facts only. |
| Legacy Architect tool policy | current Workbench schema | yes | remove from canonical schema | Core tool surface is kernel-owned. |
| Model-authored reconfiguration in production | multiple lines | suspended | keep disabled | Restore only after trusted-kernel certification. |

## Integration rule

Generic invariants from the strict branch are manually reimplemented on the
proof-contract integration base with new production-path tests. No commit is
accepted solely because it passed Gold.

## Canonical promotion condition

The integration branch becomes canonical certification source only when:

1. scorecard v1 and constitution are committed;
2. every imported generic invariant has an explicit keep/rework/remove decision;
3. completion bypass is closed;
4. source/test manifests are exact and clean;
5. local and VM commands are recorded with explained skips;
6. no unresolved parallel production path can execute task state or declare
   completion.

Until then the status remains NOT READY.
