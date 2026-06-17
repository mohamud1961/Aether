# Failure Taxonomy Audit Checklist

Use this checklist before accepting `failure_taxonomy` as complete.

This is the artifact-level gate, not the per-wave gate.

## 0. Structural Existence

- [ ] A real cumulative `failure_taxonomy` synthesis exists.
- [ ] `accepted_claims`, `contradiction_register`, `coverage_frontier`, and `open_questions` exist or their equivalent is explicit.
- [ ] The artifact inherits from `mechanism_map` through a structured handoff.

## 1. Failure Quality

- [ ] Failure classes are structured into clear groups and subgroups.
- [ ] Symptoms are separated from causes.
- [ ] Model, harness, environment, and eval contributions are kept distinct when evidence requires it.
- [ ] Per-failure evidence, uncertainty, and severity or recoverability notes are visible.
- [ ] The artifact does not collapse all failures into anecdotes.

## 2. Evidence Quality

- [ ] Real trajectories and run bundles materially support the taxonomy.
- [ ] Source is used for attribution where available.
- [ ] Issues and postmortems provide contradiction pressure rather than silent upgrades in confidence.
- [ ] Eval and benchmark structure is used when it affects attribution.

## 3. Mapping And Prevention

- [ ] Failure classes are linked back to candidate mechanisms where warranted.
- [ ] Preventive, detection, containment, and recovery roles are distinguishable.
- [ ] The artifact flags where no convincing mechanism exists yet.
- [ ] The artifact flags where a mechanism can reduce one failure while increasing another.

## 4. Regime Sensitivity

- [ ] Cross-task pass/fail comparisons are visible.
- [ ] Cross-system comparisons are visible.
- [ ] The artifact identifies where failures are regime-specific instead of universal.
- [ ] The artifact preserves mixed or unresolved attribution when evidence does not close it.

## 5. Downstream Usefulness

- [ ] The artifact is detailed enough to support `eval_implications`.
- [ ] The artifact is detailed enough to support `variant_family_seeds`.
- [ ] High-leverage failures are distinguishable from lower-leverage failures.

## 6. Family Saturation

- [ ] Promoted failure families are explicitly labeled `exploratory`, `emerging`, or `decision_ready`.
- [ ] Any `decision_ready` failure family satisfies the protocol saturation rule rather than only having many anecdotes.
- [ ] Regime-local failures are marked as regime-local instead of being silently generalized.
- [ ] Major attribution contradictions are either bounded narrowly or carried forward explicitly before a family is marked `decision_ready`.

## 7. Completion Gate

- [ ] Major unread path families in `coverage_frontier` are either closed or explicitly accepted by the human owner.
- [ ] The artifact-level verdict is one of:
  - `pass`
  - `pass_with_warnings`
  - `blocked`

Rule:

- Do not mark `failure_taxonomy` complete because many failure anecdotes exist.
- Mark it complete only if the classes are structured, evidenced, attributed carefully, and useful for downstream design.
