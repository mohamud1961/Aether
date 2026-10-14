# Postmortem: the held-out falsifier fired

**What this is:** A postmortem of the October 2026 held-out campaign, which tested whether the Gen 4 candidate lifted the same open model over a stock reference agent on three held-out tasks.
**Key result:** The candidate scored 5 of 9 attempts (56 percent). The stock reference agent scored 4 of 6 (67 percent). The pre-registered falsifier triggered, so the lift claim was not supported.
**Why it matters:** The campaign was written down before any row ran, and it reported a result against the claim. Task-level detail is held back here; the claim is decided on the aggregate.

## Design

- **Pre-registration.** Sealed before any row launched. It stated the predictions, the falsifier and the promotion bar.
- **Arms.** The candidate: 3 attempts on each of 3 held-out tasks (9 attempts). A stock reference agent (Terminus-2) with the same model: 2 attempts on each task (6 attempts).
- **Promotion bar.** Nine of nine across repetitions.
- **Falsifier.** If the stock agent's per-attempt rate is at least the candidate's, the lift claim is not supported.

## Timeline

| When (2026) | Event |
|---|---|
| 23 September | The September held-out set had closed at official 0 of 3. |
| Before the first row | Preregistration sealed (commit abd6b615c). The preregistration file is dated 12 October; the results file dates the campaign 11 October. |
| 11 October | All 15 scheduled attempts ran in sequence; zero invalid rows, none replaced. |
| 11 October, after the run | Failure audit written as pre-registered. |

## What the measurement claimed and what it showed

| Claimed | Reality |
|---|---|
| The candidate lifts the same model over a stock agent. | Candidate 5 of 9 (56 percent); stock agent 4 of 6 (67 percent). The falsifier triggered. |
| The prediction for the stock agent was 1 to 2 of 6. | The stock agent scored 4 of 6. The prediction was wrong. |
| The prediction for the hardest held-out task was 30 to 65 percent. | Candidate 0 of 3. Every run was still debugging at the 900-second limit. The prediction failed. |
| "All tasks at least once" and the 9-of-9 bar. | Neither met. |

The failure audit found two causes, both recorded as facts about the run. On the hardest task, the debug phase needed roughly 9 to 27 steps after a 20 to 25 step build, and at 17 to 19 seconds per step that did not fit the time limit. On one of the easier tasks, the candidate's final submission failed a verification step that its own finish review did not catch.

## Fix

No fix was tuned against this result. The page records the falsifier and withdraws the lift claim. The audit names cheaper debug cycles, fewer first-version defects and no end-of-task ritual as the levers for the time-limited task. It states that these are a separate work item and were not patched into this campaign.

## Lesson

A held-out campaign is only as honest as its falsifier. Write the falsifier and the predictions before the rows, report the falsifier when it fires, and do not re-score the same tasks to rescue the claim. Three tasks and nine attempts also give wide uncertainty on any rate; the aggregate is the only claim this campaign supports.
