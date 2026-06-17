# Implementation Loop

Use this skill when a planned change needs to move from contract to verified
diff through a bounded maker/checker loop.

This is stronger than a normal implementation packet. It defines the complete
cycle for code, docs-as-contract, runner logic, hooks, tools, or workflow
changes where the first patch is only one turn in the loop.

## Governing Question

Can this change be implemented, checked, reviewed, repaired, and handed back
without expanding scope or weakening the acceptance signal?

## Use Cases

- Turn a failure classification into one mechanism patch.
- Implement a new hook, tool, runner helper, or workflow skill.
- Repair a flaky validation path with a known-bad case.
- Apply accepted review findings after a review thread reports issues.
- Move a real implementation from an internal location to a public-safe home.
- Update docs that define an operational contract, not just prose.

## Inputs

- objective and write scope;
- behavior contract or doc contract;
- target checks and sentinel checks;
- known dirty-tree boundaries;
- reviewer or orchestrator handoff format;
- stop conditions and retry cap.

## Workflow

1. **Freeze the contract**
   - State the behavior that must change.
   - Name what is out of scope.
   - Confirm the target check before editing.

2. **Inspect before editing**
   - Read the local pattern you will extend.
   - Identify owner boundaries and adjacent dirty files.
   - Decide the smallest coherent diff.

3. **Patch once**
   - Implement one mechanism or contract change.
   - Prefer existing local helpers and naming.
   - Avoid opportunistic refactors.

4. **Run the target check**
   - Run the check that proves the contract.
   - If it fails, classify whether the failure is code, environment, fixture,
     or scope.

5. **Run sentinels**
   - Run the smallest adjacent checks that catch regressions.
   - Record omitted sentinels with a reason.

6. **Review**
   - Self-review for small slices.
   - Use a review thread for larger or riskier diffs.
   - Accept, reject, or defer each finding with evidence.

7. **Repair loop**
   - Apply accepted findings only.
   - Rerun focused checks.
   - Stop after the retry cap if the same blocker repeats.

8. **Handoff**
   - Report exact files changed, checks run, residual risks, and next action.
   - Include external-state status if any process, server, or VM was touched.

## Output Contract

```text
status: complete | partial | blocked | invalid_due_to_environment
objective:
scope:
files_changed:
target_checks:
sentinel_checks:
review_findings:
accepted_fixes:
rejected_findings:
retry_count:
external_state:
next_action:
```

## Guardrails

- Do not start coding without a target check.
- Do not broaden the slice after seeing a failure.
- Do not let the maker be the only checker for risky work.
- Do not treat a generated artifact as proof unless the verifier checks it.
- Do not keep retrying when failures stop adding new evidence.

