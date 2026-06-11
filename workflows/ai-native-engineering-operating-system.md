# AI-Native Engineering Operating System

This guide explains the public engineering method behind HarnessEng. It is a
workflow description, not a claim that every future surface is already shipped
or eval-certified.

For the compact capability split, see [Loop engineering](loop-engineering.md).
For the role-oriented proof map, see
[Agentic engineer capability map](agentic-engineer-capability-map.md).
For the project lifecycle view, see [Stages](stages/).

## The Loop

HarnessEng treats agent work as a governed loop, not a sequence of manual
prompts. The pattern is:

1. `run`
2. `analyze`
3. `hypothesize`
4. `eval`
5. `implement`
6. `validate`
7. `promote` or `kill`

The important boundary is that traces explain behavior, but promotion comes
from scored evidence. A promising run, a long trace, or a polished summary is
not enough on its own.

The full loop is thread-based:

1. an orchestrator thread owns the task, context map, scope, evidence contract,
   and stop conditions;
2. specialist threads take bounded packets for analysis, eval design,
   implementation, review, publication, or maintenance;
3. specialists can use their own subagents for narrow search, inventory,
   fixture comparison, test writing, or review support;
4. every specialist hands results back to the orchestrator with evidence,
   validation, risks, and external-state status;
5. the orchestrator integrates the live tree, launches review when useful,
   accepts or rejects findings, and decides whether to rerun, promote, kill,
   park, or block.

This is the application's strongest workflow claim: the repo demonstrates how
to build the system that prompts agents, checks agents, remembers what agents
did, and improves the next cycle.

## Capability Split

The operating story is easiest to understand when reviewers separate three
buckets:

- product / application-facing loop engineering: bounded orchestration,
  handoffs, eval-first promotion, sentinel checks, and adversarial review;
- internal AI-native engineering workflow skills: analysis, orchestration,
  briefing, handoffs, provenance, and validation patterns used to build the
  system;
- future / optional capabilities: useful next steps that remain unclaimed
  until there is evidence for them.

## What "AI-Native Engineering" Means Here

The repository is organized around several cooperating layers:

- `harness.aether2`: the runtime/control/tooling surface.
- `eval_suite/`: task packs, graders, boards, sentinels, and scoreboards.
- `workflows/`: the operator method for goals, reviews, handoffs, and analysis.
- `tracking/collab/public_repo_readiness/`: curated public handoffs that show
  what changed, how it was validated, and what remains blocked.

The system is designed so the model can act, but cannot quietly redefine
success.

## Project Lifecycle

The workflow folder now exposes the project build path directly:

1. [Research gathering](stages/01-research-gathering/) - collect source,
   trace, run, code, and eval evidence before drawing conclusions.
2. [Deep synthesis](stages/02-deep-synthesis/) - convert evidence into
   mechanism maps, failure taxonomies, contradictions, and eval implications.
3. [Evals and variants](stages/03-evals-and-variants/) - turn failure families
   into score surfaces, sentinels, variant seeds, and keep/kill decisions.
4. [Implementation and runtime](stages/04-implementation-and-runtime/) - build
   bounded runtime slices under test/eval-first contracts.
5. [Review, repair, and publication](stages/05-review-repair-and-publication/)
   - close findings, clean public/private boundaries, and publish only what is
   evidence-backed.
6. [Loop operations and continuity](stages/06-loop-operations-and-continuity/)
   - preserve memory, handoffs, state, and next actions so another agent can
   continue without reopening every thread.

For an agentic engineering reviewer, the important claim is not that the repo
used many model calls. The claim is that the repo turns model work into an
inspectable engineering system: scoped goals, durable memory, reusable skills,
eval-first implementation, review gates, handoffs, and public/private
publication boundaries.

## Loop Engineering As Leverage

The workflow layer turns loop engineering into concrete practice:

- automations and scheduled wakeups can start maintenance, triage, rerun, or
  follow-up loops;
- isolated branches or worktrees keep parallel agents from colliding;
- skills store reusable project knowledge so each loop does not start cold;
- connectors and plugins let the loop touch real tools when available;
- subagents separate maker, checker, analyst, and reviewer roles;
- memory lives in handoffs, continuation notes, scoreboards, decision logs, and
  ledger inboxes rather than only in chat context.

The operator skills now cover the recurring real cases:

- [Analyze agent runs](skills/analyze-agent-runs.md) for trace and failure
  diagnosis;
- [Implementation loop](skills/implementation-loop.md) for contract-to-diff
  repair cycles;
- [Run and VM operations](skills/run-vm-operations.md) for long-running runs,
  artifact capture, and teardown;
- [Tournament runner](skills/tournament-runner.md) for fixed candidate
  comparisons and keep/kill decisions;
- [Hooks and automations](skills/hooks-and-automations.md) for repeatable
  enforcement, scheduled wakeups, and monitors;
- [Review repair loop](skills/review-repair-loop.md) for finding disposition
  and focused reruns;
- [Deep synthesis loop](skills/deep-synthesis-loop.md) for multi-lane evidence
  work with contradiction review.

The pattern is deliberately bounded. Loops are strongest when the success
signal is objective: tests pass, eval rows improve, a review finding is fixed,
a link check clears, a public/private scan returns clean, or a scoreboard
decision is reached. When judgment or taste is required, the loop hands back
to the human owner instead of pretending autonomy is the same as correctness.

See [Loop engineering](loop-engineering.md) and
[Loop orchestrator](skills/loop-orchestrator.md).

## Governed Orchestration

HarnessEng uses bounded goals and explicit worker handoffs instead of ad hoc
"let's try stuff" delegation.

Each serious slice should name:

- objective and scope;
- entry and exit criteria;
- evidence outputs;
- stop conditions;
- review gate;
- blocked or out-of-scope escalation triggers.

Worker handoffs are expected to report:

- final status;
- completed scope;
- files changed;
- requirement disposition;
- validation commands and evidence paths;
- review findings and dispositions;
- unresolved risks;
- external-state status.

Public examples:

- [Public evidence index](../docs/publication/public_evidence_index.md)
- `tracking/collab/public_repo_readiness/documentation_packaging_handoff.md`
- `tracking/collab/public_repo_readiness/public_eval_pack_handoff.md`
- `harness/aether2/hooks/`
- `harness/aether2/tools/mcp.py`
- `harness/aether2/skills/`
- `harness/aether2/agents/`

## Eval-First Development

The repo's reset-stage rule is simple: do not promote mechanisms from vibes.
Open a failure lane only after it has a concrete eval contract or diagnostic.

The public examples are intentionally small and local:

- `eval_suite/families/filesystem/public_manifest_repair_smoke/`
- `eval_suite/families/environment/runtime_policy_hook_smoke/`
- `eval_suite/families/tooling/mcp_registry_contract_smoke/`
- `eval_suite/families/tooling/skill_loader_contract_smoke/`
- `eval_suite/families/orchestration/subagent_handoff_contract_smoke/`

Those packs show the pattern:

- task pack with a bounded contract;
- visible fixture and reference state;
- deterministic grader when feasible;
- board entry;
- example scoreboard row;
- targeted tests around the implementation slice.

Regression sentinels matter because a change that improves one lane can still
damage tool calling, verification, or handoff truthfulness somewhere else.

## Analysis Skills In The Loop

Analysis is treated as a reusable operating skill, not a one-off postmortem.
The public version is [Analyze agent runs](skills/analyze-agent-runs.md).

That skill emphasizes:

- evidence ranking over narration;
- first decisive divergence, not just final failure;
- fake-progress detection;
- explicit failure taxonomy;
- fix design tied to custom evals and sentinels.

In practice, the analysis step is what stops a team from rewarding
activity-shaped progress.

## Evaluation, Review, And Publication

The workflow stack becomes more useful when analysis feeds directly into
bounded implementation, review, and publication gates.

Public-facing examples:

- [Code review closeout](skills/code-review-closeout.md) for helper-first
  review closure with a manual fallback when the helper is unavailable;
- [Eval-first implementation slice](skills/eval-first-implementation-slice.md)
  for preregistering the target eval, baseline, ceiling, and sentinels before a
  change is coded;
- [Agentic TDD and verification](skills/agentic-tdd-and-verification.md) for
  freezing checks before implementation and blocking agent self-grading;
- [Context, memory, and token economy](skills/context-memory-token-economy.md)
  for deciding what stays live, what becomes durable handoff memory, and what
  stays private;
- [Adversarial code review closeout](skills/adversarial-code-review-closeout.md)
  for the manual adversarial variant of the review gate;
- [Provenance and publication review](skills/provenance-publication-review.md)
  for keeping source adaptation and public wording honest;
- [Deep Synthesis family](skills/deep-synthesis.md) for the phase-shaped
  coverage, inventory, mechanism, failure, dossier, case-study, adjudication,
  and closure skills used in the synthesis work;
- [Synthesis and adjudication](skills/synthesis-adjudication.md) plus
  [Synthesis handbook](synthesis/synthesis-handbook.md) for turning multiple
  analyses into one public-safe claim set.

The public templates for those slices live in `workflows/templates/` and are
intended to be concrete enough to use without exposing private execution
history.

## Aether Runtime Capability Slices With Provenance Guardrails

The public runtime slices are presented as Aether-native interfaces. The
repository's public rule is to separate:

- external subsystem study;
- owned Python implementation;
- eval evidence;
- publication readiness.

The runtime capability slices show this discipline:

- exact Python files changed;
- bounded capability scope and deferred pieces;
- validation evidence;
- explicit publication boundaries.

See:

- `docs/provenance/agent_runtime_adaptation_policy.md`
- `docs/publication/public_evidence_index.md`

The current public position is intentionally qualified: these are owned runtime
interfaces with public eval coverage, not affiliation, parity, or clone claims.

## How Evidence Prevents Fake Progress

The engineering method tries to make false confidence expensive:

- runs emit inspectable artifacts;
- evals separate valid rows from invalid environment/provider rows;
- worker handoffs must name evidence paths and unresolved risks;
- provenance notes keep source adaptation explicit;
- scoreboards and targeted tests decide keep/kill, not enthusiasm.

This is the core portfolio claim of the repo: not that every mechanism is
finished, but that the engineering system is built to surface truth early.

## Future Direction

The public story stays careful about what is already shown and what is still
aspirational.

Not yet claimed here:

- universal agent reliability;
- eval dominance;
- product-grade readiness across every workflow surface;
- private worker threads as public demos;
- full disclosure of run logs or private evaluation materials.

## Suggested Reading Order

1. `README.md`
2. `docs/publication/public_evidence_index.md`
3. `docs/architecture/public-architecture.md`
4. this guide
5. `workflows/agentic-engineer-capability-map.md`
6. `workflows/loop-engineering.md`
7. `workflows/skills/context-memory-token-economy.md`
8. `workflows/skills/agentic-tdd-and-verification.md`
9. `workflows/templates/README.md`
10. `workflows/skills/analyze-agent-runs.md`
11. [Aether runtime capability migration case study](../docs/case-studies/aether-runtime-capability-migration.md)
12. [Public manifest repair smoke case study](../docs/case-studies/public-manifest-repair-smoke.md)
13. `docs/publication/publication_gap_list.md`
