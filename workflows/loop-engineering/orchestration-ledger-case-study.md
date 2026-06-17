# Orchestration Ledger — Case Study

A sanitized walk-through of how a 32-worker bounded build was orchestrated
using the governed multi-agent model. Worker thread IDs, model version strings,
and internal script names have been replaced with generic terms.

---

## Context

This ledger documents the build of a new harness runtime line (Aether-2) from
scratch through its first integration checkpoint (G1). The objective was to
have all relevant tests green and a genericity check passing before any G2 work
could begin.

The build was intentionally orchestrated using many small, disjoint worker
tasks rather than one large monolithic implementation pass.

---

## Objective

Build a new harness line through G1:

- all `tests/test_<harness>_*.py` green
- genericity check green
- no G2 work before G1 is green

---

## Scope

**In scope:** new harness module files, corresponding tests, genericity tool,
and VM lifecycle scripts. Existing-file edits limited to explicitly named
governance docs.

**Out of scope:** historical MLPCP/kernel/blocks files (harvest-only), successor
modules, tracking archives outside the approved collaboration surfaces.

---

## Binding Edit Policy

- Primary implementation lives in the new harness module directory.
- Old files are harvest-only: inspect and copy patterns; do not edit.
- Reject any worker patch that edits a harvest-only file without a spec-backed reason.
- Prefer many compact worker tasks over broad lane-sized tasks.
- Worker write scopes must be disjoint.
- All work stays in the main checkout on `master`; no worktrees, no branch-based execution.

---

## Worker Policy

Every worker packet must include:

- exact files allowed to create or edit
- exact harvest-only files allowed to inspect
- explicit do-not-touch list
- exact acceptance criteria
- exact tests and checks
- interface sketch from the spec
- anti-contamination constraints
- required handoff format
- explicit instruction not to redesign architecture

Workers must also:

- use Goal structure when available, or explicitly report the fallback
- use code-review skill when available for closeout, or explicitly report the fallback
- avoid reverting other workers' edits
- implement the full file-level spec contract for their slice, not a knowingly thin placeholder
- receive a **contract-complete packet**: manifest row, interfaces, behaviors, cross-cutting constraints, acceptance checklist, and tests for the full component contract
- mark the handoff `partial` with exact missing items if a required behavior cannot be completed inside the slice

---

## Setup Checks (pre-execution discipline)

| Check | Status | Evidence |
|---|---|---|
| Build spec reviewed | complete | Sections on module contracts, interfaces, and acceptance reviewed |
| Repo structure inspected | complete | All relevant directories present |
| Harvest sources identified | complete | See decision log D-003 |
| Code-review skill availability checked | complete | Skill present in environment |
| Worker delegation mechanism checked | complete | Thread-based delegation in use |
| Hour-0 contract freeze recorded | complete | `workflows/loop-engineering/hour-zero-contracts-example.md` |
| Predictions file checked | complete | Predictions file exists |
| Main checkout confirmed | complete | On master branch |

---

## Task Status Table (representative subset)

The full build dispatched 32 workers (W-001 through W-032). This table shows
the orchestration pattern — including supersession, re-dispatch, and escape-hatch
use — rather than every individual row.

| ID | Role | Status | Write Scope (generic) | Loop Stage Evidenced |
|---|---|---|---|---|
| O-001 | orchestrator | complete | ledger and setup artifacts | orchestrate: contract freeze |
| O-002 | orchestrator | complete | hour-0 contracts | orchestrate: interface freeze |
| W-001 | worker | accepted (after parent review) | prompts module + tests | implement: thin slice → contract review |
| W-002 | worker | superseded by W-014 | envelope module + tests | implement: spec-incomplete → re-dispatch |
| W-003 | worker | superseded by W-017 | tools module + tests | implement: prompt-debt → re-dispatch |
| W-004 | worker | accepted (G1 gate pending) | genericity check + tests | implement → validate: CI gate |
| W-005 | worker | superseded by W-016 | metrics module + tests | implement: missing §4.11 contract |
| W-006 | worker | blocked; re-dispatched as W-009 | receipts module + tests | escape hatch: budget limit before any code written |
| W-007 | worker | superseded by W-013 | orientation module + tests | implement: spec-incomplete |
| W-008 | worker | partial; spec-incomplete | delta module + tests | implement: registry slots honest placeholders |
| W-009 | worker | superseded by W-015 | receipts module + tests | implement: robustness gap |
| W-013 | worker | accepted (integration-ready) | orientation module + tests | implement: full §7 contract |
| W-014 | worker | accepted (integration-ready) | envelope module + tests | implement: full contract |
| W-015 | worker | accepted (integration-ready) | receipts module + tests | implement: serializer robustness |
| W-016 | worker | accepted (integration-ready) | metrics module + tests | implement: labeling gap closed |
| W-017 | worker | accepted (integration-ready) | tools module + tests | implement: 10-tool surface complete |
| W-018 | worker | accepted after orchestrator repair | executor module + tests | implement: budget exhausted → orchestrator completed validation |
| W-019 | worker | accepted (integration-ready) | mirror module + tests | implement: contract-complete |
| W-031 | worker | active (registry final contract) | jobs module | implement: re-dispatched after stall |
| W-032 | worker | active (registry final contract) | sessions module | implement: re-dispatched after stall |

---

## Integration Notes

- Workers W-002, W-007, W-008, and W-009 were reclassified from "accepted" to
  "partial/spec-incomplete" when a tightened full-spec acceptance rule was applied.
  This is orchestration prompt debt, not worker-quality failure — the original packets
  omitted parts of the component contract.
- **Root-cause correction adopted (D-012):** when a slice is spec-incomplete because
  the worker packet omitted part of the component contract, track that as
  orchestration prompt debt. Dispatch an immediate follow-up worker for the
  missing behavior instead of letting the thin slice stand.
- The `codex-review` helper showed a shared environment/config blocker on
  worker follow-up attempts. Centralized as one shared blocker (D-014) instead of
  having every worker retry the same failing invocation.
- W-018 executor exhausted its own token budget before validation; the orchestrator
  completed local verification rather than redispatching.
- W-031 and W-032 initially stalled because the packet was double-wrapped; plain
  follow-up prompts corrected both threads (D-017).
- Current board at end of ledger: all existing surfaces green.

---

## Escape Hatches

If a worker mechanism fails:

- record the exact tool failure
- keep the write scope reserved
- re-dispatch using the next available agent/thread mechanism
- do not silently collapse into single-agent execution unless all delegation paths are
  unavailable and documented

---

## Orchestration Patterns Evidenced

This ledger surfaces the following patterns for study:

1. **Contract-complete packets:** each worker received the full manifest row, interfaces,
   behaviors, constraints, and acceptance checklist — not just a vague task description.

2. **Prompt-debt tracking:** when a worker produced incomplete output, the root cause was
   analyzed. If the packet was under-specified, that was recorded as orchestration prompt
   debt and the corrective action was a better-specified re-dispatch.

3. **Escape-hatch discipline:** when a worker hit a budget limit (W-006) or a tool
   blocker (review helper), the failure was recorded, the write scope was reserved, and
   a re-dispatch followed immediately.

4. **Acceptance tightening mid-build:** the acceptance rule tightened partway through
   (D-011), retrospectively reclassifying several accepted workers as partial. This is
   the correct behavior — the standard should be the full spec contract, not just a
   passing test suite.

5. **Centralized shared blockers:** instead of having each worker retry the same broken
   tool, the blocker was centralized and a dedicated diagnosis lane was assigned.

---

*Private content removed: worker thread IDs, exact model version strings, internal
script names, VM lifecycle details, and Azure-specific references. The orchestration
pattern, decision taxonomy, and escape-hatch discipline are the public artifacts.*
