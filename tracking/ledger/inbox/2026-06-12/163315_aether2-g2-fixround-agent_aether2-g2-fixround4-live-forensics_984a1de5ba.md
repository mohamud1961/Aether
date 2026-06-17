# Raw Ledger Update

- recorded_at_utc: 2026-06-12T16:33:15.644854+00:00
- source: aether2-g2-fixround-agent
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: aether2-g2-fixround-agent
- task: aether2_g2_fixround4_live_forensics
- event_type: experiment
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 984a1de5bafc83503cd7ba817f4fb6a3194e570d791b5ce5279760634407756a
- commit_message: fix(aether2): retry EAGAIN spawns, fix G2 row serialization gaps, and tighten verifier output schema (G2 fix round 4)
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-12/163315_aether2-g2-fixround-agent_aether2-g2-fixround4-live-forensics_984a1de5ba.md

```text
RAW_LEDGER_UPDATE
- actor: aether2-g2-fixround-agent
- task: aether2_g2_fixround4_live_forensics
- event_type: experiment
- summary: Fixed two confirmed Layer-2 finalize-verification defects found by live G2 forensics (run 20260612T160622Z): (b) G2 row serialization dropped verification_rounds/discrepancy_reports/verifier_clean-supporting fields, and (a) EAGAIN/spawn_failed poisoned replay_checks during all verification rounds plus a verifier-output-schema mismatch caused verifier_parse_failed on every round. Also added bounded EAGAIN retry-with-backoff to ContainerExecutor (V2) and verifier.sh env/cwd parity with the executor's sh -lc context (V3, fixes g2_04 cowsay).
- observations: Live receipts (model_exchange_4/5.json under each g2_*_homologs/.aether2/host_receipts/receipts) showed verify_fresh_context DID run 3 rounds with model_calls=5 for every homolog, but replay_checks' checks_results showed error_kind=spawn_failed/exit_code=71 (EAGAIN "Resource temporarily unavailable") on every check in every round, causing has_discrepancies=True always. tools/run_aether2_g2.py's row["run_result"] dict only included a hand-picked field subset, omitting verification_rounds/discrepancy_reports (present in scorecard but not run_result). Post-fix run 20260612T161923Z (full 5/5) showed verifier.sh 4/5 pass (g2_04 cowsay now passes) with verification_rounds=3 and discrepancy_reports populated on all rows, but verifier_clean=False on all due to verifier_parse_failed (GPT-5.4 mini returned non-conforming JSON shapes like claim_satisfied/top-level verdict). After tightening verify.py's system prompt schema, partial run 20260612T162428Z (2/5 before host process pressure killed it) showed g2_01 fully green end-to-end (verifier.sh PASS, verification_rounds=1, verifier_clean=True) and g2_02 verifier.sh FAIL classified as a model-capability issue (model left an old python3 -m http.server bound to port 8123 instead of the fixed handler it wrote in response to round 1-2 feedback) -- correctly caught by post-exit verifier.sh, not a harness defect.
- inference: V1 root cause was BOTH (a) and (b): the finalize verification flow in loop.py was executing correctly end-to-end (not inert), but (b) the G2 runner's row serialization dropped the fields that would have shown this, and (a) production EAGAIN spawn failures during replay_checks plus a loosely-specified verifier output schema both independently forced verifier_clean=False even on objectively-passing tasks. All three fixes (V1b row serialization, V2 EAGAIN retry, V3 verifier env parity, plus an additional V1a-part2 verifier schema prompt fix) are confirmed individually working via live receipts; a full clean 5/5 post-all-fixes run could not be completed due to severe host process-pressure (load average ~13-15) repeatedly killing the orchestrating python process across 4 further attempts.
- evidence_paths: tracking/collab/aether2_g2_homologs/runs/20260612T161923Z/result_rows.jsonl, tracking/collab/aether2_g2_homologs/runs/20260612T162428Z/result_rows.jsonl, tracking/collab/aether2_g2_homologs/g2_01_file_artifact/.aether2/host_receipts/receipts/model_exchange_4.json, tracking/collab/aether2_g2_homologs/g2_01_file_artifact/.aether2/host_receipts/receipts/model_exchange_5.json, runner/aether2/executor.py, runner/aether2/verify.py, tools/run_aether2_g2.py, tests/test_aether2_executor.py, tests/test_aether2_loop.py, tracking/collab/aether2_build_orchestration/g1_checkpoint_handoff.md
- affected_components: runner/aether2/executor.py, runner/aether2/verify.py, tools/run_aether2_g2.py, tests/test_aether2_executor.py, tests/test_aether2_loop.py
- decision_change: G2 scoreboard interpretation must use the full run_result row (now including verification_rounds/discrepancy_reports) rather than verifier_clean alone, since verifier_clean depends on the fresh-context verifier model's output conforming to the required JSON schema; the schema is now strictly specified in verify.py's system prompt.
- unresolved_questions: A full clean 5/5 live G2 run with all fixes applied was not completed in this session due to host resource exhaustion (unrelated to harness code); g2_02's port-8123 stale-server issue (model leaves an old http.server bound after writing a fixed handler) recurs across runs and may warrant a future task-instruction clarification (tell the model to stop prior servers before starting a new one) though this is a homolog/task-design question, not a harness defect.
- confidence: medium
- commit_message: fix(aether2): retry EAGAIN spawns, fix G2 row serialization gaps, and tighten verifier output schema (G2 fix round 4)
```
