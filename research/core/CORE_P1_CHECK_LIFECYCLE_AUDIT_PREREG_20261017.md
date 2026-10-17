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
