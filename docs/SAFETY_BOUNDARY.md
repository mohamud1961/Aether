# Safety boundary

## More autonomy does not have to mean less control

Aether deliberately separates **cognitive autonomy** from **execution authority**.

The model is allowed to lead the reasoning: choose approaches, adapt, decide what it needs and change direction. The runtime is responsible for constraining and recording how those decisions become actions in the world.

This is safety-relevant architecture, not a claim that Aether has already been proven safe.

## Core boundary

```text
MODEL
free to reason and choose
        │
        ▼
explicit capability request
        │
        ▼
AETHER BOUNDARY
permission · workspace · schema · deadline · evidence
        │
        ▼
ISOLATED EXECUTION
        │
        ▼
OBSERVABLE RESULT
receipt · provenance · freshness · trace
```

## 1. Isolated execution

Benchmark tasks run through Harbor-managed isolated environments. Aether treats the environment boundary as part of the runtime contract rather than assuming that model-generated shell activity is harmless.

Provider-free preflight and smoke paths exist so environment failures can be detected without spending a benchmark attempt or exposing provider credentials.

## 2. Explicit capability surfaces

The model acts through declared capabilities rather than unrestricted hidden runtime access.

The runtime can reject actions that fall outside the declared workspace or capability contract. A sealed held-out run, for example, correctly rejected an attempted read outside the declared `/app` workspace. The task still failed, but the boundary behaved correctly; Aether did not silently broaden permissions to help the model pass.

That distinction is important: safety and benchmark performance are separate measurements.

## 3. One observed action frontier

Aether's control loop is designed around an observation boundary after external action:

```text
choose → execute → observe → choose again
```

This limits the amount of unobserved causal work that can accumulate before the model sees whether its assumptions were correct.

It also produces a clearer audit trail: each consequential action can be associated with the observation that informed the next decision.

## 4. Durable receipts and provenance

Aether records task-visible reality outside the model's prose memory.

Evidence can include:

- action/result receipts;
- file/process/service observations;
- launch identity;
- provider continuity events;
- verification requests/results;
- deadlines and budgets;
- hashes of sealed run artifacts.

The aim is to make post-hoc questions answerable:

- What did the model see?
- What action was actually executed?
- What changed in the environment?
- What evidence existed at completion time?
- Was an observation stale?
- Did a provider/runtime failure interrupt the run?
- Did internal review agree with the external grader?

## 5. Fail closed on malformed control data

Provider responses and model-authored actions are treated as untrusted control inputs.

Where a response cannot be unambiguously canonicalised or parsed, the safe action is **no execution**, not "extract something plausible and continue."

This prevents duplicated or malformed provider output from silently becoming duplicated external actions.

## 6. Recovery without hidden strategy

A runtime needs recovery, but recovery can become a hidden planner if it decides *what the task should do next*.

Aether's target boundary is narrower:

- recover transport/runtime continuity;
- preserve the failure as evidence;
- restore the ability to act;
- return current reality to the model;
- let the model decide the task strategy.

Retries are therefore an execution policy, not an excuse for the harness to take over cognition.

## 7. Independent completion review

Aether includes an independent read-only verifier because self-reported completion is not enough for reliable autonomous work.

The verifier is intended to falsify or request evidence, not to become a second planner. If review tooling fails or disagrees with externally graded reality, that disagreement is preserved as evidence rather than rewritten into a cleaner story.

One historical `configure-git-webserver` run is useful precisely because the external grader passed while Aether's verifier remained blocked. That exposed a harness-side completion/review problem instead of hiding it.

## 8. No hidden grader access

Official benchmark grading remains outside model context and outside the production agent's strategy loop.

Aether should not become stronger by leaking hidden tests, expected answers or benchmark-specific solve logic into the model-visible environment.

This protects both evaluation validity and attribution.

## 9. Redaction and publication

A complete internal trace is not automatically a safe public trace.

Before evidence is promoted to `evidence/`, it should be checked for:

- credentials and provider secrets;
- private host paths and identifiers;
- hidden or held-out benchmark content that should not be republished;
- unrelated personal data;
- excessive raw model content that does not improve auditability;
- artifacts whose provenance cannot be explained simply.

The public evidence layer therefore contains **small promoted packets**, while larger internal run archives remain private.

## 10. What safety research this enables

Aether creates a substrate for asking safety-relevant questions such as:

- Can a model be given more strategic autonomy while external action becomes more permissioned and inspectable?
- Which failures come from the model versus the runtime around it?
- How often does internal review disagree with external reality?
- What information does a model actually need to act reliably without flooding context with runtime internals?
- Which recovery mechanisms preserve capability without quietly introducing another decision-maker?
- Can stronger models be inserted without weakening the execution boundary?

## Current evidence boundary

The latest sealed held-out campaign accepted Aether's **runtime mechanical integrity** but did **not** establish benchmark competitiveness. No generic Aether production defect was demonstrated in the audited rows; valid failures were predominantly model/task misses, with separate infrastructure/provider invalid rows preserved rather than rerun away.

That is the standard the project is aiming for: failures should remain attributable even when the result is disappointing.

## Research claim

Aether's safety claim today is intentionally narrow:

> **The architecture is designed to let the model lead cognition while keeping execution bounded, permissioned, isolated and auditable.**

Whether that architecture measurably improves safety or reliability is part of the next research phase, not a conclusion assumed in advance.
