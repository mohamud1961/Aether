# False confidence in AI agents

Aether's main research target. This page summarises the evidence; the raw trajectories are not in this repository.

## The failure

An agent meets a point the task does not fully settle. It fills the gap with a convenient stand-in (an example
value, a guessed host, today's data instead of the stated date), then checks its work against that stand-in. The
check passes, the agent reports "done and verified", and the work is wrong.

The common shape: **the check that should settle the assumption is derived from the assumption itself.**

## Evidence

**Scale.** 3,448 graded trials of Aether's own agents on Terminal-Bench, plus 736 public trials from all 22
Terminal-Bench 2.1 leaderboard submissions (13 models), on six study tasks.

**Agents fail by finishing wrong, not by running out of time.** Of 853 failures by GPT Luna in Core, 797 ended
with the agent finishing and claiming success. Wrong answers are often deterministic: on one task, 43 of 58
failures were the same byte-identical wrong answer, so retrying the same model does not fix it.

**The information was there.** In 15 of 16 audited failures, the fact that decided the task was in the agent's
environment: obtainable by running a command (8), already in the container or context (6), in a reference (1).
The agent either never checked it, or checked it and overrode it.

**It happens at the frontier.**

| Task | What the top agents did |
|---|---|
| extract-elf | Codex on GPT Astra, the #1 agent overall, 0/25 at every reasoning effort. It used the example's base address in 25/25 runs. Across 13 models, using the example passes 13/73; using the file's own addresses passes 43/50. |
| configure-git | GPT Astra 0/25. It read "you don't have to worry about login" as meaning ssh was handled, verified a local clone instead, and reported success. Across agents, installing the ssh server passes 27/50; not installing it passes 14/72. |
| sanitize | GPT Astra 5/25. Rewriting history passes 2/19, against 52/102 without a rewrite. |

On capability tasks the same frontier agents pass about 95-100%. The failures are about assumptions, not ability.

**The harness moves it, it does not remove it.** The same five models in two harnesses, 25 runs per cell: one
harness did better on two tasks and worse on two others. A finish-confirmation prompt ("are you sure?") led to new
action in 41 of 147 runs and rarely changed the outcome.

**What better runs do differently.** Comparing two frontier models in the same harness on the same tasks, both made
assumptions. The passing runs tested theirs against an independent source: a standard definition, manufactured
ground truth, an external measurement, a second tool. The failing runs checked against tests generated from their
own theory, or an internal metric standing in for the real one.

## What has been tried and failed

Self-check text, a same-model verifier (0 refutations), prewritten acceptance checks (harmful in 42% of cases), a
requirement ledger and a reading judge (AUROC 0.475, chance). In Core's own runs, a circular or unchecked last check
was about as common in wrong finishes as in passes (24% against 21%), so circularity alone does not predict the outcome.
See [findings.md](findings.md) and the [cemetery](cemetery.md).

## What is open

How to make an agent choose an independent check at the moment it commits to an assumption, without the harness
interpreting the task for it. That is the next stage of the programme:

1. An open false-confidence benchmark with graders tested against known-bad solutions.
2. A trace-level map of where false confidence enters.
3. Pre-registered tests of safeguards across frontier agents and models, with every trace published.
