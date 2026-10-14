# Gen 1: planner memory

**What this is:** The first harness line. A planner held the task's plan and state outside a stateless coding agent, and a repository context tool supplied the rest.
**Key result:** No scored result was recorded for this line. Its evaluations were a bug-fix task set without recorded scores, a synthetic validator run, and a determinism audit of an external benchmark.
**Why it matters:** Two defects found here shaped every later line: a verifier that could read the answers, and a check that passed when its signals were missing.

## Core idea

A stateless model forgets. A planner keeps the plan, the phase and the evidence, and feeds each step back to the worker. Later versions replaced the planner with a deterministic context tool, then with a role pipeline, then with a container-isolated verifier.

## Design

```
planner (phase plan, event log)  ──►  worker agent (stateless per turn)
        ▲                                   │
        └──── context tool / phase gate ◄───┘
                                            ▼
                         verifier container (no oracle mount)
```

- **Planner.** Phase plans and a hash-chained event log. Defaults failed closed.
- **Context tool.** An MCP `context` tool that returned a budgeted slice of the repository. A token saving of 40 to 50 percent was claimed; no measurement was recorded.
- **Role pre-phase.** A nine-role pipeline designed the harness before any code was written.
- **Verifier.** A container with no mount of the task's answers.

## Evaluations

| Eval | What it measured | Result |
|---|---|---|
| Bug-fix task set (21 task IDs across five open-source repositories) | Whether a context tool helps bug fixes | 138 sessions, many repeats of one prompt. No grader and no scores recorded. |
| Compliance validator (synthetic run) | Whether the planner records context slices and conflict decisions | Validator built. Run on a synthetic report only. |
| Determinism audit of an external benchmark | Whether the harness gives the same result on repeat | The same task passed in 26 steps and failed in a 50-step read-only loop. Cause: a premature transition from exploration to verification. |
| Property checks on the harness | Whether checks fail closed | A phase check passed with its signals missing. |

The determinism audit found 571 summary files on one count and 508 on the other. A recount was never recorded, so the total is not used here.

## What was learned

- The verifier could read the answers because the oracle was mounted into its container. Verifier isolation became a fixed rule.
- Tool schemas were filtered to run-only commands, which hid the tools the worker needed.
- A check that passes when a signal is missing is worse than no check.
- A verifier that is isolated from the answers is the only durable idea from this line.

## Why it was superseded

The line stopped in late February 2026 after three pivots (22 December 2025, 11 January 2026 and 20 February 2026). No score existed to justify keeping it, and each defect found was in its planner or gate design.

