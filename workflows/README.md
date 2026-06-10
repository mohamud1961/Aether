# Workflows

The AI-native engineering operating layer. This folder is not a transcript
gallery; it is the loop engineering system used to plan, launch, review,
repair, rerun, and close real agentic work.

---

## The Loop

> `orchestrate -> delegate -> integrate -> review -> decide -> re-dispatch`
>
> inside that: `run -> analyze -> hypothesize -> eval -> implement -> validate -> promote/kill`

Every stage has an operator skill, a handoff shape, and a stop condition. The
headline operating manual is **[loop-engineering/](loop-engineering/)**.

For a stage-by-stage view, start with [stages/](stages/). For concrete ways to
use the workflow layer, start with [use-cases/](use-cases/).

For a role-oriented reviewer path, start with
[agentic-engineer-capability-map.md](agentic-engineer-capability-map.md). It
maps the workflow artifacts to concrete agentic engineering capabilities:
orchestration, skill authoring, context/memory management, agentic TDD,
review gates, eval systems, and clean handoffs.

---

## Sections

### [stages/](stages/) — project lifecycle

The AI-native build lifecycle, organized by the real project path:

1. research gathering;
2. deep synthesis;
3. evals and variants;
4. implementation and runtime slices;
5. review, repair, and publication;
6. loop operations and continuity.

Each stage is broken into `skills/`, `prompts/`, and `artifacts/` subfolders so
the repo shows how AI was used at that stage without dumping every asset into
one list.

### [phases/](phases/) — compact phase reference

A compact execution-phase table retained for quick routing and backward links.

### [use-cases/](use-cases/) — practical playbooks

Use-case pages for common reviewer and operator questions:

- [Eval-driven development](use-cases/eval-driven-development.md)
- [Runtime capability slice](use-cases/runtime-capability-slice.md)
- [Multi-agent orchestration](use-cases/multi-agent-orchestration.md)
- [Deep synthesis loop](use-cases/deep-synthesis-loop.md)

### [agentic-engineer-capability-map.md](agentic-engineer-capability-map.md) — reviewer map

The fast proof path for an agentic engineering reviewer. It maps role-critical
capabilities to concrete public artifacts and makes clear which claims are
supported by code, evals, workflows, and handoffs.

### [loop-engineering/](loop-engineering/) — operating manual

The loop operating folder. Contains:

- A [README](loop-engineering/README.md) that walks every loop stage with
  skills and evidence artifacts linked at each step.
- **Orchestration ledger case study:** a sanitized 32-worker build showing
  contract-complete worker packets, escape-hatch use, prompt-debt tracking,
  and mid-build acceptance standard tightening.
- **Hour-zero contracts example:** the interface freeze discipline that prevents
  integration drift across parallel workers.
- **Run analysis case study:** evidence freeze, validity verdict before any
  capability analysis, and a causal family taxonomy (F1–F7) with
  competing-hypothesis rejection.
- **Decision log example:** named orchestration decisions with rationale and
  consequence.
- **Pre-milestone handoff example:** partial-complete status, finding-by-finding
  disposition, blocked gate accounting, and adversarial rebuttal.

See also: [loop-engineering.md](loop-engineering.md) — the concise public
taxonomy (what is claimed, what is internal, what is future).

### [skills/](skills/) — operator skills

Reusable, reviewer-facing workflow skills. Each has a governing question,
step-by-step workflow, output contract, and guardrails.

Skills are the main public surface. Prompts support the skills; they are not the
portfolio by themselves.

| Skill | Loop stage | Purpose |
|---|---|---|
| [loop-orchestrator.md](skills/loop-orchestrator.md) | Run | Set up the control map, dispatch workers, use escape hatches |
| [hooks-and-automations.md](skills/hooks-and-automations.md) | Run | Decide what belongs in hooks, scheduled automations, skills, and memory |
| [run-vm-operations.md](skills/run-vm-operations.md) | Run → Validate | Launch, monitor, collect, and tear down long-running local, container, or VM runs |
| [analyze-agent-runs.md](skills/analyze-agent-runs.md) | Analyze | 11-step run analysis: evidence freeze, fake-progress detection, harness component evaluation |
| [task-briefing-and-planning.md](skills/task-briefing-and-planning.md) | All | Frame tasks, choose collaboration mode, issue explicit agent callouts |
| [context-memory-token-economy.md](skills/context-memory-token-economy.md) | Run → Validate | Tier context, durable memory, handoffs, compaction, and token spend |
| [agentic-tdd-and-verification.md](skills/agentic-tdd-and-verification.md) | Eval → Validate | Freeze checks before implementation and block agent cheating/drift |
| [eval-first-implementation-slice.md](skills/eval-first-implementation-slice.md) | Eval → Implement | Define the eval contract before writing code |
| [eval-design-and-variant-governance.md](skills/eval-design-and-variant-governance.md) | Eval | Design a proper eval, create a variant seed, make the keep/kill decision |
| [tournament-runner.md](skills/tournament-runner.md) | Eval → Validate | Compare candidates under one fixed score surface with invalid-run accounting |
| [implementation-loop.md](skills/implementation-loop.md) | Implement | Move from contract to verified diff through maker/checker repair loops |
| [bounded-implementation-slice.md](skills/bounded-implementation-slice.md) | Implement | Worker-facing: receive a contract-complete packet, implement, produce a handoff |
| [git-commit-slicing.md](skills/git-commit-slicing.md) | Implement | Checkpoint work as regular, coherent commits with a clean narrative |
| [handoff-writing.md](skills/handoff-writing.md) | Validate | Produce a handoff the orchestrator can act on without reopening the full task |
| [review-repair-loop.md](skills/review-repair-loop.md) | Validate | Turn review findings into accepted fixes, evidence rebuttals, or follow-up work |
| [code-review-closeout.md](skills/code-review-closeout.md) | Validate | 4-level review gate taxonomy and closeout discipline |
| [adversarial-code-review-closeout.md](skills/adversarial-code-review-closeout.md) | Validate | Manual fallback when the automated review skill is unavailable |
| [provenance-publication-review.md](skills/provenance-publication-review.md) | Promote | Publication gate for public claims and promoted changes |
| [synthesis-adjudication.md](skills/synthesis-adjudication.md) | Analyze | Claim ladders, contradiction handling, synthesis audit |
| [deep-synthesis-loop.md](skills/deep-synthesis-loop.md) | Analyze | Orchestrate multi-lane synthesis with contradiction review and closure |
| [deep-synthesis.md](skills/deep-synthesis.md) | Analyze | Overview of the 8-member deep-synthesis specialist family |

References for analyze-agent-runs are in `skills/references/`.

### [orchestration/](orchestration/) — governance model

The governance layer for multi-agent work.

| File | Purpose |
|---|---|
| [governed-multi-agent-model.md](orchestration/governed-multi-agent-model.md) | Role hierarchy, collaboration modes, stage-aware governance |
| [principal-agent-workflow.md](orchestration/principal-agent-workflow.md) | Human-facing engagement protocol for the principal agent |
| [synthesis-team-spec.md](orchestration/synthesis-team-spec.md) | Deep-synthesis team: per-artifact cell activation, run order, specialist roles |
| [codex-goal-governance.md](orchestration/codex-goal-governance.md) | Goal governance, handoff requirements, review gates, experiment discipline |

### [prompts/](prompts/) — role prompts

Sanitized prompts for the specialist agents in the loop. See
[prompts/README.md](prompts/README.md) for the full role map.

The prompt library is intentionally small: principal agent, base task agent,
git commit agent, synthesis prep roles, and deep synthesis specialists. Use a
prompt only when it represents a reusable specialist role; otherwise encode the
method as a skill or template.

### [schemas/](schemas/) — data templates

Structured templates for failure cards, mechanism cards, variant seeds,
case studies, and task packets. See [schemas/README.md](schemas/README.md).

### [synthesis/](synthesis/) — synthesis handbook and protocols

The synthesis workflow: evidence-based multi-agent analysis for mechanism maps,
failure taxonomies, and eval implications.

- [synthesis-handbook.md](synthesis/synthesis-handbook.md)
- [synthesis-prep-checklist.md](synthesis/synthesis-prep-checklist.md)

### [templates/](templates/) — concise checklists

Repeatable checklists for specific workflow moments:
run-analysis closeout, eval-first slice, multi-thread handoff, runtime
capability provenance review, adversarial review closeout, and provenance
publication review.

### [evals/](evals/) — eval workflow notes

Eval-board and calibration workflow guidance.

### [case-studies/](case-studies/) — public case study guidance

Public case-study construction guidance. For concrete orchestration evidence,
see [loop-engineering/](loop-engineering/).

---

## How to Use This Workflow Layer

**Start with the loop operating model:**
1. Read [agentic-engineer-capability-map.md](agentic-engineer-capability-map.md)
   for the reviewer capability map.
2. Read [stages/README.md](stages/README.md) for the project lifecycle map.
3. Read [use-cases/README.md](use-cases/README.md) for task-oriented playbooks.
4. Read [loop-engineering/README.md](loop-engineering/README.md) for the
   stage-by-stage narrative.
5. Follow any link to the skill or evidence artifact for that stage.

**To see the governance model:**
6. Read [orchestration/codex-goal-governance.md](orchestration/codex-goal-governance.md)
   for the Goal governance rules.
7. Read [orchestration/governed-multi-agent-model.md](orchestration/governed-multi-agent-model.md)
   for the multi-agent role model.

**To run a skill:**
8. Pick the skill from the table above.
9. Follow its governing question, workflow, output contract, and stop rules.

**To understand the prompt family:**
10. Read [prompts/README.md](prompts/README.md) for the role map.
11. Start every deep synthesis specialist with
   [prompts/deep-synthesis-shared-policy.md](prompts/deep-synthesis-shared-policy.md).
