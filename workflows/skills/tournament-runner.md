# Tournament Runner

Use this skill when several variants, prompts, tools, routes, or configs need
to be compared under the same evaluation contract.

A tournament is not a pile of runs. It is a preregistered comparison with fixed
candidates, fixed rows, invalid-run accounting, sentinels, and a keep/kill
decision.

## Governing Question

Which candidate is actually better under the declared score surface, and is
the result strong enough to keep, kill, iterate, or park?

## Use Cases

- Compare route variants after a failure analysis.
- Compare prompt/tool configurations under the same runner.
- Choose between two implementation mechanisms.
- Validate whether a repair helped its target without hurting sentinels.
- Reproduce a previous result after runner or environment changes.

## Tournament Contract

Before launching runs, define:

- tournament id;
- candidate list;
- target rows or diagnostics;
- regression sentinels;
- baseline and incumbent;
- predicted score movement;
- max attempts and invalid retry policy;
- cost or runtime budget;
- scoreboard schema;
- keep/kill/iterate rule.

## Workflow

1. **Freeze candidates**
   - Do not add or remove candidates after seeing early results.
   - Version candidate configs and prompts.

2. **Freeze score surface**
   - Name target rows and sentinels.
   - State which rows are diagnostic-only.
   - State how invalid rows affect decisions.

3. **Run matrix**
   - Run each candidate under the same command shape.
   - Capture run ids, configs, traces, result rows, and costs.
   - Classify invalids separately from failures.

4. **Score**
   - Build one scoreboard from raw rows.
   - Include target score, sentinel score, invalid rate, cost, and step budget.
   - Preserve negative results and failed predictions.

5. **Review**
   - Inspect whether the winner is real or lucky.
   - Check whether target gains came from evaluator drift, hidden leakage, or
     invalid-row filtering.

6. **Decide**
   - Promote only when the result is net-positive on target, sentinels,
     validity, and cost.
   - Kill candidates that regress guardrails.
   - Iterate only when the next testable hypothesis is specific.

## Output Contract

```text
tournament_id:
candidates:
target_rows:
sentinels:
baseline:
prediction:
result_rows:
scoreboard:
invalid_rows:
winner:
decision: keep | kill | iterate | park | blocked
evidence_paths:
next_action:
```

## Guardrails

- Do not promote from a single lucky pass when sentinels are missing.
- Do not compare candidates run under different contracts without labeling the
  result invalid for promotion.
- Do not reinterpret a failed prediction as success after the fact.
- Do not let tournament scale outrun review capacity.

