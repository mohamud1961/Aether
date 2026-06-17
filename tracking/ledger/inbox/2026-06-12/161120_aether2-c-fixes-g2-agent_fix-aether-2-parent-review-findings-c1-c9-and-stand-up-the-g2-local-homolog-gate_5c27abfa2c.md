# Raw Ledger Update

- recorded_at_utc: 2026-06-12T16:11:20.177136+00:00
- source: aether2-c-fixes-g2-agent
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: aether2-c-fixes-g2-agent
- task: Fix Aether-2 parent-review findings C1-C9 and stand up the G2 local-homolog gate
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 5c27abfa2c4639761bddd933e9cd6c9d88aba3f9483f63d9ae5509a66a4ad2af
- commit_message: impl: decouple job/session registries by backend (C1), make container exit a no-op pre-grading (C2), surface tail telemetry events (C4), extend fact ledger with installed packages/nonzero exits (C5), split verifier_clean from grader_reward (C6), harden read-only verifier context with audit trail (C7), preserve pre-existing workspace fixtures (C8), gitignore/bundle hygiene (C9), fix tool-schema flattening and cache_prefix_len bug in aether2 model client, and stand up the G2 local-homolog gate with live GPT-5.4 mini results
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-12/161120_aether2-c-fixes-g2-agent_fix-aether-2-parent-review-findings-c1-c9-and-stand-up-the-g2-local-homolog-gate_5c27abfa2c.md

```text
RAW_LEDGER_UPDATE
- actor: aether2-c-fixes-g2-agent
- task: Fix Aether-2 parent-review findings C1-C9 and stand up the G2 local-homolog gate
- event_type: implementation
- summary: Fixed all nine Codex parent-review findings (C1-C9) in runner/aether2 (backend-aware job/session registries, no-op container exit, fact-ledger package/exit tracking, tail-telemetry events, RunResult.verifier_clean/grader_reward split, deny-by-default read-only verifier context with full audit trail, preserve pre-existing workspace fixtures, gitignore/bundle hygiene), discovered and fixed a tool-calling bug in runner/aether2/model_client.py that silently dropped all native tool schemas and forwarded an invalid cache_prefix_len kwarg to Azure chat-completions, and built+ran the G2 local-homolog gate (5 self-authored non-TB task shapes) live against GPT-5.4 mini.
- observations: C3 was already fixed by a prior agent (verified, no change). All other findings required code changes in runner/aether2/*.py plus matching test updates. Live G2 run (tracking/collab/aether2_g2_homologs/runs/20260612T160622Z/) shows 3/5 homologs pass their independent verifier.sh (g2_01 file artifact, g2_03 interactive session, g2_05 long-running job); g2_02 (service survives exit) and g2_04 (package install) fail due to genuine model-quality issues (wrong HTTP server type; pip install path mismatch with verifier interpreter), not harness defects. loop verifier_clean=False on all rows is expected -- it reflects the model's own Layer-1 self-check, independent of verifier.sh's Layer-2 result.
- inference: The Aether-2 harness (10-tool loop, job/session registries, context/compaction, receipts, bridge_harbor) is now correct for both local and docker backends per C1-C9, and is capable of running real GPT-5.4 mini agentic sessions end-to-end once the tool-schema flattening bug is fixed. Remaining G2 failures are model-behavior quality gaps to address in future model/prompt tuning, not harness gaps.
- evidence_paths: tracking/collab/aether2_build_orchestration/g1_checkpoint_handoff.md (Fix round 3 + G2 status sections); tracking/collab/aether2_g2_homologs/runs/20260612T160622Z/result_rows.jsonl; tracking/collab/aether2_g2_homologs/runs/20260612T160622Z/scoreboard.md; runner/aether2/model_client.py; runner/aether2/loop.py; runner/aether2/jobs.py; runner/aether2/sessions.py; runner/aether2/bridge_harbor.py; runner/aether2/metrics.py; runner/aether2/delta.py; runner/aether2/receipts.py
- affected_components: runner/aether2/jobs.py; runner/aether2/sessions.py; runner/aether2/bridge_harbor.py; runner/aether2/loop.py; runner/aether2/metrics.py; runner/aether2/delta.py; runner/aether2/receipts.py; runner/aether2/model_client.py; .gitignore; scripts/build_harnesseng_runtime_bundle.sh; tests/test_aether2_*.py; tools/run_aether2_g2.py (new); tracking/collab/aether2_g2_homologs/ (new)
- decision_change: G2 phase gate is closed (attempted live, 3/5 pass); fix round 3 (C1-C9) is closed. Harness is ready for further G-phase gating (G3+) pending orchestrator direction.
- unresolved_questions: Should g2_02/g2_04 model-quality failures be retried with a different prompt/temperature, or accepted as the recorded G2 attempt? Should the tool-schema-flattening fix in runner/aether2/model_client.py be upstreamed/reported against runner/model_client.py (out of this agent's edit scope) since it affects any caller using TOOL_SCHEMAS-shaped tools with Azure chat-completions routes?
- confidence: high for C1-C9 fixes and gate evidence (101/101 tests x5, py_compile, genericity check all green); medium-high for G2 live results (real model run, n=1, not yet repeated for variance).
- commit_message: impl: decouple job/session registries by backend (C1), make container exit a no-op pre-grading (C2), surface tail telemetry events (C4), extend fact ledger with installed packages/nonzero exits (C5), split verifier_clean from grader_reward (C6), harden read-only verifier context with audit trail (C7), preserve pre-existing workspace fixtures (C8), gitignore/bundle hygiene (C9), fix tool-schema flattening and cache_prefix_len bug in aether2 model client, and stand up the G2 local-homolog gate with live GPT-5.4 mini results
```
