# Head to head: Aether against other agents

Aether is a research harness, not a product, but a harness that cannot hold its own against production agents
would not be worth studying. This page puts Aether Core with a small, cheap model next to public results from
production agents with larger models, on the same tasks.

**These comparisons were chosen after the runs.** They are the reference points that existed for tasks we had
already run, not a pre-registered benchmark. The aggregate table covers every shared task, including the ones
Aether loses. The selected tables that follow are labelled as selected.

## The setup

| System | Agent | Model | Runs per task | Source |
|---|---|---|---|---|
| **Aether** | Aether Core | GLM-5.3-Flash | 2 (1 on three tasks) | Our runs |
| Codex + GPT-5.6-Luna | Codex CLI 0.144 | GPT-5.6-Luna | 5 | Public Harbor Hub leaderboard |
| Codex + GPT-6-Astra | Codex CLI 0.151 | GPT-6-Astra | 25 | Public Harbor Hub leaderboard |
| Claude Code + GLM | Claude Code 2.1 | GLM-5.1, maximum reasoning | 5 | Public Harbor Hub leaderboard |

The tasks are 25 Terminal-Bench 2 tasks that both Aether and all three reference agents have results on. Task
names are aliased here, as everywhere in this repository.

## All 25 shared tasks

| System | Mean pass rate | Cost per run | Time per run | Tokens per run |
|---|---|---|---|---|
| **Aether + GLM-5.3-Flash** | **0.64** | **$0.031** | 499 s | **390k** |
| Claude Code + GLM-5.1 | 0.64 | not published | 588 s | 628k |
| Codex + GPT-5.6-Luna | 0.77 | $0.316 | 335 s | 1.46M |
| Codex + GPT-6-Astra | 0.82 | $1.302 | 407 s | not published |

What this shows:
- **Against the same model family in a frontier agent, Aether ties.** It matches Claude Code with a larger GLM
  model on maximum reasoning, using 38% fewer tokens.
- **Against frontier models, Aether loses on pass rate and wins on cost.** It reaches 84% of Codex + GPT-5.6-Luna's
  pass rate at a tenth of the cost, and 78% of Codex + GPT-6-Astra's at a forty-second.

Task by task, counting a difference of any size:

| Aether against | Aether ahead | Equal | Aether behind |
|---|---|---|---|
| Claude Code + GLM-5.1 | 6 | 13 | 6 |
| Codex + GPT-5.6-Luna | 5 | 12 | 8 |
| Codex + GPT-6-Astra | 4 | 10 | 11 |

## Selected: where Aether led

Pass rates. Aether's runs are shown as passes over runs, because with 2 runs a single pass moves the rate by 0.5.

| Task | Aether | Codex + GPT-5.6-Luna | Codex + GPT-6-Astra | Claude Code + GLM | What happened |
|---|---|---|---|---|---|
| wal-restore | **2/2** | 0.40 | 1.00 | 0.00 | In both Claude Code traces examined, the first database query checkpointed the write-ahead log and destroyed the data to recover. One trace then guessed the missing rows and reported them as recovered. Why Aether's runs avoided this is not verified. |
| markup-filter-bypass | **2/2** | 0.80 | 0.36 | 0.80 | |
| heap-crash-debug | **2/2** | 0.80 | 0.24 | 1.00 | |
| binary-secret-extract | **2/2** | 1.00 | 0.04 | 1.00 | GPT-6-Astra's 0.04 over 25 runs is unusually low for a task the other agents all pass; we have not examined those traces. |
| toolpath-decode | **1/2** | 0.00 | 1.00 | 0.00 | |
| image-to-code | **2/2** | 1.00 | 1.00 | 0.60 | |
| log-range-summary | **2/2** | 1.00 | 0.96 | 0.80 | |

## Where Aether lost

Every task where Aether was behind at least one reference agent, plus the one no agent solves. toolpath-decode,
above, also trails GPT-6-Astra.

| Task | Aether | Codex + GPT-5.6-Luna | Codex + GPT-6-Astra | Claude Code + GLM | Note |
|---|---|---|---|---|---|
| rejection-sampler | 0/2 | 1.00 | 1.00 | 0.00 | The later task version specifies the function signature; ours did not. |
| eigen-solver-speedup | 0/1 | 1.00 | 1.00 | 0.20 | |
| query-optimise | 0/1 | 0.75 | 0.80 | 0.20 | |
| repo-secret-scrub | 0/2 | 0.60 | 0.20 | 0.00 | Our task copy was labelled ungradable. |
| mailing-list-server | 1/2 | 1.00 | 1.00 | 1.00 | |
| grid-puzzle-merge | 1/2 | 1.00 | 1.00 | 1.00 | The failed run hit a substrate fault: numpy was missing. |
| stats-model-port | 1/2 | 1.00 | 1.00 | 1.00 | |
| dataset-token-count | 1/2 | 0.20 | 1.00 | 1.00 | |
| typesetting-fix | 1/2 | 0.60 | 1.00 | 0.40 | The later task version ships a new image. |
| seq-insert-design | 0/2 | 0.00 | 0.88 | 0.00 | Only GPT-6-Astra solves it. |
| sanitize-markup | 0/1 | 0.00 | 0.00 | 0.00 | No agent solves it. |

## Same model, same tasks

Three comparisons hold the model fixed, so the harness is the only difference:

| Comparison | Aether | Other | Reading |
|---|---|---|---|
| Gen 4 candidate vs Meta's CLM agent (`clm-minimal`, run as published), GLM-5.3-Flash, 13 tasks × 2 | 23 of 26 | 20 of 26 | Aether ahead. CLM's losses came from its 120 s command limit. Aether used fewer steps on 11 of 13 tasks. The plain Gen 4 control scored 22 of 26 |
| Aether Core vs Terminus 2, GLM-5.3-Flash, 18-run board | 12 of 18 | 12 of 18 | Tie ([research/core/](core/CORE_L1_LUNA_BOARD_PREREG_20261014.md)) |
| Gen 4 candidate vs a stock agent, sealed held-out tasks | 5 of 9 | 4 of 6 | The pre-registered falsifier fired: no lift ([generations](generations/)) |

Against Meta's CLM agent Aether is ahead by 3 of 26, and most of that gap is CLM's command time limit rather
than its reasoning. Against Terminus and on the sealed test there is no lift. The fair summary is parity or better
with the same model, at much lower cost than frontier agents.

## Limits

- **Small samples on our side.** Aether has 2 runs per task, against 5 or 25 for the reference agents. A
  one-task difference is often one run. The aggregates are the meaningful numbers; single rows are illustrations.
- **Task versions differ.** Aether ran the Terminal-Bench 2.0 task copies; the reference agents ran 2.1. Of the 25
  tasks, a few changed in ways that affect grading, noted in the rows above. The runner now uses 2.1, but those
  runs have not been made.
- **Different models.** Only the Claude Code row uses a GLM model, and it is GLM-5.1, not GLM-5.3-Flash.
- **Costs are list-price token costs**, computed from recorded token counts, not from invoices. Claude Code's cost is
  not published.
- **The reference results are other people's runs.** We examined a few of their traces, cited in the rows, and took
  the rest as published.
