# Held-out evaluation

This method runs a fixed set of tasks that the harness was never tuned on. The set is preregistered with a falsifier and a promotion bar. Results are reported in aggregate only, so the task list stays private.

The lesson: the two held-out evaluations of the Gen 4 candidate both failed their own bars. Development numbers did not predict the held-out result.

This matters because a candidate tuned on development rows can look like it lifts a model when it does not.

## Why we needed it

The candidate's development screens used pools of 13 to 29 tasks, with one to four episodes each. One screen read 47 of 52 against 42 of 52 for the control. Those numbers are not a test of lift against a fixed reference on tasks the candidate had not been tuned on.

## How it works

The design is sealed in version control before any row runs. It names three held-out tasks, a falsifier, and a promotion bar. The candidate ran three repetitions per task, for nine attempts. The stock reference ran two repetitions per task, for six. The promotion bar was 9 of 9 across repetitions.

Each trial runs in a fresh container, and the grader's checks are reported separately from the verifier's verdict. A completed status is only counted as a verifier false clean if the verifier was called.

Task names do not appear in published pages. Only counts are reported.

## What it caught

- **October set, falsifier fired.** The candidate scored 5 of 9 (56%). The stock reference scored 4 of 6 (67%). The promotion bar of 9 of 9 was not met, and the claim that the candidate lifts the model was not supported.
- **Wrong submission not caught.** On one held-out task the candidate submitted a wrong answer, and the finish review did not catch it.
- **September set, closed negative.** The official grader scored 0 of 3. The grader's checks passed 14 of 50, 1 of 2, and 1 of 3. The two completed rows were grader disagreements, not verifier false cleans. The result was recorded as not validating the candidate.
- **Gate on the wrong measure.** A held-out mini board passed 30 contract-valid rows and 4 full passes, and was promoted on a mechanical gate. The semantic results were kept as diagnostic only.

## Where it fell short

Each held-out set has three tasks. Three repetitions cannot separate close results, and the stock reference had two. The mini board was promoted on a gate that did not measure task success. The verifier-head holdout reports 20 of 20 pooled in one source and a positive verdict on three controls in another, and the two have not been reconciled. Aggregate-only reporting is deliberate, so readers cannot audit individual tasks.
