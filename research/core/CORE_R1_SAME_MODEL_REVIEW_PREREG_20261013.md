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

## Results (run on `b311d0780`, 13 October, 15:03–15:26Z)

All 14 labels were re-proved by the official tests. 28 of 28 runs completed: 17 reached a verdict and 11
ended at the 24-turn limit. Evidence is in `audit_output/aether_r1_20261013/`.

| Task | Bad runs (hold / pass / error) | Good runs (hold / pass / error) |
|---|---|---|
| net-fit | 2 / 2 / 0 | 0 / 4 / 0 |
| seq-assembly | 1 / 1 / 0 | 0 / 0 / 2 |
| credential-recovery-recovery | 0 / 0 / 4 | 0 / 3 / 3 |
| graph-query-catalog | 0 / 0 / 2 | 1 / 3 / 0 |
| **Total** | **3 / 3 / 6** of 12 | **1 / 10 / 5** of 16 |

**Predictions:**
- **R-D1 failed.** 3 of 12 bad runs held (25%, predicted at least 50%).
- **R-D2 held.** 1 of 16 good runs held (6%, ceiling 15%). This is far better than A1's 42%.
- **R-D3 failed.** 17 of 28 runs reached a verdict (61%, predicted at least 90%).
- **R-D4 failed.** graph-query-catalog bad runs: 0 of 2 held; both hit the turn limit.
- **R-D5 failed.** One seq-assembly bad run was held, but neither oracle run passed (both hit the turn limit).

## Audit of every verdict on a bad state, and of the false hold

| Run | Verdict | Assessment |
|---|---|---|
| **net-fit B1 ep 1, r1 and r2** | hold | **Justified, with real measured evidence.** Both reviewers fitted the CPDs and measured the delivered `final_bn_sample.csv`. The samples were independent of U (corr ≈ 0.01, where about 0.70 was expected), and the node means equal the fitted intercepts. The worker's script had effectively set every node's parents to 0, a real defect against a stated requirement that the grader's first failing test (DAG structure) never reached. |
| **seq-assembly B1 ep 2, r1** | hold | **On a bad state, but for a doubtful reason.** The cited "4-nt spacer is required" is not the standard BsaI design. The second claim, an annealing mismatch, was not shown with a command. This is not counted as clean detection. |
| seq-assembly B1 ep 2, r2 | pass | Missed. |
| net-fit flipped edge, r1 and r2 | pass | Missed. The orientation is decided by the task's stated tie-break rule, and the reviewer did not apply it. |
| **graph-query-catalog oracle, r1** | hold (**false**) | The reviewer could not run the query: rdflib could not be installed with no network, and the fixture lacks the tools the solver had installed. It simulated the graph-query by hand and produced a long, self-contradictory argument ("actually returning 1-2 rows"). |

**Turn-limit errors (11):**
- credential-recovery ×7: every one tried to re-solve the task by carving and inflating the deflate stream byte by byte
  with `dd`/`od`/perl, and ran out of turns.
- graph-query-catalog bad ×2: the reviewers recomputed enrolments by hand in perl, which was slow and error-prone.
- seq-assembly oracle ×2.

In each case, verification meant re-deriving the answer, and that cost as much as solving the task.

## What R1 shows

1. **Same-model, fresh-context review rarely harms correct work:** 1 false hold in 16, against 42% for the
   prewritten checks. That false hold came from a tool it could not use.
2. **It is strong when correctness can be measured from the produced artefacts.** In net-fit, it computed
   statistics from the outputs and inputs: 2 of 2 justified holds, and 6 of 6 correct passes on good states.
3. **It is weak when the only way to check is to solve the task again** (credential-recovery, graph-query semantics, a
   tie-break orientation). It either runs out of budget or misses the error. Detection overall: 25%.
4. **Environment fidelity matters.** A reviewer without the solver's tools and network falls back to
   simulating by hand, and that produced the one false hold.

**Bench limits that bear on the reading:**
- The fixtures plant output files only, not the tools the solver installed.
- The clone has no network.
- 24 turns is below what the solver needed on credential-recovery.

A matched in-run reviewer would see the solver's real final container. **Nothing is promoted.**

## Cost

| Item | Cost |
|---|---|
| Model (metered; 11 failed attempts have unknown usage) | $0.3975 lower bound (≈ £0.32) |
| VM, 15:02:19 to 15:27:10Z | ≈ $0.19 (≈ £0.15) |
| **R1 total** | **≈ £0.47** |
| **Program cumulative** (B1 £0.96 + A1 £0.35 + R1 £0.47) | **≈ £1.78 of £5** |

The VM was deallocated and the deallocation verified at 15:27Z.

**Process defect:** Claude's background waiter used `pgrep -f`, which matched its own ssh command line, so it
never reported completion. It was found by a manual check and stopped.
