# Evidence map

Where to look in this repository for evidence of each skill below. Every entry points to code, an evaluation or a
write-up that can be read and checked; none is a summary of itself.

## Working with Claude and Claude Code

- **Claude orchestrating a fleet of agents (8 October onward):** Claude in Claude Code planned, delegated to Sonnet and
  Haiku subagents, reviewed and audited. See [workflows/orchestration.md](../workflows/orchestration.md) (Phase 3)
  and the rules that came from incidents in [workflows/governance.md](../workflows/governance.md).
- **Gen 5 was built this way.** Most commits under `aether/core/` carry a `Co-Authored-By: Claude` trailer
  (`git log -- aether/core`).
- **Reusable skills and templates for agent work:** [workflows/skills/](../workflows/skills/) and
  [workflows/templates/](../workflows/templates/), for example
  [the pre-registration template](../workflows/templates/pre-registration.md) and
  [the review gate checklist](../workflows/templates/review-gate-checklist.md).

## Prompt design and optimisation

- **The solver prompt and tool descriptions** of the current loop: `system_prompt` in
  [aether/core/tools.py](../aether/core/tools.py).
- **Prompt and turn-format experiments, each pre-registered with a falsifier:** request shape (S1), turn format (S2),
  reasoning effort (S3), an analysis turn (S4), JSON turns (S5, S6), naming rules in the prompt (P1 role experiment) and
  an independent-check prompt (P1). See [research/core/](../research/core/). Most failed, and are recorded as failed.
- **A prompt change that did help:** cache-stable context halved cost per run at equal passes
  ([N1](../research/core/CORE_N1_EFFICIENCY_AND_VERIFICATION_PREREG_20261014.md)).

## Testing and evaluating model output

- **An evaluation framework:** [harness_evals/](../harness_evals/), with grader validity checks, trial rows and
  statistics.
- **Tasks validated against known-bad states and careless agents before use:** [evals/](../evals/), and the
  catalogue of all 151 evaluations in [evals/catalogue.md](../evals/catalogue.md).
- **Auditing results row by row,** including results that overturned earlier wins:
  [workflows/case-studies/](../workflows/case-studies/) and [research/postmortems/](../research/postmortems/).

## Guardrails and hallucination management

- **False completion (the agent says it is done when it is not)** is the main subject of Gen 5's experiments: acceptance
  checks, same-model review, state verification, a requirement ledger and a reading judge. See the table in
  [research/generations/gen5.md](../research/generations/gen5.md).
- **Review without the agent's own claims** caught 15 of 18 wrong finishes, against 10 of 18 when the reviewer saw
  the claims. See [research/findings.md](../research/findings.md).
- **The No Fake Work rule** and the vision's test for harness code: [docs/no-fake-work.md](no-fake-work.md) and
  [docs/VISION.md](VISION.md).
- **Keeping benchmark and grader framing out of what the model sees,** enforced by tests:
  `tests/harness/test_model_visible_hygiene.py`.

## Understanding model behaviour

- **Outcomes are close to deterministic per model and task;** the same harness gives opposite results on two tasks
  for two models: [research/core/CORE_FAILURE_STUDY_ALL_BOARDS_20261015.md](../research/core/CORE_FAILURE_STUDY_ALL_BOARDS_20261015.md).
- **Where the error is:** reading versus constructing, traced to individual turns:
  [research/core/CORE_FIRST_DIVERGENCE_20261013.md](../research/core/CORE_FIRST_DIVERGENCE_20261013.md) and the P1
  decision-probe results in [research/core/](../research/core/).
- **A self-audit of our own questions:** [research/core/CORE_SELF_AUDIT_RESEARCH_QUESTIONS_20261017.md](../research/core/CORE_SELF_AUDIT_RESEARCH_QUESTIONS_20261017.md).

## Turning requirements into specifications

- **Every experiment states its question, prediction and falsifier before it runs,** then appends results without
  changing the predictions: the pre-registrations in [research/core/](../research/core/).
- **How a principal's goals became work packets, review gates and handoffs** for agents:
  [workflows/README.md](../workflows/README.md) and [workflows/governance.md](../workflows/governance.md).
- **Decisions and why they were made:** [notebook/DECISIONS.md](../notebook/DECISIONS.md).
