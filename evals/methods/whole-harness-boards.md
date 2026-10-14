# Whole-harness boards

This method scores the whole harness on a fixed evaluation board. The board holds hard tasks, flagship tasks, sentinel tasks, and suite tasks. Each trial is checked for launch integrity before it counts. Invalid trials are reported apart from scored trials.

The lesson: a board number is only as good as its launch record. Launch failures and queue starvation must be counted apart from capability, and a saturated board cannot separate two arms.

This matters because early boards counted infrastructure failures as zeros, and the headline numbers from them were misleading.

## Why we needed it

The full Terminal-Bench 2.1 board ran 241 tasks with two attempts each. In attempt 1, 216 of 241 trials never launched; they failed on an import crash. Attempt 2 was fully contaminated, with 0 of 241 scoreable. The valid-scored result was 5 of 19 (26.3%). The naive figure of 5 of 241 (2.07%) was misleading, and the full population was marked as insufficient evidence.

The decision history records the first whole-harness runs as all invalid, because the container runtime was down. Those runs were never rescored.

## How it works

The board registry lists each trial with a status. A trial is one of valid-scored, invalid-launch, or environment-invalid. The score is computed over valid trials only, and the count of invalid trials is printed beside it. A launcher refuses combinations that would run inertly.

The registry holds eight hard tasks (two flagship) and three to five sentinel or composition tasks. Promotion status is recorded in the registry itself. The current status is no promotion yet.

Saturation is checked directly. A task that is always 0 or always 1 across arms carries no information about the arms.

## What it caught

- **Saturated board.** About 18 of 60 trials were always 0 and about 12 were always 1 across arms, so the board could not discriminate. The three arm scores were 0.83, 0.93, and 0.90.
- **Queue starvation counted as zeros.** Queue-starved runs were counted as zeros, and an inert verifier arm with no callback and zero broker requests went unnoticed until it was caught by construction.
- **Green once, then red.** A five-homolog gate passed 5 of 5 on one run. On 17 June, verifier_clean was False on every scoreable row.

## Where it fell short

The repo holds no certified, scored whole-harness run. The attempts folder for the final board is absent from the tree and from every reference checked. The public boards are structural examples with no real per-trial scores. The conflict over whether the first whole-harness rows were invalid is unresolved between the decision history and the result rows.
