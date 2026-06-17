# .gitignore Review

- Reviewed at: `2026-06-15T16:33:49Z`
- Input state: current `.gitignore` diff plus the preservation inventory and public-readiness maps

## Summary

The current `.gitignore` changes are narrowly aligned with the private/public split that the preservation docs describe. I did not identify a correction that was both necessary and safe enough to make in this pass.

## What Is Correctly Hidden

- Private eval and task corpora: `official_tasks/`
- Raw research mirrors and intake: `research/sources/`, `research/intake/`, `research/external/`
- Historian and variant execution state: `tracking/ledger/`, `tracking/variants/`
- Raw collaboration run artifacts: `tracking/collab/**/runs/`, `tracking/collab/**/.aether2/`, `tracking/collab/**/workspaces/`, and related workspace copies
- Local cache and environment noise: `.venv/`, `venv/`, `website/node_modules/`, `website/.next/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.tox/`, `.nox/`, `.playwright-mcp/`, `.tmp_codex_home/`

## Public Paths That Remain Visible

- `tracking/collab/public_repo_readiness/`
- `runner/README.md`
- `tests/test_aether2_genericity.py`
- `tools/aether2_genericity_check.py`
- the new public skeleton directories under `harness/`, `eval_suite/`, `variants/`, `workflows/`, and `docs/`

## Over-Broad Pattern Check

- I checked the broad run-artifact globs and they only suppress raw execution material, not the new public docs/tree.
- The `tracking/collab/**/*.log`, `tracking/collab/**/*.jsonl`, `tracking/collab/**/*.tar.gz`, and `tracking/collab/**/*.zip` rules are broad, but they are acceptable because they target raw artifacts that should stay private.
- I did not find a public-tree path that needed to be re-exposed for this phase.

## Validation Evidence

- `git check-ignore -v official_tasks/ tracking/ledger/ research/sources/ tracking/collab/**/.aether2/ tracking/collab/**/runs/`
- `git status --short --untracked-files=all` confirmed that public readiness docs and the Aether-2/test/tool surfaces remain visible

## Changes

- No `.gitignore` edits were necessary in this pass.
- The review outcome is: preserve the current ignore boundaries as-is.
