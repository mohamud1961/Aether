# Deep Synthesis: Failure Taxonomy

Use this skill when evidence needs to be turned into failure families and
attribution rules.

## Trigger

Use when the task is to classify what failed, why it failed, and which
component should have changed the next rational action.

## Inputs

Bring:

- run analyses and outcome rows;
- mechanism-map carry-forward notes;
- source and informal evidence that affects attribution;
- verifier, grader, or replay notes when they matter;
- known stale or superseded prep artifacts.

## Workflow

1. Separate symptoms from causes.
2. Split model, harness, environment, and eval contributions.
3. Classify primary and contributing failure families.
4. Preserve mixed attribution when evidence does not close it.
5. Connect failures to preventive, detection, containment, or recovery roles.

## Outputs

A good failure-taxonomy pass should include:

- structured failure families and subfamilies;
- severity or recoverability notes;
- attribution caveats;
- cross-task or cross-system comparisons where useful;
- downstream implications for eval or mechanism design.

## Validation Checklist

- the taxonomy does not collapse everything into anecdotes;
- symptoms and causes stay distinct;
- evaluator or environment failures are not mislabeled as model capability;
- regime-specific failures remain marked as regime-specific;
- no family is promoted without enough evidence depth.

## What Not To Do

- do not treat every failure as model failure;
- do not generalize from one path to a universal cause;
- do not hide contradictions;
- do not claim decision readiness before the wave is actually saturated.

