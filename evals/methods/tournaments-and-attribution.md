# Tournaments and attribution

This method runs several mechanism arms on the same paired trials. Each arm is scored on target rows and sentinel rows. A change is credited only when one difference explains the result, and only when the sample is large enough to separate the arms.

The lesson: small tournaments produce winners that do not replicate. Attribution needs paired trials and a power calculation written before the run.

This matters because most candidate mechanisms in this programme were first judged on one to three tasks.

## Why we needed it

The first scored tournament ran 3 tasks, 4 arms, and 12 trials. The control scored 0 of 2 on target rows and 1 of 1 on the sentinel. The ignored-IDs arm scored 0 of 2 and was killed. The no-call arm scored 1 of 2 and was kept. The combined arm scored 2 of 2 on target rows and 0 of 1 on the sentinel. The combined guard hard-coded one tool's argument injection.

A later family tournament found no winner. Its verifier-repair family passed every row and did not discriminate.

Cost savings were not the same as fewer calls. The solver's prefix bytes fell 29% and its config bytes fell 74%, but solver calls rose from 16 to 25 (+56%).

## How it works

Arms share tasks, and each arm differs from the control by one change. Every arm reports target and sentinel results separately. A keep decision needs a target win and no sentinel regression. A promotion decision needs a sample sized in advance. Duplicate tournaments are graded as duplicates and are not counted twice. The decision table and prediction file are stored with the result.

When a trial shows no headroom, the arm is not scored on efficiency. A task that every arm solves cannot separate them.

## What it caught

- **Win that failed the gate.** A tooling change got a directional efficiency effect that replicated. It missed the promotion gate, so the wording was rejected as a default.
- **Sample too small to decide.** A commitment ablation ran 9 trials per arm. The control scored 2 of 9 and the treatment 3 of 9. The result was kept as inconclusive and the control was kept.
- **Headroom-free efficiency test.** Both arms solved both tasks, so the test could measure efficiency only. The full-replay arm used 19 calls on one task against 45 for the latest-exchange arm, and 13 against 143 on the other. That is about 2.4x and about 11x. The 13x figure is in a second source that is not reconciled with the audit read.
- **Screen noise.** Per-task noise dominated the one-episode open-model screens, as the plan itself warned. The two combined screens gave 47 of 52 against 42 of 52, and the candidate was kept on that basis.

## Where it fell short

Only one per-variant tournament has been scored in the repo, and its sentinel set has one trial. Most arms in the later screens have 3 to 9 trials each. The open-model pool is 13 tasks, run for 1 to 4 episodes, and the plan warns that per-task noise dominates. The efficiency ratio is reported two ways across sources and has not been reconciled.
