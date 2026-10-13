# Core B1 — hardened Core 0.2.0 on a small TB2.1 board (preregistration)

Status: **SEALED by Claude on 13 October 2026, before any B1 model call.** Authority: the principal's instruction
"you have £5 budget, youre in charge / test and improve aether as much as possible", relayed verbatim by Codex
GPT-6-Astra's handback. Claude accepted ownership at f943ced6f.

## Question

Does hardened Core 0.2.0 do real work on TB2.1 tasks without harness-caused harm? Where is useful model work
still lost? B1 is a pressure screen, not a certification or a capability comparison. Fixes are chosen from what
the traces show, then B2 re-runs the same board on the fixed source.

## Frozen source and route

- **Source:** branch `codex/aether-core-takeover` at `f943ced6f2b93eaaa3dcdf1e99c465bba258c92b`. Executable
  checkpoint `d0192a38b`; wheel 0.2.0 SHA256 `51ea9a13…13e33a9`. It is copied to the VM with `git archive`; no
  edits during the run.
- **Agent:** `aether.core.harbor_agent:AetherCoreAgent` via `tools/aether_program/run_screen.py` (suite tb21),
  using the existing launcher `run_tb21_glm_diagnostic.py`. Harbor and its Python come from the launcher's gates.
- **Model:** GLM-5.3-Flash, Azure Fireworks, endpoint `resource`, deployments
  `FW-GLM-5.3-Flash-par` (3 lanes) and `-par-2` (1 lane). Profiles `glm-research-par-v1` and `-par2-v1`,
  unchanged. Credentials come through the launcher's existing transient route; none are read, printed or
  substituted.
- **Arm `core-b1`:** `--core-review off --core-context clm --core-repl on --core-images on`. These are V4's
  context, REPL and image settings, without the reviewer or contract review: B1 measures the runtime itself. No reviewer calls.

## Board

All 9 V4 tasks × 2 episodes = 18 rows: net-fit, seq-assembly, construct-assembly, repair-history, binary-extract,
graph-query-catalog, credential-recovery-recovery, dual-language-build, cipher-diff-attack. Each uses V4's task
timeout and task files, from the VM's existing `<home>/finalproof_sources_20260923/tb21/tasks`.
`game-port-build` is not in B1.

**Grader:** each task's own TB2.1 tests, run by Harbor after the agent ends (reward 1/0). Neither Aether nor
Claude grades. A runtime "finished" is a submission, not a pass.

**Reference (descriptive only, different code):** V4 solved 26 of 36 rows on these tasks. By task:
repair-history, dual-language-build and cipher-diff-attack 4/4; binary-extract and graph-query-catalog 3/4; net-fit and credential-recovery 2/4; seq-assembly and construct-assembly 0/4.

## Accounting and retry policy

- Every provider attempt, from every role, is counted from `core_calls.jsonl`, including failed, cancelled and
  open attempts. Unknown usage stays unknown and the cost is then reported as a lower bound.
- **Cost basis:** Azure retail meters for the deployed product (effective 1 Sep 2026), USD per 1M tokens:
  uncached input 0.188, cached input 0.038, output 0.625 (reasoning is billed as output). These are converted to
  GBP at 0.80 (conservative). VM Standard_D8ds_v4 costs $0.452/h, about £0.36/h, from start to deallocation.
- **Correction:** V4's recorded `cost_usd` used 0.15/0.03/0.50 per 1M, about 25% below the real meters. Its
  36 rows cost about £1.66 at the real meters.
- **Retries:** the provider honours Retry-After up to the run deadline (unchanged). The screen does not rerun a
  row automatically. A row that is infra-invalid (launch or environment failure before any model call) may be
  rerun once, labelled, and both rows are kept.

## Budget

| Item | Estimate |
|---|---|
| B1 model (18 rows, V4 means ×2 at real meters) | ≈ £0.9 |
| B1 VM (setup + about 50 min of rows + retrieval) | ≈ £0.6 |
| B2 same board after fixes | ≈ £1.5 |
| Reserve (reruns, a make-doom post-failure row if earned) | ≈ £1.5 |

**Hard stop:** £4.50 cumulative estimated spend. The VM is deallocated whenever no sealed batch is running.

## Predictions (recorded before running)

1. **P1 (primary):** 0 rows with a harness-caused failure. A harness-caused failure is any of: a crash, a lost
   tool result, a stuck terminal or REPL, missing or invented accounting, a deadline overrun, or a context
   error. Every row's trace is audited.
2. **P2:** 0 rows with unaccounted attempts (`open` = 0 after the run, and every attempt has an end row).
3. **P3:** solved rows are not distinguishable from V4 at n=18. This is recorded so that any difference is not
   over-read.
4. **P4:** seq-assembly and construct-assembly reach the deadline unsolved again. Their traces are the main
   source of pressure on context, time and tools.

## Kill/keep

B1 changes nothing by itself. A fix goes into B2 only if a B1 trace shows the failure and an offline test
reproduces it (failing before the fix). B2 keeps a fix if P1 holds and no task loses a pass for a reason
attributable to the fix. Model-policy changes (output cap, effort, idle cutoff, context mode) need a concrete
pressure case and are measured separately, never bundled with substrate fixes.

## Amendment 1 (13 October, before any model call)

Two launch attempts were infra-invalid; both are kept on the VM (`<run-dir>/b1/`). No model call
was made and no row reached a task.

1. **Attempt 1 (`screen_attempt1_infra_invalid`):** the source was copied with `git archive`, so the launch gate
   correctly refused it ("git status failed; custody cannot be established"). Fixed by making
   `<home>/claude-b1` a real git checkout of the sealed commit (git bundle).
2. **Attempt 2 (`b1r2`):** Harbor failed to start the agent. `AetherCoreAgent.version()` read the installed
   package metadata, and the research launcher runs Core from the source tree without installing the wheel
   (PackageNotFoundError). This is a real Core defect: run from source, the adapter could not start.
   `version()` now reports `core-unpackaged` in that case; the launcher manifest records the exact commit.
   There is a new adapter test, and the package suite gives 120 passed, 22 platform skips.

B1 runs as attempt 3 on the commit that carries this fix and amendment. Nothing else changed: board, arm,
route, prices, predictions and stop line are as sealed above.

## Results (attempt 3, commit `01512422a`, 13 October 2026)

All 18 rows ran. 17 were graded; seq-assembly ep 1 ended with `provider_error` before grading.
Harbor's grader passed **10 of 17 graded rows** (10/18 counting the lost row). Evidence:
`audit_output/aether_b1_20261013/` (traces, call logs, grader output, `B1_AUDIT.json`).

| Task | B1 | V4 (different code) | Note |
|---|---|---|---|
| repair-history | 2/2 | 4/4 | |
| binary-extract | 2/2 | 3/4 | |
| dual-language-build | 2/2 | 4/4 | |
| graph-query-catalog | 1/2 | 3/4 | ep 1 finished with a wrong answer |
| credential-recovery-recovery | 1/2 | 2/4 | ep 2 finished with a wrong answer |
| cipher-diff-attack | 1/2 | 4/4 | ep 2 hit the deadline (111 attempts) |
| net-fit | 0/2 | 2/4 | both finished early with the wrong edge orientation |
| seq-assembly | 0/2 | 0/4 | ep 1 lost to a cut stream (harness); ep 2 finished, `test_primers` failed |
| construct-assembly | 0/2 | 0/4 | ep 1 hit the deadline; ep 2 finished unsolved at 432 s |

**Predictions:**

- **P1 failed.** One row had a harness-caused failure. On seq-assembly ep 1, the provider stream ended
  without a `finish_reason`, and Core ended the run instead of retrying. Nothing from the cut stream had been
  dispatched, so a retry was safe. Fixed in `c7679c1cc`: `IncompleteStream` is retryable and the partial
  response is kept in the call log. The two tests that had encoded "no retry" were updated, and the new tests
  fail on the old code. No other row had a crash, lost tool result, stuck terminal or REPL, deadline overrun
  or context error. Every row had 0 tool errors.
- **P2 held.** Every row had 0 open attempts. Two attempts had unknown usage, and both have end rows:
  - the cut stream on seq-assembly ep 1;
  - an attempt cancelled at the deadline on construct-assembly ep 1.

  Those two rows are priced as lower bounds.
- **P3 held (descriptive).** 10/17 against V4's 26/36. The per-task differences are within 2-episode noise.
  cipher-diff-attack 1/2 against 4/4 is the largest gap; its failed episode was a deadline, not an error.
- **P4 held in part.**
  - Neither task was solved.
  - construct-assembly ep 1 reached the deadline.
  - construct-assembly ep 2 (432 s) and seq-assembly ep 2 (746 s of 1,800 s) finished early with wrong answers.
  - seq-assembly ep 1 was lost.

**Dominant pressure: the run ends early with a wrong answer** (6 rows: net-fit ×2, seq-assembly ep 2, construct-assembly ep 2,
credential-recovery ep 2, graph-query-catalog ep 1). The model submitted, and no review was enabled in this arm. This is a
model-policy question (B1 ran without review), not a substrate defect. Under the kill/keep rule it is measured
separately and not bundled into B2.

**Open observation O1 (seq-assembly ep 2):**
- Turn 2 spent 32,768 reasoning tokens over 270 s and ended at `length` with no tool call.
- The next request carried 38,707 input tokens, which is over the 32k CLM budget.
- It was followed by three low-effort turns, each cut at 8,192 tokens.
- About 470 s went to reasoning with no action.

It is unconfirmed whether the replayed reasoning is counted before the request is sent. It needs an offline
reproduction before any fix.

**Cost (real meters, GBP at 0.80):**

| Item | Cost |
|---|---|
| Model, 18 rows | $0.634 (£0.51); seq-assembly ep 1 and construct-assembly ep 1 are lower bounds |
| VM, 11:50:48 to 13:04:54Z (74.1 min) | ≈ $0.56 (£0.45) |
| Smoke row | ≈ $0.007 |
| Attempts 1 and 2 (no model calls) | — |
| **B1 total** | **≈ £0.96** of the £1.5 approved |

The VM was deallocated and the deallocation verified; no clone containers or images remain.

**Fixes from B1 traces, each with a failing-first offline test:**
- `c7679c1cc`: cut-stream retry.
- `8c0e8775d`: screen rows priced from all-role call totals.
- `d6bd7f9ae`: audit spend taken from every call-log attempt.

B2 (same board on the fixed source) needs the principal's approval before any spend.

### Review gate (Codex GPT-6-Astra, 13 October, on `fd59b1b11`)

- **Retry (`c7679c1cc`):** no double-dispatch path was found. An unfinished stream is rejected before any
  executable tool call is produced, and the loop dispatches only the returned successful turn. A retried
  attempt can still be billed, so budget limits stay conservative for unknown-usage attempts.
  Follow-up: add a loop-level regression in which a cut partial tool call is followed by a retry, ending with
  exactly one observable effect.
- **O1 reclassified:** this is a mismatch in the budget contract, not missing accounting. `clm.tokens()`
  includes replayed reasoning. `held()` subtracts it on purpose, and `over_limit()` uses `held()`.
  GPT-6-Astra's offline reproduction gave:
  - full request estimate 40,299 tokens;
  - held 7,531 tokens;
  - `over_limit` False, with the reasoning preserved.

  The 32k budget therefore limits editable context, not the whole request. Nothing shows that the overshoot
  caused the 470 s of reasoning.
  Follow-up: separate the editable-state budget from the full wire/provider admission limit. Preserve
  reasoning rather than compact it. Replay the actual O1 messages through pre-send admission offline before
  choosing any policy change.
- **Not changed by the review:** no B2 run is authorized.
