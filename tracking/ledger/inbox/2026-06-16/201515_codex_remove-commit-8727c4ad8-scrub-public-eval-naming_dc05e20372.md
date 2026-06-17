# Raw Ledger Update

- recorded_at_utc: 2026-06-16T20:15:15.002834+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: remove commit 8727c4ad8 Scrub public eval naming
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: dc05e203723f970e7cc6c62af849f4cf8ce5b14f087d64aa379a763339122721
- commit_message: HOLD - git history/index writes blocked by sandbox permission
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/201515_codex_remove-commit-8727c4ad8-scrub-public-eval-naming_dc05e20372.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: remove commit 8727c4ad8 Scrub public eval naming
- event_type: implementation
- summary: Applied the inverse patch for commit 8727c4ad8 to the working tree while preserving the newer loop-engineering showcase edits in workflows/loop-engineering.md, workflows/ai-native-engineering-showcase.md, and workflows/agentic-engineer-capability-map.md.
- observations: Git history could not be changed because the sandbox cannot write inside .git; creating .git/index.lock and direct touch inside .git both fail with Operation not permitted. `git apply -R --check` failed only on workflows/loop-engineering.md, so the inverse patch was applied with exclusions for the three newer loop-showcase files. `git diff --check` passed and JSON parsing passed. Markdown link check reports restored older links in docs/publication/public_evidence_index.md to paths that are not present in the current working tree.
- inference: The commit's effects are mostly removed from the working tree, but the commit still exists in Git history and a local Git operation is required to stage/commit or rewrite history.
- evidence_paths: README.md; docs/; eval_suite/; variants/; workflows/; research/case_studies/; research/methodology/; research/phases/; research/synthesis/; tracking/collab/public_repo_readiness/CONTINUATION_STATE_2026-06-16.md
- affected_components: public docs; eval suite docs; variants docs; workflow docs; research public surfaces
- decision_change: Public naming scrub commit is no longer treated as the current working-tree target, except for later loop-engineering edits intentionally preserved.
- unresolved_questions: Whether the desired final Git operation is a non-destructive revert commit or history rewrite/drop of 8727c4ad8 once .git writes are available.
- confidence: medium
- commit_message: HOLD - git history/index writes blocked by sandbox permission
```
