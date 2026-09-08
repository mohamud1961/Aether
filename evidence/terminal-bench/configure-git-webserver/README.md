# Case: `configure-git-webserver`

This case is public because it is unusually useful for understanding Aether's research question. It should **not** be read as a benchmark-wide superiority claim.

## Aether result: smaller Luna model, official pass

Aether has two preserved observations on the task.

### Sealed September held-out row

The final H10 held-out audit records:

| Field | Value |
| --- | --- |
| Task | `configure-git-webserver` |
| Benchmark family | `terminal-bench-2x` |
| Model | **GPT-5.6 Luna** |
| Agent | **Aether** |
| Classification | **VALID_PASS** |
| Official reward | **1.0** |
| Provider failures | **0** |
| Solver parse errors | **0** |
| Solver continuation | **intact** |

This row was part of the sealed 10-task H10 campaign: one attempt per task, zero benchmark retries, zero reruns, zero substitutions, and no mid-campaign tuning or repair. See [`../../qualification/`](../../qualification/).

### Historical August attribution row

A preserved 25 August 2026 native Harbor run also used **GPT-5.6 Luna + Aether** on the same named task.

Recorded outcome:

| Field | Value |
| --- | --- |
| Official reward | **1.0** |
| Official CTRF | **1 / 1 passed** |
| Model | **GPT-5.6 Luna** |
| Attempts | **1** |
| Retries | **0** |
| Architect calls | **0** |
| Solver responses | **10** |
| Verifier responses | **3** |
| Solver continuation | intact |
| Aether terminal status | `verifier_blocked_stalemate` |
| Internal failure | three verifier path-escape failures |

The structured record is [`aether-luna-result.json`](aether-luna-result.json). The causal sequence is summarized in [`trace-summary.md`](trace-summary.md).

The important historical observation is not merely that the grader returned 1. The official grader **passed while Aether's own review path still failed to close cleanly**.

That disagreement is direct evidence for the attribution problem the project is trying to reduce.

## Terra + Codex comparison

The funding site also shows a reported Terminal-Bench 2.1 result for **GPT-5.6 Terra + Codex** on the same named task with reward `0.00`.

The public Terminal-Bench repository independently verifies the broader comparison configuration. Its merged leaderboard submission **#115** is:

- **GPT-5.6 Terra**;
- **Codex 0.144.1**;
- `max` reasoning effort;
- 89 tasks;
- 445 trials;
- final aggregate accuracy **78.43% ± 1.25%**.

See [`terra-codex-source.md`](terra-codex-source.md).

**Evidence boundary:** the public dossier has independently verified the Terra+Codex submission identity and aggregate submission. It has not yet attached a public per-task receipt that independently establishes this exact task's `0.00` row. Until that receipt is attached, the website comparison remains a **reported motivating observation**, not a completed causal evidence package.

## What makes the comparison interesting

Luna is the **smaller model** in the selected website comparison, yet Luna+Aether is reported as passing this task while Terra+Codex is reported as failing it.

That is a useful anomaly. It is not proof.

The configurations differ in both model and agent, and the exact budgets/environment details are not yet matched. The observation therefore motivates the research question rather than answering it.

## What this case supports

It supports two modest claims:

1. **GPT-5.6 Luna + Aether has a preserved official pass on `configure-git-webserver`.**
2. **Aether's own historical review machinery could still mishandle a task-visible success.**

It does **not** establish:

- that Luna is generally better than Terra;
- that Aether is generally better than Codex;
- that the website pair had identical budgets or environments;
- that the observed pair difference was caused by Aether.

Those are precisely the questions the matched three-month programme is intended to test.
