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

---

## Results (13 Oct 2026, run 16:21–17:29Z at `68992e87f`; all 18 rows valid)

| Task | T1 ep1 | T1 ep2 | B1 ep1 / ep2 |
|---|---|---|---|
| net-fit | ✗ wrong finish 240 s | ✓ | ✗ wrong / ✗ wrong |
| seq-assembly | ✗ timeout | ✗ timeout | ✗ provider error / ✗ wrong |
| construct-assembly | ✗ timeout | ✗ wrong finish 1440 s | ✗ timeout / ✗ wrong |
| repair-history | ✓ | ✓ | ✓ / ✓ |
| binary-extract | ✓ | ✓ | ✓ / ✓ |
| graph-query-catalog | ✓ | ✓ | ✗ wrong / ✓ |
| credential-recovery-recovery | ✓ | ✗ timeout | ✓ / ✗ wrong |
| dual-language-build | ✓ | ✗ shell killed (harness) | ✓ / ✓ |
| cipher-diff-attack | ✓ | ✓ | ✓ / ✗ timeout |

- **Solves:** T1 12/18; B1 9/17 graded.
- **Voluntary finishes:** T1 13, of which **2 wrong (15%)**; B1 15, of which 6 wrong (40%).
- **Timeouts:** T1 4; B1 2.
- **Harness loss in T1:** dual-language-build ep2 ran a test loop with `exit 1` in Terminus's interactive shell; the tmux
  session closed ("Session has ended, breaking out of agent loop") at 310 s with no submission.
- **Confirmation prompt:** Terminus asked "Are you sure…?" before all 13 voluntary finishes. In every case the
  model reaffirmed in the next turn with no new command, so the prompt changed no outcome.

### Predictions

- **P1 (wrong-finish rate ≥ 25%): FAILED.** 2/13 = 15%, below the 20% falsifier with ≥ 8 finishes. On these
  tasks the gap is at least partly harness-driven.
- **P2 (6–10 solves): FAILED** (12).
- **P3 (T1 wrong finishes later in the limit than B1's ≈ 15% median): HELD, weakly** (7% and 80%; n = 2).

### Trace and reasoning-token audit

| Measure | T1 Terminus | B1 Aether |
|---|---|---|
| Model turns, 18 rows | 246 | 460 |
| Median output tokens per turn | **2,022** | **160** |
| Turns under 300 output tokens | 9% | 68% |
| Turns with zero reasoning tokens | 0% (every turn has reasoning text) | **67%** |
| Finish decisions made with zero reasoning | 0 of 13 | **13 of 17** row endings (final turn reasoning 0; max 267) |
| Total output tokens | 926k | 418k |

Request differences that can explain the gap (none yet tested in isolation):

1. Aether sends `tool_choice: "required"`; Terminus uses no native tools (JSON text with Analysis/Plan each turn).
2. Aether replays reasoning only on the newest assistant turn; earlier turns go back with `reasoning_content`
   stripped.
3. Aether sets `parallel_tool_calls: false` (one action per turn); Terminus batches keystrokes.
4. Both request max 32,768 output tokens. Aether asks `reasoning_effort: high`; Terminus sends none.

Claude Code + GLM-5.3-Flash (G4 sample) also ends with short final reasoning (median ≈ 100 chars) and also
false-finishes heavily. Across the three harnesses, more deliberation at the finish goes with fewer false
finishes. This is correlation, not yet a cause.

Shared model failures: net-fit DAG edge orientation fails on both harnesses (T1 ep1, B1 ep1–2); construct-assembly
fusion order claimed but wrong (T1 ep2); seq-assembly primer BsaI site (T1 ep2 at timeout; B1 ep2).

### Cost

Model (Harbor token totals; provider retries not counted, so a lower bound): 4.85M input (89% cached), 0.93M
output = $0.847 ≈ £0.68. VM 16:20:37–17:31:16Z ≈ £0.43. **T1 ≈ £1.11. Program ≈ £2.89 of £5.** VM deallocated
and verified. Evidence: `audit_output/aether_t1_20261013/` (credential scan: no leaks; matches were `task-`
strings and library code).
