# Raw Ledger Update

- recorded_at_utc: 2026-06-16T19:50:28.634982+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: public/private boundary cleanup after public-readiness continuation
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: fa934198fd423b754eb7b179411f926b3604392829a289968f0e91e1c532aa23
- commit_message: HOLD - raw/private source untracking blocked by Codex sandbox git index lock permission
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/195028_codex_public-private-boundary-cleanup-after-public-readiness-continuation_fa934198fd.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: public/private boundary cleanup after public-readiness continuation
- event_type: implementation
- summary: Sanitized public eval/provenance references and added a continuation-state handoff; confirmed raw trajectories, mirrored codebases, benchmark captures, research intake, and official_tasks remain tracked from earlier history and need local-terminal untracking.
- observations: Commit 346c60ae1 replaced private repair logs in public eval reference files, softened provenance docs so quarantined codebase paths are not public artifacts, and added tracking/collab/public_repo_readiness/CONTINUATION_STATE_2026-06-16.md. Audit command `git ls-files 'research/sources/**' 'research/intake/**' 'official_tasks/**' | wc -l` reports 4368 tracked raw/private-source paths. `git rm --cached` failed for both bulk and single-file attempts with `fatal: Unable to create '.git/index.lock': Operation not permitted`; no stale index.lock file was present.
- inference: Public narrative files are cleaner, but publication is not complete until a normal local terminal removes the raw/private source paths from Git tracking while preserving local files.
- evidence_paths: docs/provenance/agent_runtime_adaptation_policy.md; docs/provenance/third_party_notices.md; eval_suite/calibration_lanes/terminal/reference/final_harness_task.md; eval_suite/whole_harness/final_harness_v1/task.md; tracking/collab/public_repo_readiness/CONTINUATION_STATE_2026-06-16.md
- affected_components: docs; eval_suite; tracking/collab/public_repo_readiness; research/sources; research/intake; official_tasks
- decision_change: Raw trajectories, mirrored codebases, benchmark captures, research intake, and official task assets must be local/private only and removed from Git tracking before publication.
- unresolved_questions: A local terminal with Git index write access must run `git rm -r --cached --ignore-unmatch research/sources research/intake official_tasks` and commit the result.
- confidence: high
- commit_message: HOLD - raw/private source untracking blocked by Codex sandbox git index lock permission
```
