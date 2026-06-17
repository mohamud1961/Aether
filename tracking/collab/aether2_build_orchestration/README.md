# Aether-2 Build Orchestration

This directory is the orchestrator-owned coordination surface for the Aether-2 build.

Objective:
- Build Aether-2 through G1 from [AETHER2_BUILD_SPEC.md](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_build_spec/AETHER2_BUILD_SPEC.md) with Hour-0 contracts first, bounded `gpt-5.4-mini` worker tasks next, and integration/review discipline throughout.

Working posture:
- Direct orchestration, not Goal-gated.
- Mandatory bounded `gpt-5.4-mini` delegation.
- New-files-first implementation under `runner/aether2/`.
- Old MLPCP/kernel/blocks code is harvest-only unless the spec explicitly says otherwise.

Review gate:
- `codex_review_skill_plus_adversarial`

Primary artifacts:
- `orchestration_ledger.md`: active tasks, workers, files, tests, review state, integration state, blockers.
- `decision_log.md`: binding orchestration decisions and constraint changes.
- `hour0_contracts.md`: frozen Hour-0 contracts used by workers and integrator.
