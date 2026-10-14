# Five findings

What should a harness add to a model, and how would we know? These five results survived eleven months of
building and auditing harnesses. Each one changed how the next system was built or measured.

| # | Finding | Headline number |
|---|---|---|
| 1 | Cheaper calls made trajectories more expensive | Prefix bytes −29%, model calls +56% |
| 2 | A pre-registered falsifier fired on our own harness | 5/9 vs a stock agent's 4/6 |
| 3 | A completion verifier needs its own evaluation | It ran 0 real checks in 20 runs |
| 4 | Most measured wins were measurement artefacts | 456 of 482 verifier rounds errored behind a "78.5%" |
| 5 | Review without the agent's claims catches more | 15/18 wrong finishes caught vs 10/18 |

---

## 1. Cheaper calls made trajectories more expensive

**Claim.** Optimising the cost of a single model call can raise the cost of the whole task, because the
model takes more steps to recover what was removed.

**Evidence.**
- Removing byte-identical fields from the worker's context cut prefix bytes by 29% and config bytes by
  74%. Model calls rose from 16 to 25 (+56%) at the same pass rate (3/3 in both arms).
- In a second screen the same deduplication cut prompt size by 29% but raised steps by 50% and output
  tokens by 172%.
- Compacting context at a low 8k threshold raised total tokens by 58.8% and 105.1% on the two tasks measured.
- By turn 16 of a long run, 98.8% of a 266 KB request was replayed content the model had not observed
  freshly. The cost sat in the trajectory, not in any single call.

**Why it matters.** Context engineering is usually scored per call. The unit that matters is the
trajectory: total tokens, steps and wall time to a correct end state. Every context change after this was
judged on whole-trajectory cost.

**Limits.** Small samples (three tasks per arm in the deduplication screen). The direction held across
screens; the size of the effect is not pinned down.

## 2. A pre-registered falsifier fired on our own harness

**Claim.** The harness did not lift the model on held-out tasks, and the test said so in advance.

**Evidence.** Before any trial ran, the plan stated the prediction, the falsifier and the promotion bar,
and the plan was sealed. The harness, built around the same open model, solved 5/9 attempts on three
held-out tasks. A stock reference agent with the same model solved 4/6. The falsifier fired, the "lift"
claim was recorded as not supported, and the promotion bar (9/9) was not met. On one task every attempt
from both agents was still debugging at the 900 s limit.

**Why it matters.** Most harness comparisons are run after the fact, on tasks the builder has seen. Sealing
the claim first is the only way the result can count against you, and here it did.

**Limits.** Three tasks and 15 attempts. This does not show the harness is worse. It shows the claimed
advantage was not there on this test.

## 3. A completion verifier needs its own evaluation

**Claim.** A verifier that decides whether the task is done is a model-driven component like any other. It
fails silently unless it is measured directly.

**Evidence.**
- In one generation the verifier ran 0 real checks across 20 runs, while runs still reported as verified.
- A known-bad falsifier (frozen wrong and right end states) never passed: 3/5, then 2/5, with a wrong
  state accepted and correct states blocked.
- The bench built in response holds 377 graded finishes, 29 of them wrong. The kept verifier caught 22/29
  wrong finishes and wrongly held 6 of 348 correct ones. A variant that caught 25/28 wrongly held 33% of
  correct finishes.
- In an external corpus of 312 parsed runs, runs with a verifier succeeded at 0.908 against 0.2 without
  one, yet 17 runs passed their verifier and failed overall.

**Why it matters.** Verification is where a harness adds the most and where it fails most quietly. It
needs both rates, catches and false holds, before anyone trusts it.

**Limits.** The bench's case pool was drawn from benchmark runs. The current tasks supply our own cases
from references, known-bad states and careless agents.

## 4. Most measured wins were measurement artefacts

**Claim.** Before trusting a result, check that the measurement worked. Here, it often did not.

**Evidence.**
- A batch reported as 11/14 (78.5%) was a rate-limit storm. 456 of 482 verifier rounds errored, and 8 of
  the 11 passes came from the external grader rescuing runs the verifier never confirmed.
- On a 241-task board, 216 first attempts never launched. The valid rate was 5/19; the naive 5/241 meant
  nothing.
- A grader leak let candidates run inside the oracle process, so two rejection controls scored 1.0.
- An open model ran at temperature 0.0 by default, and two candidate losses were greedy-decoding runaways.
- One parsing bug meant every earlier verifier bench read the wrong tool-result field.

**Why it matters.** Each of these was caught by auditing rows, not by reading summaries. The method that
came out of it is invalid-row accounting, known-bad controls and a row-level audit of every run, and it
is now part of every evaluation.

**Limits.** These are failures of our own measurement stack. How common they are elsewhere is not tested
here.

## 5. Review without the agent's claims catches more

**Claim.** A reviewer that sees only the task and the end state catches more wrong finishes than one that
also reads the agent's account of what it did.

**Evidence.** On an offline bench of wrong finishes, claim-free review caught 15/18. The same reviewer
given the agent's claims caught 10/18.

**Why it matters.** Agents describe their work persuasively, including work they did not do. Independence
means separating the verifier from the claim, not only from the model.

**Limits.** 18 cases. Promising but small, and it should be replicated on larger case pools.
