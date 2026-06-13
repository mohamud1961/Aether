# Adversarial Code Review Closeout

Use this skill as the manual fallback when the `codex-review` helper is not
available or when a reviewer wants a second adversarial pass.

The goal is not to "sound reviewed." The goal is to decide, with evidence,
which findings are real, which are false positives, what was fixed, and what
still remains risky.

## Governing Question

> Does the live diff actually do what the review says it does?

## When To Use

Use this skill for:

- review-driven fixes;
- boundary or policy changes;
- eval substrate or measurement-critical changes;
- any slice where a reviewer could plausibly disprove the closeout.

## Manual Review Workflow

1. Read the actual diff and the tests or sentinels that should cover it.
2. Triaging findings into accepted, rejected, or needs-more-evidence.
3. Fix accepted findings and rerun the smallest useful checks.
4. Re-run the review lens against the updated code and evidence.
5. Close with truthful residual risk or keep the slice open.

## Output Contract

A useful closeout note should include:

- the diff under review;
- the review findings and dispositions;
- accepted fixes and evidence;
- consciously rejected findings and why;
- residual risks;
- the next concrete action.

## Companion Skill

Use [Code review closeout](code-review-closeout.md) for the primary workflow,
and keep this page as the manual adversarial variant.

