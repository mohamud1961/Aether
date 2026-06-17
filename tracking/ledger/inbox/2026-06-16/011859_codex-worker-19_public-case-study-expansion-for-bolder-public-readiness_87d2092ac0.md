# Raw Ledger Update

- recorded_at_utc: 2026-06-16T01:18:59.545781+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex-worker-19
- task: public case study expansion for Bolder/public-readiness
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 87d2092ac0df6c48fcbd4267bd9a927b0662b00f0c34a3765b0f60bfe5f69339
- commit_message: Expand public case study with validation evidence and public-safe indexes
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/011859_codex-worker-19_public-case-study-expansion-for-bolder-public-readiness_87d2092ac0.md

```text
RAW_LEDGER_UPDATE
- actor: codex-worker-19
- task: public case study expansion for Bolder/public-readiness
- event_type: implementation
- summary: Replaced the Aether migration/direct-port skeleton with a concrete public-safe case study and updated public indexes so reviewers can find it.
- observations: The case study now covers problem/context, engineering loop, public namespace migration outcome, eval-first smoke packs, bounded direct TS-to-Python slices, provenance/license guardrail, validation summary, and out-of-scope boundaries. Public index links in README.md, docs/README.md, docs/case-studies/README.md, and workflows/ai-native-engineering-showcase.md now point reviewers at the case study.
- inference: The public story is now concrete enough for reviewer-facing use without leaking private trajectories, raw ledger material, hidden graders, or benchmark leadership claims.
- evidence_paths: docs/case-studies/aether-migration-direct-port-skeleton.md; docs/case-studies/README.md; docs/README.md; README.md; workflows/ai-native-engineering-showcase.md; docs/provenance/agent_runtime_adaptation_policy.md; docs/provenance/third_party_notices.md; docs/publication/publication_gap_list.md; tracking/collab/public_repo_readiness/public_eval_pack_handoff.md; tracking/collab/public_repo_readiness/aether_namespace_closeout_handoff.md; tracking/collab/public_repo_readiness/claude_ts_hooks_permissions_port_handoff.md; tracking/collab/public_repo_readiness/claude_ts_mcp_port_handoff.md; tracking/collab/public_repo_readiness/claude_ts_skills_port_handoff.md; tracking/collab/public_repo_readiness/claude_ts_subagent_port_handoff.md
- affected_components: docs/case-studies; docs/README.md; README.md; workflows/ai-native-engineering-showcase.md; tracking/ledger/inbox
- decision_change: Promote the public narrative from a skeleton outline to a finished case study while keeping the public-safe, provenance-aware framing.
- unresolved_questions: None for this slice.
- confidence: high
- commit_message: Expand public case study with validation evidence and public-safe indexes
```
