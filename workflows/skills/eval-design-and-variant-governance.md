# Eval Design and Variant Governance

Use this skill when a failure family needs a proper eval, or when a variant
hypothesis needs to be translated into a governed experiment.

This skill sits between the **analyze** and **implement** stages of the loop.
It prevents the most common failure mode: implementing a mechanism before the
evidence exists to keep/kill it.

## Governing Question

> What failure family are we targeting, and what evidence will make the
> keep/kill decision?

Both parts are required. A variant without a failure family is guessing.
A failure family without a keep/kill criterion is indefinite exploration.

## When To Use

Use this skill when:

- a failure taxonomy has identified a targetable family;
- you need to design a proper eval before writing implementation;
- you need to create a VARIANT_FAMILY_SEED for a new experiment;
- you need to make a keep/kill/iterate decision on a scored variant;
- you need to open a new failure lane.

Do not use this skill for:

- broad eval-suite architecture (that requires the orchestrator);
- post-hoc justification of a change that was already implemented
  (record the failed discipline instead).

## The Eval-First Constraint

No variant may be created without:

- a target eval that measures the specific behavior being changed;
- a predicted score delta (what will move, by how much, in which direction);
- named regression sentinels (what must not regress).

If any of these are missing, design the eval first. Do not start the
implementation.

## Workflow

### 1. Classify the Failure Family

Use the failure class taxonomy:

- `environment/runtime`
- `provider/model transport`
- `sandbox/container setup`
- `tool contract`
- `path/cwd`
- `schema/parsing`
- `evidence acquisition`
- `reduction/selection`
- `execution/reasoning`
- `process/service/session persistence`
- `verification/grading`
- `timeout/step-budget`
- `contamination`
- `model capability`
- `unclear`

Separate environment and tooling failures from capability failures before
designing any mechanism.

### 2. Design a Proper Eval

A proper eval must have:

- **task contract:** what the task asks for, in a form that does not leak
  suite-specific knowledge into harness code;
- **fixture/workspace:** the environment state the task starts in;
- **ground truth:** what the grader checks;
- **deterministic grader:** when feasible — a grader that produces the same
  result regardless of which model runs the task;
- **baseline run:** a run before the mechanism is applied;
- **ceiling check:** a run that proves the eval is solvable in principle;
- **known-bad cases:** at least one case that should fail so the eval can
  detect regression;
- **contamination checks:** nothing in the harness code encodes the specific
  task names, expected answers, or hidden test shapes;
- **admission level:** the score threshold that makes a variant promotable.

A custom eval is preferred over a cloned public eval row. The eval
must abstract the failure family, not copy a specific instance.

### 3. Create the Variant Family Seed

Use the [VARIANT_FAMILY_SEED schema](../schemas/variant-family-seed.md):

```text
VARIANT_FAMILY_SEED
- seed_id: <stable identifier>
- name: <human-readable label>
- short_definition: <one sentence>
- source_mechanism_families: <from mechanism map>
- source_failure_families: <from failure taxonomy>
- source_eval_implications: <from eval implications artifact>
- evidence_paths: <concrete repo-local paths>
- affected_block_types: orientation | tool | execution | context | verification | recovery | runner | eval
- expected_interface_pressure: <what contracts would change or stay stable>
- atomic_or_combo: atomic | combo | unclear
- composition_constraints: <where this seed is only valid if other assumptions hold>
- minimal_sufficient_baseline: <the simpler contender that must remain visible>
- required_ablation_hooks: <what needs to be toggled to test this seed>
- required_eval_hooks: <what eval surfaces are required>
- likely_tradeoffs: <expected downsides>
- contradictory_or_complicating_evidence: <evidence that weakens or complicates>
- confidence: low | medium | high
- open_questions: <unresolved uncertainty>
```

No seed without upstream evidence. No seed without explicit block or interface
mapping.

### 4. Open the Lane

Before any implementation begins, record:

- which failure family is targeted;
- which eval will prove the mechanism;
- what the baseline score is;
- what a promotable result looks like;
- which regression sentinels will run with every candidate.

### 5. Run the Scored Board

After implementation, run:

- target eval;
- baseline;
- ceiling check (to confirm the eval still works);
- known-bad cases;
- regression sentinels.

Record the result as a scoreboard row, not as a prose summary.

### 6. Make the Keep/Kill/Iterate Decision

The scoreboard row drives the decision:

- **Keep (promote):** net-positive on target scores, sentinels, contamination/invalid
  rates, and cost/step budget. No sentinel regression.
- **Kill:** net-negative, or regression on a sentinel, or contamination violation.
  Record the failed prediction. Do not silently reinterpret.
- **Iterate:** inconclusive evidence. Name the specific gap that would change the
  decision. Do not iterate indefinitely.

A prediction that fails is data, not a prompt to widen scope.

## Guardrails

- Do not create a variant before the eval exists.
- Do not promote from traces alone. Traces diagnose; evals prove.
- Do not use local replays or verifier verdicts as promotion evidence without
  fresh end-to-end certified runs.
- Parallel diagnosis is allowed; lane-local promotion is not. Multiple failure
  families may be investigated in parallel, but every fix must pass the shared
  global sentinel board before promotion.
- When multiple fixes target related failures, test the interaction explicitly:
  fix A alone, fix B alone, and A+B together.

## Sources

- `workflows/orchestration/codex-goal-governance.md` — §Experiment Discipline
  (the governing rules for eval design and variant governance)
- `workflows/orchestration/codex-goal-governance.md` — §Eval-First Reset Rules
- `workflows/skills/eval-first-implementation-slice.md` — the gate between
  hypothesis and implementation
- `workflows/schemas/variant-family-seed.md` — the full VARIANT_FAMILY_SEED schema
- `workflows/schemas/failure-card.md` — the FAILURE_CARD schema for source
  failure families
