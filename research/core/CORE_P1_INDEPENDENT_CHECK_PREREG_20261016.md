# P1 independent-check experiment (A + B) — pre-registration (2026-10-16)

Status: **SEALED by Claude before any model call.** Authority: the principal's "go" (2026-10-16) after the ChatGPT
review "GO with A+B, conditional on preregistration", whose tightening is adopted below.

## Question

Does one generic solver-prompt paragraph that asks GLM to test each delivered file, **read the way its consumer will
read it**, against **facts not taken from the code that wrote it**, cause fewer wrong files, without harm elsewhere?

Origin: check-independence study (`CORE_P1_CHECK_INDEPENDENCE_STUDY_PREREG_20261016.md`, with Amendment 1): such
checks were rare (9/122 rows, 4 of them under the V4 contract mechanism) and caught 3/3 reversed files they met;
views, tuple compares and positional loads passed every reversed file. **Priors against:** step 4's read-back
paragraph (header-faithful reading, no independent fact) failed; A1 prewritten checks and V4's contract caught some
errors but also caused harm. The new paragraph differs from read-back only in requiring the independent fact and an
executed test in code.

## Treatment (one change)

`--core-readback independent` adds `tools.INDEPENDENT_CHECK_DOC` to the solver's system prompt (code commit recorded
below; unit tests show the prompt is otherwise byte-identical to base). No task text changes; no harness check runs.

Arms (`coreb1` base vs `ib1`): both `--core-review off --core-context clm --core-repl on --core-images on`;
`ib1` adds `--core-readback independent`. Same model (GLM-5.3-Flash via managed identity), tools, budgets, timeouts,
graders. Paired: every task × episode runs in both arms.

## Boards

**A (target, fresh graphs never used in any earlier row):** `eval_suite/role_p1/generate.py --board check`: g4
(5 nodes/5 edges, do(O)), g5 (6/6, do(S)), g6 (6/7, do(L)); same supplied fitted pgmpy model and grader as role
experiment 1. `tofrom` (reversal-prone): 3 graphs × **4** episodes × 2 arms = 24 rows; `fromto` (control): 3 × **2** ×
2 = 12 rows. Checker validated before any call: 36/36 fixture verdicts (oracle, reversed, dropped edge, unapplied
intervention, swapped header order, missing file); the role board still 72/72. Oracle run on the VM before model rows.

**B (harm screen + end-to-end):** TB tasks `net-fit` (end-to-end target), `graph-query-catalog`, `repair-history`,
`credential-recovery-recovery`, `dual-language-build`, `cipher-diff-attack` × 2 episodes × 2 arms = 24 rows (base
passed 5/6 of these at 2/2 or 1/2 in step 4). This is a **safety screen, not a safety proof**: zero regressions would
not show the paragraph harmless.

## Predictions (screening thresholds, not statistical proof)

- **I-P1 (primary, A tofrom):** `ib1` reversal rate ≤ `coreb1` rate − **20 points** (12 rows each), **and** `ib1` ≤
  `coreb1` on ≥ 2 of 3 graphs with no graph worse by more than 1. If `coreb1` reverses < 3/12 the board has no
  headroom: **inconclusive**, reported as such.
- **I-P2 (mechanism, A tofrom):** IH checks (the study's hand rubric: file read by its declared fields + a direction
  fact not derived from tuple order, tested in code) after a write in ≥ 6/12 `ib1` rows and ≥ `coreb1` + 4.
- **I-P3 (link, A):** every `ib1` row in which an IH check ran on a reversed file ends correct (contradiction →
  repair). Count reported; any exception hand-read.
- **I-P4 (graph harm, A fromto):** `ib1` correct ≥ `coreb1` − 1 (of 6).
- **I-P5 (task harm screen, B):** `ib1` solves ≥ `coreb1` − 1 (of 12) and no task drops by 2. Every row that
  `coreb1` solves and `ib1` fails is hand-read (cause: the check? time? unrelated?).
- **I-P6 (cost):** `ib1` mean token-priced cost per valid row ≤ 1.5× `coreb1` on each board; calls, output tokens
  and wall time also reported. Timeouts reported per arm.

Decision table (agreed with review): large reversal reduction + checks demonstrably made + no meaningful harm →
broader replication, **not** straight into Core; checks up but errors not down → do not promote; errors down without
more independent checks → investigate another mechanism; no independent checks produced → stop this prompt approach;
regressions or disproportionate overhead → reject or redesign.

## Procedure and budget

Order: oracle (A) → A model rows → B model rows. Each screen launched twice (second pass reruns only infra-invalid
cells). **Hard cap $3 token-priced** (estimate: A ≈ $0.2, B ≈ $1.7). If the cap would be exceeded the run stops and
the study is reported **incomplete**; no cases are dropped or selected to fit the budget. Evidence archived to blob
`p1-indep-20261016/` and `audit_output/aether_p1_indep_20261016/`; VM the run VM deallocated afterwards. Audit:
final files (grader `check.json` / test output), IH classification by hand from the code that ran, every
contradiction→repair traced, every B regression read. Failed predictions are recorded as failed.

**Code:** treatment and board at `0e98428ee` (branch `codex/aether-core-takeover`). Tests: aether-core 231 passed; `tests/test_core_launch.py` 27/27 on a clean checkout with only these commits (the shared worktree has another session's uncommitted launcher edits that fail 13 of them; the VM receives commits only).

## Results (2026-10-17)

Complete: every planned row ran and is valid (oracle 6/6; A tofrom 24, A fromto 12, B 24; 0 infra-invalid). Spend
**$1.23** token-priced of the $3 cap (A $0.21, B $1.01). Evidence: blob `p1-indep-20261016/` (A1, B1, B2 tarballs,
sha256 verified locally), `audit_output/aether_p1_indep_20261016/` (results rows, `piaudit.py`, `tl.py`,
`hand_labels.json`). the run VM deallocated 2026-10-17.

| Prediction | Result | Verdict |
|---|---|---|
| I-P1 reversals (A tofrom) | `coreb1` 5/12, `ib1` **7/12** (g4 1→2, g5 2→3, g6 2→2) | **FAILED**: treatment worse; `ib1` ≤ base on 1/3 graphs |
| I-P2 IH checks | `ib1` **5/12**, `coreb1` 1/12 (+4) | **FAILED** (threshold ≥6); the +4 part met |
| I-P3 IH on reversed → repair | `ib1` **0/1** (g4 e3); `coreb1` 1/1 (g5 e1) | **FAILED** |
| I-P4 fromto harm | 6/6 vs 6/6 | holds |
| I-P5 task harm (B) | `ib1` **12/12**, `coreb1` 8/12; no `ib1` regression | holds |
| I-P6 cost | tofrom 1.24×, fromto 1.03×, B 0.81×; timeouts `coreb1` 1, `ib1` 0 | holds |

**Mechanism.** The paragraph raised header-read independent checks fivefold, but four of the five ran on files that
were already correct. The one that met a reversed file (g4 e3) **failed correctly** and the model then rewrote the
check to match the file ("my error in the check… edges are (parent, child)") and finished reversed. g5 e4 wrote a
tuple-order check it described as independent. Five `ib1` rows made no candidate check. The archive pattern
(independent check on a reversed file → repair, 3/3) did not reproduce: when the check contradicted the model's
binding belief, the belief won.

**B is not evidence for the treatment.** The 12 vs 8 gap is two tasks at 2 vs 0. Hand-read: on net-fit all four
rows chose the R–M orientation during structure learning, before any check (`ib1` checks touched sample moments only);
on cipher-diff-attack both arms executed real attack tests and `coreb1` e1 passed its own 10/10 test then failed the grader. Neither
split traces to the check paragraph; read it as model×episode variance at n=2.

**Decision (per table):** checks up, errors not down → **do not promote**. `--core-readback independent` stays
default-off. This closes prompt-level levers for the binding failure: read-back, naming, and now independent checks
all fail to cut reversals. A further lever has to change what the model sees, or how a failing check is resolved, not
what it is told.
