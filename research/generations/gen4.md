# Gen 4: persistent worker and independent verifier

**What this is:** The fourth line. One persistent model owned the task across turns; the kernel executed one causal action per turn and returned exact receipts; an independent verifier and a fresh deterministic gate checked completion.
**Key result:** The October held-out campaign for the candidate (the Gen 4 candidate) recorded 5 of 9 attempts against 4 of 6 for a stock reference agent. The pre-registered falsifier triggered, and the lift claim was not supported.
**Why it matters:** This line was the first with a production release and the first with a pre-registered held-out test. Its qualification counts measured the substrate; the held-out test measured the claim.

## Core idea

Give the task to one model for its whole life. Keep the kernel dumb and the verifier independent. Finish only when a deterministic gate agrees, even after the model says it has completed.

## Design

```
            ┌─────── persistent worker (one model, provider-native continuity)
            │            │ one causal action per turn
            │            ▼
            │       kernel: exact receipts, findings lifecycle,
            │       bounded stalemate handling
            │            │
            │            ▼ finish requested
            │       independent verifier (state only)
            │            │
            └── findings back to worker   ──►  fresh deterministic gate
                                              │
                                              ▼
                                  official grader, after the run
```

- **Continuity.** Provider-native continuation, so the model keeps its own reasoning state across turns.
- **Findings.** A verifier finding stays active until it is resolved or superseded.
- **Harness boundary.** The evaluation harness owns the task and its lifecycle.

## Evaluations

| Eval | Result |
|---|---|
| Production qualification (local, shared Linux, real Docker) | 301 of 301 local; 301 of 301 shared Linux; 16 of 16 real Docker. Counts measure the substrate, not capability. |
| Batch of 15 parallel tasks, one model deployment | Reported 11 of 14 (78.5 percent). Audit found the verifier mostly unavailable; see the rate-limit storm postmortem. |
| Candidate board (20 tasks) | About 2.64 million tokens, roughly ten times the clean baseline. Verifier stalemates on tasks the grader passed. |
| Candidate screens, 13 to 14 tasks each | Claim ledger version 1 scored 12 of 13 against a control of 10 of 13. Two combined screens: 47 of 52 against 42 of 52, a noisy pool. |
| Final candidate screen (the Gen 4 candidate) | 13 of 14, against 10 of 14 and 12 of 14 for two earlier versions. Single episode per row. |
| Verifier bench (wrong-finish catching) | Version at threshold 0.7 caught 22 of 29 wrong finishes with 6 of 348 false holds. An artifact verifier caught 25 of 28 with 68 of 208 false holds (33 percent) and was reverted. |
| Held-out, September set | Official 0 of 3. Grader checks 14 of 50. Closed as not validating the candidate. |
| Held-out, October set, against a stock reference agent | Candidate 5 of 9 (56 percent); stock agent 4 of 6 (67 percent). Falsifier triggered. |

The verifier bench is the strongest verifier measurement in this line. A packet-unwrapping bug meant that every earlier bench read the wrong tool-result field. Those benches were invalidated and rerun.

## What was learned

- **Qualification counts are not capability.** The 301 clean local runs showed the substrate worked. They did not show a lift.
- **Defaults matter.** Open-model runs were using greedy decoding (temperature 0.0) by default. Identical malformed calls repeated up to 18 times, and one runaway produced a 32,000-token output.
- **A held-out claim needs its falsifier written first.** The October campaign was sealed before any row ran. The falsifier then reported the result that mattered.
- **Small campaigns give wide uncertainty.** Three tasks and nine attempts support only the aggregate, and this page claims nothing finer.

## Why it was superseded

The October held-out campaign did not support the lift claim. From October, new work went to Gen 5 (a lean loop), keeping only parts of this line that held up, such as file tools and deadline visibility.

## Known debt

The engineering standard sets a 500-line file limit, but this snapshot includes files above that limit. Splitting them remains work to do. The `_v1` and `_v2` names also remain in experimental modules and interfaces; they record iterations rather than a finished naming scheme. These are known maintenance debts, not completed cleanup.
