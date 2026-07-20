# Aether-Next Architecture Constitution

Status: certification authority for scorecard v1

## 1. Purpose

Aether-Next is a model-authored runtime compiler with a small trusted kernel.
Models own task semantics and strategy. Trusted code owns execution truth,
observation boundaries, evidence identity, safety, lifecycle, and completion
integrity.

No benchmark result, model preference, or isolated task failure may override
this separation.

## 2. Semantic authority

The Architect owns:

- interpretation of the immutable task prompt;
- task clause decomposition;
- success definition;
- false-success traps;
- Solver workflow;
- proof intent and evidence dependencies;
- context pins;
- task-local helper strategy;
- configuration-owned reconfiguration triggers.

The kernel must not infer semantic task requirements from keywords, filenames,
benchmark categories, or known task families.

Forbidden trusted-code behaviour includes task strategies for video, QEMU, Git,
G-code, gRPC, cryptography, or any other task family.

## 3. Mechanical authority

The kernel owns only mechanically decidable facts:

- provider output status and identity;
- protocol validity;
- which action was authorised;
- what actually executed;
- which world generation an inspection observed;
- state and process mutations;
- evidence registration and freshness;
- finding lifecycle;
- configured budget accounting;
- safety and isolation;
- final completion conjunction;
- source and evidence provenance.

The kernel may validate that Architect references resolve. It may not decide
whether the Architect's semantic interpretation is correct.

## 4. Fixed generic capability surface

The kernel exposes one generic capability surface. Architect output may explain
how to use it but may not add, remove, enable, or disable core actions.

The canonical surface covers reading, writing, execution, process lifecycle,
probing, inspection, perception, retained-evidence query, task-local helper
execution, and submission.

## 5. Observation boundary

Each Solver decision authorises exactly one of:

1. one potentially state-changing or effect-unknown action; or
2. one bounded batch of certified read-only inspections.

All members of an observation batch must:

- be mechanically certified read-only;
- observe the same frozen WorldState generation;
- have individual request and result identities;
- return successes and failures together;
- record route, target, tool identity, result hash, and generation;
- finish before the Solver receives another decision turn.

A command, HTTP request, test, or helper whose effects are unknown is treated as
state-changing unless executed in a disposable isolated environment.

A helper remains one model-authored decision frontier, not an opaque execution
blob. Its subprocesses, files, network activity, outputs, process identities,
and resulting generation remain observable.

## 6. Provider boundary

Aggregated provider text is never the authoritative Solver output.

- one valid assistant message may be used;
- semantically identical duplicate messages may be canonicalised once while all
  raw items remain preserved;
- multiple distinct messages execute nothing;
- incomplete, truncated, malformed, mixed, or ambiguous output executes
  nothing;
- every retry variant must be pre-certified.

No rejected provider output may dispatch a task action.

## 7. Evidence authority

Every accepted evidence item binds to a canonical inspection record containing:

- inspection ID;
- requesting role;
- route and parameters;
- target identity and generation;
- workspace generation;
- tool/runtime identity;
- result hash and summary;
- evidence ceiling;
- start and completion times;
- success or failure.

The Verifier cites inspection IDs. The kernel derives all mechanical properties
from the registry and never trusts model-restated route, ceiling, or generation.

## 8. Proof freshness

The Architect declares semantic dependencies and invalidators for each proof
clause.

- precise dependencies: mutation of a declared dependency invalidates proof;
- absent, incomplete, or uncertain dependencies: any relevant workspace,
  process, or service generation change invalidates proof conservatively.

Derived representations retain source hash, transformation/helper hash,
parameters, creator, output hash, and generation. Solver-produced
representations do not become independent evidence merely by being inspected.

## 9. Findings

A finding binds to clause, target, observed generation, owner, supporting
inspection IDs, repair condition, and required fresh evidence.

Unrelated reads, writes, observations, memory queries, or repeated submissions
cannot clear it. Relevant current evidence may resolve or rebut it. Mutation may
require reinspection but does not silently clear the finding.

## 10. Completion

Internal completion requires the conjunction:

- Verifier verdict is completed;
- a fresh deterministic completion decision is ready;
- no blocking finding remains;
- required proof is current;
- process/service obligations are current;
- integrity checks are clear;
- state capture is complete enough for the claim.

A Verifier verdict is semantic evidence. It is never direct completion
authority.

## 11. Network and isolation

The environment supplies explicit permitted network scope. The kernel enforces
that scope mechanically. The Architect decides how to use permitted
connectivity.

Regex command scanning is not a security boundary.

Filesystem containment is path-aware and symlink-safe. Secrets are redacted in
normal evidence. Raw provider payloads are retained only in a protected evidence
lane.

## 12. Reconfiguration

Reconfiguration is disabled until the trusted kernel is certified.

When restored, only independently verified configuration-owned blockers may
transfer control to the Architect. Reconfiguration cannot replace the task
contract, delete evidence, alter kernel code, or compensate for an ordinary poor
Solver decision.

## 13. Minimalism

Production has one authoritative path for each guarantee:

- one kernel;
- one Solver protocol;
- one Architect IR and compiler;
- one context compiler;
- one ledger;
- one inspection registry;
- one Verifier protocol;
- one production runner;
- one evidence finaliser;
- one completion path.

Non-authoritative legacy paths are removed or isolated outside production.

## 14. Patch admission

A kernel patch is admissible only when it closes a generic trusted invariant or
adds a genuinely missing generic primitive.

A poor model strategy, weak task interpretation, or one benchmark miss is not
by itself a kernel defect.
