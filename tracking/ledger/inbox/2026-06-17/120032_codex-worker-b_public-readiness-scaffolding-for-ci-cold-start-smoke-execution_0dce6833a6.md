# Raw Ledger Update

- recorded_at_utc: 2026-06-17T12:00:32.563813+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Codex Worker B
- task: public-readiness scaffolding for CI/cold-start/smoke execution
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 0dce6833a64682d06b8a83aeccabb35a0c3576a0a18a76e73ba99e8314d25513
- commit_message: HOLD - public readiness scaffolding not committed
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-17/120032_codex-worker-b_public-readiness-scaffolding-for-ci-cold-start-smoke-execution_0dce6833a6.md

```text
RAW_LEDGER_UPDATE
- actor: Codex Worker B
- task: public-readiness scaffolding for CI/cold-start/smoke execution
- event_type: implementation
- summary: Added public-facing readiness docs plus Makefile, workflow, and shell wrappers for cold-start and smoke execution; cleaned reviewer-facing provenance wording in the public docs slice.
- observations: The live tree does not include the older runner/tools Python helpers, so the readiness wrappers were rewritten to use only the filesystem family assets, docs sweeps, and local grader logic. The smoke script now exercises eval_suite/families/filesystem/public_manifest_repair_smoke directly. The public README, reviewer guide, provenance notes, and publication index now point at the readiness path instead of quarantine-style wording.
- inference: A public-only readiness lane is viable in this checkout without depending on missing internal Python packages. The aggregate make target is the right reviewer-facing entrypoint for CI and local verification.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/README.md; /Users/mohamud/Downloads/harnesseng/PUBLIC_REVIEWER_GUIDE.md; /Users/mohamud/Downloads/harnesseng/docs/README.md; /Users/mohamud/Downloads/harnesseng/docs/provenance/README.md; /Users/mohamud/Downloads/harnesseng/docs/provenance/agent_runtime_adaptation_policy.md; /Users/mohamud/Downloads/harnesseng/docs/provenance/third_party_notices.md; /Users/mohamud/Downloads/harnesseng/docs/publication/README.md; /Users/mohamud/Downloads/harnesseng/docs/publication/public_evidence_index.md; /Users/mohamud/Downloads/harnesseng/docs/publication/public_readiness.md; /Users/mohamud/Downloads/harnesseng/Makefile; /Users/mohamud/Downloads/harnesseng/scripts/public_readiness_cold_start.sh; /Users/mohamud/Downloads/harnesseng/scripts/public_manifest_repair_smoke.sh; /Users/mohamud/Downloads/harnesseng/tests/test_public_manifest_repair_smoke.py
- affected_components: public docs; publication nav; public readiness command surface; synthetic public manifest repair smoke wrapper; focused smoke test
- decision_change: Use a repo-local public readiness lane built from docs sweeps and the filesystem smoke family, rather than depending on missing internal runner/tools imports.
- unresolved_questions: The tree still has unrelated pre-existing edits outside this slice; they were not modified. If the parent wants broader CI coverage, the next slice should decide whether to reintroduce additional internal sentinels or keep the public-only lane intentionally minimal.
- confidence: 0.91
- commit_message: HOLD - public readiness scaffolding not committed
```
