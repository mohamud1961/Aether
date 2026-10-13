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
