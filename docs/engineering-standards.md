# Engineering Standards

This repository is held to a production-grade bar. The goal is that a reviewer
who opens any file finds clear types, clean seams, obvious state ownership, and
control flow they can follow without a debugger. These rules are normative:
code that violates them is a defect, not a style preference.

## 0. First principle: program design precedes system design

Architecture diagrams do not save a codebase whose types are vague, whose seams
are untestable, and whose state lives in five places. Before reaching for
system-level structure, every change must get the **program design** right:

- **Types first.** Model the domain with precise types. No `dict[str, Any]`
  flowing through business logic where a dataclass/`TypedDict`/enum belongs.
  Illegal states should be unrepresentable.
- **Seams and testability.** Depend on interfaces (`Protocol`/abstract base),
  not concretions. Inject collaborators (clients, clocks, filesystems) rather
  than constructing them inline, so every unit is testable without network,
  disk, or wall-clock.
- **State ownership.** Each piece of state has exactly one owner. Prefer
  immutability (`@dataclass(frozen=True)`); make mutation explicit and local.
  No hidden global/module-level mutable state.
- **Control flow.** One obvious path through each function. Errors are typed and
  surfaced, never swallowed. No control flow by exception for normal cases.
- **Abstraction boundaries.** Introduce an abstraction only where it earns its
  keep. No speculative indirection; no leaky abstractions that expose their
  internals.

## 1. Module and function shape

- **Module size cap: 500 LOC.** A module over 500 lines must be decomposed along
  a real responsibility boundary, not split arbitrarily. No "god modules."
- **Function size:** prefer < 50 lines; a function over ~80 lines needs a reason.
- **Single responsibility** per module and per function.
- **Public API is explicit:** every package module declares `__all__`; anything
  not exported is private (`_`-prefixed) and may change freely.

## 2. Types and interfaces

- Full type annotations on every public function signature; `from __future__
  import annotations` in every module.
- Use `Protocol` for the seams that need test doubles (model clients, executors,
  registries). Construct concrete implementations at the composition root only.
- No `Any` in a public signature unless it is genuinely opaque payload, and then
  it is documented as such.

## 3. Errors, state, effects

- Errors are typed exceptions or typed result envelopes — never bare `except:`,
  never `except Exception: pass`. Catch the narrowest type; attach context.
- Side effects (I/O, subprocess, network) live behind injected interfaces and at
  the edges, not buried in pure logic.
- Determinism: core logic must not depend on wall-clock, randomness, or ambient
  environment unless those are injected and overridable in tests.

## 4. No duplication, no dead code, no sediment

- **DRY across packages.** A mechanism is defined once. `variants/` references or
  imports shared code; it does not copy `runner/`/`harness/` modules wholesale.
  A variant may freeze a *small, labeled* snapshot only when the experiment
  genuinely requires a point-in-time copy — never a 1,000+ LOC parallel runtime.
- No dead code, commented-out blocks, or unreachable branches.
- No iteration-sediment naming (`*_v2`, `phase65`, `followup2/3/4`,
  `successor_phase*`, `*_final`, `*_actual`). Names describe behavior, not history.

## 5. Architecture: one-way dependencies

The dependency graph is acyclic and flows in one direction:

```
evals  ─┐
variants┼──▶  runner  ──▶  harness   (harness depends on nothing above it)
        ┘
```

- `harness/` (the aether agent) is self-contained and depends on no sibling group.
- There is **one** runner. It is the single entry point that drives the harness
  over tasks/eval packs. No competing/legacy runners.
- No import cycles. Verified mechanically (`python -m pytest` import + a cycle check).

## 6. Native and self-contained

- All code is original and owned. No language implying it was ported/adapted
  from an external source; no provider-internal endpoints, OAuth client IDs, or
  reverse-engineered backends. Model access is via the declared provider SDK
  (litellm / Azure), credentials from the environment.
- The public tree imports nothing outside itself. No references to private
  paths, private repos, internal hostnames, or secrets.
- No vendored third-party source trees. Benchmark-derived evals ship small,
  clearly-labeled synthetic fixtures with a provenance note — never the upstream
  benchmark's raw licensed data.

## 7. Evals are clean, isolated, and runnable

- Each eval is self-contained: a task contract, a grader/verifier, and a
  fixture/solver workspace with **no** absolute paths, secrets, PII, or network
  dependency. Deterministic and offline.
- Each eval is grouped correctly (capability family vs whole-harness) and
  actually runs: its grader executes against the solver pack and produces a
  score. "Present but not runnable" is not acceptable.

## 8. Packaging, runnability, tests

- `pip install -e .` succeeds from a clean clone; declared dependencies exactly
  match imported ones (no unused, no undeclared).
- A forker can run the **agent** (stub demo, zero credentials) and an **eval**
  each with one documented command.
- Tests run on the pinned interpreter (Python ≥ 3.11), pass green, and provide
  real coverage — no hollow all-skip files, no tests importing absent modules.
  CI enforces the green suite.

## 9. The maker/checker loop (how changes land)

1. A change is made as the smallest coherent slice.
2. Tests are green **before and after** the slice (the suite is the safety net
   for every refactor).
3. A separate review pass verifies the slice against these standards before it
   is accepted. Large, multi-concern diffs ("shotgun surgery") are rejected in
   favor of focused, reviewable slices.

## Acceptance gates (a change is "done" only when all hold)

- [ ] Installs clean; deps == usage.
- [ ] Agent runs (stub) and an eval runs, each one documented command.
- [ ] `pytest` green on 3.11; real coverage; CI enforces.
- [ ] Self-contained: no external/private imports, no reverse-engineered or
      vendored content.
- [ ] Clean code: no god modules, no duplication, no dead code, no sediment
      naming; typed; `__all__`; docstrings on public surfaces.
- [ ] One runner; acyclic one-way dependency graph.
- [ ] Native and owned throughout.
