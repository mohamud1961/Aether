# Check-lifecycle audit (offline, archived traces only) — pre-registration (2026-10-17)

Status: **SEALED before any event is extracted or counted.** No VM, no model calls, no spend. Authority: the principal's
"go" (2026-10-17) after the ChatGPT audit of the independent-check experiment, which approved "the no-model-call
check-lifecycle audit as the next step".

## Question

When GLM meets evidence that contradicts its deliverable, **which side does it change, and is that the right side?**
The independent-check experiment (`CORE_P1_INDEPENDENT_CHECK_PREREG_20261016.md`) showed one correct check that failed
on a reversed file being rewritten to fit the file (g4 e3); V4 showed the mirror image, a correct answer rewritten to
fit a wrong check (credential-recovery e1). This audit measures how often each happens, against how often wrong deliverables
never met contradicting evidence at all.

Stages (from the review): (1) construct a valid check, (2) detect the contradiction, (3) decide which side is wrong,
(4) repair the deliverable.

## Populations

- **P-G (primary, graph-export family; file truth known at every step):** the 122 GLM rows of the check-independence
  study (`audit_output/aether_p1_checkindep_20261016/rows_auto.json` sources) + the 36 model rows of the
  independent-check experiment (`pia`, `pib`) = **158 rows**. File state at any step = latest printed readback decoded
  by header (C/R/O, as in the earlier studies); where none, hand-read from the writer code; else `unknown`.
- **P-V (secondary, external frozen checks):** V4 `contract4` rows (`aether_worldclass_20261013`), every hold event,
  reusing the audited labels in `CORE_V4_CONTRACT_PREREG_20261012.md` (incl. the 2026-10-13 correction), re-read in the
  trace to assign the reaction labels below.
- **Excluded:** independent-check B rows and other TB rows (truth at the event time is unknown, only final reward);
  GPT-6-Luna rows (other model); A1 (fixed states, no reactions).

## Unit: a contradiction event

Any point after the first deliverable write where the solver is shown evidence that the deliverable is wrong:
(a) its own check's output reports a failure; (b) a harness/external check message (step-2 check tool, V4 holds);
(c) a printed fact (CPD parents, API output) that its reasoning treats as conflicting with the file or intended graph;
(d) a task fact it recalls in reasoning as conflicting (e.g. "U has no parents").

**Extraction:** candidates = tool results matching a failure regex (`AssertionError|Traceback.*assert|\bFalse\b|
mismatch|MISMATCH|FAIL|✗|❌|not match|differ|Extra items|missing|wrong|WRONG|violat`) or a following reasoning block
matching a contradiction regex (`mismatch|contradict|doesn't match|does not match|inconsisten|reversed|swapped|
inverted|wrong|backwards|my error|bug`), restricted to steps after the first deliverable write. **Every candidate is
hand-read**; non-events are dropped with a reason. Events that leave no matching text are invisible (disclosed).

## Labels per event (hand)

- **Check correctness:** `correct` (the true graph passes and the event-time file fails for the right reason),
  `wrong` (it rejects the true graph), `n/a` (types c/d: the fact itself is labelled true/false).
- **True contradiction** = correct evidence + wrong file. **False contradiction** = wrong evidence + correct file.
- **Reaction** (sequence until the next check or finish): `FIX-ARTIFACT`, `FIX-CHECK` (check edited so it passes
  without the property changing), `NEW-EVIDENCE` (docs/API introspection/re-derivation before deciding), `IGNORE`
  (proceeds without resolving), `DISPUTE` (V4 only).
- **Side:** `right` (true contradiction → artifact made correct; false contradiction → check dropped/changed, artifact
  kept), `wrong` (true → check changed/ignored, file stays wrong; false → artifact changed to fit), `partial`.
- **Justification** (FIX-CHECK and DISPUTE only): did the change cite authoritative evidence obtained **after** the
  failure (docs, API output, task text), or only a restated belief?
- **Sensitivity (stage 1–2):** every check involved in an event, and every IH check in P-G, is replayed offline
  against the true and reversed files **if self-contained** (reads only files and literals, no REPL state), in a
  sandbox with python3.11 -I; others are hand-judged and labelled as such. Agreement with the hand rubric is reported.

Row-level stage of failure for each **reversed-final** P-G row: `S1` no check that could detect it ran; `S2` a
sensitive check ran but its failure was not shown/seen; `S3` a true contradiction occurred and the wrong side was
changed or it was ignored; `S4` the right side was chosen but the repair failed.

## Predictions

- **L-P1 (stage 3 is a minority on this board):** of true-contradiction events in P-G, wrong-side reactions are
  **< 25%**. If there are fewer than 4 true-contradiction events, **inconclusive**.
- **L-P2 (most wrong finals never met a contradiction):** ≥ 80% of reversed-final P-G rows are `S1` or `S2`.
- **L-P3 (descriptive):** false contradictions in P-G and P-V, with reactions; every wrong-side one is listed.
- **L-P4 (justification, descriptive):** share of FIX-CHECK/DISPUTE reactions backed by new authoritative evidence;
  the g4 e3 revision is labelled under the same rule as all others.

**Decision mapping.**
- L-P1 held and L-P2 held → contradiction handling is a minor stage here; prioritise observation/check creation
  (e.g. field-aware view) before any revision mechanism.
- L-P1 failed (≥ 25% wrong-side with ≥ 4 events) → contradiction handling is material; a preregistered paid
  comparison of evidence-governed revision is justified, with correct **and** deliberately wrong expectations.
- Inconclusive (< 4 events) → the archive cannot estimate the rate; any test must induce contradictions by design.

Failed predictions are recorded as failed. Scripts, candidate lists, hand labels and replay outputs go to
`audit_output/aether_p1_lifecycle_20261017/`.

## Results (2026-10-17, appended after labelling; predictions above unchanged)

**Custody.** `audit_output/aether_p1_lifecycle_20261017/`: `lc_extract.py` (+ `lc_patterns.py`), `lc_triage.py`,
`lc_view2.py`, `lc_deep.py`, `lc_replay.py`, `candidates.jsonl`, `lifecycle_labels.json`, `replay.json`. 158 P-G rows
(grader verdicts identical row-for-row to the check-independence study for its 122), 18 P-V rows. No model calls, no
spend.

**Method deviations (disclosed).**
1. **Extractor gap fixed before counting:** v1 skipped `finish` results, where step-2 harness check messages arrive;
   v2 includes them (+5 candidates, 1 new event: p2a check-e4).
2. **Mechanical drops:** of 268 candidates, 67 tool results that were pgmpy source/doc listings with no
   assertion/mismatch text were dropped (rule D1, in `lc_triage.py`); the other 201 were hand-read.
3. **Scope:** events are edge-file contradictions (the property with known truth at every step); CPD, sample,
   covariance-ordering and library contradictions were read and recorded as non-events. Two model-input binding catches
   (CPD view) are reported separately.
4. **Counting unit:** both episodes (first failure of a piece of evidence → its resolution) and individual events are
   reported; repeated failures of one check inflate events.
5. **Replay:** 28 target checks; 13 were self-contained and replayed (all 13 agree with the hand labels: 10 correct
   checks pass truth and fail reversal, 3 wrong checks reject truth or are inverted); 15 need solver state (model
   objects, pgmpy, scripts) and are hand-judged. Printed-only checks were compared by output with the sandbox path
   normalised. Replay used a scratch venv (pandas 3.0.6, networkx 3.6.1), not the run images.

**L-P1 HELD (stage 3 is a minority).** True contradictions in P-G: **15 episodes / 27 events**. Wrong-side: **2 events
(7%)**, **2/15 episodes on first reaction (13%)**, **1/15 at resolution** (pia g4 ib1-e3, ended reversed). The other
wrong first reaction (role g1-tofrom-named e3) blamed the check, but its rewrite kept the same test, the evidence
failed again, and the model then went back to the task text and repaired the file. Three right-side episodes still
ended wrong for other reasons (faulty or collateral repair, s4 b1-e2; separate structure decisions, two step-2 rows).

**L-P2 HELD.** Reversed-final P-G rows: **51**. S1 (no sensitive check ever ran) **50**, S2 0, S3 **1**
(pia g4 ib1-e3), S4 0. 98% of wrong final files never met correct contradicting evidence.

**L-P3 (descriptive).**
- P-G false contradictions (own wrong checks on correct files): **7, all resolved on the right side** (check fixed or
  dismissed with a concrete diagnosis); none bent a correct file.
- P-V (V4 frozen external checks with arbiter): 5 hold episodes. False holds **3: 2 wrong-side** (credential-recovery e1
  complied and failed; cipher-diff-attack e1 bent the attack to pass a broken wrapper, hidden by the grader), 1 right (credential-recovery e2
  check 3 disputed and voided). True holds **2**: repair-history e1 repaired (unproven); credential-recovery e2 check 2 was first
  **disputed** (wrong side), the arbiter upheld it, and the worker then repaired.

**L-P4 (descriptive).** Check revisions in P-G: 9 (7 right, 2 wrong). Every one cited a concrete reason; the 2 wrong
ones cited the model's binding belief (one misapplied `get_parents` output, one misdiagnosed a namedtuple field).
Right revisions also often changed the check's binding (e.g. role g1-named e2). V4 disputes: 2, both cited task text;
one wrong. **No visible marker separates a right revision from a wrong one**: both sides appeal to the same belief.

**Decision (per mapping): L-P1 and L-P2 held → contradiction handling is a minor stage on this board; prioritise
observation / check creation before any revision mechanism.**

**Reading.** On the graph family, GLM almost always takes the right side when contradicting evidence reaches it
(13–14 of 15 episodes), whether the evidence is its own check, a task fact, a printed fact or a harness message. Wrong
files survive because sensitive evidence **never appears** (50/51), and the independent-check experiment suggests why:
sensitive checks were written mostly in rows whose binding was already right (4 of 5), i.e. check creation runs
through the same belief that produced the error. Frozen external checks fail the other way: 2 of 3 wrong holds bent
correct work, and 1 correct hold was disputed (the arbiter caught it). The one n=1 hint for the revision hypothesis —
evidence that survived an attempted rewrite led to repair — is too thin to act on. Limits: one task family dominates
P-G; small n (2 wrong-side events); contract3 rows ran on the later-invalidated compose substrate; invisible
contradictions (no matching text) are not counted.
