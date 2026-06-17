# Skills

Operator skills and reusable handoff patterns.

This section is the working entry point for loop engineering: the skills used
to launch threads, run jobs, implement changes, repair reviews, synthesize
evidence, and stop safely. It describes operator method, not app runtime
features.

For the compact capability split, see [Loop engineering](../loop-engineering.md).
For the staged project lifecycle, see [Stages](../stages/).

## Skill Policy

Skills are the primary public proof of AI-native engineering. They encode the
repeatable operating method: when to use a loop, what evidence is required,
what the stop condition is, and what a handoff must contain.

Prompts are secondary. A prompt belongs in the repo only when it represents a
reusable specialist role. If it is merely instructions for one task, it should
be a task packet, not part of the prompt library.

The public skill set is intentionally compact:

- 17 core operator skills cover research, synthesis, evals, implementation,
  review, publication, and continuity;
- deep-synthesis specialist skills are available when a synthesis wave needs
  that role, but they are not the default starting point;
- references and scripts support skills; they are not additional headline
  skills.

## Index

### Core Operator Skills

- [Analyze agent runs](analyze-agent-runs.md) - causal run analysis with an
  evidence ladder, validity checks, and fake-progress diagnosis
- [Loop orchestrator skill](loop-orchestrator.md) - bounded orchestration,
  handoff, stop conditions, and control-map discipline
- [Hooks and automations](hooks-and-automations.md) - decide what belongs in
  hooks, scheduled automations, skills, and memory
- [Run and VM operations](run-vm-operations.md) - launch, monitor, collect, and
  tear down long-running local, container, or VM runs
- [Context, memory, and token economy](context-memory-token-economy.md) -
  context tiering, durable handoffs, compaction-safe memory, and budget control
- [Code review closeout](code-review-closeout.md) - primary code-review gate
  with helper-first and manual-fallback paths
- [Adversarial code review closeout](adversarial-code-review-closeout.md) -
  manual adversarial review when the helper is unavailable
- [Review repair loop](review-repair-loop.md) - convert findings into accepted
  fixes, evidence rebuttals, or follow-up work
- [Agentic TDD and verification](agentic-tdd-and-verification.md) - freeze
  tests/evals before implementation and prevent agent cheating or drift
- [Eval-first implementation slice](eval-first-implementation-slice.md) -
  preregister the target eval, sentinel set, and keep/kill decision before
  coding
- [Tournament runner](tournament-runner.md) - compare variants, routes, prompts,
  tools, or configs under one fixed score surface
- [Implementation loop](implementation-loop.md) - move from contract to
  verified diff through maker/checker repair loops
- [Bounded implementation slice](bounded-implementation-slice.md) - execute a
  contract-complete worker packet and hand it back to the orchestrator
- [Provenance and publication review](provenance-publication-review.md) -
  public-safe adaptation and publication guardrails
- [Synthesis and adjudication](synthesis-adjudication.md) - evidence inventory,
  claim ladder, contradictions, and public-safe closeout
- [Deep synthesis loop](deep-synthesis-loop.md) - orchestrate multi-lane
  synthesis with specialist threads, contradiction review, and closure

### Specialist Deep Synthesis Skills

- [Deep Synthesis family](deep-synthesis.md) - phase-specific public-safe
  skills for coverage, inventory, mechanisms, failures, dossiers, cases, and
  closure
