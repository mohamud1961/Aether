# Agentic Engineer Capability Map

This is the reviewer map for the workflow layer. It connects the public
HarnessEng artifacts to the practical skills expected of an agentic engineer:
orchestrating models, designing reusable skills, managing context, verifying
work, and shipping clean slices without letting automation redefine success.

The map is deliberately evidence-shaped. It points to concrete skills,
templates, case studies, eval surfaces, and handoff patterns rather than
claiming that private threads or raw traces are themselves public proof.

## Reviewer Signal

| Capability | Public proof surface | What it demonstrates |
|---|---|---|
| AI-native project lifecycle | [stages](stages/), [AI-native operating system](ai-native-engineering-operating-system.md) | Research gathering, synthesis, evals/variants, implementation, review, and continuity as one governed build loop |
| Agent orchestration | [loop-orchestrator](skills/loop-orchestrator.md), [governed multi-agent model](orchestration/governed-multi-agent-model.md), [orchestration ledger case study](loop-engineering/orchestration-ledger-case-study.md) | Bounded goals, worker scopes, handoffs, escape hatches, integration review |
| Loop engineering | [loop engineering](loop-engineering.md), [loop engineering README](loop-engineering/README.md), [multi-thread handoff](templates/multi-thread-handoff.md) | Orchestrator-owned loops, specialist thread launches, nested subagents, review threads, memory, stop rules |
| Run operations | [run and VM operations](skills/run-vm-operations.md), [hooks and automations](skills/hooks-and-automations.md) | Long-running run leases, monitor cadence, artifact capture, teardown, scheduled wakeups |
| Skill and prompt authoring | [skills/](skills/), [prompts/](prompts/) | Reusable operating procedures, specialist role prompts, shared policies |
| Context, memory, and token economy | [context-memory-token-economy](skills/context-memory-token-economy.md), [multi-thread handoff](templates/multi-thread-handoff.md) | Context tiering, durable filesystem memory, compaction-safe handoffs, budget control |
| Agentic TDD and verification | [agentic-tdd-and-verification](skills/agentic-tdd-and-verification.md), [eval-first implementation slice](skills/eval-first-implementation-slice.md) | Test/eval first, known-bad cases, verifier discipline, anti-cheating controls |
| Implementation loops | [implementation loop](skills/implementation-loop.md), [bounded implementation slice](skills/bounded-implementation-slice.md) | Contract freeze, maker/checker repair loop, focused checks, scoped handoff |
| Code review reflex | [code-review closeout](skills/code-review-closeout.md), [adversarial closeout](skills/adversarial-code-review-closeout.md) | Findings-first review, accepted/rejected finding disposition, rerun discipline |
| Eval frameworks | [eval workflow notes](evals/README.md), [eval_suite/](../eval_suite/) | Task packs, graders, result rows, boards, scoreboards, sentinels |
| Experiment governance | [eval design and variant governance](skills/eval-design-and-variant-governance.md), [tournament runner](skills/tournament-runner.md), [variants/](../variants/) | Predicted deltas, regression sentinels, fixed candidate matrices, keep/kill decisions |
| Deep synthesis | [deep synthesis loop](skills/deep-synthesis-loop.md), [deep synthesis family](skills/deep-synthesis.md) | Multi-lane evidence work, contradiction review, accepted claims, public-safe closure |
| Git and clean slices | [git commit slicing](skills/git-commit-slicing.md) | Coherent commits, dirty-tree awareness, handoff-ready diffs |
| Honest communication | [handoff writing](skills/handoff-writing.md), [codex goal governance](orchestration/codex-goal-governance.md) | Complete/partial/blocked statuses, evidence paths, external-state accounting |
| Source and publication hygiene | [provenance publication review](skills/provenance-publication-review.md), [publication gap list](../docs/publication/publication_gap_list.md) | Public/private boundary control, third-party notice gaps, overclaim prevention |

## The Proof Path

For a fast review, read in this order:

1. [Loop engineering](loop-engineering.md) for the public taxonomy and the
   fleet-loop model.
2. [Stages](stages/) for the project lifecycle from research gathering through
   continuity.
3. [Loop engineering README](loop-engineering/README.md) for the full
   run-to-promotion loop and evidence artifacts.
4. [Loop orchestrator](skills/loop-orchestrator.md) for the control-map,
   launch, handoff, memory, and stop-rule skill.
5. [Run and VM operations](skills/run-vm-operations.md) plus
   [hooks and automations](skills/hooks-and-automations.md) for run lifecycle
   and loop heartbeat.
6. [Context, memory, and token economy](skills/context-memory-token-economy.md)
   for how long-running agent work stays coherent.
7. [Agentic TDD and verification](skills/agentic-tdd-and-verification.md) for
   the anti-cheating test/eval discipline.
8. [Implementation loop](skills/implementation-loop.md) and
   [tournament runner](skills/tournament-runner.md) for patch and comparison
   loops.
9. [AI-native engineering operating system](ai-native-engineering-operating-system.md) for the
   repo-wide method.
10. [eval_suite/](../eval_suite/) and [variants/](../variants/) for the
   code-bearing proof surfaces that the workflows govern.

## Claims Kept Honest

This folder is a workflow operating layer, not a private transcript dump. It does not
publish raw provider logs, hidden graders, task answer keys, credentials, or
private worker histories. It also does not claim eval dominance or broad
production readiness. The public claim is narrower and stronger: this repo
shows a disciplined operating system for using agents as serious engineering
partners.
