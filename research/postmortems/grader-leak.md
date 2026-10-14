# Postmortem: the grader ran candidates inside the oracle

**What this is:** A postmortem of the October 2026 grader-validity audit of two development boards. The audit found that the grader let candidate code run in the same process as the hidden answers.
**Key result:** Two known-bad controls scored 1.0 on the grader. One copied the hidden answer from metadata; the other read the grader's answer from the caller's frame. A grader that gives full marks to both can score a candidate without solving the task.
**Why it matters:** The board comparisons had informed a configuration decision. After the audit, the scores were recorded as not portable as-is, and the defects were recorded as open.

## Timeline

| When (2026) | Event |
|---|---|
| 4 to 5 October | First development board runs: arms A0 to A5 on 19 tasks, 100 valid cells. Arm A4 (high effort) scored 12.33 of 20; A0 scored 9.00 of 19. |
| 5 October | Second development board (canonical board) runs. 54 main-board results are recorded, plus one smoke result; five cells have no terminal result or record. |
| 5 October | Independent audit finds the grader executes candidates inside the oracle process. Two known-bad controls score 1.0. |

## Root cause

The grader's command-line entry point imported each candidate into the grader's own process and called its function there. While this happened, the hidden truth function and the expected-response function were live in the caller's local variables. A candidate running in that process could reach them.

The audit built two controls and ran them through the same grader:

- **Frame reader.** Does no estimation. It reads the grader caller's truth and response functions through frame inspection, then emits their values. It scored 1.0 on two of two cases.
- **Truth reader.** Copies the answer coefficients from metadata that the grader wrote into the candidate's inputs, and computes predictions from them. It scored 1.0 on two of two cases.

The grader also accepted an empty list of ranges, because its check tested only that the ranges object had at least two keys.

The audit did not establish that any historical candidate used frame access, and it does not accuse the model of cheating. The defect is that a score could be earned without solving the task. Two further findings came with it. Three tasks could not be graded as specified, because the output schema was not stated. One real task-budget timeout had been counted as an infrastructure failure, and the board recorded no score for it.

## What the measurement claimed and what it showed

| Claimed | Reality |
|---|---|
| Each score independently established capability under hidden-truth isolation. | The grader ran candidates in the oracle process, and known-bad controls scored full marks. |
| The high-effort arm (A4) beat the baseline (A0), 12.33 to 9.00. | That comparison used the grader the audit showed could be exploited. A4 and A5 were kept; the board was recorded as not portable as-is. |
| The canonical board covered all planned cells. | 54 main-board results were recorded. Five cells had no terminal result or record, so the board stopped at 55 of 60 accounted cells. |

## Fix

The audit's required actions:

1. Keep the hidden truth only in the grader. Remove it from candidate inputs on both the command-line and the certified paths.
2. Isolate candidate execution from the oracle process, and use one declared grading contract.
3. Add the two controls as rejection tests. The grader must fail them while passing a real ceiling run.
4. Audit every remaining development grader at the same boundary before its scores are used for selection.
5. Where feasible, regrade preserved candidates under the repaired contract rather than repeating model runs.

The audit recorded these as required next actions. This page does not record their completion.

## Lesson

A grader is part of the measurement. Test it with known-bad controls before using its scores, and keep the answer key out of anything the candidate can import or inspect. A control that scores full marks is the cheapest evidence that the grader is broken.
