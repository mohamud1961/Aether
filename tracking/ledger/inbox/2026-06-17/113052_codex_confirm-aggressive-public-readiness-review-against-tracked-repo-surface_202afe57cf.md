# Raw Ledger Update

- recorded_at_utc: 2026-06-17T11:30:52.042800+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: confirm aggressive public-readiness review against tracked repo surface
- event_type: source_analysis
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 202afe57cffcb8fabb59566d64aa870dc7748bcc5bc5db4469f88b61d279d381
- commit_message: NONE - no tracked file changes
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-17/113052_codex_confirm-aggressive-public-readiness-review-against-tracked-repo-surface_202afe57cf.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: confirm aggressive public-readiness review against tracked repo surface
- event_type: source_analysis
- summary: Reviewed the tracked public-facing HarnessEng surface against an aggressive external review and confirmed several material issues: broken `harness/aether2` navigation claims, no visible tracked GitHub Actions workflows, no root license file, and an MCP smoke grader that passes on direct equality to a public reference JSON. Also confirmed that root `AGENTS.md` does exist, so that portion of the external review is outdated/incorrect.
- observations: README.md, PUBLIC_REVIEWER_GUIDE.md, docs/publication/public_evidence_index.md, and docs/architecture/public-architecture.md point reviewers to `harness/aether2/...` paths that are not tracked in git; tracked runtime capability files exist under `aether/...` instead. `git ls-files '.github/**'` returned no tracked GitHub workflow files. No root LICENSE file is present. aether/hooks/README.md publicly states the adapted slice did not recover the referenced root license text and should not be published until notice text is recovered. eval_suite/families/tooling/mcp_registry_contract_smoke/grader.py compares candidate JSON fields directly against a public reference JSON, and tests/test_mcp_registry_contract_smoke.py encodes the pass case as copying the reference JSON into the workspace.
- inference: The aggressive review is directionally correct and likely understates the navigation/runtime namespace problem. The public story currently over-promises the `harness.aether2` surface while exposing provenance caveats and a gameable smoke grader. The specific claim that `AGENTS.md` is missing is false for this checkout.
- evidence_paths: README.md; PUBLIC_REVIEWER_GUIDE.md; docs/publication/public_evidence_index.md; docs/architecture/public-architecture.md; pyproject.toml; aether/hooks/README.md; aether/agents/README.md; aether/skills/loader.py; aether/tools/mcp.py; eval_suite/families/tooling/mcp_registry_contract_smoke/README.md; eval_suite/families/tooling/mcp_registry_contract_smoke/grader.py; eval_suite/families/tooling/mcp_registry_contract_smoke/fixture/reference/mcp_audit.json; tests/test_mcp_registry_contract_smoke.py
- affected_components: public docs/navigation; packaging/public namespace; CI visibility; licensing/provenance; eval_suite smoke grading
- decision_change: NONE - review confirmation only
- unresolved_questions: Whether the untracked harness/aether2 stub is intended to replace the aether/ tree soon; whether publication should wait for a real canonical namespace migration and license/provenance cleanup; whether public smokes should remain diagnostic-only or be redesigned around behavioral execution.
- confidence: high
- commit_message: NONE - no tracked file changes
```
