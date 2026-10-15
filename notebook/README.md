# Notebook

This is the decision log for the Aether work: one row per decision, a dated timeline, and a list of turning points, kept next to the work it describes.
The key result is that the record keeps failed and negative results, including the held-out evaluation that falsified the lift claim.
This matters because a reader can check which claims were withdrawn, and which numbers come from primary files.

## What this notebook is

A decision log, not a changelog or a results page. Each entry says what was decided, why, what evidence was used, and what changed afterwards.

## How entries were written

- Work sessions wrote raw entries with twelve fields: actor, task, event type, summary, observations, inference, evidence paths, affected components, decision change, open questions, confidence, and a commit message.
- Event types are decision, experiment, failure, source analysis, implementation, regression, and open question.
- Entries were written by hand. Nothing in the published set was generated from a model's summary alone.
- Before publication, host names, private paths, held-out task names, benchmark task names, and private operational details were removed.

## How entries are indexed

- `DECISIONS.md`: one row per decision, with date, reason, evidence, and the change it made.
- `timeline.md`: dated events from November 2025 to October 2026.
- `turning-points.md`: moments where a claim changed, a result overturned an assumption, or a process rule was added.
- Entry counts depend on scope. The main branch holds 820 top-level entries; wider sets range from 1,004 to 1,793. This notebook does not add those counts together.

## How to read it

1. Start with `timeline.md` for the shape of the period.
2. Use `DECISIONS.md` to find a choice and the evidence behind it.
3. Read `turning-points.md` for failures, corrections, and reversals.

Conventions:

- Numbers come from primary files. Where sources disagree, the primary file wins. Where no primary file exists, the number is left out.
- Some figures come from the principal's own working notes and were not re-checked against a repository. Those are marked in the source comment.
- Each paragraph or row with a number carries a source comment, which is hidden when the page renders.
- A "trial" is one run of one task. An "evaluation board" is a set of trials run under one protocol.
- Generation names (Gen 1 to Gen 5) follow the public glossary. Gen 5 is in development.
