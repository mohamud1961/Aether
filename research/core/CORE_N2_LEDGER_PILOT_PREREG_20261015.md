# N2: requirement ledger pilot — PRE-REGISTRATION (SEALED 15 Oct ~04:25Z)

Status: **authorized** by the principal (15 Oct, before going to bed: "you are now in autonomous mode … vm usage is unlimited
for tonight … you have £10 to spend on models"). Sealed before any row. Source: `720a57d44` (runtime code; this
sealing commit changes documents only), Linux-qualified on the run VM: gate 246 + 143 passed, no skips, no leftover
clone containers, images or volumes (`<run-dir>/n1/linux_qual_720a57d44.log`), including the real
read-only clone test. No Codex review (Codex is out of usage); the principal's go stands in for it.

## Why

`CORE_WRONG_FINISH_DIVERGENCE_STUDY_20261015.md`: the recurring wrong finishes across harnesses and models sit on
requirements the task states explicitly, checked against the run's own reading. One minimal intervention against
that type: the requirement ledger (`--core-ledger on`, `916cef586`). Nothing else changes between the arms.

## Design

- Arms (`CORE_N2_LEDGER_ARMS_20261015.json`): `e` (N1's arm `e`, the concurrent baseline on this host) and `g` =
  `e` + `--core-ledger on`. Verifier off in both (one intervention at a time).
- Tasks (development board, recurring wrong finishes): construct-assembly, seq-assembly, net-fit, binary-extract,
  graph-query-catalog. Held-out tasks untouched.
- 3 episodes per task per arm = 30 rows (raised from the draft's 2 before sealing, for power); arm order interleaved; same model (GPT-6-Luna), host, limits,
  `--host-cpus 4 --max-parallel-rows 2`. One retry for infra-invalid rows only; cancelled and invalid rows stay in
  the denominator.
- Grading: the official grader, after the agent terminates. Model identity, deployment and response IDs are
  recorded per row from the call logs (not from launcher labels).

## Predictions (written before any row)

- **N2-a (mechanism):** every `g` row that finishes calls `requirements` at least once before its first finish;
  ≥ 80% of `g` rows quote every requirement sentence by their last ledger call.
- **N2-b (reading, primary):** wrong voluntary finishes on stated requirements (grader assertion on a requirement
  stated in the task) are fewer in `g` than in `e`: `g` ≤ `e` − 2 of 15. Honest prior: uncertain; prompt-level
  levers failed six times (S1–S6, L1/L2).
- **N2-c (outcome):** `g` passes ≥ `e` + 2 of 15.
- **N2-d (cost):** `g`'s all-role token cost ≤ 1.5 × `e`'s.
- **N2-e (harm):** no task passed by `e` in all 3 episodes is failed by `g` in 2 or more.
A null or negative result is recorded as such; n = 15 per arm supports a pilot reading, not a claim.

## Budget (sealed at authorization)

GPT-6-Luna token prices ($0.10 in / $0.01 cached / $0.50 out per 1M). N1 rows on these tasks cost $0.006–0.09; estimate
≈ $1–2 for 30 rows. **Kill rule:** stop if recorded model spend passes $3.0 (recorded spend is a lower bound;
the remaining £10 budget, ≈ £8.9 at most, is an upper bound). VM: ≈ 2–3 h on the run VM (VM time authorized without limit tonight), deallocated after.

## Smoke (before launch; not part of the pilot)

One arm-`g` row on repair-history (not an N2 task; wiring check only), 15 Oct 04:0x UTC: finished in 16 steps, reward
0.0 (`test_about_file`: `_includes/about.md` hash mismatch), $0.0051. The ledger worked as built: 2 items, both
quoting the task exactly and marked met, nothing uncovered, no hold. The miss is a merge judgement: the task says
only "find them and merge them into master"; the solver resolved the `about.md` conflict by writing new text
(and changed a link) instead of keeping the recovered commit's version, which the grader's hash expects. The task
states no conflict rule, so the ledger had no sentence to bind; whether its prompt text nudged the choice cannot be
told from one row (an arm-`e` smoke on repair-history passed earlier). Recorded as a possible harm signal to watch, not a
blocker; repair-history is outside N2's tasks. Launched 04:14:50 UTC at ef69daf9e.

## Results (run 04:14:50–06:05:40 UTC, ef69daf9e; all 30 rows valid, graded by the official tests after each run)

| Arm | Passed | Finished | Wrong finishes | Finish precision | Model cost | Steps |
|---|---|---|---|---|---|---|
| e (no ledger) | 8/15 | 15 | 7 | 53% | $0.282 | 359 |
| g (ledger) | 6/15 | 14 (+1 timeout) | 8 | 43% | $0.430 | 559 |

Per task (P pass, W wrong finish): net-fit e PPP g PPP; seq-assembly e WPW g PWW; binary-extract e WWW g WWW; construct-assembly e WWP g
WW+timeout; graph-query-catalog e PPP g WPP. Cost is recorded token spend at GPT-6-Luna prices (a lower bound).

**Predictions:**
- **N2-a (mechanism): held.** Every `g` row called `requirements` before its first finish (2–10 calls); 15/15
  quoted every requirement sentence by their last call (0 uncovered). The hold fired twice (construct-assembly e2, 5 items
  unsure; binary-extract e3, 1 unsure); both rows finished again and failed.
- **N2-b (reading, primary): failed.** Wrong finishes 8 vs 7 (needed ≤ 5). Every wrong `g` finish had all its
  items marked met with cited steps, e.g. graph-query-catalog e1 read "full professors" as role literals beginning with
  "Professor" and marked it met; seq-assembly e2/e3 marked the Tm requirement met from their own check.
- **N2-c (outcome): failed**, in the wrong direction: 6 vs 8 passes (needed ≥ 10).
- **N2-d (cost): failed narrowly.** 1.52× cost (limit 1.5×), 1.56× steps; construct-assembly rows ran 66–150 steps.
- **N2-e (harm): held** by its letter (no task `e` passed 3/3 failed by `g` in 2+), but graph-query-catalog lost one pass.

**Reading.** The ledger is adopted fully and changes nothing that matters: it records the solver's beliefs, and
the solver believes its wrong readings. This is the "no commitment" condition of SpecHarness (arXiv 2609.29921),
whose ablation found letting the agent's claim count to be the largest single loss; see
`CORE_FALSE_COMPLETION_PRIOR_ART_20261015.md`. n = 15 per arm is a pilot; the difference in passes (−2) is within
noise, the absence of a gain is not. **Not promoted; `--core-ledger` stays off.** Held-out tasks untouched.

**Evidence:** `audit_output/aether_n2_20261015/n2_evidence.tgz` (sha256
48e17334b6db08c9aa058e769a9008a1a8fc83b10487b0f50e51bcf94fbe2326, equal on the VM and locally): run dir, scorer
outputs (`n2/mech.txt`), per-row archives, smoke. VM the run VM left running: the portal session had expired and
no other credential reaches the subscription; deallocation needs the principal.
