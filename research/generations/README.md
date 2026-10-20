# Five generations of the harness

**What this is:** A timeline of the five generations of the agent harness, from a planner that acted as external memory (Gen 1) to the lean loop now in development (Gen 5). Each generation has its own page.
**Key result:** No generation has a clean, frozen, official benchmark win on record. The one held-out campaign run against a stock reference agent (October 2026) did not support the lift claim for the Gen 4 candidate.
**Why it matters:** Each replacement was triggered by a measurement, not by a new idea alone. Several claims that looked like wins were later retired on grader or launch-integrity grounds. The lineage is useful only with those retirements kept in view.

## Timeline

| Gen | Core idea (one line) | Dates | Why it was replaced |
|---|---|---|---|
| 1. Planner memory | A planner holds the task plan as external memory for a stateless coding agent. | 2025-11-22 to 2026-02-25 | Oracle files leaked answers, tool schemas were filtered, and a phase check passed with signals missing. The durable idea was an oracle-free verifier. |
| 2. Receipt kernel | A "done" claim needs a receipt, and a task-local profile (Adaptive Harness Profiles) is generated before the solve loop. | 2026-05 to 2026-07-08 | Fake progress (candidate lock-in, circular self-checks, shape-only success). Profiles gave a probabilistic advantage, not a promotable win. Demoted to a reference line on 2026-07-03. |
| 3. Architect, solver, verifier | An architect model writes the harness config and the solver and verifier prompts; a trusted compiler realises them. | 2026-07-01 to 2026-08-19 | The architect's proof authority was unsound (forensic verdict NOT READY, 2026-07-19). The verifier ran no real checks in an early audit. Architect calls were removed from production on 2026-08-19. |
| 4. Persistent worker, independent verifier | One persistent model owns the task; the kernel executes one action per turn; an independent verifier and a deterministic gate check completion. | 2026-08-05 to 2026-10 (production line to 2026-09-08) | The October held-out campaign did not support the lift claim (candidate 5/9, stock reference agent 4/6). Work moved to Gen 5 for October. |
| 5. Aether Core | The model pilots: a lean loop of model turn, tools and results until finish or time, with a claim-free review at finish. | 2026-10-12 onward | Current. The matched 18-row development board tied the stock reference agent, 12/18 each; there is no frozen benchmark win. |

## Reading the table

- Mechanisms that survived: receipts (Gen 2), the oracle-free verifier (Gen 1), state-delta hashing and an executable check path (Gen 3), and file tools with deadline visibility (Gen 4, kept in Gen 5). The architect (Gen 3) and the task profile (Gen 2) were removed.
- Dates are the span in which each line was the active or reference line in the repository, not the span of every experiment. Eval-level detail sits in each generation page.
- Generation numbers follow the public glossary. Internal codenames for each line are not used here.

