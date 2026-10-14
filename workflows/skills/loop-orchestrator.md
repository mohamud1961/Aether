# Loop orchestrator

Use this when a task needs a bounded agentic loop rather than one prompt or an ad hoc sequence. The orchestrator turns a request into a controlled run with a clear authority map, specialist packets, a short evidence chain, and a truthful stop condition.

## Governing question

> Who owns the task, which specialists act, what evidence counts, and how do we know when to stop or rerun?

## Loop

`discover -> plan -> launch -> receive -> integrate -> verify -> review -> decide -> remember`

The orchestrator does not have to do every step. It decides which specialist acts, what each owns, what evidence must come back, and when the loop has enough signal.

Be suspicious of two failures:

- **Under-orchestration:** many agents act, and nobody owns the integrated truth.
- **Over-looping:** retries continue after they stop producing new evidence.

## Control map

Write the smallest useful control map before launching anyone:

```text
objective:
scope:
out_of_scope:
context_sources:
specialist_threads:
subagent_permissions:
review_gate:
memory_paths:
success_signal:
retry_cap:
stop_conditions:
handoff_required:
external_state_policy:
```

The map can change as evidence arrives. Success cannot be silently lowered. A material scope change becomes a partial or blocked closeout, or a follow-up task, never hidden drift.

## Launch rules

- Launch a specialist only when its packet has a bounded output.
- Give each one an owner boundary and a handoff format.
- Let subagents work only inside a specialist's packet.
- Use separate branches or worktrees for parallel code edits.
- Set the retry cap before launch.
- Record where memory will live before the first worker starts.

## Specialists

| Specialist | Launch when | Expected handoff |
|---|---|---|
| Analysis | A run needs causal reconstruction | Validity verdict, failure class, evidence paths |
| Eval design | A failure needs a test surface first | Contract, grader plan, baseline, known-bad case |
| Implementation | The packet is bounded and complete | Files changed, tests run, risks |
| Review | A claim or diff could be disproved | Findings with dispositions |
| Publication check | Public wording or a privacy boundary matters | Sanitised wording, withheld list |

## Intake

Do not accept a worker result until you can answer:

- Did the worker stay inside its packet?
- Which requirements are complete, partial, blocked, or invalid?
- Which files changed, and who owns them?
- Which commands or paths verify the claim?
- Does any process or external state remain active?
- What is the next action: review, repair, rerun, promote, kill, or park?

## Stop rules

Stop or hand back when:

- the success signal is met and review is complete;
- the retry cap is reached;
- failures repeat with no new evidence;
- a needed dependency is unavailable;
- the work needs a material scope change;
- the next decision needs human judgement or sensitive access;
- continuing would hide uncertainty rather than reduce it.

Valid end states: complete, partial, blocked, invalid due to environment, out of scope, parked, killed, follow-up recommended. A truthful partial is better than an expensive loop that looks autonomous.

## Rule of split

- Judgement and interpretation stay in the skill.
- Anything that must happen before or after every tool use goes in a hook.
- Deterministic, repeated work is automated.
- Work needing independent scepticism goes to a review thread.
- Narrow expertise goes to a specialist thread.
- Taste, direction, and sensitive approval stay with a human.

## Memory

Keep outside the context window: the objective, packets and their owners, accepted facts and rejected claims, evidence paths, review dispositions, blockers, and the next exact action. The format matters less than the rule: the next run must continue without re-inventing what already happened.

Related: [handoff writing](handoff-writing.md), [code review closeout](code-review-closeout.md), [bounded implementation slice](bounded-implementation-slice.md).
