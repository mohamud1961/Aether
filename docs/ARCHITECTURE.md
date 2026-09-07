# Aether architecture

## Design target

> **Make the model the limit.**

Aether is built around a narrow ownership rule:

- **the model owns cognition and strategy;**
- **Aether owns execution reality;**
- **review owns falsification/evidence pressure, not strategy;**
- **the external benchmark owns official grading.**

The purpose of this split is not aesthetic minimalism. It is experimental: if the harness stops supplying hidden cognition, improvements in the underlying model should translate more directly into improvements in the agent.

## Production flow

```text
raw task
   │
   ▼
Harbor lifecycle / isolated task environment
   │
   ▼
Aether task + capability projection
   │
   ▼
MODEL ── chooses next action ──► AETHER EXECUTION
  ▲                                  │
  │                                  ▼
  └──── observed result / state ◄── WORLD
   │
   ▼
read-only completion review
   │
   ▼
external official grader
```

## 1. Model: intelligence

The model is expected to:

- understand the task;
- decide what to inspect;
- choose the next action;
- interpret observations;
- change strategy when evidence contradicts its assumptions;
- decide when it believes the task is complete.

Aether does not put a second semantic planner above this process.

## 2. Aether: capability and reality

Aether is responsible for the things a model should not have to simulate internally:

- exposing the task and mechanically observed environment;
- presenting available capabilities;
- executing external actions;
- returning the real result of each action;
- preserving files, process state, receipts and provenance;
- maintaining evidence freshness;
- enforcing capability and workspace boundaries;
- recovering from infrastructure failures without inventing task strategy;
- exporting traces and run evidence.

The current production package is `aether/`.

Important implementation surfaces in the current research line include:

- `aether/model_interface.py` — provider/model boundary;
- `aether/kernel.py` and kernel turn modules — control loop;
- `aether/execution.py` / `aether/real_executor.py` — external action execution;
- `aether/ledger.py` / `aether/receipts.py` — durable reality/evidence state;
- `aether/context_views.py` / `aether/solver_facing_projection.py` — model-visible state;
- `aether/proof_contract.py` — completion evidence contract;
- `aether/verifier.py` and verifier modules — read-only review;
- `aether/harbor_agent.py` / `aether/harbor_runtime.py` — benchmark lifecycle integration;
- `aether/redaction.py` — evidence redaction boundary.

## 3. One observed action frontier

The fundamental control loop is:

```text
model chooses action
→ Aether executes
→ result is persisted
→ model observes result
→ model chooses again
```

The model should not be encouraged to plan several causally dependent external actions and then execute them blind. Later actions should be informed by what actually happened.

This is an execution-reliability rule, not a task-solving heuristic.

## 4. State and context

Aether treats context as a projection of current reality, not as the authority itself.

Durable state lives in artifacts such as:

- action/result receipts;
- current workspace state;
- evidence records;
- process/service observations;
- provider continuity state;
- run budgets and deadlines;
- trace events.

The model receives the smallest useful projection of those facts for the current turn. Historical detail can remain available without forcing every internal runtime detail into every prompt.

## 5. Completion review

The verifier is deliberately narrower than a second agent.

It may:

- inspect task-visible state;
- challenge a completion claim;
- identify missing evidence;
- preserve falsifying observations;
- report that review could not be completed.

It must not:

- own the task strategy;
- secretly substitute its preferred plan for the model's plan;
- access hidden grader truth;
- turn uncertainty into a benchmark-specific completion veto.

This boundary matters because a powerful verifier can otherwise become an unacknowledged second mind and make it impossible to attribute capability to the underlying model.

## 6. External grader

The official benchmark grader is outside Aether's cognitive loop.

That separation allows three outcomes to be distinguished:

1. **model/task miss** — the final task state is wrong;
2. **harness/runtime failure** — the system prevented or corrupted useful model work;
3. **internal review disagreement** — the external state passes even though Aether's review machinery did not recognise completion cleanly.

The third category has already appeared in live evidence and is one reason Aether exists as a research project.

## 7. Benchmark neutrality

Production Aether is intended to remain benchmark-neutral.

The runtime should not contain:

- task-name branches;
- expected benchmark answers;
- hidden test access;
- task-specific solve packs;
- benchmark-specific strategy prompts;
- special completion rules added because one benchmark row failed.

Evaluation code can know which benchmark is being run. The production agent runtime should not need benchmark-specific cognition to solve it.

## 8. What Aether is not

Aether is not currently claiming to be:

- a benchmark-leading agent;
- a multi-agent planner swarm;
- a universal safety solution;
- proof that harness design matters more than model intelligence;
- proof that the current architecture is optimal.

It is a working experimental runtime for testing a narrower proposition:

> **How much more of a model's capability reaches real work when the harness owns execution reality and stops trying to own the thinking?**

## Research consequence

The architecture creates a clean experimental prediction:

```text
same runtime + stronger model
           ↓
better agent performance
```

If that does not happen under controlled evaluation, Aether's mechanisms should be simplified or removed rather than protected by additional hand-built strategy.
