# External source — GPT-5.6 Terra + Codex

This file separates what is independently verified from what is still awaiting a public per-task receipt.

## Independently verified submission identity

Terminal-Bench's public `terminal-bench-2-1` repository contains merged leaderboard submission **#115**, titled:

> `Leaderboard Submission: GPT-5.6 Terra (max) + Codex`

Public source:

- https://github.com/harbor-framework/terminal-bench-2-1/pull/115
- https://github.com/harbor-framework/terminal-bench-2-1/blob/main/leaderboard/submissions/2026-07-11-openai-gpt-5-6-terra-max-codex.json

The public submission records:

- agent: `codex`
- agent version: `0.144.1`
- model: `openai/gpt-5.6-terra`
- reasoning effort: `max`
- evaluation date: `2026-07-11`
- tasks: 89
- trials: 445
- static-analysis submission checks: passed
- final aggregate accuracy after one disqualified reward-hacking trial: **78.43% ± 1.25%**
- reported total cost: **$421.15**

Terminal-Bench's submission automation checked that the trial count covered 89 tasks with at least five trials per task and that task digests, metadata, resource settings and timeout settings were valid.

## Exact task-row status

The Aether funding page currently reports the following motivating observation for the named task `configure-git-webserver`:

```text
GPT-5.6 Terra + Codex: 0.00
GPT-5.6 Luna + Aether: 1.00
```

The public source above independently establishes the **Terra + Codex submission configuration and aggregate result**. This repository has **not yet attached the public Terminal-Bench per-task receipt** that independently proves the exact `configure-git-webserver = 0.00` row from that submission.

Therefore this external half of the selected comparison is currently classified:

> **submission identity verified; exact per-task receipt pending**

It should not be used as causal proof until the receipt is attached.

## Why keep the caveat visible?

Because the research proposal does not need this comparison to already prove Aether's hypothesis. Its purpose is to motivate the matched experiment. Publishing the boundary between verified aggregate evidence and a still-unlinked per-task claim is more useful than hiding that boundary.
