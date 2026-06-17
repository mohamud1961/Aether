# Documentation And Packaging Handoff

- Status: COMPLETE
- Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Target thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-15`

## Public-Facing Audit Findings

- The root README still described the project as a generic “Aether” MVP and did not explain the canonical `harness.aether2` versus compatibility `runner.aether2` boundary.
- `runner/README.md` pointed at dead docs (`docs/current_surface_map.md` and `docs/deprecation_map.md`) and needed a public, live-tree navigation target.
- The public navigation pages under `harness/`, `docs/`, `eval_suite/`, `variants/`, and `workflows/` were still mostly skeleton language and needed truthful status wording instead of placeholders.
- Editable install discovery failed in a foreign temp cwd because setuptools auto-discovery saw many unrelated flat-layout top-level directories.

## Files Changed

- `README.md`
- `pyproject.toml`
- `runner/README.md`
- `harness/README.md`
- `harness/aether2/README.md`
- `harness/aether2/runtime/README.md`
- `harness/aether2/control/README.md`
- `harness/aether2/tools/README.md`
- `harness/aether2/traces/README.md`
- `harness/aether2/agents/README.md`
- `harness/aether2/cli/README.md`
- `harness/aether2/env/README.md`
- `harness/aether2/hooks/README.md`
- `harness/aether2/monitoring/README.md`
- `harness/aether2/skills/README.md`
- `harness/aether2/verification/README.md`
- `docs/README.md`
- `docs/architecture/README.md`
- `docs/architecture/public-architecture.md`
- `docs/research/README.md`
- `docs/case-studies/README.md`
- `docs/provenance/README.md`
- `docs/publication/README.md`
- `docs/schemas/README.md`
- `eval_suite/README.md`
- `eval_suite/boards/README.md`
- `eval_suite/adapters/README.md`
- `eval_suite/custom/README.md`
- `eval_suite/graders/README.md`
- `eval_suite/schemas/README.md`
- `eval_suite/scoreboards/README.md`
- `eval_suite/sentinels/README.md`
- `eval_suite/fixtures/README.md`
- `variants/README.md`
- `variants/families/README.md`
- `variants/shared/README.md`
- `variants/scoreboards/README.md`
- `workflows/README.md`
- `workflows/orchestration/README.md`
- `workflows/synthesis/README.md`
- `workflows/evals/README.md`
- `workflows/case-studies/README.md`
- `workflows/skills/README.md`

## Requirement Dispositions

- Audit stale names, broken links, misleading claims, empty placeholders, and legacy import examples: DONE.
- Curate a truthful root README and canonical directory separation: DONE.
- Curate concise navigation files for the major public directories: DONE.
- Audit packaging metadata and make canonical `harness.aether2` discoverable in editable installs: DONE.
- Retain `runner.aether2` compatibility where still required: DONE.
- Add a small package/import smoke check only if packaging changes required it: satisfied via the documented editable-install smoke and existing identity tests; no new test file was needed.
- Create a public architecture/navigation document: DONE.
- Verify all changed-doc links/paths/commands against the live tree: DONE.
- Produce a publication-readiness gap list for the next slice: DONE.

## Validation Results

- `python3 -m pip install -e .` in a temporary venv from the repo root, then from a foreign temp cwd `python -c "import harness.aether2, runner.aether2; print(...)"`: passed, output `harness.aether2` and `runner.aether2`.
- `python3 tools/aether2_genericity_check.py`: passed.
- Path/link existence check for the changed docs and referenced files: passed, output `path-check-ok`.
- Broad local compatibility baseline: `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`: passed, `239 passed in 47.20s`.
- `git diff --check`: passed.
- `python3 -m py_compile`: not applicable here because this slice did not change any `.py` source files.

## Claims Deliberately Excluded Or Qualified

- No claim of production readiness.
- No claim of eval leadership.
- No claim that `runner.aether2` is canonical; it is compatibility-only.
- No claim that the navigation-only `harness.aether2` subpackages are implemented code.
- No claim that private eval runs, raw ledgers, hidden graders, credentials, or private research artifacts are public.

## Adversarial Review

- Python maintainer finding: editable install failed because setuptools auto-discovery tried to include unrelated flat-layout top-level directories. Repair: explicit `tool.setuptools.packages.find` include rules for `harness*` and `runner*`.
- AI-agent/eval researcher finding: the public README and navigation pages overstated status and hid the canonical package boundary. Repair: root README, `harness/README.md`, `harness/aether2/README.md`, and the public architecture doc now describe the implemented runtime/control/tools/traces split and the navigation-only stubs.
- Hiring reviewer finding: dead links and placeholder copy made the repo look less coherent than the live tree. Repair: retargeted `runner/README.md` to the live architecture map and compatibility map, and replaced placeholder prose with concise navigation across the major public directories.
- Remaining accepted adversarial findings: none after the final validation rerun.

## Remaining Publication Gaps

- The navigation-only `harness.aether2` subpackages still need either real public modules or explicit “planned only” content if they remain stubs.
- `eval_suite/` still lacks concrete public task-pack content and scored rows on the public side of the tree.
- `workflows/` is still mostly navigation-only and needs one concrete public example per major workflow bucket.

## Exact Next Dependency-Ready Publication Slice

- Publish the first concrete public eval-pack slice: one board, one custom task-pack, one grader, and one score summary under `eval_suite/`, then add a small automated public smoke around the editable-install/import story if packaging changes continue.

## External-State Confirmation

- No branch, worktree, commit, or push was created.
- No persistent process, server, VM, or credential home was left running for this task.
- The temporary venv used for the editable-install smoke was ephemeral and left no active service behind.

## RAW_LEDGER_UPDATE

- Persisted: yes
- Private raw historian input path: `tracking/ledger/inbox/2026-06-15/183101_public-repository-worker-6_public-aether-documentation-and-python-packaging-curation_cdb79c616f.md`

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Send result: success (`codex_app.send_message_to_thread`)
