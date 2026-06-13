# Loop Engineering

Loop engineering is the operating system for using agents as serious
engineering partners. It is the shift from prompting one agent to designing
the system that prompts, checks, routes, and improves agents on your behalf.

The core pattern is not "ask one model to try again." It is an orchestrated
thread loop:

1. an orchestrator thread owns the task, gathers context, freezes scope, and
   defines the evidence contract;
2. the orchestrator launches specialist worker threads with bounded packets;
3. each specialist may run its own subagents for search, implementation,
   analysis, or review support;
4. specialists hand results back to the orchestrator with evidence, risks,
   validation, and external-state status;
5. the orchestrator integrates the handoffs, either reviews the work directly
   or launches a review thread;
6. review findings become fixes, rejected findings, or follow-up packets;
7. the loop reruns with updated evidence until the change is promoted, killed,
   parked, or honestly blocked.

This is the capability HarnessEng is meant to operate: AI-native engineering
as a governed orchestration loop, not a pile of prompts.

## Definition

A loop is a repeatable feedback system:

`discover -> plan -> execute -> verify -> decide -> remember`

The important design question is not "what prompt should I write?" It is:

- what starts the loop;
- what context and skills the agent receives;
- which worker owns each part of the job;
- what objective signal checks the work;
- who reviews the result;
- where memory is written;
- when the loop stops, retries, escalates, or hands back to a human.

That is why loop engineering belongs above ordinary prompt engineering. A
prompt asks for an output. A loop designs a small production system for turning
imperfect outputs into verified progress.

## The Loop

The public loop has four stacked layers.

| Layer | Purpose | Typical owner | Stop signal |
|---|---|---|---|
| Agent loop | One agent uses tools until a bounded task is done | Specialist or subagent | Tool result, test result, artifact exists |
| Verification loop | A maker's output is checked and retried if it fails | Specialist plus reviewer/checker | Rubric, test, eval, lint, score, diff check |
| Orchestration loop | An owner thread delegates, receives handoffs, integrates, and redirects | Orchestrator thread | Integrated evidence decision |
| Improvement loop | Run evidence changes the next variant, skill, prompt, tool, or guardrail | Orchestrator plus review thread | Keep, kill, iterate, park, or block |

The outer orchestration loop is:

`orchestrate -> delegate -> integrate -> review -> decide -> re-dispatch`

The improvement loop inside it is:

`run -> analyze -> hypothesize -> eval -> implement -> validate -> promote/kill`

Together they support the high-value cadence:

`variant run -> trace analysis -> review -> improvement proposal -> patch -> rerun -> scoreboard decision`

The point is repeatability. A strong loop makes it natural to run another
iteration without losing context, silently changing success criteria, or
letting one worker's confident summary become the source of truth.

## Fleet Topology

The strongest loop in this repo is a fleet loop:

```text
Human owner
  |
  v
Orchestrator thread
  |-- context map, scope, evidence contract, stop conditions
  |-- specialist thread: analysis
  |     `-- subagents: trace inventory, failure matrix, evidence extraction
  |-- specialist thread: eval design
  |     `-- subagents: fixture review, grader sketch, known-bad check
  |-- specialist thread: implementation
  |     `-- subagents: focused code search, test authoring, local QA
  |-- specialist thread: publication/provenance
  |     `-- subagents: privacy scan, source-boundary scan
  `-- review thread
        `-- adversarial pass, accepted/rejected findings, rerun demand
```

The orchestrator is not just a manager. It is the control surface that keeps
the loop from becoming a swarm:

- it owns the task and decides what counts as evidence;
- it assigns specialist packets with bounded write scopes;
- it requires handoffs back to the originating thread;
- it reconciles conflicting claims against the live tree;
- it chooses whether to self-review or launch a review thread;
- it records memory so the next cycle can continue without re-deriving the
  entire project.

This is especially strong for repeated improvement work:

`variant run -> analyze -> review -> propose improvement -> apply -> rerun -> decide`

The same shape works for documentation, code review repair, source migration,
CI triage, issue maintenance, and public/private publication cleanup. The loop
changes the role of the engineer from "type the next prompt" to "design and
govern the system that decides the next prompt."

## Thread Architecture

| Role | Responsibility | Output |
|---|---|---|
| Orchestrator thread | Owns the objective, context map, scope, evidence contract, delegation plan, and final decision | Control map, worker packets, integrated closeout |
| Specialist thread | Owns one bounded slice such as analysis, implementation, eval design, provenance review, or docs packaging | Worker handoff with files, tests, evidence, risks |
| Specialist subagents | Perform narrow support work under a specialist thread, such as file inventory, focused search, or matrix construction | Support notes folded into the specialist handoff |
| Review thread | Tries to disprove completion, inspects the live diff or evidence bundle, and forces accepted/rejected finding disposition | Review report and repair recommendations |
| Historian / ledger path | Preserves material decisions, failures, evidence, and follow-up state | Raw ledger handoff or durable continuation note |

This is why handoffs matter. The orchestrator cannot close a loop from vibes,
and files appearing in the checkout are not a handoff. Work becomes loop-ready
when the receiving thread can continue without replaying the full history.

## Six Control-Plane Primitives

The public loop-engineering story has six practical building blocks.

| Primitive | What it does | HarnessEng surface |
|---|---|---|
| Automations | Provide the heartbeat: scheduled triage, monitors, reruns, report refresh, follow-up wakeups | `workflows/skills/loop-orchestrator.md`, continuation notes |
| Worktrees | Isolate parallel edits so workers do not collide | branch/worktree handoff conventions, git-slicing skill |
| Skills | Encode reusable project knowledge and specialist behavior | `workflows/skills/` |
| Connectors/plugins | Let the loop interact with real tools rather than only local files | GitHub/Linear/browser/document workflows where available |
| Subagents | Separate maker, checker, searcher, analyst, and reviewer roles | governed multi-agent model and handoff templates |
| Memory | Preserve state outside a single context window | handoffs, continuation files, ledger inbox, scoreboards, decision logs |

Hooks are a seventh supporting mechanism: they enforce repeated policy around
tool use, permission checks, audit capture, and external-state accounting. They
belong in the runtime boundary, while the orchestrator owns judgment and
meaning.

## Closed Loops First

Good loops are bounded before they are autonomous.

Closed loops have:

- a clear goal;
- a known work surface;
- objective checks;
- iteration caps;
- a handoff path when stuck;
- a memory file or ledger entry that survives the run.

Open loops are useful for exploration, but they are expensive and easier to
mislead. A broad instruction like "make this better" gives the loop no stable
score to chase. A stronger loop says: "run this board, classify failures,
patch one failure class, rerun target plus sentinels, and stop after three
attempts or a clear keep/kill decision."

The rule of thumb is simple: automate the parts with objective feedback, keep
human taste and high-impact direction in the loop, and make every retry pay
for itself with new evidence.

## What Makes It AI-Native

- Thread launches are first-class orchestration moves, not side chats.
- Skills encode repeatable specialist behavior: run analysis, eval design,
  implementation slices, review closeout, provenance review, handoff writing,
  and context/memory management.
- Hooks enforce always-on policy: permission checks, audit capture, argument
  logging, external-state tracking, and unsafe-action denial.
- Automations handle repeatable loop mechanics: scheduled reruns, monitors,
  receipt capture, smoke checks, scoreboard refresh, and follow-up wakeups.
- Handoffs make long-running work compaction-safe and cross-thread safe.
- Review gates turn "looks done" into an evidence decision.
- Iteration caps, token budgets, and stop states prevent loopmaxxing: retries
  that burn context without adding evidence.
- The engineer remains accountable for direction, taste, and final acceptance.

The result is a human-amplifying loop: the human sets direction and taste; the
orchestrator controls the system; specialists do focused work; reviewers attack
weak claims; automation keeps the repetitive checks moving.

## Concrete Loop Recipes

### Variant-Improvement Loop

1. Orchestrator chooses one failing lane and freezes the current score.
2. Analysis specialist classifies the failure and cites evidence.
3. Eval specialist confirms the target row, known-bad case, and sentinels.
4. Implementation specialist applies one bounded mechanism.
5. Review thread attacks the diff and the claim.
6. Orchestrator reruns target plus sentinels.
7. Scoreboard decides: keep, kill, iterate, park, or block.

### Review-Repair Loop

1. Orchestrator receives a diff and review gate.
2. Review thread returns findings with severity and evidence.
3. Implementation specialist applies accepted findings only.
4. Tests and focused checks rerun.
5. Remaining findings are either fixed, rebutted with evidence, or promoted to
   follow-up work.
6. Orchestrator closes with a handoff that names residual risk.

### Maintenance Loop

1. Automation wakes on a cadence or event.
2. Triage skill reads issues, checks, reports, or repo state.
3. Orchestrator creates bounded packets for real findings only.
4. Specialists work in isolated scopes.
5. Review and validation gate the result.
6. Memory updates so the next wakeup starts from the current state.

### Publication-Readiness Loop

1. Provenance/publication specialist scans public surfaces.
2. Privacy boundary findings become rewrite or exclusion packets.
3. Review thread checks for overclaiming and missing notices.
4. Orchestrator commits clean public slices and records blockers.
5. Raw/private assets stay out of the public package or are explicitly
   withheld.

## Product And Application-Facing Claims

These are the capabilities that belong in the public application story:

- governed multi-thread orchestration with explicit worker handoffs;
- specialist skills for planning, analysis, implementation, review, and
  publication hygiene;
- loop mechanics for variant runs, review repair, maintenance, and publication
  readiness;
- evidence-first promotion with target evals, known-bad cases, sentinels, and
  scoreboards;
- hooks and automations that keep the loop observable and repeatable;
- honest stop states: complete, partial, blocked, invalid, or out of scope.
- token and comprehension controls that prevent unattended churn from becoming
  technical debt.

## Costs And Failure Modes

Loop engineering is powerful because it compounds judgment. It is dangerous
when it replaces judgment.

Known failure modes:

- fuzzy goals that create endless retries;
- maker/checker collapse, where the same agent grades its own work;
- context drift across long loops;
- token burn without new evidence;
- review theater with no accepted/rejected finding disposition;
- hidden external state left running after a worker finishes;
- comprehension debt, where the repo changes faster than the human owner can
  understand.

The countermeasures are the point of the workflow folder: bounded packets,
objective checks, independent review, durable memory, iteration caps,
explicit handoffs, and a human owner who still decides what matters.

## Internal Workflow Skills

These are repo-side operating skills used to run the loop:

- `loop-orchestrator` for the control map and delegation plan;
- `hooks-and-automations` for deciding what belongs in hooks, scheduled
  wakeups, recurring monitors, and durable memory;
- `run-vm-operations` for long-running local, container, and VM run lifecycle;
- `task-briefing-and-planning` for worker packet design;
- `analyze-agent-runs` for trace and failure analysis;
- `eval-design-and-variant-governance` for proper eval and variant admission;
- `tournament-runner` for candidate matrices, fixed score surfaces, invalid
  accounting, and keep/kill decisions;
- `implementation-loop` for maker/checker implementation repair loops;
- `bounded-implementation-slice` for contract-complete worker execution;
- `handoff-writing` for orchestrator-ready result transfer;
- `review-repair-loop` for accepted/rejected finding disposition and focused
  reruns;
- `code-review-closeout` and `adversarial-code-review-closeout` for review
  gates and finding disposition;
- `context-memory-token-economy` for durable memory, compaction, and thread
  continuity;
- `deep-synthesis-loop` for multi-lane evidence synthesis, contradiction
  review, and closure;
- `provenance-publication-review` for public/private boundary control.

## Future / Optional Capabilities

These stay future-facing until backed by public evidence:

- richer dashboards for loop state, worker queues, and scoreboards;
- automatic thread routing from failure class to specialist skill;
- scheduled rerun monitors and follow-up wakeups for long experiments;
- deeper replay and cross-run comparison tools;
- broader public case-study coverage across more failure families.

## What The Public Story Excludes

- raw private traces, hidden graders, and private-eval-sensitive artifacts;
- credentials, personal history, or internal-only mistake narratives;
- claims that a private worker thread is itself a public product demo;
- any implication that the public docs expose the full private control plane.

## How To Use The Rest Of The Workflow Layer

- [AI-native engineering operating system](ai-native-engineering-operating-system.md)
- [Loop engineering README](loop-engineering/README.md)
- [Agentic engineer capability map](agentic-engineer-capability-map.md)
- [Loop orchestrator skill](skills/loop-orchestrator.md)
- [Hooks and automations](skills/hooks-and-automations.md)
- [Run and VM operations](skills/run-vm-operations.md)
- [Task briefing and planning](skills/task-briefing-and-planning.md)
- [Analyze agent runs](skills/analyze-agent-runs.md)
- [Tournament runner](skills/tournament-runner.md)
- [Eval design and variant governance](skills/eval-design-and-variant-governance.md)
- [Implementation loop](skills/implementation-loop.md)
- [Bounded implementation slice](skills/bounded-implementation-slice.md)
- [Review repair loop](skills/review-repair-loop.md)
- [Handoff writing](skills/handoff-writing.md)
- [Context, memory, and token economy](skills/context-memory-token-economy.md)
- [Deep synthesis loop](skills/deep-synthesis-loop.md)
- [Code review closeout](skills/code-review-closeout.md)
- [Adversarial code review closeout](skills/adversarial-code-review-closeout.md)
- [Provenance and publication review](skills/provenance-publication-review.md)
- [Workflow templates](templates/README.md)
