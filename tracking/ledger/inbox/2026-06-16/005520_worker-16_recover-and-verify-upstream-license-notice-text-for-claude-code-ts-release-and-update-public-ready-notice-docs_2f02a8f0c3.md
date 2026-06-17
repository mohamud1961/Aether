# Raw Ledger Update

- recorded_at_utc: 2026-06-16T00:55:20.657181+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Worker 16
- task: Recover and verify upstream license/notice text for claude-code_ts_release and update public-ready notice docs
- event_type: source_analysis | implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 2f02a8f0c327039b041d6a016dc05d266d6f4de3248ba22185069a5d00e27cef
- commit_message: HOLD - update provenance notice docs with verified Anthropic license pointer
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-16/005520_worker-16_recover-and-verify-upstream-license-notice-text-for-claude-code-ts-release-and-update-public-ready-notice-docs_2f02a8f0c3.md

```text
RAW_LEDGER_UPDATE
- actor: Worker 16
- task: Recover and verify upstream license/notice text for claude-code_ts_release and update public-ready notice docs
- event_type: source_analysis | implementation
- summary: Verified the official upstream source family for the quarantined TS-derived tree and replaced the placeholder MIT framing with the upstream Anthropic license pointer.
- observations: Local quarantine metadata points to yasasbanukaofficial/claude-code.git, but the authoritative upstream package/repo family is @anthropic-ai/claude-code / anthropics/claude-code. The official repo root has LICENSE.md and no standalone NOTICE file. The npm package metadata license field is SEE LICENSE IN README.md. The official LICENSE.md text is copyright/terms-based, not MIT.
- inference: The prior local README license wording was unverified placeholder prose, so publication should cite the official Anthropic license pointer rather than MIT.
- evidence_paths: research/sources/codebases/quarantine/claude-code_ts_release/.git/config; research/sources/codebases/quarantine/claude-code_ts_release/README.md; docs/provenance/third_party_notices.md; docs/publication/publication_gap_list.md; tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md; https://registry.npmjs.org/@anthropic-ai/claude-code/2.1.0; https://api.github.com/repos/anthropics/claude-code/contents?ref=main; https://raw.githubusercontent.com/anthropics/claude-code/main/LICENSE.md; https://raw.githubusercontent.com/anthropics/claude-code/main/NOTICE; https://registry.npmjs.org/@anthropic-ai/claude-code/-/claude-code-2.1.0.tgz
- affected_components: public provenance docs; publication gap list; third-party notice package
- decision_change: Publication blocker narrowed/resolved for this source tree by recovering verified upstream licensing evidence; no standalone upstream NOTICE file was found.
- unresolved_questions: Need to verify any additional quarantined source trees independently before reusing this notice pattern.
- confidence: high
- commit_message: HOLD - update provenance notice docs with verified Anthropic license pointer
```
