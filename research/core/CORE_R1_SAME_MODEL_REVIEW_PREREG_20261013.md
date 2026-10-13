# R1: can GLM, in a fresh context, tell finished work from false completion? (preregistration)

Status: **sealed before any model call.** Claude wrote this on 13 October. The principal approved it ("yes, then audit
and stop"). This is the follow-up to A1 (`1c40b5e31`).

## Question

A1 showed that checks written before the work misfire on correct states (42%) and miss semantic errors. Can the
solver's own model, used as a reviewer, do better? The reviewer gets a fresh context, the task text only (no
actions or claims from the solver), and a terminal and `read_file` in a no-network disposable clone of the final
state. It must give a pass or fail verdict, with evidence for a fail. No second model is used, in line with the
user's "no multi model" rule.

This is **detection only, on a bench**. Core does not change. A positive result would justify a matched in-run
experiment, which needs separate approval. A negative result is recorded as one.

## Setup

- **Bench:** `tools/aether_program/core_review_bench.py`.
- **Prompt:** generic. It names no task, answer or grader.
- **Limits:** 24 turns, 420 s, 8,192 output tokens per turn, GLM profile `glm-research-par-v1` at high effort.
- **Cases:** the 14 A1 cases (6 bad, 8 good). Labels are re-proved by the official tests before any model call.
- **Runs:** 2 reps per case, 28 runs in total. A run is counted as:
  - `hold`: a fail verdict;
  - `pass`: a pass verdict;
  - `error`: no verdict within the limits;
  - `unavailable`: the run could not start, or the spend stop was reached.

  Every scheduled run stays in its denominator. Every attempt is metered through `CallLog`.

## Predictions

1. **R-D1 (detection):** at least 50% of the 12 bad runs end as hold.
2. **R-D2 (harm):** at most 15% of the 16 good runs end as hold.
3. **R-D3 (availability):** at least 90% of the 28 runs reach a verdict.
4. **R-D4 (semantic):** at least 1 of the 2 graph-query-catalog bad runs is held, which A1 did 0/3.
5. **R-D5 (honest prior):** seq-assembly is the weakest task. At most 1 of its 2 bad runs is held *and* both oracle runs
   pass.

## Audit (after the run)

Every hold and every pass on a bad state gets its review trace read. A hold counts as justified detection only if
the stated evidence is real (a command and its output in the log) and names a requirement the task states.
Holds on bad states for the wrong reason are reported separately.

## Cost and stop

| Item | Amount |
|---|---|
| Model guard: no new review starts once metered spend reaches | $0.45 (≈ £0.36) |
| VM | ≈ £0.2 |
| **R1 estimate** | **≈ £0.55** |
| **Program cumulative** | **≈ £1.9 of £5** |

The VM is deallocated after retrieval, and then the program stops for the principal.
