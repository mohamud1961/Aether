# Incorrect work

Aether's main research target: why capable AI agents deliver wrong results they believe are right. This page
summarises the evidence; the raw trajectories are not in this repository.

## Why it matters

Wrong work is the most expensive work: it is paid for once to produce it and again to find it and redo it. On new
work with no answer key, a confident wrong result may never be caught. At frontier scale the stakes are large:
OpenAI's claimed Navier-Stokes result used about 10,000 agents for 88 hours, at around $10 million by Sam Altman's
estimate. Models that can do the work should not get it wrong; fixing that saves money and multiplies what the same
model can deliver.

## The failure

An agent meets a point the task does not fully settle. It fills the gap with a convenient stand-in (an example
value, a guessed host, today's data instead of the stated date), then checks its work against that stand-in. The
check passes, the agent reports "done and verified", and the work is wrong. This is false confidence, and it is
one of the main sources of incorrect work.

The common shape: **the check that should settle the assumption is derived from the assumption itself.**

## Evidence

**Scale.** More than 4,000 graded agent trials: 3,448 of Aether's own agents on Terminal-Bench, and 736 public
Terminal-Bench 2.1 leaderboard trials from 13 frontier models across OpenAI, Anthropic, Google, xAI, Meta and
Zhipu.

**A universal LLM problem.** Six study tasks: three that test ability (bn-fit-modify, mcmc-sampling-stan,
mteb-leaderboard) and three that hinge on an assumption the agent must check (extract-elf,
configure-git-webserver, sanitize-git-repo). The tasks were chosen to contrast the two kinds.

| Model | Ability tasks | Assumption tasks |
|---|---|---|
| GPT Astra | 99% | 7% |
| GPT Terra | 100% | 30% |
| GPT-5.5 | 93% | 47% |
| GPT Luna | 89% | 48% |
| Claude Fable 5 | 100% | 33% |
| Claude Opus 4.7 | 100% | 63% |
| Claude Opus 4.8 | 100% | 73% |
| Claude Sonnet 5 | 100% | 73% |
| Gemini 3 Pro | 80% | 40% |
| Gemini 3.1 Pro | 67% | 40% |
| Grok 4.5 | 72% | 61% |
| Muse Spark 1.1 | 93% | 53% |
| GLM-5.1 | 73% | 60% |
| **All 13** | **91%** (328 of 361) | **40%** (151 of 375) |

The #1 agent overall, Codex on GPT Astra, failed the assumption tasks at every reasoning effort from low to max.

**Same wrong reading across labs.** On extract-elf, models used the task's illustrative example address instead
of the file's own: that choice passed 18% of the time, while reading the file passed 86%. On configure-git, agents
read "you don't have to worry about login" as meaning ssh was handled and verified a local clone instead; skipping
the ssh server passed 19%, installing it passed 54%.

**The information was there.** In 15 of 16 audited failures in Aether's own runs, the deciding fact was in the
agent's environment: obtainable by running a command (8), already in the container or context (6), in a reference
(1). The agent never checked it, or checked it and overrode it.

**It ends in a confident "done", and it is costly.** In Aether's largest pool, 797 of 853 failures ended with the
agent finishing and claiming success, and failed runs took 58% of the spend. Wrong answers are often
deterministic: on one task, 43 of 58 failures were the same byte-identical answer, so retrying does not fix it.

**The harness moves it, it does not remove it.** The same five models in two harnesses: one harness did better on
two tasks and worse on two others. A finish-confirmation prompt ("are you sure?") led to new action in 41 of 147
runs and rarely changed the outcome.

**What better runs do differently.** Both strong and weak runs make assumptions. The passing runs test theirs
against an independent source: a standard definition, manufactured ground truth, an external measurement, a
second tool. The failing runs check against tests generated from their own theory, or an internal metric standing
in for the real one.

## What has been tried and failed

Self-check text, a same-model verifier (0 refutations), prewritten acceptance checks (harmful in 42% of cases), a
requirement ledger and a reading judge (AUROC 0.475, chance). In Core's own runs, a circular or unchecked last
check was about as common in wrong finishes as in passes (24% against 21%), so circularity alone does not predict
the outcome. See [findings.md](findings.md) and the [cemetery](cemetery.md).

## What is open

How to make an agent seek an independent check at the moment it commits to an assumption, without the harness
interpreting the task for it. The next stage of the programme:

1. An open benchmark for incorrect work, with graders tested against known-bad solutions.
2. A trace-level map of where wrong work starts.
3. Pre-registered tests of safeguards across frontier agents and models, with every trace published.
