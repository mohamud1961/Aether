# Orchestration Decision Log — Example

A sanitized example of the decision-log discipline used during the Aether-2
build. Worker thread IDs, model version strings, and internal references have
been replaced with generic terms.

The decision-log pattern: every major orchestration decision is recorded as a
named entry (D-001, D-002, …) with date, decision, rationale, and consequence.
This creates a traceable record of why the build evolved the way it did.

---

## D-001 — Orchestrator works directly, not Goal-gated

- **Decision:** The orchestrator will work directly from the build spec and thread
  instructions. Formal Goal usage is optional, not a prerequisite.
- **Why:** Principal correction explicitly removed Goal setup as a gate and
  prioritized forward execution.
- **Consequence:** Governance substance stays in the orchestration artifacts
  instead of a formal Goal object.

---

## D-002 — New-files-first implementation policy

- **Decision:** The new harness line is implemented primarily in the new harness
  directory plus the new tests/tools/scripts named in the spec. Existing-file edits
  are limited to a small named set.
- **Why:** Principal correction made the new harness line the primary implementation
  surface and restricted edits to reduce drift into historical code.
- **Consequence:** Old files are harvest-only unless the build spec explicitly names
  an exception.

---

## D-003 — Harvest sources accepted as read-only inputs

- **Decision:** The orchestrator and workers may inspect, copy patterns from, or
  adapt logic from a named set of old files without editing them.
- **Why:** The spec names these as the intended harvest surfaces.

---

## D-004 — Mandatory worker delegation

- **Decision:** Worker delegation is mandatory. The orchestrator must dispatch
  bounded workers and keep their scopes narrow, guided, and disjoint.
- **Why:** Principal correction explicitly made worker delegation mandatory and
  preferred many compact tasks over lane-sized tasks.
- **Consequence:** Any delegation mechanism failure must be recorded and followed
  immediately by a fallback delegation attempt.

---

## D-005 — Hour-0 contracts frozen before wider lane work

- **Decision:** The observation envelope schema, the exact tool schemas, and the
  loop ↔ bridge interface are the Hour-0 contracts. Workers build against
  `hour-zero-contracts-example.md`.
- **Why:** The build spec marks Hour-0 as blocking and a prerequisite for all
  later lanes.

---

## D-006 — Worker mechanism is same-checkout threads

- **Decision:** Build workers run as pinned threads, not subagents. They stay in
  the same checkout on `master`, with no worktrees and no branch-based execution.
- **Why:** Principal correction explicitly required thread-based workers and
  clarified that all work must stay in the main checkout with no forking/worktrees.
- **Consequence:** Thread coordination may be used only in same-directory mode;
  no git worktree or branch isolation is allowed.

---

## D-008 — Initial subagent dispatch was superseded and shut down

- **Decision:** The first worker dispatch used a subagent mechanism, but that
  approach was superseded by principal policy. All five subagents were shut down
  and replaced with pinned worker threads.
- **Why:** Principal required thread-based workers only.

---

## D-009 — Worker threads should use Goal structure plus code review

- **Decision:** Worker threads should explicitly use Goal structure and the code
  review skill when available, rather than only reporting that those tools exist.
- **Why:** Principal preference tightened the worker workflow after the first batch
  of narrow slices had already started.
- **Consequence:** Early worker slices that only self-reviewed may need follow-up
  repair or integration-side review notes.

---

## D-010 — Runtime surfaces need contract-level review, not only slice-local tests

- **Decision:** Review executor-facing surfaces as live runtime contracts, not only
  as narrow worker slices.
- **Why:** The initial prompts slice was test-green but too thin for the real
  executor role until a parent/runtime review strengthened the system prompt and
  ensured doctrine lines were embedded directly inside it.
- **Consequence:** Future worker accept/reject decisions should check whether a
  green slice is still too weak for the actual runtime contract.

---

## D-011 — Full-spec acceptance, not thin placeholders

- **Decision:** No slice may be marked accepted or complete if its implementation
  is knowingly a placeholder for a spec-required behavior.
- **Why:** Parent audit clarified that the acceptance target is the full file
  contract in the build spec, not a thinner substitute that only satisfies a
  narrow smoke or unit test.
- **Consequence:**
  - Mark such slices as `partial`, `functionally green but spec-incomplete`, or equivalent.
  - Record the exact missing spec requirements in the orchestration ledger.
  - Dispatch an immediate follow-up worker for the missing behavior.

---

## D-012 — Root cause was under-specified worker packets

- **Decision:** Treat spec-incomplete worker output primarily as orchestration
  prompt debt when the worker packet itself was not contract-complete for the
  assigned component.
- **Why:** Principal correction clarified that the main failure mode was not worker
  weakness but under-specified tasks that omitted parts of the component contract.
- **Consequence:**
  - Every worker task must be contract-complete for its assigned component.
  - Worker packets must include the exact manifest row, required public interfaces,
    required behaviors, cross-cutting constraints, and the full acceptance checklist
    for that component.
  - If a worker output is incomplete because the prompt omitted part of the contract,
    reject or return it as orchestration prompt debt, fix the packet, and re-dispatch.

---

## D-013 — Return to orchestrator-heavy cadence

- **Decision:** Direct orchestrator coding is now limited to interface freezes, tiny
  integration repairs, grouped verification, and final wiring that cannot be safely
  isolated.
- **Why:** Parent review confirmed that progress was real but the orchestrator had
  drifted too far into primary implementation.
- **Consequence:** Complete components and adversarial contract reviews should be
  delegated to fresh same-directory threads wherever write scopes are disjoint.

---

## D-014 — Centralize the broken review-helper blocker

- **Decision:** Stop asking every worker to retry the known-broken review helper.
  Treat the config parse failure as one shared blocker until a dedicated diagnosis
  lane resolves it or establishes the supported alternate gate.
- **Why:** Repeating the same failing helper invocation burns worker budget without
  increasing assurance.
- **Consequence:** Workers use the manual review checklist by default; a dedicated
  review-gate diagnosis thread owns the fix.

---

## D-016 — Route-level behavior must be proven, not assumed

- **Decision:** Acceptance of a model-client module requires an explicit test that
  the route factory enables the relevant behavior (pacing, retry, fail-fast) when
  the route requests it.
- **Why:** Wrapper-only monkeypatches are not sufficient evidence that the
  manifest row's behavior path is actually exercised.
- **Consequence:** Prove behavior wiring through a route-level path; treat transient
  retry and non-transient fail-fast as separate contract checks.

---

## D-017 — Replacement threads get plain follow-up prompts

- **Decision:** When replacing a stalled worker by same-directory fork, send the
  actionable task as a plain prompt to the child thread rather than nesting an
  extra escaped delegation wrapper inside the message body.
- **Why:** Workers stalled because the packet was double-wrapped and reached the
  child as escaped text instead of executable instructions.
- **Consequence:** Replacement worker threads must receive plain, direct task prompts.
  If a thread only records setup text and does not start implementation, correct
  it in-thread immediately before creating yet another replacement.

---

## Pattern Summary

These decisions follow a recognizable pattern for how orchestration evolves:

1. **Delegation mode clarified early** (D-001, D-006, D-008): which worker mechanism
   is authoritative, resolved at the start.

2. **Interface contracts frozen before work** (D-005): prevents integration drift.

3. **Acceptance standard tightened mid-build** (D-010, D-011): accepting thin
   slices as complete creates rework. The correct standard is the full component
   contract.

4. **Root cause attributed correctly** (D-012): spec-incomplete worker output is an
   orchestration failure, not a worker failure, when the packet was under-specified.

5. **Shared blockers centralized** (D-014): prevents repeated failed tool retries
   across workers.

6. **Communication protocol corrected** (D-017): double-wrapped packets stall
   workers; plain prompts fix it.

---

*Private content removed: model version strings, thread IDs, config error messages,
Azure/VM references, internal script names. The decision taxonomy and orchestration
patterns are public artifacts.*
