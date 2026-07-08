# CLAUDE.md

Contributor and agent guide for HarnessEng.

## Governing Vision (read first)

The harness architecture and build discipline are governed by
[`docs/HARNESS_VISION.md`](docs/HARNESS_VISION.md). It outranks convenience and
any agent's idea of what "should" be added. Core rules:

- **One test:** the better the model, the better the system. If a stronger model
  would make a piece of harness code redundant or want to override it, it is a
  crutch and does not belong. Build the workbench, never the crutch.
- **Four roles, hard boundaries:** the *architect* designs the workbench and
  authors the solver + verifier system prompts; the *solver* works; the
  *verifier* independently verifies the task **state** (not the solver's story)
  with read-only tools; the *official grader* is external, post-run only, and is
  **never** part of our harness or the agent loop.
- **Two layers:** the *substrate* (docker/fs/executor) must be robust and ideally
  never fail; the *judgment/config* layer has **zero fallbacks**. A substrate
  failure is fixed at the substrate and reported honestly; a config/judgment
  failure is surfaced as blocked, never silently absorbed by a default.
- **Propose, never blind-build.** New mechanisms need approval. Before any
  non-trivial change, produce a current-state map (what exists / matches /
  violates / missing / smallest next step). Skipping the map is grounds for
  rejecting the work.

## Architecture

Canonical target decision, 2026-07-03: **Aether-Next is the active
agent/harness line.** Until the consolidation rename is executed, its
implementation lives at `aether_next_build/aether_next/`. The intended
canonical package name is `aether/`.

`harness/aether2/` and `runner/aether2/` are reference/compatibility surfaces.
They contain useful tested patterns and runner integration history, but new
production-harness build slices should not target them unless a future
evidence-backed decision explicitly reverses this.

The desired dependency flow after consolidation is:

```
eval_suite  →  runner  →  aether
                              ↑
                         (no upward imports)
```

- **`aether_next_build/aether_next/`** — Current canonical Aether-Next source
  until it is renamed or exposed as `aether/`. The agent runtime:
  control loop, tool dispatch, model routing, traces, skills, hooks.
  Generic and task-agnostic. No benchmark-specific hardcoding here.
- **`harness/aether2/` / `runner/aether2/`** — Reference and compatibility
  surfaces. Port generic ownership-boundary lessons from here; do not treat this
  as the active production target.
- **`runner/`** — Eval execution engine. Loads task packs from `eval_suite/`,
  sets up sandboxes, runs agents, collects grader scores. CLI entry:
  `python -m runner run-eval`.
- **`eval_suite/`** — Task packs, graders, schemas, adapters, and result
  evidence. Organized by capability family (`tooling/`, `retrieval/`,
  `filesystem/`, `environment/`) and `whole_harness/` surface. Self-contained:
  no imports from `runner/`, `aether_next_build/aether_next/`, or `harness/`.
- **`variants/`** — Mechanism-family and whole-harness variant cards,
  scoreboards, and evidence. References harness code; does not duplicate it.
- **`research/`** — Promoted synthesis outputs, mechanism maps, failure
  taxonomies, case studies.
- **`workflows/`** — AI-native engineering operating system: orchestration,
  skills, synthesis protocols, review and handoff templates.

### Dependency rule

Imports flow downward only: `eval_suite → runner → aether` after
consolidation. During migration, treat `aether_next_build/aether_next/` as the
canonical implementation and avoid adding new dependencies from canonical
Aether back up into `runner/` or `eval_suite/`.
No module may import upward. No cycles. Verify with:

```bash
grep -rn 'from runner\.' eval_suite/   # must be empty
grep -rn 'from eval_suite\.' aether_next_build/aether_next/ harness/  # must be empty
```

## Architecture Layers & Terminology

Use these terms consistently:

- **Aether / Aether-Next** (`aether_next_build/aether_next/`, intended
  `aether/`) — the active harness/runtime: the whole agent system. When we say
  "the harness" going forward, we mean canonical Aether, not Aether-2.
- **Aether-2** (`harness/aether2/`) — reference/compatibility line. It may supply
  portable generic patterns, but it is not the production authority.
- **Invariant core** — the fixed rules inside canonical Aether that **no variant or model
  may weaken or reconfigure**: workspace/path safety, tool truthfulness, audit
  logging, No Fake Work, executor boundaries, verification-must-happen, cleanup
  accounting, evidence ledger, the baseline loop shape, and model-visible context
  hygiene (no benchmark/grader/hidden-test framing ever reaches the model).
  *(The `kernel_*.py` filename prefix names specific trace/audit components — do
  not conflate it with this concept.)*
- **Configurable surfaces** — the task-facing knobs a variant may adapt: solver
  prompt (task block), context inclusion, exposed tool subset, completion
  contract / success definition, verifier `stated_requirements` / verification
  focus, evidence guidance.
- **Variant** (e.g. **AHP — Adaptive Harness Profile**) — adapts the configurable
  surfaces around the invariant core for a given task. A variant **never** modifies
  the invariant core, **never** adds task-specific branches to the runner, and is
  always flag-gated with the baseline path preserved. The model decides *what the
  task needs*; the harness decides *how to apply it safely* via one data-driven
  adapter (`AdaptationContract → ValidatedRunConfig`), not control-flow branches.

## Key Commands

```bash
# Install (editable mode)
pip install -e .

# Run full test suite (65 tests, the verification floor)
python3 -m pytest -q

# Run an eval offline (zero credentials needed)
python3 -m runner run-eval \
  --task-pack eval_suite/mcp_registry_contract_smoke \
  --agent stub --offline

# Public readiness checks (cold-start + smoke + focused tests)
make public-readiness

# Focused public-readiness pytest slice
make public-tests

# Build wheel
python3 -m pip wheel --no-deps -w dist .
```

## Module Size Cap

Every Python module must be ≤ 500 lines of code. Modules over this limit
are decomposed along real responsibility boundaries. Check with:

```bash
find aether_next_build/aether_next -name '*.py' | xargs wc -l | sort -rn | head -10
```

## Eval Discipline

- No variant without a target eval, a prediction, and named sentinels.
- Separate environment failures from capability failures.
- Record failed predictions; do not reinterpret them into wins.
- Scoreboards and result rows are the source of truth for promotion.
- Promotion authority lives with scored eval evidence, not trace aesthetics.

## Aether Principle

> The model pilots. The harness instruments. The verifier reflects.
> The ledger remembers. The grader decides.

No task-specific hardcoding in canonical Aether. No benchmark-name affordances.
No harness-side completion veto theater. The verifier judges task-visible state;
the official grader evaluates only after the agent terminates.

## Engineering Standards

Full standards: [`docs/engineering-standards.md`](docs/engineering-standards.md).

Key points: types first, inject dependencies, 500 LOC cap, no dead code,
no duplication across packages, every meaningful run leaves inspectable
evidence.

## No Fake Work (Anti-Proxy-Success)

A change is "done" only when it does **real work**, proven by evidence independent
of your own claims. Making a check turn green is not the goal; making the
underlying thing true is. Full standard: **No Fake Work** in
[`AGENTS.md`](AGENTS.md).

Never acceptable, never "complete":

- A file/asset/shim that exists **only to satisfy an existence or import check**
  (e.g., to make `.exists()` or `find_spec()` return True). If you report
  `X_present: True` / `available: True`, `X` must be real and functional.
- No-op swallow-all shims, stub functions returning `{"status": "stubbed"}` /
  `[]` / canned values, or synthetic placeholder data (e.g., `ping()`-only
  ground truth) presented as real.
- Passing a test/preflight by weakening it, mocking past it, or feeding it
  synthetic data that masquerades as real.
- Claiming `fixed` / `ready` / `green` when the green is satisfied by mocks,
  stubs, shims, or import-success rather than real execution.

Required: distinguish "imports succeed" from "really works" and report which;
when real assets/deps are missing, report **BLOCKED with the exact missing
piece** (honest blocked beats a fake green); make every check you add
falsifiable (a known-bad must fail it). Adversarial review must audit
faithfulness — open the files behind any green and confirm real code/data, not
stubs — before any "fixed/complete" claim is accepted.

## Commit Discipline

Commit in coherent slices. Do not bury unrelated work in one giant
checkpoint. Material changes should emit a `RAW_LEDGER_UPDATE` under
`tracking/ledger/inbox/`.
