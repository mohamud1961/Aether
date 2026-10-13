# T1 — stock Terminus-2 + GLM-5.3-Flash on the B1 board (preregistration)

Status: **SEALED by Claude on 13 October 2026, before any T1 model call.** Authority: the principal's instruction
"run then terminus … on the exact B1 board … that way we have 2 traces" (13 Oct 2026). Budget stop ≈ £1.2.

## Question

B1 failed mainly by **false completion**: 6 of 15 voluntary finishes were wrong, usually after 3–41% of the
time limit. The public Claude Code + GLM-5.1 TB2.1 submission failed mainly by **timeout** (136 of ~184
failures), with ~15% of voluntary finishes wrong. Is our false-completion rate a property of GLM-5.3-Flash on
these tasks, or of Aether? T1 runs the stock harness on the same model, tasks, VM and grader, and keeps traces.

## Fixed setup

- **Arm `terminus2`:** Harbor's built-in `terminus-2` via `tools/aether_program/terminus_baseline.py`
  (`CORE_T1_ARMS_20261013.json`). No custom prompt, task knowledge or model-facing text; output cap 32768
  from the same profile; stock context handling. Credentials through the existing transient route.
- **Board:** B1's 9 tasks × 2 episodes = 18 rows, same task files, task-native timeouts, same pool manifest,
  same lanes and `--max-parallel-rows 4`. Grader: each task's own TB2.1 tests, run by Harbor after the agent ends.
- **Reporting:** every row reported; infra-invalid rows labelled, never replaced (one labelled rerun allowed
  if no model call was made). Token totals from Harbor `agent_result`; unknown usage stays unknown.

## Measures

1. Solves / 18 (graded rows as denominator; invalid shown separately).
2. **Wrong voluntary finishes / voluntary finishes** (agent ended before its timeout and the grader failed it).
3. Time used at each wrong finish, as a share of the task limit.
4. For each wrong finish: which stated requirement was unmet (from traces, after all rows end).

## Predictions (sealed)

- **P1:** Terminus wrong-finish rate ≥ 25% of its voluntary finishes, i.e. false completion is mostly
  model-driven on these tasks. **Falsifier:** < 20% with ≥ 8 voluntary finishes → the gap is harness-driven;
  then diff the traces before building any fix.
- **P2:** Terminus solves 6–10 of 18 (B1: 9 of 17 graded).
- **P3:** Terminus's median time at a wrong finish is a larger share of the limit than B1's (B1 median ≈ 15%).

## Not claimed

T1 is a same-model harness comparison on 9 hard tasks, 2 episodes each. It is not a capability claim, and
it does not rank Aether against Terminus. The model in the public Claude Code run (GLM-5.1, max effort)
differs from ours, so that comparison stays descriptive.
