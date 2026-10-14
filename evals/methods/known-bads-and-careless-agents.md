# Known-bad answers and careless attempts

This method plants wrong answers and lazy attempts in every task and checks that the grader and verifier reject them. A known-bad answer is a wrong final state. A careless attempt is a cheap script that does nothing, fakes the output, skips the check, edits the wrong target, or stops halfway.

The lesson: a verifier or grader that has never rejected a known-bad answer has not been tested.

This matters because a verifier that says "complete" on wrong work produces a score that looks like progress. In this programme the verifier did exactly that in several trials.

## Why we needed it

The known-bad verifier falsifier was built to check whether the verifier blocks completion on known-bad snapshots and allows known-good ones. It never passed. Run 1 scored 3 of 5 hits. Run 2 scored 2 of 5. One known-bad snapshot was read as completed, and in run 2 both known-good snapshots were blocked by tooling.

On a five-task Terminal-Bench 2.1 run, the verifier produced two false cleans in five trials. The shorter follow-up produced one false clean in two trials.

## How it works

Each task carries at least three known-bad answers, plus a set of careless scripts. The careless set covers do-nothing, fake-it, skip-check, wrong-target, and half-done. Each script has a header line that states the reason it must fail. The grader must reject every known-bad and every careless script. A grader that passes any of them fails the task's static check.

The static validator fails closed when a known-bad is visible to the solver, when a manifest is weak, or when the ceiling solution would also pass a known-bad.

A standalone solvability script checks that each task can be solved from the workspace alone. No task is admitted on the strength of its grader alone.

## What it caught

- **Verifier false cleans.** The falsifier caught the verifier on the known-bad snapshots, and the 15-task batch gate accepted two false cleans, scored 0.98 and 0.93.
- **Fake success.** In the Docker isolation smoke, a known-bad file task scored 0.0 with a stub verifier that claimed completion. The golden file task scored 1.0.
- **Clean instrument result.** The lifecycle factuality board ran 17 known-bad mutations and one positive row. It produced 0 false cleans and passed. It checks the instrument, not model capability.

## Where it fell short

Known-bads are written by the same people who write the verifier, so they test the failures we thought of. The falsifier used five snapshots taken from earlier runs. The planned fix is our own fixtures with more known-good cases, and the verifier has not passed a version of that test. The docker smoke has three cases. Careless scripts show that the grader rejects obvious failures; they do not show that a model avoids subtle wrong answers. Solvability has not been established for any ported task, and the suite still needs independent review.
