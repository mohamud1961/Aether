# P1 repair test (step 2) and think-reminder test (pre-registration, 2026-10-16)

Status: **SEALED by Claude before any row of either test.** Authority: the principal's "do the full plan on old account,
once done, extract, save, deallocate, audit entirely" and "test reasoning always on one single task"
(2026-10-16), after the step-4 reviews (Codex, ChatGPT). Host: the run VM (old account), GLM-5.3-Flash via managed
identity, B1 route, ≤ 3 parallel rows (step 4 had a rate-limit storm at 4).

## Step 0 (done before sealing)

Step-4 evidence (35 attempted rows, both launch scripts, logs, results, audit scripts) archived to
`run-evidence/p1-step4-20261016/p1_step4_20261016.tgz` (sha256 `e88740e49c2278bf…`) and to
`audit_output/aether_p1_step4_20261016/`. Reconciliation: the 322 calls without a reasoning count in construct-assembly
`coreb1` e2 are **failed attempts (HTTP 429 RateLimitError)**; 448 of 1,988 step-4 call records were 429s (364
`coreb1`, 84 `rb1`). graph-query-catalog: **both** e1 rows installed rdflib and ran their query (correcting Amendment 1 item 5:
the baseline was not without execution; it ran once and finished).

## Test A — does correct, concrete feedback produce a repair? (step 2)

**Question (Codex/ChatGPT):** is the bottleneck producing the right evidence, or acting on it? Here the evidence is
supplied, so only "acting on it" is tested. It is not autonomous checking.

**Instrument** (commit `a54b43cf5`, flag-gated, off by default): the first finish is held once with a generic
nudge ("inspect … against each requirement … repair … then call finish again"). Both arms run the same
experiment-supplied check in the task container at that moment:
- `nudge` arm: the check runs and is **recorded only**; the model sees the nudge alone.
- `check` arm: the model sees the nudge **plus** the check's verdict and output.

So both arms record whether the first finish was defective, and the only difference is the shown evidence.
Live, not replayed: Harbor never saved end-of-run workspaces, so the bad states arise naturally.

**Checks** (`tools/aether_program/finish_checks/`), derived from the task text only, never from the hidden tests:
- net-fit: CSV read by its header (`to`,`from`); "U has no parents"; "six total edges"; an intervention on
  Y removes the edges into Y and keeps the rest. Known limitation: a wrong graph that satisfies all of these passes.
- credential-recovery-recovery: each line is a guess; ≥ 1 line must be 23 characters, start `8XD`, end `W54`, `[A-Z0-9]`.
- Offline validation `validate.py`: 16/16 expected verdicts, including legitimate alternatives (column order,
  extra valid-format guesses) and **real step-4 delivered net-fit files** recovered from traces (all four step-4 net-fit
  states fail the check, each for a stated reason).

**Board:** net-fit × {nudge, check} × 4 episodes; credential-recovery-recovery × {nudge, check} × 3 episodes = 14 rows.

**Definitions.** *Defective first finish (D)*: the recorded check FAILED at the held finish. *Repair*: on a D row,
the final graded state fixes the defect the check named (net-fit: the grader's learned/intervened structure subtests
for the named file pass; credential-recovery: reward 1). *Solve*: grader reward 1. *Damage*: a row whose check PASSED at the
held finish but whose final reward is 0 while the change after the nudge touched a delivered file.

**Predictions:**
- **S2-P1 (primary):** repairs on D rows: `check` ≥ `nudge` + 2. Falsifier: smaller gap.
- **S2-P2:** `check` repairs ≥ ½ of its D rows (the feedback is usually acted on).
- **S2-P3 (harm):** 0 damaged rows in `check`; `check` timeouts ≤ `nudge` + 1.
- **S2-P4:** solves `check` ≥ `nudge` (net-fit solving also needs correct statistics and sampling; repair ≠ solve).
- Honest prior: the finish receipt (S6, showing the bytes) produced 0/18 corrections; the named re-read probe
  (P1) recognised the net-fit error 18/21 times. A failed S2-P1 means GLM does not act on even correct, named evidence.

**Decision rule (from the reviews):** S2-P1 fails → next is how the solver responds to contradictions, not
check generation. S2-P1 holds → step 3 (the solver writes its own source-grounded checks) becomes the next
proposal; it is **not** run tonight (needs a new pre-registration and the principal's review).

## Test B — does a "think before acting" reminder change anything? (one task)

**Probes (done before sealing, ≈ $0.15):** 4 logged zero-reasoning requests (net-fit, credential-recovery, graph-query-catalog, repair-history),
replayed unchanged except for the variant.
- Probe 1: `thinking: {type: enabled}` 1/8 calls reasoned (> 20 tokens); `chat_template_kwargs.enable_thinking`
  2/8; `tool_choice: auto` 2/8; unchanged 2/8. **No provider switch forces reasoning.** The same request can give
  0 or 3,302 reasoning tokens.
- Probe 2: unchanged 0/12; a system-prompt line asking to reason before every action 3/12 (mean 204 tokens); a
  one-line user reminder after the results **7/12 (mean 502)**. The net-fit request gave the same 26-token reply under
  every variant.

**Instrument** (commit `d60a32fad`): `--core-think on` appends the reminder ("[reminder] Think through the last
result and your next step before acting.") as a user message after every turn's results. Off: request unchanged.

**Board:** net-fit × {`coreb1`, `think`} × 4 episodes = 8 rows (net-fit: the studied failure, cheap, nearly
always wrong at baseline, so a gain is visible).

**Predictions:**
- **T-P1 (manipulation):** `think` share of calls with > 20 reasoning tokens ≥ 2 × `coreb1`'s. If this fails, the
  reminder did not turn reasoning on and T-P2 is uninformative.
- **T-P2 (outcome):** `think` solves ≥ `coreb1` + 2 of 4. Honest prior: fails (S2: written analysis did not
  separate right from wrong finishes).
- **T-P3 (cost):** reported descriptively (more reasoning tokens are expected).

## Audit (after both tests)

Per row: outcome, finish type, held-finish check verdict, what the model did after the nudge (hand-read), cost,
calls, 429s. Reasoning tokens per arm (provider-reported; failed attempts excluded and counted separately). Hand
reading of every D row's response to the nudge or check: acknowledged? changed the file? re-ran the check?

## Budget and stop

Expected ≈ $1 model (22 rows at $0.02–0.08) plus ≈ $0.7 VM. **Hard stop: $3 token-priced for both tests
together.** After the runs: archive to blob and `audit_output/`, deallocate the run VM, audit, commit, stop for
reviews.

## Amendment 1 (2026-10-16, before any extra row; user-approved "yes run extra check-arm episodes")

Interim state when written: the two valid net-fit `check` rows both **passed** the check at the held finish (one with a
correct graph that failed only the sampled-data test; one with a wrong graph that satisfies every stated
constraint, the check's known blind spot), so the `check` arm had **0 defective (D) rows**: S2-P1 was untestable.
The three valid `nudge` rows were all D, and none repaired the graph.

Change: the net-fit `check` arm gets **8 extra episodes (e5–e12)**, same flags, run after the queued infra-invalid
reruns, ≤ 3 parallel. No other arm is extended. Because arm sizes now differ, S2-P1/P2 are scored as **repair
rates on D rows** (check repairs / check D rows vs nudge repairs / nudge D rows), with counts reported; "≥ nudge +
2" is restated as "check repair rate exceeds nudge's by ≥ 2 rows' worth on the nudge arm's D count". If the
`check` arm still has fewer than 3 D rows after e12, S2-P1 is reported **untested**, not failed. Extra cost ≈
$0.15; the $3 cap is unchanged.

## Amendment 1 not executed

The 8 extra `check` episodes (e5–e12) were **cancelled before any of them started** (the principal's later instruction,
in favour of the matched repair test `CORE_P1_MATCHED_REPAIR_PREREG_20261016.md`). The launcher process was killed
before its first row; no extra row exists. Scoring below uses the original board.

## Results (2026-10-16, the run VM, commit `e62af8cf4` lineage, 22 valid rows)

**Custody.** Archive `run-evidence/p1-step2-20261016/p1_step2_20261016.tgz` (sha256 `a9d6baf0f619f41f…`), extracted
to `audit_output/aether_p1_step2_20261016/`; audit script `p2audit.py` (scratchpad). 26 attempts: 4 first-wave net-fit rows
infra-invalid (Harbor's 10 s `docker info` preflight on a cold concurrent start, not a Docker restart; the same cause
probably explains step 4's 3 invalid rows), rerun as `a2` by relaunching the screen. 0 HTTP 429s. Token-priced spend
**$0.545** (plus ≈ $0.15 probes).

**Manipulation checks (verified in the files, not the flags).** `check` rows' held-finish text carries the check
output; `nudge` rows carry the nudge only, with the check recorded in `finish_second_look`. The think reminder is in
12/13 requests of a sampled `think` row (the first request has no prior result) and in 0 `coreb1` requests;
`think_reminder: True` in its run record.

| Task | Arm | Solves | D rows (held check FAILED) | Repairs on D | Cost |
|---|---|---|---|---|---|
| net-fit | `nudge` | 0/4 | 4 | 0/4 | $0.067 |
| net-fit | `check` | 0/4 | 2 | 0/2 | $0.060 |
| credential-recovery | `nudge` | 3/3 | 0 | – | $0.101 |
| credential-recovery | `check` | 3/3 | 1 | **1/1** | $0.103 |
| net-fit | `coreb1` | 0/4 | – | – | $0.147 |
| net-fit | `think` | 0/4 | – | – | $0.066 |

### Hand reading of every D row

- **credential-recovery `check` e3 — real repair.** First finish wrote `PASSWORD=<answer>`; the check named the prefix; GLM
  rewrote the bare answer, re-measured it, finished; reward 1. The grader matches whole lines exactly, so the
  original file would have scored 0: the shown check turned a fail into a pass.
- **net-fit `check` e1-a2 — acted on the check, the defect was deeper.** The check said the rows put parents on U; GLM
  reasoned it had the column reading backwards, swapped the write, re-printed, ticked "U has no parents ✓" and
  finished. The file now satisfies the check, but its graph (U→R, M→R, M→Y, R→Y, Y→D, R→D) is wrong in structure,
  so both graph tests still fail: the check's known blind spot (a consistent wrong graph passes).
- **net-fit `check` e4-a2 — fixed what was named, broke something else.** It swapped the orientation, but overwrote
  *both* files with all six edges, so the intervened file no longer removes the edges into Y. It did not re-run the
  check and finished. Its graph also has D→Y instead of Y→D.
- **net-fit `nudge` (4 D rows) — no repair.** Each re-printed its files and ticked them. `nudge` e2 had the learned
  graph **correct** and removed the wrong edge in the intervention (Y→D instead of U→Y); on re-reading it wrote
  "5 edges (Y→U removed) ✓" about a file that still contains U→Y. Generic re-inspection misread its own file.

### The principal's question: did GLM fix the net-fit graph but fail another grader part, or fail the graph itself?

**It fails the graph itself.** Across the 16 valid net-fit rows (step 2 + think), only **1** ends with both graph tests
passing (`check` e2, which failed only `test_sampled_data`); learned graph correct in 3/16 (`check` e2, `nudge` e2,
`think` e4), and 15/16 rows fail at least one graph test. In step 4, learned passed 1/2 per arm, both graphs 0/4.
Sampling is a secondary loss; the graph files are the main one.

### Predictions

- **S2-P1 FAILED.** D-row repair rate `check` 1/3 vs `nudge` 0/4: 1.33 rows' worth on the nudge D count, below +2.
  (The `check` arm reached 3 D rows across both tasks, so it is scored, not "untested".) On net-fit alone: 0/2 vs 0/4.
- **S2-P2 FAILED.** `check` repaired 1/3 D rows (< ½).
- **S2-P3 HELD.** 0 damaged `check` rows (no `check` row that passed at the hold wrote a delivered file afterwards);
  timeouts 0 vs 0.
- **S2-P4 HELD** (equal): solves 3 vs 3.
- **T-P1 FAILED (manipulation).** Share of calls with > 20 reasoning tokens: `think` 27/90 (0.30) vs `coreb1` 64/155
  (0.41). In the replayed probes the reminder raised reasoning (7/12); inside live runs it did not.
- **T-P2 FAILED** (0/4 vs 0/4), uninformative given T-P1.
- **T-P3 (descriptive):** `think` $0.066 vs `coreb1` $0.147 (one `coreb1` row of 85 calls costs $0.096); mean
  reasoning tokens per call 134 vs 259.

### What this means

Shown, concrete evidence was **acted on every time** (3/3 D rows changed the file in the named way), but the
action was literal: it fixed the named symptom and stopped. When the named symptom was the whole defect (credential-recovery),
that solved the task; when it sat on top of a wrong structure (net-fit), it did not, and in one row the edit created a new
violation that went unchecked. Generic re-inspection (nudge) acted 0/4 and in one row misread the file. So "acting on
evidence" is not the bottleneck by itself; the evidence has to cover the defect. The matched repair test (from known
broken files) measures this without depending on live defects.
