# Raw Ledger Update

- recorded_at_utc: 2026-06-15T15:12:01.626344+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Codex GPT-5.4-mini run worker
- task: Aether-2 targeted calibration board run completed
- event_type: experiment
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: bed07d7abfdb9c86cd492149a16b3bc376f78d9f230ea2f09b20be8374f194cd
- commit_message: NONE - no tracked file changes
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-15/151201_codex-gpt-5-4-mini-run-worker_aether-2-targeted-calibration-board-run-completed_bed07d7abf.md

```text
RAW_LEDGER_UPDATE
- actor: Codex GPT-5.4-mini run worker
- task: Aether-2 targeted calibration board run completed
- event_type: experiment
- summary: The live targeted calibration board completed all 14 rows. Six rows passed, four rows failed, and four rows were invalid (two resource-killed, one invalid_grader, one invalid_provider). Verifier_clean was false on all rows with verifier metadata, including the passing rows.
- observations: Final progress.tsv shows 14/14 tasks complete. Row summaries observed: acl-permissions-inheritance pass, analyze-access-logs pass, assign-seats fail, attention-mil pass, build-pmars pass, break-filter-js-from-html invalid_resource_killed, broken-python pass, broken-networking invalid_grader, build-stp pass, build-cython-ext fail, qemu-startup fail, extract-moves-from-video fail, install-windows-3.11 invalid_resource_killed, video-processing fail. The first row still shows verifier_clean=false with 3 verification rounds and 2 completion-precheck rejections.
- inference: The harness still suppresses clean verification even on grader passes, so the calibration issue remains unresolved. The board is useful evidence that the targeted sentinel set is not yet a discriminating verifier gate.
- evidence_paths: /home/azureuser/aether2_full_tournament/l1_targeted_20260615T142411Z/progress.tsv; /home/azureuser/aether2_full_tournament/l1_targeted_20260615T142411Z/20260615T142412Z/acl-permissions-inheritance/row.json; /home/azureuser/aether2_full_tournament/l1_targeted_20260615T142411Z/20260615T143103Z/broken-python/row.json; /home/azureuser/aether2_full_tournament/l1_targeted_20260615T142411Z/20260615T143633Z/build-cython-ext/row.json
- affected_components: tools/run_aether2_g3_official.py, scripts/run_aether2_tournament.sh, official Terminal-Bench VM run surface
- decision_change: No additional runs are needed for this thread unless a calibration fix is proposed; the active VM should be deallocated if no other job is pending.
- unresolved_questions: Whether the over-strict verifier is the only remaining blocker or whether some failures reflect genuine capability gaps in the targeted set.
- confidence: high
- commit_message: NONE - no tracked file changes
```
