# Pre-registration

Use this before a non-trivial change or a held-out run. Fill it in and commit it before any result exists. Results are appended in a later commit and must not edit this one. A run that changes its source, scorer, prompt, task pack, or verifier after this is sealed is a different run.

## 1. Question and claim

- Question:
- Claim being tested, in one sentence:
- Failure family or capability gap:

## 2. Scope

- In scope:
- Out of scope:
- Files likely touched:
- Behaviour the evaluator sees:

## 3. Checks fixed in advance

- Target test, eval, or verifier (path):
- Baseline (what the comparison is against, and its recorded result):
- Ceiling or reference behaviour:
- Known-bad case (must fail the check):
- Regression sentinels (what adjacent behaviour must not change):
- Checks that must not be weakened:

## 4. Prediction

- Expected result, with a number:
- Expected result under the falsifier:
- The falsifier, stated so a reader can see whether it fired:

## 5. Validity rules

- What counts as an invalid row (provider, protocol, environment, grader, timeout, model):
- Retry policy: no blind retries. Invalid rows are kept and counted.
- Minimum valid rows before a verdict is allowed:
- Stop conditions:

## 6. Run freeze

- Source commit and tree hash:
- Task pack and version:
- Model, route, and settings:
- Scorer and verifier version:
- Evidence location:

## 7. Decision rule

- Keep if:
- Kill if:
- Iterate if:
- Who decides: the principal.

## 8. Seal

- Commit that contains this file:
- Date:
