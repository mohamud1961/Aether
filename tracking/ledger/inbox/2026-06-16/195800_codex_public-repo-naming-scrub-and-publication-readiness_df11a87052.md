# Raw Ledger Update

- recorded_at_utc: 2026-06-16T19:58:00.086715+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: public repo naming scrub and publication readiness
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: df11a87052f8ef183479f39af7e198db158140967da671721b458e4bfd9d139c
- commit_message: Scrub public eval naming
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/195800_codex_public-repo-naming-scrub-and-publication-readiness_df11a87052.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: public repo naming scrub and publication readiness
- event_type: implementation
- summary: Scrubbed curated public surfaces so staged public docs/eval/variant/workflow/research files no longer mention TerminalBench, benchmark wording, known benchmark suite names, or official task IDs; renamed public dossier/prompt/case-study paths to neutral eval language.
- observations: Commit 8727c4ad8 `Scrub public eval naming` updated README.md, docs/, eval_suite/, variants/, workflows/, research public surfaces, and tracking/collab/public_repo_readiness/CONTINUATION_STATE_2026-06-16.md. Staged-content scan for disallowed public terms returned no hits before commit. Validation passed: JSON parse, Ruby YAML parse, py_compile on touched Python helpers, git diff --check, and python3 tools/aether2_genericity_check.py. Wider repo scan still finds benchmark/task terms in internal/private areas such as AGENTS.md, runner/, website/, tracking/collab/final_harness_eval_suite/, and tracking/collab/stage_02_synthesis/.
- inference: Curated public-facing surfaces are clean under the strict scan, but the entire checkout is not yet safe for a whole-repo public push unless internal/private folders are excluded or separately scrubbed.
- evidence_paths: README.md; docs/; eval_suite/; variants/; workflows/; research/case_studies/; research/methodology/; research/phases/; research/synthesis/; tracking/collab/public_repo_readiness/CONTINUATION_STATE_2026-06-16.md
- affected_components: public documentation; public eval surfaces; public variant cards and summaries; AI-native workflow showcase; research synthesis/case-study surfaces
- decision_change: Public publication should use a curated allowlist/export or a follow-up whole-repo scrub; do not publish raw trajectories, codebases, official task assets, or internal tracking folders as-is.
- unresolved_questions: Why git rm --cached for research/sources, research/intake, and official_tasks cannot create .git/index.lock in this sandbox despite normal git add/commit succeeding; whether AGENTS.md, runner/, website/, and internal tracking folders are intended to be public or private in the final publication shape.
- confidence: high for curated public-surface scrub; medium for whole-repo readiness because raw/private tracked assets remain indexed.
- commit_message: Scrub public eval naming
```
