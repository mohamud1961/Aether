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
