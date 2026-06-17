# Raw Ledger Update

- recorded_at_utc: 2026-06-15T14:29:38.904116+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Codex GPT-5.4-mini run worker
- task: Aether-2 targeted calibration board run on the live VM
- event_type: experiment
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 7cb9199cfff0724c6f99502057e811459fdb86bcecc0e0b07ab675bf14f31baf
- commit_message: NONE - no tracked file changes
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-15/142938_codex-gpt-5-4-mini-run-worker_aether-2-targeted-calibration-board-run-on-the-live-vm_7cb9199cff.md

```text
RAW_LEDGER_UPDATE
- actor: Codex GPT-5.4-mini run worker
- task: Aether-2 targeted calibration board run on the live VM
- event_type: experiment
- summary: Launched the L1 targeted board on the active VM and confirmed live progress plus a real pass row. The run is still in flight on build-pmars.
- observations: The board started under tmux at /home/azureuser/aether2_full_tournament/l1_targeted_20260615T142411Z. Current progress.tsv shows 4 rows: acl-permissions-inheritance pass rc=0, analyze-access-logs pass rc=0, assign-seats rc=1, attention-mil pass rc=0. The first pass row has verifier_clean=false with 3 verification rounds and 2 completion-precheck rejections. The run log shows the board continuing onto build-pmars.
- inference: The targeted board is live and valid, and the verifier calibration issue remains visible even on a grader pass. The early assign-seats failure suggests the sentinel board is not uniformly clean yet, but the board has not completed.
- evidence_paths: /home/azureuser/aether2_full_tournament/l1_targeted_20260615T142411Z/progress.tsv; /home/azureuser/aether2_full_tournament/l1_targeted_20260615T142411Z/20260615T142412Z/acl-permissions-inheritance/row.json; tmux session codex_l1_targeted on harnesseng-regular-01
- affected_components: tools/run_aether2_g3_official.py, scripts/run_aether2_tournament.sh, official Terminal-Bench VM run surface
- decision_change: Continue the board in detached mode; do not deallocate the VM because the active run still needs it.
- unresolved_questions: Whether the remaining sentinel tasks will preserve the known passes, and whether any later rows flip verifier_clean to true for a genuinely strong pass.
- confidence: medium
- commit_message: NONE - no tracked file changes
```
