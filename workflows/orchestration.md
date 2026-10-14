# Orchestration: how the agent setup changed

The agent setup changed three times. Each change had a trigger, and each trigger is recorded. The short version: Codex-led workstreams in spring and summer, ChatGPT-led takeovers and wakeups in late summer and early autumn, then Claude orchestrating Sonnet and Haiku subagents from 8 Oct 2026.

## Phase 1: packets and Codex-led workstreams (April to August)

- **April.** Single-session prompts and a packet-based build of an evaluation factory (packets 01 to 05A, 14 to 22 Apr). About 120 synthesis sessions ran in one week (6 to 13 Apr).
- **May.** The eval-first reset (13 May) moved promotion authority from packets to scored evaluation. About 20 worker prompts were used in one day (21 May). An orchestrator dispatched to worker workstreams.
- **June.** A 91-session fan-out from one delegation wrapper (2 Jun). Orchestrator dispatch to pinned, goal-driven Codex teams (13 Jun).
- **Why it changed.** Broad packets stopped being the operating unit, and the fan-out showed that handoffs had to close. The handoff rule in [governance rule 11](governance.md#11-handoff-closure-with-a-delivery-receipt) followed.

## Phase 2: ChatGPT takeovers and wakeups (August to September)

- **4 Aug.** 63 ChatGPT branch tips were advanced in one day. Later days in August had 54 and 58.
- **23 Aug.** The principal handed lead to a ChatGPT main agent with a plan target. The phase was read-only takeover first.
- **Late Aug to Sep.** Heartbeat wakeups, pasted transcripts, and "keep going" nudges. A critical-path-only rule was added on 29 Aug.
- **Why it changed.** Plan speed was the goal, but the nudge pattern produced repeated sessions and delegation churn. A 29 Aug review found churn delaying behavioural progress.
- **Overnight workstream, 6 Oct.** One ChatGPT overnight workstream produced 26 rows with 0 rewarded. The model stated the correct hypothesis at call 8 and dismissed it without testing it.

## Phase 3: Claude orchestrates, subagents code (8 Oct onward)

- **6 Oct.** An audit of the overnight ChatGPT workstream found 0 of 26 rows rewarded and a capacity change that silently removed a control.
- **7 Oct.** A later revision was handed to Codex. A Claude edit was committed in a Codex worktree that another agent was using, then soft-reset.
- **8 Oct.** The principal put Claude in charge and closed the Codex and ChatGPT workstreams. Claude orchestrates and audits. Sonnet and Haiku subagents code in worktrees.
- **8 to 10 Oct.** 24, 8, and 11 branches (three revision series) were built and merged in about 72 hours.
- **13 Oct.** Concurrent subagents capped at 3, after one workflow fanned out to about 30.

## Failure modes met

| Date | Failure | Number or detail | Response |
|---|---|---|---|
| 2 Jun | Fan-out of 91 single-workstream sessions | Each opened from one wrapper with a source thread | Handoff closure rule |
| 9 Jul | Rate-limit storm: 15 agents on one model deployment | 456 of 482 verifier rounds errored, 421 of them rate limits; 5.4% returned a verdict | Backoff with jitter, a rate limiter, and a rule against 15-way parallel runs on one deployment |
| 19 Jun, 14 Aug | Detached background processes reaped at the end of an exec | Two incidents | Lease registration |
| 22 Jun, 5 Sep | Transport loss during live rows | One serial run sat 73+ minutes with an open provider socket and no progress | Bounded waits |
| 8 Sep | Handoff via the multi-agent message tool blocked | Delivered by file instead | Handoff through the multi-agent channel |
| 10 Sep | Contradictory append-only plan | Replaced by one consolidated plan | Consolidated plan |
| 28 Sep | VM deallocated mid-run | Outcome of one row not recorded | Lease and reaper rule |
| 7 Oct | Writer collision in a shared checkout | A Claude edit in a Codex worktree, then soft-reset | One writer per branch |
| 13 Oct | Subagent fan-out | About 30 agents in one workflow | Cap of 3 concurrent |

## What the failures taught

1. **Fan-out has a ceiling.** Parallel workers on one deployment hit rate limits before they hit useful work. The 9 Jul storm and the 13 Oct cap set the limit.
2. **A handoff is only real when it is received.** File drops and pasted transcripts were not enough. The receipt field exists for this reason.
3. **One writer per branch.** Overlap caused reverted work. Coordination rules did not stop it on their own.
4. **Orchestration needs an owner.** The setup in place since 8 Oct is one orchestrator that audits and integrates, with narrow subagents. It is too recent to judge by results. Earlier, several workstreams each claimed completion, and that is where most of the false claims came from.

These are observations from one build. They are not a general claim that one orchestration pattern is better.

See also: [loop-orchestrator](skills/loop-orchestrator.md) for the control map and intake rules, and [handoff template](templates/multi-thread-handoff.md).
