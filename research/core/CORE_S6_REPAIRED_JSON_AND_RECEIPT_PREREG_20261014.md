# Core S6: repaired JSON turns (x2r) and the finish receipt (r1) (preregistration)

Status: **SEALED by Claude on 14 Oct 2026, before any S6 model call.**

Authority: the principal's instruction of 14 Oct. Claude is in charge of the £7.

## Arms (each one change from the B1 baseline, flag-gated)

- **x2r** = `--core-turn json` at commit `95a5664a0`. This is S5's x2 interface plus two changes:
  - the reported repair of unclosed action objects and stray quotes;
  - unreadable replies no longer count toward the idle stop.
- **r1** = `--core-finish receipt` with native tool turns (commit `b612bf83d`). On the first `finish`, the model sees the heads of every file changed under the working directory since the start, and is asked to check them against each requirement. The next `finish` ends the work. The receipt is information, not a gate, and is shown once.

  **Why:** the S4 and first-divergence audits found final claims that the delivered bytes contradicted. net-fit b1 e2's summary says R→M while its file encodes M→R. Terminus's content-free "Are you sure?" changed 0 of 13 outcomes.

## Board and comparison

- **Board:** the same 9 tasks × 2 episodes per arm, 36 rows, on the same route.
- **Reference:** S4's same-day b1 (12/18 solves; 4/16 wrong voluntary finishes, 25%; 2 timeouts) and S5's x2 (10/18).

## Predictions (recorded before running)

**x2r**

- **X-P1:** 0 runs stopped by the protocol. Every `no_tool_loop` stop in x2r counts against it.
- **X-P2:** ≥ 12 solves (at least b1's).
- **X-P3:** the wrong share of voluntary finishes is ≤ 25% (not worse than b1).

**r1**

- **R-P1 (primary):** the wrong share of voluntary finishes is ≤ 15%.
  - **Falsifier:** ≥ 25%, i.e. no better than b1.
- **R-P2 (mechanism):** in at least 2 rows, the model does more work after the receipt (any tool call besides `finish`).
- **R-P3 (harm):**
  - 0 rows where a state the grader would pass is changed into a failing one after the receipt. Audited from the trace: what changed after the receipt.
  - Timeouts ≤ b1's + 1.
- **R-P4:** ≥ 12 solves.

## Kill/keep

- **Keep a candidate default:** its primary prediction holds and solves are ≥ 12.
- **If both arms qualify:** they are combined only in a later, separately sealed batch.
- **No claim against Terminus without a fresh confirmation batch.** Even then, it is stated with its uncertainty: at n = 18, a gap of ±3 solves is noise (Fisher p = 0.50 for 12/18 vs 9/17).

## Budget

| Item | Estimate |
|---|---|
| Model | ≈ £1.5 |
| VM | ≈ £0.6 |

- **Hard stop:** £6.0 cumulative from the fresh £7. About £3.05 had been spent at sealing.

## Results (14 Oct 2026, 06:15–07:57Z at `585605cb3`; 36 valid rows, 0 infra-invalid)

| Task | x2r e1 / e2 | r1 e1 / e2 | (S4 b1 e1 / e2) |
|---|---|---|---|
| net-fit | ✗ wrong / ✗ wrong | ✗ wrong / ✗ wrong | ✗ / ✗ |
| seq-assembly | ✗ wrong / ✗ timeout | ✗ wrong / ✗ wrong | ✗ timeout / ✗ timeout |
| construct-assembly | ✗ wrong / **✓** | ✗ wrong / ✗ wrong | ✗ / ✗ |
| repair-history | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |
| binary-extract | ✗ wrong / ✓ | ✓ / ✓ | ✓ / ✓ |
| graph-query-catalog | ✗ wrong / ✓ | ✓ / ✗ wrong | ✓ / ✓ |
| credential-recovery-recovery | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |
| dual-language-build | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |
| cipher-diff-attack | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |

| | x2r | r1 | (S4 b1) |
|---|---|---|---|
| Solves | 10 of 18 | 11 of 18 | 12 of 18 |
| Wrong voluntary finishes | 6 of 17 (35%) | 7 of 18 (39%) | 4 of 16 (25%) |
| Timeouts | 1 | 0 | 2 |
| Protocol stops | 0 | — | — |

**x2r**

- **X-P1: HELD.** There were 0 protocol stops. cipher-diff-attack went from 0/2 (S5, both stopped) to 2/2, even though e1 had 7 unreadable replies and the repair handled 6 replies across the arm. The S5 harness loss is fixed.
- **X-P2: FAILED** (10 solves).
- **X-P3: FAILED** (35%).

**r1**

- **R-P1: FAILED; the falsifier was hit** (39% ≥ 25%).
- **R-P2: HELD in letter, empty in substance.** 4 of 18 rows ran one command after the receipt. All 4 were cleanup or format checks:
  - `rm` of scratch files: binary-extract, dual-language-build;
  - `git log`/`status`: repair-history;
  - `wc`/`grep` of the line format: construct-assembly.
  - **Corrections after a receipt: 0 of 18.** The other 14 rows re-finished at once, mostly with empty reasoning ("The receipt shows the file; everything meets requirements").
  - The first audited net-fit receipt showed a `to,from` file whose rows contradict the model's own claim. The model still re-finished.
- **R-P3: HELD.** No right state became wrong, and there were 0 timeouts. The cleanup `rm`s touched only scratch files. The seq-assembly timeouts became wrong finishes near the deadline (1,674 s and 1,347 s), so they did not become solves.
- **R-P4: FAILED** (11 solves).

**Decision**

- **Both arms are killed as candidate defaults.** The defaults stay `--core-turn tool --core-finish direct`.
- The receipt adds no information the model acts on. A wrong belief survives the very bytes that contradict it.
- The JSON-turn interface is now harness-loss-free. Pooled over S5 and S6 it scores 20/36, against the baseline's 21/35 (B1 + S4 b1). That is no difference.

**What this board says about the problem**

- Three cheap interventions at finish time all failed to move the wrong-finish share below the baseline's 25–35% band:
  - a confirmation question (Terminus);
  - deliberation forced every turn (x2/x2r);
  - showing the delivered bytes (r1).
- The wrong finishes sit on the same three domain tasks: net-fit, seq-assembly, construct-assembly.
- The errors are domain-correctness errors that the model cannot see from its own vantage, for example:
  - edge direction under a `to,from` header;
  - BsaI orientation on reverse primers;
  - chromophore residues.
- These are not lapses in checking. A finish-time mechanism cannot supply knowledge the model does not have.

Cost: model $1.658 (≈ £1.33; token-priced from metered usage; 1 lower bound on the seq-assembly x2r e2 timeout, where the final call was cancelled). VM 03:41–08:01Z for S3–S6 (≈ 4.3 h, ≈ £1.56). Program cumulative ≈ £4.98 of the fresh £7. No further live batch: a confirmation would exceed the £6.0 hard stop, and no arm qualified. The VM was deallocated and verified at 08:01Z. Evidence: `audit_output/aether_s6_20261014/` (main checkout; 36 rows, 36 traces).
