# How the evaluations evolved

Each layer of this evaluation programme was added because the previous layer had misled us. This page
follows that sequence. Detail for each step is on the [method pages](methods/) and [target pages](README.md).

| Stage | When | What we built | What it exposed |
|---|---|---|---|
| 1. Sanity checks | Feb 2026 | Property checks on the harness's own eval layer | Checks passed when signals were missing. Evaluations must fail closed |
| 2. Capability families and sentinels | Feb–May 2026 | Small hidden-graded tasks per capability, plus sentinel rows that must not regress | Determinism audits showed the same task passing in 26 steps and failing in a 50-step loop. One run proves little |
| 3. Pre-registered tournaments | May 2026 | Mechanism A/Bs with predictions written first | A guard hit its target 2/2 and regressed its sentinel 0/1. Without sentinels it would have been promoted |
| 4. Whole-harness boards | May–Jun 2026 | Full-suite boards for complete harnesses | 216 of 241 first attempts never launched. Launch integrity became a gate before any score |
| 5. Adaptive workbench qualification | Jun–Aug 2026 | Rubric and outcome evals for an architect that configured the solver and verifier | Rubrics scored the architect 9–10/10 while outcomes did not improve. Rubric quality is not outcome quality |
| 6. Verifier evaluation | Jul–Oct 2026 | Known-bad falsifiers, then a bench of 377 graded finishes | The verifier had run 0 real checks in 20 runs. The bench measures catches and false holds |
| 7. Grader and measurement audits | Jul–Oct 2026 | Row-level audits, invalid-row accounting, grader leak tests | A 78.5% batch was a rate-limit storm; a grader leak scored rejection controls at 1.0 |
| 8. Pre-registered held-out evaluation | Sep–Oct 2026 | Sealed plans on unseen tasks against a stock agent | The falsifier fired: 5/9 vs 4/6. The claimed lift was not there |
| 9. The current tasks | Oct 2026 | 28 tasks across nine targets, each validated against known-bad states and careless agents | — |

## What the sequence taught

1. **Validate the instrument before the subject.** Most wrong conclusions came from graders, launchers and
   verifiers, not from the agents being tested.
2. **A score needs controls.** Known-bad states and careless agents must fail; sentinels must hold.
3. **Write the claim down first.** Only a sealed prediction can count against you.
4. **Audit rows, not summaries.** Every artefact in stage 7 was invisible in the aggregate.

## The current tasks

Each of the 28 tasks targets a named failure mode drawn from this history: decoys, stale documents,
indirection, proxy checks, injected instructions and out-of-scope edits. Each one must pass four checks:

- the grader accepts the reference and rejects the untouched workspace;
- every known-bad state is rejected for its stated reason;
- five careless agents fail: do nothing, fake it, skip the check, edit the wrong target, stop half done;
- the reference derives the answer from the workspace alone.
