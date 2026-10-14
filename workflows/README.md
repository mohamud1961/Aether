# Workflows: running research with an agent fleet

One principal ran this whole programme with coding agents doing the implementation, analysis and
auditing: five harness generations, 151 evaluations and the research. The workflow is itself a
multi-agent system, with roles, work packets, review gates, concurrency limits, failure modes and
fixes. This page describes that system and where human judgment sat inside it.

**Scale.** About 5,800 commits of real work across 1,641 branches and refs, plus 23,658 automation
commits from scheduled agent loops. Three orchestration regimes over eight months (Codex-led, then
ChatGPT takeovers with scheduled wake-ups, then Claude orchestrating parallel subagents).

## The system

```
            principal: questions, standards, budgets, sealed predictions, keep/kill
                                         │
                                         ▼
     orchestrator agent ── control map, packet dispatch, choosing the review gate per risk
            │                            │                                │
            ▼                            ▼                                ▼
     worker agents             independent verifier /             automation loops
     one bounded packet        audit agent                        dispatch, receipts,
     each, own worktree,       tries to disprove completion       scoreboards, reruns
     named checks, handoff     from task state, read-only
            │                            │                                │
            └──────────── evidence: commits, trial rows, traces, notebook entries ─┘
```

| Role | Owns | Never owns |
|---|---|---|
| Principal | The question, the standard of evidence, budgets, pre-registrations, promotion and kill decisions | Day-to-day code |
| Orchestrator | Decomposition into packets, dispatch, intake of handoffs, the review gate for each change | Reviewing its own work |
| Worker | One packet: owned files, named checks, a handoff with evidence | Scope or architecture changes, promotion |
| Verifier / audit agent | Disproving completion from task-visible state | Doing the work it checks |
| Automation | Scheduling, receipts, scoreboards | What a result means |

## How a piece of work moves

1. **Question → plan.** Every non-trivial change starts with a current-state map: what exists, what
   matches, what violates the design, what is missing, and the smallest next step. Building without the
   map is grounds for rejecting the work.
2. **Plan → packets.** The orchestrator splits work into packets with owned files and named checks. One
   writer per branch; parallel workers get their own worktrees.
3. **Packet → evidence.** A packet is done only when its checks ran and the evidence is attached:
   commands, outputs, trial rows. "Imports succeed" is not "works".
4. **Evidence → review.** The review gate scales with risk, from a self-check up to an independent
   adversarial audit that reads the files behind every green result.
5. **Review → decision.** Promotion needs scored evidence against a pre-registered bar, never a
   trajectory that looks good.

## Where the principal's judgment changed the outcome

| When | Decision | Why it mattered |
|---|---|---|
| Jul 2026 | Rejected a reported 78.5% batch win and ordered a row-level audit | The win was a rate-limit storm; the audit produced the backoff and invalid-row rules |
| Jul 2026 | Introduced "No Fake Work" after a handoff called stub files a working dependency | Every later "done" claim had to show real execution |
| Jun–Aug 2026 | Downgraded the adaptive-profile claim after the single-task win did not reproduce | The architect was later removed from the production path |
| Sep 2026 | Required a single-model comparison for the harness test | Isolated what the harness adds from what a better model adds |
| Oct 2026 | Sealed the held-out prediction before any trial and kept held-out tasks closed to agents | The falsifier could fire, and it did: 5/9 vs 4/6 |
| Oct 2026 | Recorded the falsified claim as falsified, and moved to a leaner core | Negative results stayed in the record |

## Failure modes of an agent fleet, and the fixes

| Failure | What happened | Fix |
|---|---|---|
| Fake completion | Stubs and shims made checks green | No Fake Work: every check must be falsifiable by a known-bad |
| Self-review | Agents approved their own work | Reviewer independent of the author; claim-free review where possible |
| Overlapping writers | Parallel agents edited the same files | One writer per branch; worktree per worker |
| Fan-out | One orchestration run launched about 30 agents at once | Hard concurrency cap in the orchestration script |
| Shared provider quota | Parallel agents starved each other's model calls | Concurrency cap per deployment; invalid-row accounting |
| Silent drift between agents | Handoffs lost state between sessions | Handoff template with a delivery receipt and explicit open items |
| Unattended compute | Long runs continued with no owner | Lease-and-reaper rule for paid compute |

## Read next

| Page | What it covers |
|---|---|
| [governance.md](governance.md) | Twelve rules, the incident behind each, and whether it worked |
| [orchestration.md](orchestration.md) | The three orchestration regimes, why each changed, and the failures met |
| [case-studies/](case-studies/) | An audit that overturned a win; a falsifier that fired; a row-level audit that found 11 defects |
| [skills/](skills/) | Eight working instructions given to agents (trace analysis, bounded slices, review loops, handoffs) |
| [templates/](templates/) | Pre-registration, review gate, handoff and notebook entry |
