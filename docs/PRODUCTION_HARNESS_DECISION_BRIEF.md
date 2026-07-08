# Which Harness Is Production? — Decision Brief

Decision status, 2026-07-03: accepted. Aether-Next is canonical; Aether-2 is
reference/compatibility. The executable consolidation plan is
`docs/CANONICAL_AETHER_CONSOLIDATION_PLAN.md`.

Date: 2026-07-02. Purpose: resolve the two-source-of-truth question before more
build slices land. Grounded in both codebases, not summaries.

## The two candidates

| | **Aether-Next** (`aether_next_build/aether_next/`) | **Aether-2** (`harness/aether2/`) |
|---|---|---|
| Size | 46 modules, ~12.5k LOC | 101 modules |
| Core concepts | Architect / solver / verifier, WorkbenchArchitect, HarnessConfigIR | AHP (Adaptive Harness Profile), adaptive_profile, receipt-driven variant |
| Runs the real benchmark via | `run_pilot.py` → `docker_helpers.py` → real Terminal-Bench docker images (alexgshaw/*) + official grader | "Harbor" backend + `runner/aether2/` (the documented `eval_suite → runner → harness/aether2` path) |
| Most recent real scored runs | **2026-07-01** (this session's Stage-1 filter/sparql/openssl VM runs) | **2026-06-23** (Harbor board rows: financial_receipt_probe, qemu_service_smoke) — ~9 days older |
| Tests | 245 pass under default `python3` (3.9.6) | 154 pass, but only under `python3.10+`; default `python3` can't even import it |
| This session's validated fixes | All here (permission, trace-write, verifier deadlock, finding resolution) + VM validation loop | None |
| Codex's 6 vision slices | None | All here |

## The decisive facts

1. **"Aether-Next" is the successor line; "Aether-2" is the predecessor.** The
   naming is literal, and the evidence is one-sided: every recent artifact —
   the Pro run (2026-06-25), the Phase-2 Terminal-Bench audits, STATUS.md
   ("Aether-Next build"), this entire session — is **Aether-Next**. Aether-2's
   most recent real runs are ~9 days older.

2. **CLAUDE.md is stale, and that is what caused the switch.** CLAUDE.md calls
   `harness/aether2` "the active Python harness line" and **does not mention
   `aether_next` at all** (grep: zero hits). Codex followed CLAUDE.md literally
   and retargeted to Aether-2. That was a reasonable read of a misleading doc —
   but the doc describes the *predecessor* as active while all actual active
   development is on the *successor*.

3. **Both can run the real benchmark.** This is not "one is real, one is a toy."
   Aether-Next runs Terminal-Bench directly via `run_pilot.py`; Aether-2 runs it
   via Harbor + `runner/`. The difference is which is *current* and *validated*,
   not which is *capable*.

## What each choice costs

**Choose Aether-Next as production** (implement the vision here):
- *Keeps:* all 245 tests, the VM validation loop, this session's fixes, and the
  successor line the user has actually been building.
- *Costs:* re-apply the vision here (Codex's 6 slices become reference, not waste
  — the code patterns port cleanly). Formalize the `eval_suite → runner` wiring
  if an official-pipeline submission is required (Aether-Next currently runs the
  benchmark standalone, not through `runner/`).
- *Migration:* the vision changes we designed were derived *from this codebase's
  actual current state* — so they apply directly, no re-derivation.

**Choose Aether-2 as production** (keep Codex's direction):
- *Keeps:* Codex's 6 slices, the `runner/eval_suite` integration, Harbor.
- *Costs:* abandons this session's validated work and the successor line; the
  concrete current-vs-desired analysis does **not** transfer (Aether-2 lacks the
  specific structures we diagnosed); every slice needs its own real-task
  validation (none done yet); and the default `python3` can't run it.
- *Risk:* you are building the future on the line you were moving *away from*.

## Recommendation

**Aether-Next (`aether_next_build`) is the stronger production candidate**, on the
weight of evidence: it is the successor line, the actively-developed line, the
validated line, the line producing the most recent real scores, and the line that
holds all of this session's work. Aether-2's one genuine advantage — the formal
`runner/eval_suite` wiring — is a fixable integration detail, not a reason to
rebuild the vision on the line you were superseding.

**The honest caveat:** I can see the code, not your intent. If Aether-2 is
mandated for a specific reason not visible in the repo (e.g. an official
Terminal-Bench submission must go through `runner/`, or Aether-Next was always
meant to be a throwaway sandbox), that overrides the above — but nothing in the
code says so, and everything recent says the opposite.

**First action either way:** fix CLAUDE.md to state, truthfully, which line is
production. The entire divergence traces to that one stale sentence.
