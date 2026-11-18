# What was tried, kept and removed

Core improves by small experiments. Each one answers a question, and the answer decides whether the change stays.
Below is a selection, grouped by question. The full record, with every prediction and result, is in the
[research](../research/) folder.

## Can we make runs cheaper without losing passes?

| Idea | How it was tested | Result | Decision |
|---|---|---|---|
| Keep the start of every request identical, so the provider's cache stays warm | Paired task runs | Cost per run roughly halved, same success rate | **Kept** |
| Write the run's state as stable facts, instead of rewriting it every turn | Found the cause in the logs: one changing block near the top made the whole history uncached. Then a screen and a separate holdout set | Cost 0.52x on the screen and 0.76x on the holdout, same passes | **Kept, on by default** |
| Cut context bytes harder | Paired runs | 29% fewer bytes per call, but 56% more calls, so each run cost more | **Removed.** Optimise the whole run, not the single call |

## Do agents need more specialised tools?

| Idea | How it was tested | Result | Decision |
|---|---|---|---|
| A dedicated search tool | 9-task screen, plus a count of tool use by 19 public agent and model pairs | Core never called it; public agents call one rarely and lean on the shell | **Not added** |
| Batched parallel file reads | Same screen | The model batched calls, but never contiguous reads; no fewer round trips, cost +8% | **Off by default** |
| A code map for finding things | $0 scan of 289 real runs (4,308 steps) | Locating and reading is 15% of steps and 5% of output, so a map could save 5–10% at most | **Not built** |
| A store to avoid re-reading files | $0 count of re-reads in real runs | Re-reads are about 4–5% of calls; the best selector found under half of what was needed | **Not built** |

## What breaks in production, and how do we stop it?

| Problem | How it was found | Fix | Decision |
|---|---|---|---|
| A dead tool server froze every later call until timeout | Qualification testing | Check the server is alive while waiting; recover requests it never answered | **Kept**, with Linux end-to-end tests |
| A lost reply could run a terminal command twice | Qualification testing | Fence in-flight commands; resolve lost replies from the terminal's records | **Kept** |
| Waiting longer between requests under a rate limit | A study across many rows | Sharing the provider's retry hint cut refusals from 39 to about 10, but wall time is set by the quota, not the client | **Kept in research only**, not in Core |

## How to read this

- Every decision came from a measured result, not a preference.
- A removed idea is a good outcome: it was cheap to find out and the code stays simple.
- Numbers come from small samples, usually 8 to 30 runs per arm, so they show the direction and size of an
  effect, not a precise rate. Where a result held on a separate holdout set, it says so.
