# Agentic TDD Verification Checklist

Use this before a coding agent starts a non-trivial implementation slice.

## Contract

- Objective:
- In scope:
- Out of scope:
- Files likely touched:
- User-visible or evaluator-visible behavior:

## Frozen Checks

- Target test/eval/verifier:
- Baseline result:
- Known-bad case:
- Ceiling or reference behavior:
- Regression sentinels:
- Checks that must not be weakened:

## Anti-Cheating Rules

- Hidden answers or grader internals are not available to the implementation.
- The verifier must require artifacts, commands, or state when claims are not
  enough.
- Test changes must be stricter, narrower, or more faithful to the contract.
- The agent must explain any test or fixture change in the handoff.

## Closeout

- Target check result:
- Sentinel result:
- Review findings accepted:
- Review findings rejected with evidence:
- Invalid environment/provider rows:
- Final status:
- Exact next action:

