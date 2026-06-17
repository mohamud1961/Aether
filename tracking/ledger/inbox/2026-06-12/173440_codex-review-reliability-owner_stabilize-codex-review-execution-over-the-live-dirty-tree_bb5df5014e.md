# Raw Ledger Update

- recorded_at_utc: 2026-06-12T17:34:40.541195+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Codex Review Reliability owner
- task: stabilize Codex review execution over the live dirty tree
- event_type: experiment
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: bb5df5014e4fdadb12d63785986ed111af9501512da3c11c4b3d78be7cf3b4f5
- commit_message: HOLD - sanitized review reliability evidence only
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-12/173440_codex-review-reliability-owner_stabilize-codex-review-execution-over-the-live-dirty-tree_bb5df5014e.md

```text
RAW_LEDGER_UPDATE
- actor: Codex Review Reliability owner
- task: stabilize Codex review execution over the live dirty tree
- event_type: experiment
- summary: Established a repeatable ephemeral CODEX_HOME review invocation that reaches a real nested review over the live checkout and returns actionable findings.
- observations: A bare `codex review --uncommitted` run with the desktop `~/.codex` config failed on schema/runtime issues; a fresh 0700 `/private/tmp` CODEX_HOME with only `auth.json`, `model = gpt-5.4-mini`, `approval_policy = never`, `sandbox_mode = danger-full-access`, and `service_tier = fast` completed the review. The final review returned two actionable findings in `runner/aether2/jobs.py` at lines 62 and 74. Ephemeral review homes were removed afterward.
- inference: The recurring failures were environmental/bootstrap problems, not an inability of Codex review to inspect this tree. The stable recipe is portable if the caller recreates the ephemeral home and cert env exactly.
- evidence_paths: tracking/collab/aether2_build_orchestration/codex_review_reliability_handoff.md; tracking/collab/aether2_build_orchestration/codex_review_reliability_transcript.md; tracking/collab/aether2_build_orchestration/codex_review_actual.txt; runner/aether2/jobs.py:62; runner/aether2/jobs.py:74
- affected_components: review invocation; ephemeral CODEX_HOME bootstrap; cert env; nested shell execution; Aether-2 job registry review surface
- decision_change: Use ephemeral HOME-only auth bootstrap with `service_tier=fast` and `sandbox_mode=danger-full-access` for local dirty-tree review runs; do not copy the desktop config.toml into the temp home.
- unresolved_questions: Whether the `fast` tier remains stable across future Codex CLI releases; whether the job-registry findings should be addressed in the stabilization thread or a follow-up implementation slice.
- confidence: high
- commit_message: HOLD - sanitized review reliability evidence only
```
