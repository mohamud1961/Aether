# Raw Ledger Update

- recorded_at_utc: 2026-06-13T19:10:54.222264+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: agent_session
- task: aether2_g5_targeted_board_launch
- event_type: run_launched
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 323143ef28036c5463638d972133cdd6163e111f63a567a424309a3541f7e4e2
- commit_message: none (no repo changes; VM-side run launch only)
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-13/191054_agent-session_aether2-g5-targeted-board-launch_323143ef28.md

```text
RAW_LEDGER_UPDATE
- actor: agent_session
- task: aether2_g5_targeted_board_launch
- event_type: run_launched
- summary: Synced upgraded harness to VM and launched the G5 targeted board (14 tasks) detached in tmux on the Azure VM; not yet complete, confirmed first task active, then stopped.
- observations: Local sanity green (genericity check, bridge_harbor import, pytest 20 passed). rsync of runner/, tools/, scripts/, tests/ to azureuser@74.249.131.24:/home/azureuser/harnesseng_aether2/ completed. VM preflight green (import + --help). docker prune reclaimed 2.007GB, df shows 21G free (67% used). Auto-shutdown extended to 0900 UTC via az vm auto-shutdown. Launched tmux session aether2_g5_board_20260613 running scripts/run_aether2_tournament.sh; confirmed via ps that first task acl-permissions-inheritance is running with artifacts/workspace/logs dirs created.
- inference: runner.aether2 package and run_aether2_g3_official.py entrypoint work on VM Python 3.12.3 with PYTHONPATH set; tournament launcher preflight and serial loop operate as designed.
- evidence_paths: scripts/run_aether2_tournament.sh, tools/run_aether2_g3_official.py, runner/aether2/bridge_harbor.py, VM:/home/azureuser/aether2_runs/g5_board_20260613T190904Z/task_ids.txt, VM:/home/azureuser/aether2_runs/g5_board_20260613T190904Z/run.log, VM:/home/azureuser/aether2_runs/g5_board_20260613T190904Z/progress.tsv
- affected_components: runner/aether2 (deployed to VM), tools/run_aether2_g3_official.py (deployed to VM), scripts/run_aether2_tournament.sh (deployed and launched), VM auto-shutdown schedule for harnesseng-dev (extended to 0900 UTC)
- decision_change: None.
- unresolved_questions: Board run in progress (task 1 of 14, started 19:09:52 UTC). Acceptance gate not yet evaluated. If run needs more than ~14h, user must re-extend auto-shutdown.
- confidence: high
- commit_message: none (no repo changes; VM-side run launch only)
```
