# Verification

Verification covers whether a checker that says "done" is right. That includes a verifier judging task state, a lifecycle receipt that matches the managed process, and a serializer that produces exact bytes.

Verifiers were the largest source of wrong passes in the record. Two sentinel runs gave 2 and 1 false cleans. The known-bad falsifier never passed. One verifier bench read the wrong tool-result field in every historic run, until a packet-unwrap bug was found and the bench was rerun.

A verifier that clears a wrong finish turns a failure into a pass, and the score then measures the verifier. Verifiers need their own tests, with known-bad and known-good cases.

## Failure modes probed

- A false clean: the verifier passes a finish that the official grader rejects.
- A false hold: the verifier blocks a finish that was correct.
- Completion-contract text treated as requirements, or read-only commands blocked.
- A verifier that cannot read the evidence it grades.
- Serialization drift: key order, trailing newline, number type, precision.

## What the history taught

1. **The verifier must be measured, or it fails silently.** One generation's verifier ran 0 real checks across 20 runs. A known-bad falsifier never passed (3/5, then 2/5).
2. **Report catches and false holds together.** On a bench of 377 graded finishes (29 wrong), the kept verifier caught 22/29 with 6/348 false holds. A stricter variant caught 25/28 but held 33% of correct finishes.
3. **The bench itself needs auditing.** A parsing bug meant every earlier verifier bench read the wrong tool-result field; all were rerun.
4. **Claims bias the judge.** Review without the agent's claims caught 15/18 wrong finishes, against 10/18 with them. The verifier is an LLM-as-judge and needs the same calibration.

Every evaluation behind these lessons is listed in the [catalogue](../catalogue.md).

## Current tasks

Validation key: known-bad files, each rejected with its expected reason; careless controls, each rejected; reference solvable from the workspace. All rows pass the grader gate.

| Task | Failure mode | What makes it hard | Validation | Admission |
|---|---|---|---|---|
| `exact_serialization_contract` | Exact bytes from a typed export to a JSON spec | Export pointer names the current file; README and CSV snapshot point to the old one; superseded spec; unsorted and quoted rows; unpadded balances; inline array format | 5 known-bad; 5 careless; solvable | capability |
| `semantic_equivalence_contract` | Replacement expression evaluator | Withdrawn draft with the wrong associativity; legacy notes with 32-bit wrap and leading-zero rejection; grader adds 150 generated expressions | 7 known-bad; 5 careless; solvable | debug |

## Limits

The two tasks test exactness against a spec: bytes for the serializer, behaviour on 150 generated expressions for the evaluator. They do not grade a verifier's judgment on a live agent finish; that is what the verifier bench in the [measurement validity method](../methods/measurement-validity.md) is for. The evaluator task runs candidate code and is admitted as debug until it is graded inside a sandbox.
