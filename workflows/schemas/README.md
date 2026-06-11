# Schemas

Structured data templates used across the loop — from task packets and variant
seeds to failure cards and case study templates.

## Contents

| File | Purpose |
|---|---|
| [failure-card.md](failure-card.md) | Schema for one failure pattern: visible symptoms, severity, recoverability, likely class, direct observations, inferred root causes, evidence paths, affected harness areas, downstream effects, candidate mechanisms, eval implications |
| [mechanism-card.md](mechanism-card.md) | Schema for one proposed harness mechanism: target failure class, affected components, behavioral change, evidence base, predicted impact, implementation approach, eval hooks, risks |
| [variant-family-seed.md](variant-family-seed.md) | Schema for a surviving variant family seed: source failure families, affected block types, expected interface pressure, atomic-vs-combo classification, composition constraints, ablation hooks, eval hooks |
| [trajectory-case-study.md](trajectory-case-study.md) | 9-section CASE_STUDY template for a trajectory source: system context, run context, trajectory summary, key moments, failure classification, mechanism analysis, harness component notes, cross-family comparison |
| [task-packet.md](task-packet.md) | 25-field TASK_PACKET struct for a collaboration brief: stage, artifact, objective, exact question, inputs, exclusions, output contract, collaboration mode, external agent action, evidence expectations |

## How These Are Used

```
run-analysis → failure-card.md (classify failures)
              ↓
        hypothesis → variant-family-seed.md (design variant)
              ↓
eval design → mechanism-card.md (record mechanism)
              ↓
  deep synthesis → trajectory-case-study.md (case evidence)
```

`task-packet.md` is the input contract for every specialist agent dispatch.

## Rules

- No failure card without upstream evidence paths.
- No variant seed without a source failure family.
- No mechanism card without an owning harness component and a proving eval hook.
- One card = one pattern. Do not bundle vague "bad behavior" into a single card.
