# Adaptive workbench qualification

This method qualifies the adaptive workbench, the task-specific configuration that an architect writes for each task. A configuration is judged on solver outcomes on fixed trials. The architect's own rubric score is a diagnostic only.

The lesson: the architect's output scored 9 to 10 out of 10 on the rubric, and task outcomes did not improve. Rubric quality was not a proxy for task success.

This matters because a workbench that reads well and wins nothing is the kind of crutch the harness design rules out. It has to earn its place on outcomes.

## Why we needed it

The architect-only evaluation on official-task prompts scored outputs 9 to 10 out of 10 across rounds.The isolated architect check scored 9, 10, 9, 9, and 9 out of 10 on five tasks. The provider's first output was cut off at the token cap and was rerun with a larger cap.A 15-task audit scored the final selected outputs 10 of 10 on verifier-prompt and config-contract quality. Its author called the remaining gap "rubric polish, not verifier/config failure."

The outcome record was different. The architect ladder never produced a clean official win. The architect was removed from production on 19 August 2026. Authority moved to the primary solver plus an independent verifier.A July forensic review rated the system NOT READY and listed 20 findings. One finding was that architect quality scoring rewarded verbosity.

## How it works

The record shows three checks, in order of strength:

1. **Structure check.** The architect's output must parse, and its clauses must compile into checks.
2. **Outcome A/B.** The same solver runs with and without the configuration on fixed trials. A profile is kept only if it wins without regressing a sentinel.
3. **Held-out confirmation.** A configuration that passes the A/B is confirmed on held-out trials before promotion.

The rubric is recorded beside these checks and is not a gate.

The adaptive profile (AHP) was tested the same way. On the four-trial stage, the baseline and the profile both passed all four rows, with 0 wins and 0 regressions. A later replication gave 1 of 4 for the baseline and 3 of 4 for the profile. Six baseline-only reruns then all passed, and the result was downgraded from a deterministic win to a probabilistic advantage.

## What it caught

- **Rubric without outcome.** Architect outputs passed every rubric while the ladder produced no clean official win.
- **Mechanical gate promoted.** A held-out mini board of 36 rows had 30 contract-valid rows and 4 full passes. It was promoted on the mechanical realization gate, and the semantic result stayed diagnostic.
- **No family qualified.** On one architect set, no tested variant qualified both mixed-proof families. The best strict result was 9 of 18.
- **Verifier was inert.** In the early architect path, the verifier ran 0 real checks in 20 runs.

## Where it fell short

Most of the workbench's life was qualified by rubric scores, and solver-outcome tests came late. Those tests were small. A 9-trial commitment ablation could not separate 2 of 9 from 3 of 9. The architect's causal effect was never isolated on a clean run with a fixed control. The rubric method was not documented in the repo. The rule the record supports, that rubric scores are diagnostic and outcomes decide, is a conclusion drawn from these results, not a tested procedure.
