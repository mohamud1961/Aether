# External source — GPT-5.6 Terra + Codex

This file separates what is independently verified from what is still awaiting a public per-task receipt.

## Independently verified submission identity

Terminal-Bench's public `terminal-bench-2-1` repository contains merged leaderboard submission **#115**, titled:

> `Leaderboard Submission: GPT-5.6 Terra (max) + Codex`

Public sources:

- https://github.com/harbor-framework/terminal-bench-2-1/pull/115
- https://github.com/harbor-framework/terminal-bench-2-1/pull/114
- https://github.com/harbor-framework/terminal-bench-2-1/blob/main/leaderboard/submissions/2026-07-11-openai-gpt-5-6-terra-max-codex.json
- https://www.tbench.ai/leaderboard/terminal-bench/2.1

The public submission records:

- agent: `codex`
- agent version: `0.144.1`
- model: `openai/gpt-5.6-terra`
- reasoning effort: `max`
- evaluation date: `2026-07-11`
- tasks: **89**
- trials: **445**
- final aggregate accuracy after one disqualified reward-hacking trial: **78.43% ± 1.25%**
- reported total cost: **$421.15**
- reported tokens: **902,641,810**

The source submission was promoted from PR #114 into leaderboard-owned trial copies before review. Terminal-Bench's automation reports that all nine static checks passed, including:

- valid source filter and metadata;
- default timeout/resource settings;
- **89 tasks × at least five trials**;
- valid per-trial records;
- valid task digests.

The source run contained **433 no-error trials** and **12 AgentTimeoutError trials**, for 445 total. The final merged submission applied one separately identified disqualification and recomputed the published aggregate.

Source job recorded by the original submission:

`dd8bc272-70cf-4e40-bc52-031c4f69c7c0`

The leaderboard promotion then cloned the trials into leaderboard-owned copies and materialized all 445 trial IDs into the merged submission.

## Exact task-row status

The Aether funding page currently reports the following motivating observation for the named task `configure-git-webserver`:

```text
GPT-5.6 Terra + Codex: 0.00
GPT-5.6 Luna + Aether: 1.00
```

The public sources above independently establish the **Terra + Codex submission configuration, trial count, validation and aggregate result**.

They do **not** expose a task-name-to-trial mapping inside the merged submission JSON. Terminal-Bench's own public checker code resolves that metadata through `harbor hub job trials`. That route currently requires authenticated Harbor access, so this repository has still not attached a public Terminal-Bench receipt independently proving the exact `configure-git-webserver = 0.00` row for submission #115.

Therefore this external half of the selected comparison remains classified:

> **submission identity and aggregate provenance verified; exact per-task receipt pending**

It should not be used as causal proof until the receipt is attached.

## Why keep the caveat visible?

Because the research proposal does not need this comparison to already prove Aether's hypothesis. Its purpose is to motivate the matched experiment.

Publishing the boundary between independently verified aggregate evidence and a still-unlinked per-task claim is stronger research practice than hiding that boundary.
