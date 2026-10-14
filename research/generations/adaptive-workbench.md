# The adaptive workbench

**What this is:** The design idea that ran through Gens 2 and 3: an architect adapts the harness to each task, a solver works, and a verifier checks task state. It also covers Adaptive Harness Profiles (profile arm), the mechanism that compiled an adaptation into a run configuration.
**Key result:** Rubric scores for architect output reached 9 to 10 out of 10 while task outcomes did not improve. The profile mechanism showed a single N=1 win, a 1-of-4 versus 3-of-4 replication, and then no difference on a larger set. Its economic effect was smaller calls and steps.
**Why it matters:** It is the clearest case in the programme of a measure that rose while the thing it was meant to proxy did not. The architect was removed from the production path for that reason.

## Roles

| Role | Job | Boundary |
|---|---|---|
| Architect | Reads the task and designs the workbench: tools, checks, verifier powers, prompts. | Authors configuration only. The harness supplies generic mechanisms. |
| Solver | Executes the task and decides when it is done. | Never sees the official grader. |
| Verifier | Reads task state with read-only tools and returns a verdict with findings. | Verifies state, not the solver's account. Never sees the grader. |
| Official grader | Scores the outcome. | External. Runs only after the agent stops. Never influences the loop. |

The design test was: would a smarter model make this code redundant, or want to override it? If yes, the code was a crutch and did not belong in the harness.

## Adaptive Harness Profiles

A profile is a task-local configuration generated before the solve loop. It was meant to carry visible requirements, a frozen completion contract, verifier watch points, an initial plan and a reduced tool set, while the base system prompt stayed the same.

```
task ──► architect output ──► AdaptationContract ──► adapter (data-driven)
                                                       │
                                  validation: required fields, tool config,
                                  non-empty solver prompt, success definition
                                                       │
                                                       ▼
                                          ValidatedRunConfig (flag-gated)
```

The contract was meant to be the only path from adaptation to behaviour. Its validation was a check that ran before any run began. One known conflict remains: on a model call, parse or validation failure, the profile fell back to a baseline-like configuration. The project's rules forbid fallbacks at the judgment layer, so this fallback is recorded as an open conflict.

## Invariant core and configurable surfaces

| Invariant core (no variant may weaken it) | Configurable surfaces (a variant may adapt them) |
|---|---|
| Workspace and path safety | Solver prompt, task block |
| Tool truthfulness and audit logging | Context inclusion |
| No Fake Work; executor boundaries | Exposed tool subset |
| Verification must happen | Completion contract and success definition |
| Cleanup accounting; evidence ledger | Verifier stated requirements and focus |
| Baseline loop shape; context hygiene | Evidence guidance |

Variants were flag-gated, and the baseline path was kept. A variant never changed the core and never added task-specific branches.

## How it was qualified

| Step | Evidence | Reading |
|---|---|---|
| First win | One task, 0 for baseline and 1 for profile arm. | "N=1 and not promotion-grade." |
| Stage 2d | Four hard rows, one run per cell. Both arms passed all four; 0 wins, 0 regressions. Fresh tokens up 16 percent. | "No clear solve-rate effect." |
| Sweet-spot search | 13 tasks: 1 profile arm win, 0 regressions, 12 unchanged. | A narrow surface. |
| Replication | One task, four pairs: baseline 1 of 4, profile arm 3 of 4. A later baseline-only rerun of six runs all passed. | Downgraded to a probabilistic advantage; environment variance a serious confound. |
| Economics (four pairs) | Calls −14.0 percent (43 to 37); steps −23.8 percent (21 to 16); cached tokens −29.1 percent; fresh tokens +7.2 percent; wall time +9.5 percent. | Every paired row ended with the verifier not clean. |

The architect-level evidence was qualified in the same way. Rubric scores were the main measure, and the outcome measure lagged behind.

## Rubric scores and outcomes

| Measure | Result |
|---|---|
| Architect isolated audit, 5 tasks (rubric out of 10) | 9, 10, 9, 9, 9. |
| Architect-as-skill audit, 15 tasks | Final selected outputs 10 of 10 on verifier-prompt and config-contract quality. Remaining sub-10 scores were on the solver. |
| Verifier audit, early stage | 0 real checks in 20 runs. |
| Gold scenarios | 9 of 9 on three narrow short-horizon scenarios. The page's own source says this does not prove general reliability. |
| Architect V2, phases 20 and 25B | No tested variant qualified both mixed-proof families. Best single variant 3 of 6; 9 of 18 strict. |
| Architect V3 mini board, 36 rows | 30 contract-valid rows; 4 full 10 of 10 passes. Promoted on the mechanical realisation gate alone. |

Rubric scores rose while task outcomes did not. The rubric scored the configuration, not whether the solver then passed the task. The source does not record who scored the rubric.

## Why the architect left the production path

The architect was removed from the production path on 19 August 2026 (architect model calls set to zero). The recorded reason was authority, not output quality. The architect's authority over proofs and verification was not independent of the model that wrote the plan, and the outcomes did not follow the rubric. The lesson the programme took is this: separate roles need separate authority, not separate model personas. A second instance of the same model class, given a different name, does not add an independent check. What the programme kept was the separation of authority itself: a deterministic completion gate, a read-only verifier, and a grader that stays outside the loop.

