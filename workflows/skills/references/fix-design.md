# Generic Fix Design

## Fix Record

For every fix specify:

1. Generic failure class.
2. Owning harness component.
3. Observed evidence.
4. Intended behavior change.
5. Custom homolog eval.
6. Known-bad case.
7. Ceiling case.
8. Regression sentinels.
9. Non-leakage argument.
10. Risks and regressions.
11. Predicted impact.
12. Keep/kill criterion.

## Genericity Test

A generic fix can be described without task names, expected values, suite paths, fixed ports, grader quirks, or memorized solution strategies.

Good:

> Distinguish model-authored readback from independent requirement evidence.

Bad:

> When a specific G-code label appears, render the file before writing the expected flag.

## Eval Design

Change names, values, paths, layouts, and distractors while preserving the causal pressure and target engineering behavior. Use deterministic grading and realistic shell/environment pressure.

## Mechanism Isolation

Test baseline, A, B, A+B, then a full candidate. Record failed predictions.

## False Improvement

Reject verifier pessimism without grader gains, more blocked exits without truthfulness benefit, fewer steps caused by earlier failure, task-specific patches, contaminated gains, and replay-only wins.
