# Mechanism Map Audit Checklist

Use this checklist before accepting `mechanism_map` as complete.

This is the artifact-level gate, not the per-wave gate.

## 0. Structural Existence

- [ ] A real cumulative `mechanism_map` synthesis exists.
- [ ] `accepted_claims`, `contradiction_register`, `coverage_frontier`, and `open_questions` exist or their equivalent is explicit.
- [ ] The artifact is the result of multiple compounding waves or an explicitly accepted equivalent.

## 1. Mechanism Quality

- [ ] Mechanisms are structured into families and subfamilies.
- [ ] Mechanisms are operationally described, not vaguely named.
- [ ] Source-backed mechanisms are visibly separated from `behavioral reconstruction`.
- [ ] Per-mechanism evidence, contradictions, tradeoffs, and confidence are visible.
- [ ] Mechanisms are grounded in trajectories or source, not only in prose.

## 2. Bucket Coverage

- [ ] The artifact covers:
  - policy or program layer
  - workflow or architecture
  - tool gateway
  - execution control
  - context
  - state
  - artifacts or workspace
  - memory
  - verification or completion
  - recovery
  - observability
  - sandbox or execution environment
  - eval-related mechanisms
- [ ] Simple mechanisms remain visible alongside complex ones.
- [ ] Complex mechanisms are decomposed instead of treated as monoliths.

## 3. Source And Trajectory Reconciliation

- [ ] Real trajectory evidence materially shaped the mechanism map.
- [ ] Source-backed systems are linked back to source paths where possible.
- [ ] BigAI or other no-source systems remain explicitly behavioral where source is absent.
- [ ] Source-intent versus observed behavior disagreements remain visible.

## 4. Interaction And Contradiction

- [ ] A real interaction map or equivalent exists.
- [ ] Cross-bucket interactions are explicit.
- [ ] Contradictions are preserved and traceable.
- [ ] The artifact does not force false consensus.

## 5. Downstream Usefulness

- [ ] The artifact is detailed enough to support `failure_taxonomy`.
- [ ] The artifact is detailed enough to support `eval_implications`.
- [ ] The artifact is detailed enough to support provisional `variant_family_seeds`.
- [ ] The artifact protects simple baselines and minimal-sufficient mechanisms from prestige bias.

## 6. Family Saturation

- [ ] Promoted mechanism families are explicitly labeled `exploratory`, `emerging`, or `decision_ready`.
- [ ] Any `decision_ready` family satisfies the protocol saturation rule rather than only appearing in many summaries.
- [ ] Regime-local families are marked as regime-local instead of being silently generalized.
- [ ] Major contradictions are either bounded narrowly or carried forward explicitly before a family is marked `decision_ready`.

## 7. Completion Gate

- [ ] Major unread path families in `coverage_frontier` are either closed or explicitly accepted by the human owner.
- [ ] The artifact-level verdict is one of:
  - `pass`
  - `pass_with_warnings`
  - `blocked`

Rule:

- Do not mark `mechanism_map` complete because several lanes mentioned the same mechanism.
- Mark it complete only if the mechanism families are structured, evidenced, reconciled, and reusable downstream.
