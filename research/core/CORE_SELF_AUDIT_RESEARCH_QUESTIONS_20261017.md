# Self-audit: are we asking the right questions? (17 October 2026)

Asked for by the principal after T1: "take a step back, look at all the data, and list the right questions". Offline, no
model calls, no spend. Sources: every Core prereg/result in this folder (≈40 since 11 Oct), the all-boards failure study
(`CORE_FAILURE_STUDY_ALL_BOARDS_20261015.md`), the G4 Codex/GPT-6-Astra and GPT-6-Luna traces, `docs/HARNESS_VISION.md`.

## 1. What we did (11–17 Oct)

| Question we asked | Levers tried | Outcome |
|---|---|---|
| Does Aether lift GLM over a stock harness? | the held-out evaluation; T1/S4 b1 board | **No.** 5/9 vs 4/6; 12/18 vs 12/18 |
| Can the finish moment be made truthful? | effort, analysis turn, JSON turn, finish receipt, nudge | All failed; 25–39% wrong finishes in every arm |
| Can checks/reviewers catch false completion? | prewritten checks (A1), same-model reviewer (R1), state verifier (V1–V4), ledger (N2), qualified checks (Q1), reading judge (J1) | All failed or harmful (A1 held 42% of good states; J1 AUROC 0.475) |
| Why does GLM reverse the net-fit edge file? (one task) | probes, read-back, matched repair, naming, independent checks, lifecycle audit, field view (T1) | Understood **very well**; nothing fixed it in-run |

**Score: ~20 mechanism tests, 0 promoted.** Our understanding improved a lot. Our results did not.

## 2. What the data says about *how* we have been asking

1. **We are tuning on ~4 data points.** Outcomes are close to deterministic per (model, task). 221 rows collapse to
   9 tasks, and 4 of those tasks hold 87% of wrong finishes. The real n is tasks, not episodes. Since 15 Oct we have
   spent most effort on **one** failure of **one** task (net-fit `to,from`), through a toy board built to isolate it.
2. **That failure belongs to the model, not the harness.** On net-fit, GPT-6-Luna is 22/22 with the same harness and text; on
   binary-extract, GLM is right and GPT-6-Luna is wrong 14/14. By our own vision's test ("the better the model, the better the
   system"), a harness lever whose only purpose is to correct one model's reading of one header is a **crutch**.
   That is why prompt paragraphs, naming rules and views keep failing or moving the error elsewhere.
3. **We have mostly asked "does lever X fix symptom Y?" (mechanism-first).** We rarely asked "how big is the
   prize, and what bounds it?" first. We have no **ceiling estimates**: how many failures would flip if the model got
   the perfect hint, the perfect check, a stronger model, or more time?
4. **Our positive findings point the same way, and we have not acted on them:**
   - GLM judges a file correctly when **asked a pointed question** (T1 Stage 1: 1/18 → 18/18).
   - GLM takes the right side **when a contradiction reaches it** (13–14/15).
   - Serialisation works when the graph is supplied (25/25).
   - A second reading disagrees exactly on misreads.

   Common thread: **the model answers pointed questions well, but does not choose to ask them.** Every same-model
   lever that relied on the model asking itself failed. Lessons 3 and 4 together say the harness question is *who
   asks, and when*. That is not a display problem.
5. **Small-n comparisons keep misleading us.** The S4 "Terminus gap" was noise (p = 0.50). In T1, the arms differed
   9/12 vs 4/12 before any treatment was shown. With 12 rows per arm, only effects of ≥ 5 rows are visible.
6. **Every study built its own extractor.** We have ≈450 Core traces locally plus G4 Codex/GPT-6-Astra (330) and GPT-6-Luna
   traces, but no single row-level table. That makes cross-cutting questions (cost vs outcome, step-of-error,
   harness-attributable losses) expensive, so we don't ask them.
7. **The goal has drifted toward correctness on 4 hard tasks.** The stated goal is truthful, complete, correct
   **and efficient**, on the **whole** distribution. Efficiency and breadth have had little attention since N1.

## 3. How a harness/agent researcher would frame it

- **Start from the objective and an error budget, not a mechanism.** Where do points go, on many tasks? Split them
  into: model capability (domain), model reading, harness-attributable (timeouts, context loss, tool or substrate
  failure, bad affordances), environment/grader defects. Only the harness-attributable part is ours to win
  directly, and it is the part a stronger model also benefits from.
- **Bound before building.** Use counterfactual ceilings with oracle interventions, offline where possible:
  - the oracle hint (the precise question at the right step);
  - an oracle check (an executable test of the stated requirement);
  - more time;
  - a stronger model in the same harness;
  - the same model in a stock harness.

  Each ceiling caps a whole class of levers. Do not build inside a class whose ceiling is small.
- **Treat tasks as the unit and get breadth.** Use many tasks with a few episodes each, and a frozen held-out set.
  Report per-task effects and paired tests. Tune on nothing that is also judged.
- **Measure process, not just outcomes.** For each row: step of first error, whether the decisive evidence was ever
  on screen, whether it was attended to, wasted steps, cost to first correct artifact. Outcome-only data cannot
  separate "didn't know", "didn't look" and "looked but misbound".
- **Compare with strong reference agents on the same tasks.** For Codex/GPT-6-Astra, Terminus and GPT-6-Luna: what did passing
  runs do that failing runs did not? Prior art first (SpecHarness, Verification Horizon), as the principal asked.
- **Apply the vision test to every candidate.** Would a stronger model want it? Keep workbench improvements (tools,
  state, execution, time, verification infrastructure that *executes*). Drop crutches.

## 4. The questions to ask (in order)

**A. Destination**
1. What single number defines "elite"? Pass rate on which task set, at what cost and wall time, and against which
   baseline (Terminus+GLM, Codex+GPT-6-Astra)?
2. What is the held-out set, and is it frozen? (The dev 9 are contaminated.)

**B. Where do the points go? (error budget, all data)**
3. Across every row we hold (all boards, all models, external traces), what share of failures is domain, reading,
   harness-attributable, timeout, environment or grader?
4. Which failures are **model-specific** (flip between models) and which are **shared**?
5. Where does Aether lose to Terminus or Codex on the same task, and where does it win? What differs in the traces?

**C. What bounds each lever class? (ceilings)**
6. If the model got the precise question at the right step (oracle hint), how many failures flip? (T1 Stage 1 says
   reading failures flip; does that hold beyond net-fit?)
7. If the run had an executable test of each stated requirement (oracle check), how many flip?
8. How many failures are time-bound (more budget flips them)?
9. How many would a stronger model in Aether pass? That share is the crutch-free share.

**D. Who asks the question? (the open harness problem)**
10. Which single-model, observable signals precede a wrong finish? Candidates: the model naming an alternative
    reading (81% of wrong vs 47% of right), stated doubt, an unverified convention, an artifact never compared with
    its source.
11. Can the harness turn such a signal into a pointed question that *executes* (a check run by the runtime, not
    self-marked), without task-specific rules?
12. How much does that cost, and does it hurt correct runs? (A1 shows that frozen checks hurt.)

**E. Efficiency and the workbench**
13. Where are steps, tokens and time wasted in *passing* runs? (This is cheaper to win and benefits every model.)
14. Which Aether capabilities are used, worked around, or never touched (the capability principle), and why?

**F. Measurement validity**
15. Is every board free of grader defects (binary-extract #194, seq-assembly overhang counting)?
16. Is each comparison powered? What effect size can 12-vs-12 detect?

## 5. How to use all the data (proposal, $0)

1. **One run ledger.** One row per run ever made, covering:
   - each Aether-Next and Core board;
   - Terminus;
   - the G4 Codex/GPT-6-Astra and GPT-6-Luna traces.

   Columns: model (taken from `response_model`), harness, task, arm, outcome, grader assertion, cost, steps,
   wall time, failure class, first-error step and trace pointer. Build it by extending `core_failure_index.py`.
   The principle: "The ledger remembers".
2. **Error budget and model-flip table from the ledger** (questions 3–5, 13). Hand-label only the residue.
3. **Ceiling study design (questions 6–9).**
   - Oracle-hint and oracle-check replays on archived fixed states, across all failure tasks rather than net-fit alone.
   - Paid, small, pre-registered; needs your OK.
4. **Then pick levers by ceiling × breadth × the vision test**, not by which symptom is freshest.

Recommendation: stop the P1/bn line. Do steps 1–2 next (offline), then review them with you and GPT-6-Astra before any paid
run.

## Erratum and amendments after review (2026-10-18)

- Numbers: 4 tasks hold **62/70 (88.6%)**; serialization **30/30** outputs (9/10 agent rows both files, 4/5 full task).
- The "81% vs 47%" alternative-reading marker is a crude regex; as a trigger it is ≈ 49.5% precise (52 of 105 flags).
  It is a research lead, not a trigger.
- Retracted as too categorical: "the failure belongs to the model, not the harness", and "only the
  harness-attributable share is ours to win". A model-originated error can still be a harness opportunity (enable a
  latent capability). The line is generic affordance vs task-specific compensation.
- Oracle studies estimate **conditional recoverability under a defined intervention**, not universal ceilings.
- Retracted (chat, 10-17): "truthfulness covers the others". Fewer false "done" claims can come from abstaining;
  successful delivery, unsupported claims and unnecessary abandonment are measured separately.
