# Measurement validity

This method tests the grader and the measurement pipeline before a number is reported. The grader must run outside the candidate's process. Rejection controls must score 0. The answer key, the output schema, and the parsing of tool results are each checked.

The lesson: several headline numbers in this programme came from a broken measurement. The grader was checked after the score was published.

This matters because a grader that is wrong makes a bug look like a result.

## Why we needed it

A 15-task batch reported 11 of 14 (78.5%). In that batch 456 of 482 verifier rounds errored, 421 of them from rate limits. Eight of the 11 passes were grader rescues, meaning the verifier had missed and the grader passed the work anyway. The headline was retired.

An independent grader-validity audit found that candidates ran inside the oracle process. Two rejection controls scored 1.0. One copied the truth file, and one read locals from the oracle's caller frame. Three tasks could not be graded as specified because the output schema was not stated.

A grader key was ambiguous. The ambiguity made 2 of 3 earlier zeros wrong. Two identities were duplicated.

A packet-unwrap bug made every historic bench read the wrong tool-result field. Earlier verifier results were invalidated and rerun.

## How it works

The grader runs after the terminal state, outside the candidate's process. Known-bad controls must score 0 and known-good controls must score 1 before any score is reported. The output schema is stated in the task. Answer keys are checked for duplicate identities. Tool-result parsing is checked against a fixture that asserts the field read. The sampling temperature is set explicitly, not left to a provider default.

Scores report valid trials only. Invalid trials are counted apart, and verifier errors are reported next to each score.

## What it caught

- **Grader leak.** Two rejection controls scored 1.0 because the grader ran inside the candidate's process.
- **Default temperature.** The open-model runs used temperature 0.0 by default. A row audit found it. Two candidate losses came from greedy runaways: one malformed call repeated 18 times, and one 32,000-token runaway.
- **Rate-limit storm.** A 15-task batch reported 11 of 14 (78.5%). Most verifier rounds had errored, 456 of 482, and 421 of those came from rate limits. The number mixed provider errors with candidate results.

## Where it fell short

No standing validity gate runs across the suite. The validate-graders step is specified in the design plan and is not evidenced as run. Each defect above was found after a number had been published, and the grader leak was found by an outside audit. Two debug-only ports run their graders on the host, and one ported family carries Terminal-Bench lineage in its measurement grader that has to be cleared before use.

## The verifier is a judge, and is measured like one

A completion verifier is an LLM-as-judge on agentic finishes. It gets the same treatment as any judge:
a labelled set of 377 graded finishes (29 wrong, 348 correct), with two rates reported separately. The
**catch rate** is the share of wrong finishes held. The **false-hold rate** is the share of correct
finishes held. A hold signal is never trusted until its false-hold rate is measured.

| Verifier, threshold | Caught (of 29) | False holds (of 348) |
|---|---|---|
| Evidence-citing, 0.7 | 22 | 6 |
| Evidence-citing, 0.8 | 19 | 2 |
| Blind, 0.6 | 19 | 38 |
| Artifact-reading, 0.6 | 25 of 28 | 68 of 208 (33%) |

The artifact-reading verifier caught the most and held a third of correct work, so it was reverted. The
evidence-citing verifier at 0.7 was kept. A bench bug (every historic run read the wrong tool-result
field) invalidated the first rounds; they were rerun clean before any of these numbers counted.

Two bias controls carry over from judge calibration. **Claim-blinding:** the judge sees task state, not
the agent's account of it. Without the claims it caught 15/18 wrong finishes; with them it caught 10/18.
**Known-bad replay:** before any verifier change counts, the verifier runs on fixed wrong states and
must hold them.

