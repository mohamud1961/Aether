# Analyze agent runs

Use this to read an agent run (benchmark, terminal, coding, service, or long-running task) as an engineering trace. It separates real progress, lucky passes, harness defects, and activity with no effect.

## Governing question

> Did the harness make the model behave like a careful engineer, and where did the loop stop keeping that contract?

Treat the run as a coupled chain and find the first decisive divergence:

`model input -> model decision -> tool action -> observed state -> harness interpretation -> next input -> completion claim -> verifier -> grader`

The answer comes from artifacts, not from the feel of a long transcript.

## Rules

1. Inspect artifacts before concluding.
2. Keep observation, inference, hypothesis, and unknown apart. Label them.
3. Cite exact paths and step identifiers for each material claim.
4. Do not mistake a missing downstream artifact for the upstream cause.
5. A completion claim, a verifier's confidence, or a polished summary is not grader truth.
6. Classify invalid provider, launch, environment, grader, timeout, and resource rows separately from model capability.
7. If decisive artifacts are missing, write `UNCLEAR` and name what is missing.
8. Do not propose task-specific fixes or task-name branches in generic harness code.
9. Diagnose and audit here. Prove mechanisms in separate, controlled evaluations.
10. Do not implement fixes unless asked.
11. **A grader pass is not a harness success.** If the verifier never confirmed completion and the grader passed it, report a verifier miss, not a win.
12. **A run with a dead substrate cannot grade judgement.** If model calls were mostly rate-limited or errored, verifier and architecture questions are unmeasured for that run. Say so.
13. **If you shipped a mechanism, this run may have falsified it.** Confirm by code hash that your change was live, then check whether it did what it claimed. Record a failed prediction as failed.
14. **Separate "no feedback produced" from "feedback ignored."** Confirm the verifier actually returned verdicts before judging how the solver used them.

## Workflow

**0. Gate on provenance and substrate health, first.**
- Provenance: which code actually ran? Compare the recorded tree hash with the working tree.
- Substrate: what share of verifier rounds returned a verdict? Below about 80%, verifier quality is unmeasured. Count parse errors against steps. Name the infrastructure cause (for example, parallel runs exceeding a rate limit). That is a substrate failure, not a capability result.

**1. Freeze the authority surface.** Record run identity, task family, harness revision, model route and settings, the scoreable denominator, and the invalid rows.

**2. Build the artifact inventory.** Result rows, grader and verifier outputs, the task contract, tool calls and observations, file deltas, and service records. List the artifact classes that are missing. Missing evidence lowers confidence.

**3. Establish overall truth.** Count pass, fail, invalid, timeout. Cross the grader result with verifier alignment for every row:
- aligned pass: a real success;
- verifier completion miss with a pass: not a success; report separately;
- verifier false clean with a fail: the highest-value judgement failure; examine each one;
- aligned fail: a real capability failure the verifier caught.

Report the official pass rate and the verifier-aligned rate as two numbers. The gap is how much the grader is compensating for the internal judge.

**4. Reconstruct each task in order.** What the model saw, what it believed the contract was, its first meaningful action, the evidence it gained, the first decisive right or wrong turn, its completion claim, the verifier's reading, and the grader result.

**5. Classify steps.** One label per notable step: evidence-producing, useful setup, redundant, harmful, premature completion, or no progress. Ask whether the step changed semantic state or only activity.

**6. Find fake progress.** Look at the exact input just before the fake work began: a model-authored artifact treated as proof, a self-check that reuses the same method, shape mistaken for meaning, a proxy objective mistaken for the full contract, or a green check hunted by repetition. Ask why the next action looked rational from what the model could see.

**7. Classify passes:** robust, weakly verified, lucky, overfit, or unclear.

**8. Classify failures.** First decisive wrong turn, primary failure class, whether the model knew it was failing, whether the harness surfaced that, and what evidence would have exposed it earlier. Separate task difficulty from harness-created incentives.

**9. Evaluate components.** Prompt, requirement extraction, environment contract, tool execution, evidence ledger, no-progress detection, completion and blocked semantics, verifier, compaction, job monitoring, and the grader boundary. Report helpful and harmful behaviour.

**10. Propose a fix only if it is generic and testable.** State the prediction, the sentinels, and what would count as failure.

**11. Close out.** Give the verdict per row, the substrate status, the residual uncertainty, and the next action.

## Output

Use the [ledger entry](../templates/ledger-entry.md) for the record, and the [handoff template](../templates/multi-thread-handoff.md) for delivery.
