# Gen 3: architect, solver, verifier

**What this is:** The third line. An architect model wrote the harness configuration and the solver and verifier prompts; a trusted compiler turned them into a run; the solver took one typed action per turn; a state-only verifier checked the result.
**Key result:** The line did not earn a clean official win. Its best evidence was 9 of 9 on three narrow short-horizon scenarios, which the page's own sources say does not establish general reliability.
**Why it matters:** The line tested whether model-authored authority could be made safe. The answer was no for proof authority, and the architect was removed from production on 19 August 2026.

## Core idea

Put the design decision in a model that reads the task, and keep execution in code. The architect declares tools, checks and verifier powers. The compiler realises them. The solver and verifier are simple, and the official grader stays outside the loop.

## Design

```
task ──► Architect (model): HarnessConfigIR, proof clause list,
                            solver and verifier prompts
              │
              ▼
        trusted compiler: prompts, checks, route preflight,
                          proof compiled from the clause list
              │
              ▼
   ┌─► Solver (model): one typed action per turn (16,000 output tokens)
   │        │
   │        ▼
   │   kernel dispatches the action, hashes the state delta
   │        │
   │        ▼  submit
   │   checks + deterministic completion gate
   │        │
   │        ▼
   │   state-only verifier (read-only inspector, overlay)
   │        │ not ready: findings returned ──────────┘
   │        ▼ ready
   └── official grader, after the terminal state only
```

## Evaluations

| Eval | What it showed | Result |
|---|---|---|
| Architect-only audit, 5 tasks (primary mini model) | Parseable architect output and rubric score | 5 of 5 parseable; scores 9, 10, 9, 9, 9 out of 10. Rubric scored configurations, not outcomes. |
| Verifier-only packets, 5 synthetic types | Whether the verifier gives the expected verdict | 5 of 5 expected verdicts. Designed-in cases only. |
| Docker isolation smoke, 3 cases | Whether a known-bad solution scores 0 | Golden file 1.0; known-bad file 0.0; golden service 1.0. |
| Narrow real-task runs, 2 tasks | First real runs after fixes | 0 of 2 (one harness context failure, one grader timeout at 30 seconds). Verifier-only replay parsed 6 of 6. |
| Architect ladder, phase 20 and 25B | Whether a contract variant qualifies on mixed-proof families | Best single variant 3 of 6; 9 of 18 strict. No tested variant qualified both families. |
| Architect V3 mini board, 36 rows | Contract validity and full passes | 30 contract-valid rows; 4 full 10 of 10 passes. Promoted on the mechanical gate alone. |
| Verifier audit (early stage) | Whether the verifier runs real checks | 0 real checks in 20 runs; every completed verdict was ready by fallback. |
| Forensic code audit, July 2026 | Whether the line is ready | Verdict NOT READY, with 20 numbered findings. |

## What was learned

- **Strong models could use the design; weak ones could not.** The architect's configurations worked with a strong model and failed with a weak one.
- **Plans are not checks.** The architect wrote six to nine proof obligations per task, but none were compiled into runnable checks until the verifier path was made executable.
- **Rubric scores measured the configuration, not the outcome.** Scores rose while outcomes did not (see the adaptive workbench page).
- **Authority has to sit with code, not with the model that wrote the plan.** The proof compiler accepted what the architect omitted.

## Why it was superseded

Architect calls were set to zero on 19 August 2026 and removed from the production path. Authority moved to the primary model plus an independent verifier. The design choice the line tested (model-authored config) was not carried forward.

